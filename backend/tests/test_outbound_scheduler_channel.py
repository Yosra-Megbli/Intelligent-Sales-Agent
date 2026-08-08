"""
Tests for outbound/scheduler.py's channel selection (Telegram full-wiring
support) - separate from the pacing/batching behaviour already covered
elsewhere, this focuses on: which channel a tick sends on, and how a
lead's external_id is resolved for that channel.
"""

import pytest

from crm.campaign_repository import CampaignRepository
from crm.lead_repository import LeadRepository
from domain.enums import CampaignStatus, ConversationChannel, LeadSource
from outbound.campaign_engine import CampaignEngine
from outbound.scheduler import OutboundScheduler
from outbound.sender import OutboundSender


@pytest.fixture(autouse=True)
def fake_redis_cache(monkeypatch):
    store: dict[str, dict] = {}

    def fake_cache(conversation_id, context, ttl_seconds=3600):
        store[conversation_id] = context

    def fake_get(conversation_id):
        return store.get(conversation_id)

    monkeypatch.setattr("conversation_engine.memory.cache_conversation_context", fake_cache)
    monkeypatch.setattr("conversation_engine.memory.get_cached_conversation_context", fake_get)
    yield store


def _running_campaign(db_session):
    campaign = CampaignRepository(db_session).create(name="Telegram re-engagement")
    CampaignRepository(db_session).set_status(campaign, CampaignStatus.RUNNING)
    return campaign


def test_defaults_to_whatsapp_unchanged_from_prior_behaviour(db_session, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    LeadRepository(db_session).create(source=LeadSource.CSV, first_name="Jean", phone="+32491234567")
    campaign = _running_campaign(db_session)
    CampaignEngine(db_session).select_and_assign_leads(campaign)
    db_session.commit()

    sent: list[tuple] = []
    fake_sender = OutboundSender(db_session, senders={})
    original = fake_sender.send_opening_message

    def spy(lead, campaign, channel, **kwargs):
        sent.append(channel)
        return original(lead, campaign, channel, **kwargs)

    fake_sender.send_opening_message = spy

    scheduler = OutboundScheduler(db_session, sender=fake_sender)
    scheduler.process_campaign(campaign, sleep_between_sends=False)

    assert sent == [ConversationChannel.WHATSAPP]


def test_telegram_channel_falls_back_to_lead_id_when_no_prior_telegram_conversation(db_session):
    """A lead with no Telegram history yet has no chat_id to message cold -
    the scheduler still computes/records the send, just can't reach a real
    chat (documented limitation, see _resolve_external_id's docstring)."""
    lead = LeadRepository(db_session).create(source=LeadSource.CSV, first_name="Marie")
    campaign = _running_campaign(db_session)

    fake_sender = OutboundSender(db_session, senders={})
    scheduler = OutboundScheduler(db_session, sender=fake_sender, channel=ConversationChannel.TELEGRAM)

    result = scheduler.process_campaign(campaign, sleep_between_sends=False)

    assert result.sent == 1


def test_telegram_channel_prefers_the_leads_own_chat_id_over_a_conversation_lookup(db_session):
    """A lead created via CSV import/manual entry with telegram_chat_id set
    directly must be targetable without waiting for a Conversation row -
    and if a (stale/different) Telegram conversation also happens to exist
    for this lead, the lead's own chat_id still wins (it's the more
    directly-authoritative, more recently set value)."""
    from application.conversation_service import ConversationService

    lead = LeadRepository(db_session).create(source=LeadSource.CSV, first_name="Marie")
    LeadRepository(db_session).update_fields(lead, telegram_chat_id="11111")
    db_session.commit()

    # A different chat_id on file via an old Conversation - must lose to
    # lead.telegram_chat_id above.
    service = ConversationService(db_session)
    service.conversation_repo.create(
        lead_id=lead.id, channel=ConversationChannel.TELEGRAM, external_id="22222"
    )
    db_session.commit()

    scheduler = OutboundScheduler(db_session, channel=ConversationChannel.TELEGRAM)
    resolved = scheduler._resolve_external_id(lead)

    assert resolved == "11111"


def test_telegram_channel_reuses_an_existing_telegram_conversations_chat_id(db_session):
    """If this lead already has a Telegram conversation on file (e.g. they
    messaged the bot inbound before), a re-engagement campaign reuses that
    same chat_id instead of the lead's own UUID."""
    from application.conversation_service import ConversationService

    service = ConversationService(db_session)
    lead, conversation = service.start_conversation(
        ConversationChannel.TELEGRAM, first_name="Marie", external_id="98765"
    )
    db_session.commit()

    campaign = CampaignRepository(db_session).create(name="Re-engagement")
    CampaignRepository(db_session).set_status(campaign, CampaignStatus.RUNNING)
    CampaignEngine(db_session).select_and_assign_leads(campaign)
    db_session.commit()

    scheduler = OutboundScheduler(db_session, channel=ConversationChannel.TELEGRAM)
    resolved = scheduler._resolve_external_id(lead)

    assert resolved == "98765"

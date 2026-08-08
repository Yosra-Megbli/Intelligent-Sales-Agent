import pytest

from application.conversation_service import ConversationService
from crm.campaign_repository import CampaignRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import (
    ConversationChannel,
    ConversationState,
    LeadSource,
    LeadStatus,
    MessageRole,
)
from outbound.campaign_engine import CampaignEngine
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


def _assigned_lead_and_campaign(db_session):
    lead = LeadRepository(db_session).create(
        source=LeadSource.CSV, first_name="Jean", email="jean@test.com"
    )
    from domain.enums import CampaignStatus

    campaign = CampaignRepository(db_session).create(name="Wallonie July 2026")
    CampaignRepository(db_session).set_status(campaign, CampaignStatus.RUNNING)
    CampaignEngine(db_session).select_and_assign_leads(campaign)
    db_session.commit()
    return lead, campaign


def test_send_opening_message_does_not_create_a_second_lead(db_session):
    lead, campaign = _assigned_lead_and_campaign(db_session)
    sender = OutboundSender(db_session, service=ConversationService(db_session))

    response = sender.send_opening_message(lead, campaign, ConversationChannel.TELEGRAM, external_id="555")

    assert response.response_text  # a greeting was generated
    assert response.state == ConversationState.GREETING.value

    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.TELEGRAM, "555"
    )
    assert conversation.lead_id == lead.id  # same lead, not a fresh one


def test_send_opening_message_marks_lead_contacted(db_session):
    lead, campaign = _assigned_lead_and_campaign(db_session)
    sender = OutboundSender(db_session, service=ConversationService(db_session))

    sender.send_opening_message(lead, campaign, ConversationChannel.TELEGRAM, external_id="555")

    assert lead.status == LeadStatus.CONTACTED
    assert lead.last_contact_date is not None
    assert lead.follow_up_attempts == 1


def test_send_opening_message_increments_campaign_sent(db_session):
    lead, campaign = _assigned_lead_and_campaign(db_session)
    sender = OutboundSender(db_session, service=ConversationService(db_session))

    sender.send_opening_message(lead, campaign, ConversationChannel.TELEGRAM, external_id="555")

    assert campaign.sent == 1


def test_only_an_assistant_message_is_logged_no_fake_user_message(db_session):
    lead, campaign = _assigned_lead_and_campaign(db_session)
    sender = OutboundSender(db_session, service=ConversationService(db_session))

    sender.send_opening_message(lead, campaign, ConversationChannel.TELEGRAM, external_id="555")

    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.TELEGRAM, "555"
    )
    history = ConversationRepository(db_session).get_history(conversation)
    assert [m.role for m in history] == [MessageRole.ASSISTANT]


def test_customer_reply_after_outbound_greeting_continues_the_same_conversation(db_session):
    """End-to-end sanity check: once Sophie sends the opening message,
    a real customer reply goes through the exact same ConversationService
    path (Inbound/Outbound Architecture: one Engine, no separate agent)."""
    lead, campaign = _assigned_lead_and_campaign(db_session)
    service = ConversationService(db_session)
    sender = OutboundSender(db_session, service=service)

    sender.send_opening_message(lead, campaign, ConversationChannel.TELEGRAM, external_id="555")

    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.TELEGRAM, "555"
    )
    from application.conversation_service import ConversationRequest

    reply = service.handle_message(
        ConversationRequest(conversation_id=conversation.id, text="Oui je suis interesse")
    )

    assert reply.state == ConversationState.DISCOVERY.value


# --- real delivery wiring -------------------------------------------------------------


def test_send_opening_message_delivers_via_the_injected_sender_for_its_channel(db_session):
    """Full-wiring contract: when a real `send_message` callable is wired
    in for the channel being used, `OutboundSender` actually calls it with
    (external_id, response_text) - this is what makes an outbound Telegram
    campaign genuinely reach `TelegramBotAPISender.send` in production."""
    lead, campaign = _assigned_lead_and_campaign(db_session)
    sent: list[tuple[str, str]] = []

    def fake_telegram_send(chat_id: str, text: str) -> None:
        sent.append((chat_id, text))

    sender = OutboundSender(
        db_session,
        service=ConversationService(db_session),
        senders={ConversationChannel.TELEGRAM: fake_telegram_send},
    )

    response = sender.send_opening_message(lead, campaign, ConversationChannel.TELEGRAM, external_id="555")

    assert sent == [("555", response.response_text)]


def test_send_opening_message_does_not_call_a_sender_for_a_different_channel(db_session):
    """A sender wired in for WhatsApp must never fire for a Telegram send -
    each channel's delivery is independent."""
    lead, campaign = _assigned_lead_and_campaign(db_session)
    sent: list[tuple[str, str]] = []

    sender = OutboundSender(
        db_session,
        service=ConversationService(db_session),
        senders={ConversationChannel.WHATSAPP: lambda to, text: sent.append((to, text))},
    )

    sender.send_opening_message(lead, campaign, ConversationChannel.TELEGRAM, external_id="555")

    assert sent == []


def test_send_opening_message_with_no_senders_configured_only_computes_the_reply(db_session):
    """Default behaviour (no `senders` passed at all) is unchanged from
    before full wiring existed: the greeting is generated and the CRM is
    updated, nothing is ever sent over the network."""
    lead, campaign = _assigned_lead_and_campaign(db_session)
    sender = OutboundSender(db_session, service=ConversationService(db_session))

    response = sender.send_opening_message(lead, campaign, ConversationChannel.TELEGRAM, external_id="555")

    assert response.response_text
    assert lead.status == LeadStatus.CONTACTED


def test_a_delivery_failure_does_not_prevent_the_crm_bookkeeping(db_session):
    """If the real transport raises (network error, invalid chat_id...),
    the lead is still marked CONTACTED and the campaign's sent counter
    still increments - the greeting really was generated and recorded in
    the conversation history, so silently retrying it would duplicate it."""
    lead, campaign = _assigned_lead_and_campaign(db_session)

    def failing_send(chat_id: str, text: str) -> None:
        raise ConnectionError("simulated Telegram API outage")

    sender = OutboundSender(
        db_session,
        service=ConversationService(db_session),
        senders={ConversationChannel.TELEGRAM: failing_send},
    )

    response = sender.send_opening_message(lead, campaign, ConversationChannel.TELEGRAM, external_id="555")

    assert response.response_text
    assert lead.status == LeadStatus.CONTACTED
    assert campaign.sent == 1

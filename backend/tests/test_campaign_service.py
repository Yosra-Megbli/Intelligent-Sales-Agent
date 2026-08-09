import pytest

from application.campaign_service import (
    CampaignNotFoundError,
    CampaignService,
    InvalidCampaignTransitionError,
)
from crm.lead_repository import LeadRepository
from domain.enums import CampaignStatus, ConversationChannel, LeadSource, LeadStatus


@pytest.fixture(autouse=True)
def fake_redis_cache(monkeypatch):
    """OutboundSender -> ConversationService.start_and_greet() touches the
    Redis conversation-context cache; fake it out same as
    tests/test_outbound_sender.py so these tests don't need real Redis."""
    store: dict[str, dict] = {}

    def fake_cache(conversation_id, context, ttl_seconds=3600):
        store[conversation_id] = context

    def fake_get(conversation_id):
        return store.get(conversation_id)

    monkeypatch.setattr("conversation_engine.memory.cache_conversation_context", fake_cache)
    monkeypatch.setattr("conversation_engine.memory.get_cached_conversation_context", fake_get)
    yield store


def _seed_lead(db_session, **overrides):
    repo = LeadRepository(db_session)
    source = overrides.pop("source", LeadSource.CSV)
    # LeadRepository.create() only accepts source/first_name/last_name/
    # email/phone - anything else (region, city, ...) has to be set
    # directly on the Lead afterwards, same pattern as
    # tests/test_state_machine.py's _lead() helper.
    create_kwargs = {
        key: overrides.pop(key)
        for key in ("first_name", "last_name", "email", "phone")
        if key in overrides
    }
    lead = repo.create(source=source, **create_kwargs)
    for key, value in overrides.items():
        setattr(lead, key, value)
    db_session.flush()
    return lead


def test_create_campaign_defaults_to_draft(db_session):
    campaign = CampaignService(db_session).create_campaign(name="Wallonie July 2026")

    assert campaign.status == CampaignStatus.DRAFT
    assert campaign.total_leads == 0


def test_create_campaign_stores_target_rules_as_json(db_session):
    campaign = CampaignService(db_session).create_campaign(
        name="Wallonie July 2026", target_rules={"region": "Wallonie"}
    )

    assert campaign.target_rules == '{"region": "Wallonie"}'


def test_list_campaigns_paginates(db_session):
    service = CampaignService(db_session)
    for i in range(3):
        service.create_campaign(name=f"Campaign {i}")

    page = service.list_campaigns(limit=2, offset=0)

    assert page.total == 3
    assert len(page.items) == 2


def test_get_campaign_detail_returns_assigned_leads(db_session):
    service = CampaignService(db_session)
    lead = _seed_lead(db_session, region="Wallonie")
    campaign = service.create_campaign(name="Wallonie", target_rules={"region": "Wallonie"})
    service.start_campaign(campaign.id)

    detail = service.get_campaign_detail(campaign.id)

    assert detail is not None
    assert detail.leads.total == 1
    assert detail.leads.items[0].id == lead.id


def test_start_campaign_assigns_and_sends_first_batch(db_session):
    service = CampaignService(db_session)
    lead = _seed_lead(db_session, region="Wallonie", phone="+32491234567")
    campaign = service.create_campaign(name="Wallonie", target_rules={"region": "Wallonie"})

    started = service.start_campaign(campaign.id)

    assert started.status == CampaignStatus.RUNNING
    assert started.total_leads == 1
    assert started.sent == 1
    db_session.refresh(lead)
    assert lead.status == LeadStatus.CONTACTED


def test_start_campaign_twice_raises(db_session):
    service = CampaignService(db_session)
    campaign = service.create_campaign(name="Wallonie")
    service.start_campaign(campaign.id)

    with pytest.raises(InvalidCampaignTransitionError):
        service.start_campaign(campaign.id)


def test_pause_then_resume_does_not_resend_same_lead(db_session):
    service = CampaignService(db_session)
    lead = _seed_lead(db_session, region="Wallonie", phone="+32491234567")
    campaign = service.create_campaign(name="Wallonie", target_rules={"region": "Wallonie"})
    service.start_campaign(campaign.id)

    paused = service.pause_campaign(campaign.id)
    assert paused.status == CampaignStatus.PAUSED

    resumed = service.resume_campaign(campaign.id)
    assert resumed.status == CampaignStatus.RUNNING
    # Lead was already CONTACTED by start_campaign(); resume must not send
    # to it again (duplicate protection: list_pending_for_send only
    # returns NEW leads).
    assert resumed.sent == 1


def test_pause_non_running_campaign_raises(db_session):
    service = CampaignService(db_session)
    campaign = service.create_campaign(name="Wallonie")

    with pytest.raises(InvalidCampaignTransitionError):
        service.pause_campaign(campaign.id)


def test_unknown_campaign_raises_not_found(db_session):
    import uuid

    service = CampaignService(db_session)

    with pytest.raises(CampaignNotFoundError):
        service.start_campaign(uuid.uuid4())


# --- channel selection ---------------------------------------------------------------


def test_create_campaign_defaults_to_whatsapp(db_session):
    service = CampaignService(db_session)
    campaign = service.create_campaign(name="Wallonie")
    assert campaign.channel == ConversationChannel.WHATSAPP


def test_starting_a_telegram_campaign_creates_a_telegram_conversation(db_session):
    """The channel chosen at creation time is what start_campaign's
    synchronous first batch actually uses - not hardcoded WhatsApp."""
    service = CampaignService(db_session)
    lead = _seed_lead(db_session, region="Wallonie", phone="+32491234567")
    campaign = service.create_campaign(
        name="Telegram Wallonie", target_rules={"region": "Wallonie"}, channel=ConversationChannel.TELEGRAM
    )

    started = service.start_campaign(campaign.id)

    assert started.channel == ConversationChannel.TELEGRAM
    assert started.sent == 1
    conversations = service.conversation_repo.list_for_lead(lead.id)
    assert len(conversations) == 1
    assert conversations[0].channel == ConversationChannel.TELEGRAM


def test_resuming_a_telegram_campaign_keeps_using_its_own_channel(db_session):
    service = CampaignService(db_session)
    _seed_lead(db_session, region="Wallonie", phone="+32491234567")
    campaign = service.create_campaign(
        name="Telegram Wallonie", target_rules={"region": "Wallonie"}, channel=ConversationChannel.TELEGRAM
    )
    service.start_campaign(campaign.id)
    service.pause_campaign(campaign.id)
    _seed_lead(db_session, region="Wallonie", phone="+32491234568")

    resumed = service.resume_campaign(campaign.id)

    assert resumed.channel == ConversationChannel.TELEGRAM
    assert resumed.sent == 2


# --- update_campaign ------------------------------------------------------


def test_update_campaign_renames_regardless_of_status(db_session):
    service = CampaignService(db_session)
    campaign = service.create_campaign(name="Old Name")
    service.start_campaign(campaign.id)  # RUNNING

    updated = service.update_campaign(campaign.id, name="New Name")

    assert updated.name == "New Name"


def test_update_campaign_changes_target_rules_while_draft(db_session):
    service = CampaignService(db_session)
    campaign = service.create_campaign(name="C", target_rules={"region": "Wallonie"})

    updated = service.update_campaign(campaign.id, target_rules={"region": "Flandre"})

    assert updated.target_rules == '{"region": "Flandre"}'


def test_update_campaign_rejects_target_rules_change_once_started(db_session):
    """Once RUNNING/PAUSED, leads may already be assigned under the old
    rules - re-targeting silently would make that assignment history
    impossible to reason about (see CampaignService.update_campaign)."""
    service = CampaignService(db_session)
    campaign = service.create_campaign(name="C", target_rules={"region": "Wallonie"})
    service.start_campaign(campaign.id)

    with pytest.raises(InvalidCampaignTransitionError):
        service.update_campaign(campaign.id, target_rules={"region": "Flandre"})


def test_update_campaign_raises_for_unknown_campaign(db_session):
    import uuid

    with pytest.raises(CampaignNotFoundError):
        CampaignService(db_session).update_campaign(uuid.uuid4(), name="x")


# --- delete_campaign ------------------------------------------------------


def test_delete_campaign_removes_a_draft_campaign(db_session):
    service = CampaignService(db_session)
    campaign = service.create_campaign(name="Draft campaign")
    campaign_id = campaign.id

    service.delete_campaign(campaign_id)

    assert service.get_campaign(campaign_id) is None


def test_delete_campaign_is_blocked_while_running(db_session):
    service = CampaignService(db_session)
    campaign = service.create_campaign(name="C")
    service.start_campaign(campaign.id)

    with pytest.raises(InvalidCampaignTransitionError):
        service.delete_campaign(campaign.id)

    assert service.get_campaign(campaign.id) is not None


def test_delete_campaign_releases_its_assigned_leads_instead_of_deleting_them(db_session):
    """A lead's own CRM record/status must never be collateral damage of
    removing the campaign that once targeted it - see
    CampaignService.delete_campaign."""
    service = CampaignService(db_session)
    lead = _seed_lead(db_session, region="Wallonie", phone="+32491234567")
    campaign = service.create_campaign(name="C", target_rules={"region": "Wallonie"})
    service.start_campaign(campaign.id)  # assigns + contacts the lead, then RUNNING
    service.pause_campaign(campaign.id)

    service.delete_campaign(campaign.id)

    released_lead = LeadRepository(db_session).get_by_id(lead.id)
    assert released_lead is not None
    assert released_lead.campaign_id is None
    assert released_lead.status == LeadStatus.CONTACTED  # unchanged


def test_delete_campaign_raises_for_unknown_campaign(db_session):
    import uuid

    with pytest.raises(CampaignNotFoundError):
        CampaignService(db_session).delete_campaign(uuid.uuid4())

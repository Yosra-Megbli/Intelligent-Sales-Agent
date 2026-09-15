"""
Tests: STOP / STOPT / ARRET opt-out handler.

AGENTS.md (golden rules): STOP/STOPT/ARRET = immediate opt-out:
  - lead leaves campaign
  - PII purged
  - suppression key kept
  - opt_out_at timestamp set
  - pending follow-ups cancelled (scheduler must check opt_out_at)

All tests use the no-LLM (fallback) path and in-memory SQLite.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from application.conversation_service import ConversationRequest, ConversationService
from crm.campaign_repository import CampaignRepository
from crm.lead_repository import LeadRepository
from domain.enums import (
    ActivityType,
    CampaignStatus,
    ConversationChannel,
    ConversationState,
    FollowUpCategory,
    LeadStatus,
    RejectionReason,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lead_in_campaign(db_session):
    """Create a lead attached to a campaign, with PII fields populated."""
    from domain.models.campaign import Campaign
    from crm.lead_repository import LeadRepository
    import uuid

    campaign = Campaign(
        id=uuid.uuid4(),
        name="Test Campaign",
        channel=ConversationChannel.WEB,
        status=CampaignStatus.RUNNING,
    )
    db_session.add(campaign)
    db_session.flush()

    lead_repo = LeadRepository(db_session)
    lead = lead_repo.create(
        source="WEBSITE",
        first_name="Jean",
        last_name="Dupont",
        email="jean.dupont@example.com",
        phone="0488000001",
    )
    lead.campaign_id = campaign.id
    lead.ean = "541448911001234567"
    lead.address = "Rue de la Paix 1, 1000 Bruxelles"
    lead.current_supplier = "Luminus"
    lead.notes = "VIP prospect"
    db_session.flush()
    return lead, campaign


def _start_conversation(db_session, lead=None):
    service = ConversationService(db_session, provider=None)
    if lead is None:
        _, conv = service.start_conversation(ConversationChannel.WEB)
    else:
        from crm.conversation_repository import ConversationRepository
        conv = ConversationRepository(db_session).create(
            lead_id=lead.id, channel=ConversationChannel.WEB, language="fr"
        )
    return service, conv


# ---------------------------------------------------------------------------
# is_opt_out() pure-function tests
# ---------------------------------------------------------------------------

def test_is_opt_out_stop_lowercase():
    from conversation_engine.opt_out import is_opt_out
    assert is_opt_out("stop")


def test_is_opt_out_stop_uppercase():
    from conversation_engine.opt_out import is_opt_out
    assert is_opt_out("STOP")


def test_is_opt_out_stop_with_whitespace():
    from conversation_engine.opt_out import is_opt_out
    assert is_opt_out("  stop  ")


def test_is_opt_out_stopt():
    from conversation_engine.opt_out import is_opt_out
    assert is_opt_out("STOPT")


def test_is_opt_out_arret_with_accent():
    from conversation_engine.opt_out import is_opt_out
    assert is_opt_out("ARRET")


def test_is_opt_out_arret_without_accent():
    from conversation_engine.opt_out import is_opt_out
    assert is_opt_out("arret")


def test_is_opt_out_normal_message_returns_false():
    from conversation_engine.opt_out import is_opt_out
    assert not is_opt_out("Je veux changer de fournisseur")


def test_is_opt_out_partial_word_returns_false():
    from conversation_engine.opt_out import is_opt_out
    # "stop" embedded in a word must NOT trigger opt-out
    assert not is_opt_out("Je vais m'arreter un moment")


# ---------------------------------------------------------------------------
# handle_message() integration tests (via ConversationService)
# ---------------------------------------------------------------------------

def test_stop_keyword_triggers_opt_out_and_returns_confirmation(db_session):
    service = ConversationService(db_session, provider=None)
    _, conv = service.start_conversation(ConversationChannel.WEB)
    # Advance past GREETING to DISCOVERY
    service.handle_message(ConversationRequest(conversation_id=conv.id, text="Bonjour"))

    response = service.handle_message(ConversationRequest(conversation_id=conv.id, text="stop"))

    assert response.response_text is not None
    assert response.state == ConversationState.CLOSED.value


def test_opt_out_purges_pii_fields(db_session):
    lead, _ = _make_lead_in_campaign(db_session)
    service, conv = _start_conversation(db_session, lead=lead)

    service.handle_message(ConversationRequest(conversation_id=conv.id, text="STOP"))

    db_session.refresh(lead)
    assert lead.first_name is None
    assert lead.last_name is None
    assert lead.email is None
    assert lead.phone is None
    assert lead.ean is None
    assert lead.address is None
    assert lead.current_supplier is None
    assert lead.notes is None


def test_opt_out_keeps_suppression_key(db_session):
    """dedup_email / dedup_phone must survive so re-import is blocked."""
    lead, _ = _make_lead_in_campaign(db_session)
    original_dedup_email = lead.dedup_email
    original_dedup_phone = lead.dedup_phone

    service, conv = _start_conversation(db_session, lead=lead)
    service.handle_message(ConversationRequest(conversation_id=conv.id, text="STOP"))

    db_session.refresh(lead)
    assert lead.dedup_email == original_dedup_email
    assert lead.dedup_phone == original_dedup_phone


def test_opt_out_removes_lead_from_campaign(db_session):
    lead, campaign = _make_lead_in_campaign(db_session)
    assert lead.campaign_id == campaign.id

    service, conv = _start_conversation(db_session, lead=lead)
    service.handle_message(ConversationRequest(conversation_id=conv.id, text="STOP"))

    db_session.refresh(lead)
    assert lead.campaign_id is None


def test_opt_out_sets_status_rejected_and_reason(db_session):
    lead, _ = _make_lead_in_campaign(db_session)
    service, conv = _start_conversation(db_session, lead=lead)

    service.handle_message(ConversationRequest(conversation_id=conv.id, text="STOPT"))

    db_session.refresh(lead)
    assert lead.status == LeadStatus.REJECTED
    assert lead.rejection_reason == RejectionReason.REQUEST_HUMAN_ONLY


def test_opt_out_sets_opt_out_at_timestamp(db_session):
    lead, _ = _make_lead_in_campaign(db_session)
    service, conv = _start_conversation(db_session, lead=lead)

    before = datetime.utcnow()
    service.handle_message(ConversationRequest(conversation_id=conv.id, text="stop"))
    after = datetime.utcnow()

    db_session.refresh(lead)
    assert lead.opt_out_at is not None
    assert before <= lead.opt_out_at <= after


def test_opt_out_logs_opt_out_activity(db_session):
    from crm.activity_repository import ActivityRepository

    lead, _ = _make_lead_in_campaign(db_session)
    service, conv = _start_conversation(db_session, lead=lead)
    service.handle_message(ConversationRequest(conversation_id=conv.id, text="stop"))

    activities = ActivityRepository(db_session).list_for_lead(lead.id)
    activity_types = [a.type for a in activities]
    assert ActivityType.OPT_OUT in activity_types


def test_normal_message_does_not_trigger_opt_out(db_session):
    lead, _ = _make_lead_in_campaign(db_session)
    service, conv = _start_conversation(db_session, lead=lead)

    service.handle_message(ConversationRequest(conversation_id=conv.id, text="Bonjour"))

    db_session.refresh(lead)
    assert lead.opt_out_at is None
    assert lead.first_name is not None  # PII intact


# ---------------------------------------------------------------------------
# Follow-up scheduler must skip opted-out leads
# ---------------------------------------------------------------------------

def test_follow_up_scheduler_skips_opted_out_leads(db_session):
    """send_due_follow_ups must not contact a lead that has opt_out_at set."""
    from followup.engine import FollowUpEngine
    from crm.conversation_repository import ConversationRepository

    lead, _ = _make_lead_in_campaign(db_session)
    service, conv = _start_conversation(db_session, lead=lead)

    # Put conversation in WAITING_CUSTOMER so it is a follow-up candidate
    ConversationRepository(db_session).transition_state(
        conv, ConversationState.WAITING_CUSTOMER, remember_previous=True
    )
    past_due = datetime.utcnow() - timedelta(days=1)
    LeadRepository(db_session).update_fields(
        lead,
        next_follow_up_date=past_due,
        follow_up_category=FollowUpCategory.WARM,
    )
    db_session.flush()

    # Now opt the lead out
    service.handle_message(ConversationRequest(conversation_id=conv.id, text="stop"))

    # Run the follow-up engine -- it must skip the opted-out lead
    engine = FollowUpEngine(db_session, service=service)
    results = engine.send_due_follow_ups()

    # No follow-up should have been sent to the opted-out lead
    opted_out_results = [r for r in results if r.lead.id == lead.id]
    assert opted_out_results == [], (
        "FollowUpEngine sent a follow-up to an opted-out lead"
    )


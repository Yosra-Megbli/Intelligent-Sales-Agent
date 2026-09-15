"""
Tests for backend/scripts/reset_demo_lead.py.

Verifies that the dev-only reset script properly clears:
  - opt_out_at timestamp
  - rejection_reason
  - dedup suppression keys (dedup_email, dedup_phone)
  - conversation state (resets from CLOSED back to START)
  - detour / extraction failure counters
  - Redis cache keys
and sets lead status back to NEW, allowing subsequent /start messages to succeed.
"""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from application.conversation_service import ConversationRequest, ConversationService
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel, ConversationState, LeadStatus, RejectionReason
from scripts.reset_demo_lead import reset_demo_lead


def test_reset_demo_lead_by_chat_id_allows_start_greeting(db_session):
    """A lead who opts out via STOP on Telegram can be reset by chat_id and respond to /start."""
    service = ConversationService(db_session, provider=None)
    chat_id = "987654321"

    # Start conversation on Telegram
    lead, conv = service.start_conversation(
        channel=ConversationChannel.TELEGRAM,
        external_id=chat_id,
        first_name="Alice",
    )

    # User opts out via STOP
    opt_out_resp = service.handle_message(
        ConversationRequest(conversation_id=conv.id, text="STOP")
    )
    assert opt_out_resp.state == ConversationState.CLOSED.value

    db_session.refresh(lead)
    db_session.refresh(conv)
    assert lead.opt_out_at is not None
    assert lead.status == LeadStatus.REJECTED
    assert lead.rejection_reason == RejectionReason.REQUEST_HUMAN_ONLY
    assert conv.current_state == ConversationState.CLOSED

    # Before reset: sending /start yields no response
    conv_before = service.handle_message(
        ConversationRequest(conversation_id=conv.id, text="/start")
    )
    assert conv_before.response_text is None

    # Execute reset
    results = reset_demo_lead(db_session, chat_id=chat_id)
    assert len(results) == 1
    assert results[0]["lead_id"] == str(lead.id)
    assert results[0]["new_status"] == LeadStatus.NEW.value

    db_session.refresh(lead)
    db_session.refresh(conv)
    assert lead.opt_out_at is None
    assert lead.rejection_reason is None
    assert lead.status == LeadStatus.NEW
    assert conv.current_state == ConversationState.START
    assert conv.consecutive_detour_count == 0
    assert conv.consecutive_extraction_failures == 0

    # After reset: sending /start now produces a greeting!
    greet_resp = service.handle_message(
        ConversationRequest(conversation_id=conv.id, text="/start")
    )
    assert greet_resp.response_text is not None
    assert "Sophie" in greet_resp.response_text
    assert conv.current_state == ConversationState.GREETING


def test_reset_demo_lead_by_email_clears_suppression_keys(db_session):
    """Resetting by email clears dedup_email and resets status."""
    service = ConversationService(db_session, provider=None)
    lead_repo = LeadRepository(db_session)
    lead = lead_repo.create(
        source="WEBSITE",
        first_name="Bob",
        email="bob.tester@example.com",
    )
    _, conv = service.start_conversation(
        channel=ConversationChannel.WEB,
        email="bob.tester@example.com",
    )

    # Opt out via ARRET
    service.handle_message(ConversationRequest(conversation_id=conv.id, text="ARRET"))

    db_session.refresh(lead)
    assert lead.opt_out_at is not None
    assert lead.dedup_email == "bob.tester@example.com"
    assert lead.status == LeadStatus.REJECTED

    # Reset by email
    results = reset_demo_lead(db_session, email="bob.tester@example.com")
    assert len(results) == 1

    db_session.refresh(lead)
    assert lead.opt_out_at is None
    assert lead.dedup_email is None
    assert lead.rejection_reason is None
    assert lead.status == LeadStatus.NEW


def test_reset_demo_lead_by_phone_clears_dedup_phone(db_session):
    """Resetting by phone clears dedup_phone and resets status."""
    service = ConversationService(db_session, provider=None)
    lead_repo = LeadRepository(db_session)
    lead = lead_repo.create(
        source="WHATSAPP",
        first_name="Charlie",
        phone="0477123456",
    )
    _, conv = service.start_conversation(
        channel=ConversationChannel.WHATSAPP,
        phone="0477123456",
    )

    # Opt out via STOPT
    service.handle_message(ConversationRequest(conversation_id=conv.id, text="STOPT"))

    db_session.refresh(lead)
    assert lead.opt_out_at is not None
    assert lead.dedup_phone == "0477123456"

    # Reset by phone
    results = reset_demo_lead(db_session, phone="0477123456")
    assert len(results) == 1

    db_session.refresh(lead)
    assert lead.opt_out_at is None
    assert lead.dedup_phone is None
    assert lead.status == LeadStatus.NEW


def test_reset_demo_lead_purges_redis_cache(db_session):
    """Verify that Redis key deletion is called for each reset conversation."""
    service = ConversationService(db_session, provider=None)
    lead, conv = service.start_conversation(
        channel=ConversationChannel.TELEGRAM,
        external_id="555111222",
    )
    mock_redis = MagicMock()

    results = reset_demo_lead(db_session, chat_id="555111222", redis_client=mock_redis)
    assert len(results) == 1
    mock_redis.delete.assert_called_once_with(f"conversation:context:{conv.id}")
    assert results[0]["redis_purged_count"] == 1


def test_reset_demo_lead_unknown_identifier_raises_value_error(db_session):
    """Trying to reset a non-existent identifier raises ValueError."""
    with pytest.raises(ValueError, match="No lead found"):
        reset_demo_lead(db_session, chat_id="000000000")


def test_list_demo_leads(db_session):
    """list_demo_leads returns records with conversations and chat_id."""
    from scripts.reset_demo_lead import list_demo_leads

    service = ConversationService(db_session, provider=None)
    lead, conv = service.start_conversation(
        channel=ConversationChannel.TELEGRAM,
        external_id="11223344",
        first_name="Dana",
    )
    records = list_demo_leads(db_session)
    assert len(records) == 1
    assert records[0]["lead_id"] == str(lead.id)
    assert records[0]["telegram_chat_id"] == "11223344"
    assert len(records[0]["conversations"]) == 1
    assert records[0]["conversations"][0]["external_id"] == "11223344"

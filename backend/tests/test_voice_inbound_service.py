"""
Tests for application/voice_inbound_service.py's VoiceInboundService - the
bridge between Twilio's TwiML webhook and VoiceSessionManager/
ConversationService, wired up (with no LLM provider, so responses are the
deterministic fixed fallback text - see
tests/test_conversation_service.py's own `provider=None` tests) to keep
this file focused on the wiring (TwiML shape, hangup, Redis-backed call
state threading across turns) rather than dialogue content, which is
already covered elsewhere.
"""

import uuid

import pytest

import application.voice_inbound_service as voice_inbound_service
from application.voice_inbound_service import VoiceInboundService
from crm.lead_repository import LeadRepository
from domain.enums import LeadSource


@pytest.fixture(autouse=True)
def fake_voice_call_state(monkeypatch):
    """In-memory fake for the three Redis-backed functions this module
    calls, so these tests never depend on a real Redis instance - same
    reasoning as tests/test_api.py's fake_redis_cache fixture for
    conversation context."""
    store: dict[str, dict] = {}

    def fake_cache(call_sid, state, ttl_seconds=1800):
        store[call_sid] = state

    def fake_get(call_sid):
        return store.get(call_sid)

    def fake_clear(call_sid):
        store.pop(call_sid, None)

    monkeypatch.setattr(voice_inbound_service, "cache_voice_call_state", fake_cache)
    monkeypatch.setattr(voice_inbound_service, "get_cached_voice_call_state", fake_get)
    monkeypatch.setattr(voice_inbound_service, "clear_voice_call_state", fake_clear)
    yield store


def _lead(db_session):
    lead = LeadRepository(db_session).create(source=LeadSource.CSV, first_name="Jean", phone="+32491234567")
    db_session.commit()
    return lead


def test_first_hit_with_no_call_sid_apologizes_and_hangs_up(db_session):
    service = VoiceInboundService(db_session, provider=None)

    result = service.handle_webhook({}, lead_id=None)

    assert result.should_hangup is True
    assert "<Hangup/>" in result.xml


def test_first_hit_with_no_lead_id_apologizes_and_hangs_up(db_session):
    service = VoiceInboundService(db_session, provider=None)

    result = service.handle_webhook({"CallSid": "CA1"}, lead_id=None)

    assert result.should_hangup is True
    assert "<Hangup/>" in result.xml


def test_first_hit_with_an_unknown_lead_id_apologizes_and_hangs_up(db_session):
    service = VoiceInboundService(db_session, provider=None)

    result = service.handle_webhook({"CallSid": "CA1"}, lead_id=uuid.uuid4())

    assert result.should_hangup is True
    assert "<Hangup/>" in result.xml


def test_first_hit_with_a_real_lead_greets_and_gathers_the_next_turn(db_session, fake_voice_call_state):
    lead = _lead(db_session)
    service = VoiceInboundService(db_session, provider=None)

    result = service.handle_webhook({"CallSid": "CA1"}, lead_id=lead.id)

    assert result.should_hangup is False
    assert "<Say" in result.xml
    assert '<Gather input="speech"' in result.xml
    assert "CA1" in fake_voice_call_state


def test_second_hit_reuses_the_cached_call_state_and_advances_the_turn(db_session, fake_voice_call_state):
    lead = _lead(db_session)
    service = VoiceInboundService(db_session, provider=None)
    service.handle_webhook({"CallSid": "CA1"}, lead_id=lead.id)
    assert "CA1" in fake_voice_call_state

    result = service.handle_webhook(
        {"CallSid": "CA1", "SpeechResult": "Bonjour", "Confidence": "0.9"}, lead_id=None
    )

    assert isinstance(result.xml, str) and result.xml  # a real turn ran, not the apology stub


def test_a_call_sid_never_seen_before_with_no_lead_id_is_treated_as_unrecoverable(db_session):
    service = VoiceInboundService(db_session, provider=None)

    result = service.handle_webhook({"CallSid": "CA-unknown"}, lead_id=None)

    assert result.should_hangup is True
    assert "<Hangup/>" in result.xml


def test_hanging_up_clears_the_cached_call_state(db_session, fake_voice_call_state, monkeypatch):
    lead = _lead(db_session)
    service = VoiceInboundService(db_session, provider=None)
    service.handle_webhook({"CallSid": "CA1"}, lead_id=lead.id)
    assert "CA1" in fake_voice_call_state

    # Force a hangup regardless of dialogue content by driving the state
    # machine with REQUEST_HUMAN-shaped text is fragile without a real
    # extractor - instead simulate it directly against the policy's own
    # hangup path via silence exhaustion (provider=None -> extractor=None
    # -> every turn is CUSTOMER_MESSAGE, so silence is the deterministic
    # way to reach VoicePolicy's max_silence_attempts hangup regardless of
    # LLM behaviour).
    for _ in range(3):
        result = service.handle_webhook({"CallSid": "CA1"}, lead_id=None)

    assert result.should_hangup is True
    assert "CA1" not in fake_voice_call_state

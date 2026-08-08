from datetime import datetime, timedelta

import pytest

from application.conversation_service import ConversationService
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import (
    ConversationChannel,
    ConversationState,
    FollowUpCategory,
    LeadSource,
    LeadStatus,
)
from followup.engine import FollowUpEngine, MAX_FOLLOW_UP_ATTEMPTS, SILENCE_THRESHOLD_HOURS


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


def _silent_conversation(db_session, state=ConversationState.COLLECT_SUPPLIER, hours_silent=48):
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE, email="jean@test.com")
    conversation = ConversationRepository(db_session).create(lead_id=lead.id, channel=ConversationChannel.WEB)
    ConversationRepository(db_session).transition_state(conversation, state)
    conversation.last_message_at = datetime.utcnow() - timedelta(hours=hours_silent)
    db_session.commit()
    return lead, conversation


def test_marks_a_silent_conversation_as_waiting_customer(db_session):
    lead, conversation = _silent_conversation(db_session, hours_silent=SILENCE_THRESHOLD_HOURS + 1)
    engine = FollowUpEngine(db_session)

    marked = engine.mark_silent_conversations_as_waiting()

    assert conversation in marked
    assert conversation.current_state == ConversationState.WAITING_CUSTOMER
    assert conversation.previous_state == ConversationState.COLLECT_SUPPLIER
    assert lead.next_follow_up_date is not None


def test_does_not_mark_a_recently_active_conversation(db_session):
    lead, conversation = _silent_conversation(db_session, hours_silent=1)
    engine = FollowUpEngine(db_session)

    marked = engine.mark_silent_conversations_as_waiting()

    assert marked == []
    assert conversation.current_state == ConversationState.COLLECT_SUPPLIER


def test_does_not_mark_a_terminal_conversation(db_session):
    lead, conversation = _silent_conversation(
        db_session, state=ConversationState.CLOSED, hours_silent=SILENCE_THRESHOLD_HOURS + 1
    )
    engine = FollowUpEngine(db_session)

    marked = engine.mark_silent_conversations_as_waiting()

    assert marked == []


def test_first_follow_up_is_categorized_hot(db_session):
    lead, conversation = _silent_conversation(db_session, hours_silent=SILENCE_THRESHOLD_HOURS + 1)
    engine = FollowUpEngine(db_session)

    engine.mark_silent_conversations_as_waiting()

    assert lead.follow_up_category == FollowUpCategory.HOT


def test_sends_a_due_follow_up_and_reschedules(db_session):
    lead, conversation = _silent_conversation(db_session, hours_silent=SILENCE_THRESHOLD_HOURS + 1)
    engine = FollowUpEngine(db_session, service=ConversationService(db_session))
    engine.mark_silent_conversations_as_waiting()

    past_due = datetime.utcnow() + timedelta(days=999)  # force "due" regardless of config delay
    results = engine.send_due_follow_ups(as_of=past_due)

    assert len(results) == 1
    assert results[0].response_text
    assert results[0].gave_up is False
    assert lead.follow_up_attempts == 1  # exactly one real message has been sent so far
    assert lead.next_follow_up_date is not None


def test_does_not_send_a_follow_up_that_is_not_yet_due(db_session):
    lead, conversation = _silent_conversation(db_session, hours_silent=SILENCE_THRESHOLD_HOURS + 1)
    engine = FollowUpEngine(db_session, service=ConversationService(db_session))
    engine.mark_silent_conversations_as_waiting()

    results = engine.send_due_follow_ups(as_of=datetime.utcnow())  # delay hasn't elapsed yet

    assert results == []


def test_gives_up_after_max_attempts(db_session):
    lead, conversation = _silent_conversation(db_session, hours_silent=SILENCE_THRESHOLD_HOURS + 1)
    engine = FollowUpEngine(db_session, service=ConversationService(db_session))
    engine.mark_silent_conversations_as_waiting()
    lead.follow_up_attempts = MAX_FOLLOW_UP_ATTEMPTS
    db_session.commit()

    far_future = datetime.utcnow() + timedelta(days=999)
    results = engine.send_due_follow_ups(as_of=far_future)

    assert len(results) == 1
    assert results[0].gave_up is True
    assert conversation.current_state == ConversationState.CLOSED
    assert lead.status == LeadStatus.CLOSED
    assert lead.follow_up_category == FollowUpCategory.STOPPED
    assert lead.next_follow_up_date is None


def test_delivers_exactly_max_attempts_real_messages_before_giving_up_regression_f015(db_session):
    """The real end-to-end regression test for F-015 (BAT SC-104-106): with
    max_follow_up_attempts=3 configured, exactly 3 real follow-up messages
    must be sent before giving up - not 2. Runs the full lifecycle: go
    silent (no message sent yet), then three separate due-cycles each
    sending one real message, then a fourth that must give up instead of
    sending a message."""
    lead, conversation = _silent_conversation(db_session, hours_silent=SILENCE_THRESHOLD_HOURS + 1)
    engine = FollowUpEngine(db_session, service=ConversationService(db_session))
    engine.mark_silent_conversations_as_waiting()
    assert lead.follow_up_attempts == 0  # going silent alone must not count as an attempt

    sent_count = 0
    for cycle in range(1, MAX_FOLLOW_UP_ATTEMPTS + 1):
        far_future = datetime.utcnow() + timedelta(days=999 * cycle)
        results = engine.send_due_follow_ups(as_of=far_future)
        assert len(results) == 1
        assert results[0].gave_up is False
        assert results[0].response_text
        sent_count += 1
        assert lead.follow_up_attempts == sent_count

    assert sent_count == MAX_FOLLOW_UP_ATTEMPTS

    # One more due-cycle after the max is reached: gives up, no message.
    final_future = datetime.utcnow() + timedelta(days=999 * (MAX_FOLLOW_UP_ATTEMPTS + 1))
    final_results = engine.send_due_follow_ups(as_of=final_future)
    assert len(final_results) == 1
    assert final_results[0].gave_up is True
    assert final_results[0].response_text is None
    assert conversation.current_state == ConversationState.CLOSED
    assert lead.follow_up_attempts == MAX_FOLLOW_UP_ATTEMPTS  # giving up never counts as an attempt either


def test_ignores_a_lead_whose_conversation_already_moved_on(db_session):
    """If the customer replied through another path before the scheduler
    ran, the conversation is no longer WAITING_CUSTOMER - nothing to do."""
    lead, conversation = _silent_conversation(db_session, hours_silent=SILENCE_THRESHOLD_HOURS + 1)
    engine = FollowUpEngine(db_session, service=ConversationService(db_session))
    engine.mark_silent_conversations_as_waiting()

    ConversationRepository(db_session).resume_previous_state(conversation)
    db_session.commit()

    far_future = datetime.utcnow() + timedelta(days=999)
    results = engine.send_due_follow_ups(as_of=far_future)

    assert results == []

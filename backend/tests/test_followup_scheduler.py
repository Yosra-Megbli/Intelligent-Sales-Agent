from datetime import datetime, timedelta

import pytest

from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel, ConversationState, LeadSource
from followup.scheduler import run_followup_cycle


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


def test_run_followup_cycle_marks_and_sends_then_delivers(db_session):
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE, email="jean@test.com")
    conversation = ConversationRepository(db_session).create(lead_id=lead.id, channel=ConversationChannel.WEB)
    ConversationRepository(db_session).transition_state(conversation, ConversationState.COLLECT_SUPPLIER)
    conversation.last_message_at = datetime.utcnow() - timedelta(hours=48)
    db_session.commit()

    delivered = []
    # First cycle just marks it silent (delay hasn't elapsed) - nothing delivered yet.
    run_followup_cycle(db_session, deliver=lambda conv, text: delivered.append((conv.id, text)))
    assert delivered == []
    assert conversation.current_state == ConversationState.WAITING_CUSTOMER

    # Simulate time passing past the follow-up delay by back-dating next_follow_up_date.
    lead.next_follow_up_date = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    run_followup_cycle(db_session, deliver=lambda conv, text: delivered.append((conv.id, text)))

    assert len(delivered) == 1
    assert delivered[0][0] == conversation.id
    assert delivered[0][1]  # non-empty text was delivered

"""
P1-1 / P1-2 regression tests: ConversationService.start_conversation() must
reuse an existing Lead (matched by email/phone) instead of always creating a
new one, and PostgreSQL's own unique indexes (see domain/models/lead.py's
dedup_email/dedup_phone) must be the last line of defense against a race
between two concurrent requests.

Tests 1-5 use the standard in-memory SQLite `db_session` fixture (see
conftest.py). Test 6 (the race condition) needs two independent sessions
that actually share one database - an in-memory SQLite DB is private to its
own connection, so that test opens its own file-backed SQLite database
instead, to genuinely exercise the unique index across two separate
sessions/transactions the same way two separate Postgres connections would.
"""

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from application.conversation_service import ConversationService
from crm.lead_repository import LeadRepository
from database.postgres import Base
from domain import models  # noqa: F401 - registers models on Base.metadata
from domain.enums import ConversationChannel, LeadSource


@pytest.fixture(autouse=True)
def fake_redis_cache(monkeypatch):
    store: dict = {}

    def fake_cache(conversation_id, context, ttl_seconds=3600):
        store[conversation_id] = context

    def fake_get(conversation_id):
        return store.get(conversation_id)

    monkeypatch.setattr("conversation_engine.memory.cache_conversation_context", fake_cache)
    monkeypatch.setattr("conversation_engine.memory.get_cached_conversation_context", fake_get)
    yield store


# --- Test 1: new Lead -------------------------------------------------------

def test_start_conversation_creates_a_new_lead_when_none_matches(db_session):
    service = ConversationService(db_session, provider=None)

    lead, conversation = service.start_conversation(ConversationChannel.WEB, email="new@test.com")

    assert lead.email == "new@test.com"
    assert conversation.lead_id == lead.id
    assert len(LeadRepository(db_session).list_leads()[0]) == 1


# --- Test 2: existing Lead reused by email ----------------------------------

def test_start_conversation_reuses_existing_lead_by_email(db_session):
    existing = LeadRepository(db_session).create(source=LeadSource.WEBSITE, email="jean@test.com")
    service = ConversationService(db_session, provider=None)

    lead, conversation = service.start_conversation(ConversationChannel.WEB, email="jean@test.com")

    assert lead.id == existing.id
    assert conversation.lead_id == existing.id
    all_leads, total = LeadRepository(db_session).list_leads()
    assert total == 1  # no second Lead was created


# --- Test 3: email is matched case-insensitively ----------------------------

def test_start_conversation_matches_email_case_insensitively(db_session):
    existing = LeadRepository(db_session).create(source=LeadSource.WEBSITE, email="existing@email.com")
    service = ConversationService(db_session, provider=None)

    lead, _ = service.start_conversation(ConversationChannel.WEB, email="Existing@Email.com")

    assert lead.id == existing.id
    assert LeadRepository(db_session).list_leads()[1] == 1


# --- Test 4: existing Lead reused by phone ----------------------------------

def test_start_conversation_reuses_existing_lead_by_phone(db_session):
    existing = LeadRepository(db_session).create(source=LeadSource.WEBSITE, phone="0499998877")
    service = ConversationService(db_session, provider=None)

    lead, conversation = service.start_conversation(ConversationChannel.WEB, phone="0499998877")

    assert lead.id == existing.id
    assert conversation.lead_id == existing.id
    assert LeadRepository(db_session).list_leads()[1] == 1


# --- Test 5: no reliable identifier never merges leads ----------------------

def test_start_conversation_without_email_or_phone_never_merges_leads(db_session):
    """Telegram/WhatsApp's first contact (only a channel external_id, no
    email/phone yet) must keep creating one Lead per new conversation - there
    is nothing reliable to match on, and guessing would risk merging two
    different people."""
    LeadRepository(db_session).create(source=LeadSource.WEBSITE)  # a pre-existing, data-less lead
    service = ConversationService(db_session, provider=None)

    lead_a, _ = service.start_conversation(ConversationChannel.TELEGRAM, external_id="111")
    lead_b, _ = service.start_conversation(ConversationChannel.TELEGRAM, external_id="222")

    assert lead_a.id != lead_b.id
    assert LeadRepository(db_session).list_leads()[1] == 3


# --- Test 6: race condition -> 1 Lead, 2 Conversations ----------------------

@pytest.fixture()
def shared_file_db():
    """Two independent sessions backed by the same on-disk SQLite file, so a
    unique-index violation raised in one session is a genuine cross-session/
    cross-transaction conflict - the same shape a race between two Postgres
    connections would produce (see module docstring)."""
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    os.remove(path)  # let SQLAlchemy create a clean file
    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    try:
        yield Session
    finally:
        engine.dispose()
        if os.path.exists(path):
            os.remove(path)


def test_start_conversation_race_condition_results_in_one_lead_two_conversations(shared_file_db, monkeypatch):
    session_a = shared_file_db()
    session_b = shared_file_db()
    service_a = ConversationService(session_a, provider=None)
    service_b = ConversationService(session_b, provider=None)

    # Simulate two requests whose find_duplicate() lookup both ran before
    # either had committed anything (the actual race window P1-2 protects
    # against): force session_a's own pre-insert check to report "not
    # found", exactly like it would if it ran concurrently with session_b's
    # request, a heartbeat before session_b commits.
    real_find_duplicate = service_a.lead_repo.find_duplicate
    call_count = {"n": 0}

    def racy_find_duplicate(email, phone, *, exclude_lead_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None
        return real_find_duplicate(email, phone, exclude_lead_id=exclude_lead_id)

    monkeypatch.setattr(service_a.lead_repo, "find_duplicate", racy_find_duplicate)

    # Request B: wins the race, creates+commits the Lead first.
    lead_b, conversation_b = service_b.start_conversation(ConversationChannel.WEB, email="race@test.com")
    session_b.commit()

    # Request A: its own (patched) pre-check still reports "no match" - only
    # PostgreSQL's unique index (here, SQLite's - see shared_file_db) stops
    # it from creating a second Lead. start_conversation must catch that,
    # roll back its own failed insert, and reuse Request B's Lead instead of
    # raising a 500.
    lead_a, conversation_a = service_a.start_conversation(ConversationChannel.WEB, email="race@test.com")
    session_a.commit()

    assert lead_a.id == lead_b.id  # 1 Lead
    assert conversation_a.id != conversation_b.id  # 2 Conversations
    assert conversation_a.lead_id == lead_a.id
    assert conversation_b.lead_id == lead_b.id

    verify_session = shared_file_db()
    try:
        total_leads = verify_session.query(models.Lead).filter_by(dedup_email="race@test.com").count()
        total_conversations = verify_session.query(models.Conversation).filter_by(lead_id=lead_a.id).count()
        assert total_leads == 1
        assert total_conversations == 2
    finally:
        verify_session.close()

    session_a.close()
    session_b.close()

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.postgres import Base
from domain import models  # noqa: F401 - registers models on Base.metadata


@pytest.fixture()
def db_session():
    """Same pattern as tests/conftest.py - kept as its own copy so
    golden_tests/ can run standalone (e.g. `pytest golden_tests/`) without
    depending on tests/ being collected first."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def fake_redis_cache(monkeypatch):
    """ConversationMemory reads/writes a Redis cache for `last_question_action`
    (see conversation_engine/memory.py). Golden conversation tests don't need
    real Redis - an in-memory dict is enough to exercise the same contract."""
    store: dict[str, dict] = {}

    def fake_cache(conversation_id, context, ttl_seconds=3600):
        store[conversation_id] = context

    def fake_get(conversation_id):
        return store.get(conversation_id)

    monkeypatch.setattr("conversation_engine.memory.cache_conversation_context", fake_cache)
    monkeypatch.setattr("conversation_engine.memory.get_cached_conversation_context", fake_get)
    yield store

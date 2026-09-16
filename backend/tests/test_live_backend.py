"""
Unit and integration tests for Sprint 5 Live Backend (SSE Cockpit).
- Token issuance and validation
- Stream concurrency limits (max 5)
- InProcessAsyncBroker distribution
- Live stream endpoint with SSE formatting
- ConversationService event emissions and non-blocking failure tolerance
"""

import asyncio
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from api.routes import get_db_session
from application.conversation_service import ConversationRequest, ConversationService
from database.postgres import Base
from domain.enums import ConversationChannel, ConversationState, LeadSource, LeadStatus
from domain.models.conversation import Conversation
from domain.models.lead import Lead
from live.auth import (
    acquire_stream_slot,
    generate_live_token,
    release_stream_slot,
    verify_live_token,
)
from live.broker import InProcessAsyncBroker, set_live_broker


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def fresh_broker():
    broker = InProcessAsyncBroker()
    set_live_broker(broker)
    yield broker
    set_live_broker(None)


AUTH_HEADERS = {"X-API-Key": "test-key-123"}


def test_token_generation_and_verification():
    key_id = "test_key_abc"
    token = generate_live_token(key_id, expires_in=300)
    parsed_key, is_valid = verify_live_token(token)
    assert is_valid is True
    assert parsed_key == key_id

    # Expired token
    expired_token = generate_live_token(key_id, expires_in=-10)
    _, is_valid = verify_live_token(expired_token)
    assert is_valid is False

    # Tampered signature
    tampered = token[:-4] + "ffff"
    _, is_valid = verify_live_token(tampered)
    assert is_valid is False

    # Malformed token
    assert verify_live_token("malformed")[1] is False
    assert verify_live_token("")[1] is False


def test_concurrency_slots():
    key_id = f"test_key_{uuid4().hex[:8]}"
    for _ in range(5):
        assert acquire_stream_slot(key_id, max_concurrent=5) is True

    # 6th attempt should fail
    assert acquire_stream_slot(key_id, max_concurrent=5) is False

    # Release one slot
    release_stream_slot(key_id)
    # Now slot is free
    assert acquire_stream_slot(key_id, max_concurrent=5) is True

    # Cleanup
    for _ in range(5):
        release_stream_slot(key_id)


def test_token_endpoint(client):
    res = client.post("/api/live/token", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["expires_in"] == 300

    parsed_key, is_valid = verify_live_token(data["token"])
    assert is_valid is True


def test_live_stream_invalid_token(client):
    res = client.get("/api/live/stream?token=invalid_token")
    assert res.status_code == 401


def test_broker_zero_subscribers_does_not_error():
    broker = InProcessAsyncBroker()
    # Publishing with no subscribers should be a safe no-op
    broker.publish_sync("test_event", {"foo": "bar"})


@pytest.mark.anyio
async def test_broker_subscribe_and_publish():
    broker = InProcessAsyncBroker()
    queue = await broker.subscribe()

    broker.publish_sync("conversation_updated", {"id": "123"})
    msg = queue.get_nowait()
    assert msg["event"] == "conversation_updated"
    assert msg["data"] == {"id": "123"}

    await broker.unsubscribe(queue)


def test_key_health_endpoint(client):
    res = client.get("/api/keys/health", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "unknown"


def test_handle_message_emits_live_event(db_session, fresh_broker):
    lead = Lead(
        id=uuid4(),
        source=LeadSource.WEBSITE,
        status=LeadStatus.NEW,
        language="fr",
    )
    db_session.add(lead)
    db_session.flush()

    conv = Conversation(
        id=uuid4(),
        lead_id=lead.id,
        channel=ConversationChannel.WEB,
        current_state=ConversationState.START,
        language="fr",
    )
    db_session.add(conv)
    db_session.commit()

    # Subscribe to broker
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    queue = loop.run_until_complete(fresh_broker.subscribe())

    service = ConversationService(db_session)
    # Customer says "oui" to consent
    req = ConversationRequest(conversation_id=conv.id, text="oui j'accepte")
    resp = service.handle_message(req)
    assert resp.response_text is not None

    # Check that events were put into subscriber queue
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    event_types = [e["event"] for e in events]
    assert "conversation_updated" in event_types
    update_event = next(e for e in events if e["event"] == "conversation_updated")
    assert update_event["data"]["conversation_id"] == str(conv.id)
    assert update_event["data"]["direction"] == "out"


def test_emission_failure_does_not_break_conversation(db_session):
    lead = Lead(
        id=uuid4(),
        source=LeadSource.WEBSITE,
        status=LeadStatus.NEW,
        language="fr",
    )
    db_session.add(lead)
    db_session.flush()

    conv = Conversation(
        id=uuid4(),
        lead_id=lead.id,
        channel=ConversationChannel.WEB,
        current_state=ConversationState.START,
        language="fr",
    )
    db_session.add(conv)
    db_session.commit()

    service = ConversationService(db_session)

    # Force broker to raise an exception
    with patch("live.broker.get_live_broker", side_effect=RuntimeError("Broker crashed!")):
        req = ConversationRequest(conversation_id=conv.id, text="bonjour")
        resp = service.handle_message(req)
        # Conversation response still succeeds without error!
        assert resp is not None
        assert resp.response_text is not None

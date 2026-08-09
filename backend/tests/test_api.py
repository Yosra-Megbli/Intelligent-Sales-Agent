"""
Integration tests for the FastAPI layer (api/main.py, api/routes.py).

Uses FastAPI's dependency_overrides to swap `session_scope` for a SQLite
in-memory session (same technique as tests/conftest.py's `db_session`
fixture, adapted for a context-manager dependency) and `get_llm_provider`
for a deterministic fake - no real Postgres, Redis, or Groq call needed.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ai.providers.interface import LLMProvider, LLMResponse
from api.dependencies import get_llm_provider, get_telegram_sender, get_whatsapp_sender
from api.main import app
from api.routes import get_db_session
from database.postgres import Base
from domain import models  # noqa: F401 - registers models on Base.metadata


class ScriptedProvider(LLMProvider):
    def __init__(self, extraction_payload: dict, response_text: str = "Bonjour !"):
        self.extraction_payload = extraction_payload
        self.response_text = response_text

    def generate(self, messages, *, temperature=0.0, max_tokens=1024, json_mode=False):
        if json_mode:
            return LLMResponse(content=json.dumps(self.extraction_payload), model="fake-model")
        return LLMResponse(content=self.response_text, model="fake-model")


@pytest.fixture(autouse=True)
def clean_security_env(monkeypatch):
    """Tests must never depend on what the developer's actual `.env` sets
    for API_KEY/TELEGRAM_WEBHOOK_SECRET/TWILIO_AUTH_TOKEN - `database.postgres`
    loads that file at import time, so without this these tests silently
    pass or fail depending on the machine they run on. Force the same
    "not configured" baseline every test starts from; tests that want to
    exercise the auth-enabled path (e.g. test_telegram_webhook_requires_secret_token_once_configured)
    still set their own value on top via their own monkeypatch.setenv call.
    """
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)


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


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, future=True)

    def override_get_db_session():
        db = TestingSession()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_llm_provider] = lambda: ScriptedProvider(
        extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}}
    )
    sent_messages: list[tuple[str, str]] = []
    app.dependency_overrides[get_telegram_sender] = lambda: (
        lambda chat_id, text: sent_messages.append((chat_id, text))
    )
    sent_whatsapp_messages: list[tuple[str, str]] = []
    app.dependency_overrides[get_whatsapp_sender] = lambda: (
        lambda phone, text: sent_whatsapp_messages.append((phone, text))
    )

    with TestClient(app) as test_client:
        test_client.sent_messages = sent_messages  # type: ignore[attr-defined]
        test_client.sent_whatsapp_messages = sent_whatsapp_messages  # type: ignore[attr-defined]
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()


def _start_conversation(client) -> str:
    response = client.post("/api/conversations", json={"email": "jean@test.com"})
    assert response.status_code == 201
    return response.json()["conversation_id"]


def test_health_endpoint():
    with TestClient(app) as test_client:
        response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_start_conversation_returns_ids(client):
    response = client.post("/api/conversations", json={"email": "jean@test.com"})

    assert response.status_code == 201
    body = response.json()
    assert "conversation_id" in body
    assert "lead_id" in body


def test_send_message_advances_state_and_returns_reply(client):
    conversation_id = _start_conversation(client)

    response = client.post(f"/api/conversations/{conversation_id}/messages", json={"text": "Bonjour"})

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "GREETING"
    assert body["reply"] == "Bonjour !"


def test_send_message_to_unknown_conversation_returns_404(client):
    response = client.post(
        "/api/conversations/00000000-0000-0000-0000-000000000000/messages", json={"text": "Bonjour"}
    )
    assert response.status_code == 404


def test_get_history_returns_persisted_messages_in_order(client):
    conversation_id = _start_conversation(client)
    client.post(f"/api/conversations/{conversation_id}/messages", json={"text": "Bonjour"})

    response = client.get(f"/api/conversations/{conversation_id}/messages")

    assert response.status_code == 200
    roles = [m["role"] for m in response.json()]
    assert roles == ["USER", "ASSISTANT"]


def test_get_history_for_unknown_conversation_returns_404(client):
    response = client.get("/api/conversations/00000000-0000-0000-0000-000000000000/messages")
    assert response.status_code == 404


def test_empty_message_text_is_rejected_with_422(client):
    conversation_id = _start_conversation(client)

    response = client.post(f"/api/conversations/{conversation_id}/messages", json={"text": ""})

    assert response.status_code == 422


def test_conversation_state_persists_across_requests(client):
    conversation_id = _start_conversation(client)
    client.post(f"/api/conversations/{conversation_id}/messages", json={"text": "Bonjour"})

    second = client.post(f"/api/conversations/{conversation_id}/messages", json={"text": "encore"})

    # GREETING always advances to DISCOVERY regardless of event content.
    assert second.json()["state"] == "DISCOVERY"


def _telegram_update(chat_id: int, text: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
            "from": {"id": chat_id, "first_name": "Jean"},
        },
    }


def test_telegram_webhook_processes_an_update_and_returns_ok(client):
    response = client.post("/api/telegram/webhook", json=_telegram_update(123, "Bonjour"))

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["state"] == "GREETING"


def test_telegram_webhook_sends_the_reply_via_the_injected_sender(client):
    client.post("/api/telegram/webhook", json=_telegram_update(456, "Bonjour"))

    assert client.sent_messages == [("456", "Bonjour !")]


def test_telegram_webhook_resumes_the_same_conversation_across_requests(client):
    client.post("/api/telegram/webhook", json=_telegram_update(789, "Bonjour"))
    second = client.post("/api/telegram/webhook", json=_telegram_update(789, "encore"))

    assert second.json()["state"] == "DISCOVERY"
    # Still exactly one Telegram lead/conversation for this chat_id.
    assert len(client.sent_messages) == 2


def test_telegram_webhook_ignores_updates_with_no_text_message(client):
    response = client.post(
        "/api/telegram/webhook", json={"update_id": 1, "edited_message": {"text": "oops"}}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_start_conversation_requires_api_key_once_configured(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")

    unauthenticated = client.post("/api/conversations", json={})
    assert unauthenticated.status_code == 401

    authenticated = client.post("/api/conversations", json={}, headers={"X-API-Key": "s3cret"})
    assert authenticated.status_code == 201


def test_telegram_webhook_requires_secret_token_once_configured(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "tg-secret")

    unauthenticated = client.post("/api/telegram/webhook", json=_telegram_update(321, "Bonjour"))
    assert unauthenticated.status_code == 403

    authenticated = client.post(
        "/api/telegram/webhook",
        json=_telegram_update(321, "Bonjour"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "tg-secret"},
    )
    assert authenticated.status_code == 200


def _whatsapp_payload(phone: str, text: str) -> dict:
    return {
        "MessageSid": "SM123",
        "From": f"whatsapp:{phone}",
        "To": "whatsapp:+14155238886",
        "Body": text,
        "ProfileName": "Jean",
        "NumMedia": "0",
    }


def test_whatsapp_webhook_processes_a_message_and_returns_ok(client):
    response = client.post("/api/whatsapp/webhook", data=_whatsapp_payload("+15551234567", "Bonjour"))

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["state"] == "GREETING"


def test_whatsapp_webhook_sends_the_reply_via_the_injected_sender(client):
    client.post("/api/whatsapp/webhook", data=_whatsapp_payload("+15559998888", "Bonjour"))

    assert client.sent_whatsapp_messages == [("+15559998888", "Bonjour !")]


def test_whatsapp_webhook_resumes_the_same_conversation_across_requests(client):
    client.post("/api/whatsapp/webhook", data=_whatsapp_payload("+15550001234", "Bonjour"))
    second = client.post("/api/whatsapp/webhook", data=_whatsapp_payload("+15550001234", "encore"))

    assert second.json()["state"] == "DISCOVERY"
    assert len(client.sent_whatsapp_messages) == 2


def test_whatsapp_webhook_ignores_payloads_with_no_body(client):
    response = client.post(
        "/api/whatsapp/webhook", data={"MessageSid": "SM1", "MessageStatus": "delivered"}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_whatsapp_webhook_requires_valid_twilio_signature_once_configured(client, monkeypatch):
    from api.dependencies import _compute_twilio_signature

    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-secret")
    payload = _whatsapp_payload("+15557778888", "Bonjour")

    unauthenticated = client.post("/api/whatsapp/webhook", data=payload)
    assert unauthenticated.status_code == 403

    url = "http://testserver/api/whatsapp/webhook"
    valid_signature = _compute_twilio_signature("twilio-secret", url, payload)
    authenticated = client.post(
        "/api/whatsapp/webhook", data=payload, headers={"X-Twilio-Signature": valid_signature}
    )
    assert authenticated.status_code == 200


# --- P0: production must never boot unauthenticated -------------------------

def test_production_startup_refuses_to_boot_without_required_secrets(monkeypatch):
    from api.main import _fail_fast_if_misconfigured_for_production

    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="API_KEY.*TELEGRAM_WEBHOOK_SECRET"):
        _fail_fast_if_misconfigured_for_production()


def test_production_startup_succeeds_once_required_secrets_are_set(monkeypatch):
    from api.main import _fail_fast_if_misconfigured_for_production

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_KEY", "s3cret")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "tg-secret")

    _fail_fast_if_misconfigured_for_production()  # must not raise


def test_non_production_startup_never_fails_even_without_secrets(monkeypatch):
    """Preserves the existing dev-friendly default (see api/dependencies.py) -
    ENVIRONMENT unset (or anything other than "production") must behave
    exactly as before this change."""
    from api.main import _fail_fast_if_misconfigured_for_production

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    _fail_fast_if_misconfigured_for_production()  # must not raise

    monkeypatch.setenv("ENVIRONMENT", "staging")
    _fail_fast_if_misconfigured_for_production()  # must not raise

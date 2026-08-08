"""
Integration tests for api/voice_routes.py - POST /api/voice/outbound-calls
and the /api/voice/twiml stub webhook.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_telephony_provider
from api.main import app
from api.routes import get_db_session
from channels.voice.providers.telephony_interface import (
    CallRequest,
    CallResult,
    TelephonyError,
    TelephonyProvider,
)
from crm.campaign_repository import CampaignRepository
from crm.lead_repository import LeadRepository
from database.postgres import Base
from domain import models  # noqa: F401 - registers models on Base.metadata
from domain.enums import CampaignStatus, LeadSource


class _FakeTelephonyProvider(TelephonyProvider):
    def __init__(self, error=None):
        self.error = error
        self.calls: list[CallRequest] = []

    def initiate_call(self, request: CallRequest) -> CallResult:
        self.calls.append(request)
        if self.error:
            raise self.error
        return CallResult(provider_call_id="CA999", status="queued")


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _client(db_engine, telephony_provider):
    TestingSession = sessionmaker(bind=db_engine, future=True)

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
    app.dependency_overrides[get_telephony_provider] = lambda: telephony_provider

    test_client = TestClient(app)
    return test_client, TestingSession


def _seed_lead_and_campaign(session_factory, phone="+32491234567"):
    db = session_factory()
    lead = LeadRepository(db).create(source=LeadSource.CSV, first_name="Jean", phone=phone)
    campaign = CampaignRepository(db).create(name="Voice campaign")
    CampaignRepository(db).set_status(campaign, CampaignStatus.RUNNING)
    db.commit()
    lead_id, campaign_id = lead.id, campaign.id
    db.close()
    return lead_id, campaign_id


def test_initiate_outbound_call_returns_201_when_configured(db_engine):
    provider = _FakeTelephonyProvider()
    client, Session = _client(db_engine, provider)
    lead_id, campaign_id = _seed_lead_and_campaign(Session)

    response = client.post(
        "/api/voice/outbound-calls", json={"lead_id": str(lead_id), "campaign_id": str(campaign_id)}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["provider_call_id"] == "CA999"
    assert body["status"] == "queued"
    assert len(provider.calls) == 1

    app.dependency_overrides.clear()


def test_initiate_outbound_call_returns_503_when_not_configured(db_engine):
    client, Session = _client(db_engine, None)
    lead_id, campaign_id = _seed_lead_and_campaign(Session)

    response = client.post(
        "/api/voice/outbound-calls", json={"lead_id": str(lead_id), "campaign_id": str(campaign_id)}
    )

    assert response.status_code == 503

    app.dependency_overrides.clear()


def test_initiate_outbound_call_returns_404_for_an_unknown_lead(db_engine):
    provider = _FakeTelephonyProvider()
    client, Session = _client(db_engine, provider)
    _, campaign_id = _seed_lead_and_campaign(Session)

    response = client.post(
        "/api/voice/outbound-calls", json={"lead_id": str(uuid.uuid4()), "campaign_id": str(campaign_id)}
    )

    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_initiate_outbound_call_returns_502_on_a_provider_failure(db_engine):
    provider = _FakeTelephonyProvider(error=TelephonyError("simulated Twilio outage"))
    client, Session = _client(db_engine, provider)
    lead_id, campaign_id = _seed_lead_and_campaign(Session)

    response = client.post(
        "/api/voice/outbound-calls", json={"lead_id": str(lead_id), "campaign_id": str(campaign_id)}
    )

    assert response.status_code == 502

    app.dependency_overrides.clear()


def test_twiml_stub_webhook_returns_valid_xml():
    """No TWILIO_AUTH_TOKEN configured in this test env -
    verify_twilio_signature degrades to logging a warning and allowing the
    request through (same as every other webhook's test in this suite),
    it's the security tests below that actually exercise the guard."""
    with TestClient(app) as client:
        response = client.post("/api/voice/twiml", data={"CallSid": "CA123"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "<Hangup/>" in response.text


def test_twiml_stub_webhook_rejects_an_invalid_signature_when_configured(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "fake_auth_token")
    with TestClient(app) as client:
        response = client.post(
            "/api/voice/twiml", data={"CallSid": "CA123"}, headers={"X-Twilio-Signature": "not-a-real-signature"}
        )

    assert response.status_code == 403


def test_twiml_stub_webhook_accepts_a_valid_signature_when_configured(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "fake_auth_token")
    from api.dependencies import _compute_twilio_signature

    with TestClient(app) as client:
        url = "http://testserver/api/voice/twiml"
        signature = _compute_twilio_signature("fake_auth_token", url, {"CallSid": "CA123"})
        response = client.post(
            "/api/voice/twiml", data={"CallSid": "CA123"}, headers={"X-Twilio-Signature": signature}
        )

    assert response.status_code == 200

"""
Integration tests for the Dashboard HTTP API (api/dashboard_routes.py).

Same TestClient + dependency_overrides technique as tests/test_api.py -
SQLite in-memory DB, no real Postgres needed. No LLM provider override is
needed here: dashboard routes never call one.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from api.routes import get_db_session
from crm.activity_repository import ActivityRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from database.postgres import Base
from domain import models  # noqa: F401 - registers models on Base.metadata
from domain.enums import (
    ActivityType,
    ConversationChannel,
    ConversationState,
    LeadSource,
    LeadStatus,
)


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

    with TestClient(app) as test_client:
        test_client.session_factory = TestingSession  # type: ignore[attr-defined]
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()


def _seed_lead(client, **overrides) -> str:
    db = client.session_factory()
    repo = LeadRepository(db)
    lead = repo.create(
        source=overrides.pop("source", LeadSource.WEBSITE),
        first_name=overrides.pop("first_name", None),
        last_name=overrides.pop("last_name", None),
        email=overrides.pop("email", None),
        phone=overrides.pop("phone", None),
    )
    if overrides:
        repo.update_fields(lead, **overrides)
    db.commit()
    lead_id = str(lead.id)
    db.close()
    return lead_id


# --- GET /api/dashboard/leads ------------------------------------------------------


def test_list_leads_empty_database(client):
    response = client.get("/api/dashboard/leads")

    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_leads_returns_seeded_leads(client):
    _seed_lead(client, first_name="Jean", last_name="Dupont", email="jean@test.com")

    response = client.get("/api/dashboard/leads")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["first_name"] == "Jean"
    assert body["items"][0]["status"] == "NEW"


def test_list_leads_exposes_telegram_chat_id(client):
    _seed_lead(client, first_name="Jean", telegram_chat_id="987654321")

    response = client.get("/api/dashboard/leads")

    assert response.json()["items"][0]["telegram_chat_id"] == "987654321"


def test_list_leads_filters_by_status_query_param(client):
    _seed_lead(client, first_name="Jean")

    matching = client.get("/api/dashboard/leads", params={"status": "NEW"})
    non_matching = client.get("/api/dashboard/leads", params={"status": "QUALIFIED"})

    assert matching.json()["total"] == 1
    assert non_matching.json()["total"] == 0


def test_list_leads_invalid_status_is_a_422(client):
    response = client.get("/api/dashboard/leads", params={"status": "NOT_A_REAL_STATUS"})

    assert response.status_code == 422


def test_list_leads_respects_limit_and_offset(client):
    for i in range(3):
        _seed_lead(client, first_name=f"Lead{i}")

    response = client.get("/api/dashboard/leads", params={"limit": 2, "offset": 1})

    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 1


def test_list_leads_search_by_name(client):
    _seed_lead(client, first_name="Jean", last_name="Dupont")
    _seed_lead(client, first_name="Marie", last_name="Martin")

    response = client.get("/api/dashboard/leads", params={"search": "dupont"})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["last_name"] == "Dupont"


# --- GET /api/dashboard/leads/{id} ------------------------------------------------------


def test_get_lead_detail_not_found(client):
    import uuid

    response = client.get(f"/api/dashboard/leads/{uuid.uuid4()}")

    assert response.status_code == 404


def test_get_lead_detail_returns_lead_conversations_and_activities(client):
    lead_id = _seed_lead(client, first_name="Jean", email="jean@test.com")

    response = client.get(f"/api/dashboard/leads/{lead_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["lead"]["id"] == lead_id
    assert body["lead"]["email"] == "jean@test.com"
    assert body["conversations"] == []
    assert body["activities"] == []


# --- GET /api/dashboard/stats ------------------------------------------------------


def test_get_stats_empty_database(client):
    response = client.get("/api/dashboard/stats")

    assert response.status_code == 200
    assert response.json() == {"total_leads": 0, "by_status": {}}


def test_get_stats_counts_seeded_leads(client):
    _seed_lead(client, first_name="Jean")
    _seed_lead(client, first_name="Marie")

    response = client.get("/api/dashboard/stats")

    body = response.json()
    assert body["total_leads"] == 2
    assert body["by_status"]["NEW"] == 2


# --- GET /api/dashboard/overview ------------------------------------------------------


def test_get_overview_empty_database(client):
    response = client.get("/api/dashboard/overview")

    assert response.status_code == 200
    assert response.json() == {
        "total_leads": 0,
        "active_conversations": 0,
        "active_campaigns": 0,
        "contacted": 0,
        "qualified": 0,
        "rejected": 0,
        "human_handoff": 0,
        "conversion_rate": 0.0,
    }


def test_get_overview_reflects_seeded_leads(client):
    _seed_lead(client, first_name="New")
    _seed_lead(client, first_name="Qualified", status=LeadStatus.QUALIFIED)
    _seed_lead(client, first_name="Rejected", status=LeadStatus.REJECTED)

    response = client.get("/api/dashboard/overview")

    body = response.json()
    assert body["total_leads"] == 3
    assert body["contacted"] == 2
    assert body["qualified"] == 1
    assert body["rejected"] == 1
    assert body["conversion_rate"] == pytest.approx(100 / 3)


def test_dashboard_overview_requires_api_key_once_configured(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")

    unauthenticated = client.get("/api/dashboard/overview")
    assert unauthenticated.status_code == 401

    authenticated = client.get("/api/dashboard/overview", headers={"X-API-Key": "s3cret"})
    assert authenticated.status_code == 200


# --- dashboard static UI is actually mounted ------------------------------------------------------


def test_dashboard_static_ui_is_served():
    with TestClient(app) as test_client:
        response = test_client.get("/dashboard/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# --- security: dashboard endpoints require an API key once one is configured --------------


def test_dashboard_stats_requires_api_key_once_configured(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")

    unauthenticated = client.get("/api/dashboard/stats")
    assert unauthenticated.status_code == 401

    authenticated = client.get("/api/dashboard/stats", headers={"X-API-Key": "s3cret"})
    assert authenticated.status_code == 200


def test_dashboard_leads_list_requires_api_key_once_configured(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")

    unauthenticated = client.get("/api/dashboard/leads")
    assert unauthenticated.status_code == 401

    authenticated = client.get("/api/dashboard/leads", headers={"X-API-Key": "s3cret"})
    assert authenticated.status_code == 200


def test_dashboard_lead_detail_requires_api_key_once_configured(client, monkeypatch):
    lead_id = _seed_lead(client, first_name="Jean")
    monkeypatch.setenv("API_KEY", "s3cret")

    unauthenticated = client.get(f"/api/dashboard/leads/{lead_id}")
    assert unauthenticated.status_code == 401

    authenticated = client.get(f"/api/dashboard/leads/{lead_id}", headers={"X-API-Key": "s3cret"})
    assert authenticated.status_code == 200


def test_dashboard_leaks_no_pii_without_api_key_when_key_is_unset_is_a_known_gap(client):
    """Documents the honest default rather than hiding it: without API_KEY
    configured at all, dashboard endpoints run unauthenticated (see
    api/dependencies.py's require_api_key docstring). This test exists so
    that if that default ever silently changes to "deny", someone notices
    and updates this test deliberately instead of the gap reappearing
    unnoticed."""
    _seed_lead(client, first_name="Jean", email="jean@test.com")

    response = client.get("/api/dashboard/leads")

    assert response.status_code == 200
    assert response.json()["items"][0]["email"] == "jean@test.com"


# --- GET /api/dashboard/handoffs (P04, Handoff Queue) ------------------------------------


def test_list_handoffs_empty_database(client):
    response = client.get("/api/dashboard/handoffs")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_handoffs_returns_lead_waiting_on_a_human(client):
    lead_id = _seed_lead(client, first_name="Jean", phone="+33600000000")

    db = client.session_factory()
    conversation_repo = ConversationRepository(db)
    conversation = conversation_repo.create(lead_id=lead_id, channel=ConversationChannel.WHATSAPP)
    conversation_repo.transition_state(conversation, ConversationState.HANDOFF)
    ActivityRepository(db).log(lead_id, ActivityType.STATE_CHANGED, details="QUALIFIED -> HANDOFF")
    db.commit()
    db.close()

    response = client.get("/api/dashboard/handoffs")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    entry = body["items"][0]
    assert entry["lead"]["id"] == lead_id
    assert entry["lead"]["phone"] == "+33600000000"
    assert entry["channel"] == "WHATSAPP"
    assert entry["reason"] == "Qualified — ready for appointment"


def test_list_handoffs_excludes_leads_not_in_handoff_state(client):
    _seed_lead(client, first_name="Jean")  # never enters a conversation

    response = client.get("/api/dashboard/handoffs")

    assert response.json()["total"] == 0


def test_dashboard_handoffs_requires_api_key_once_configured(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")

    unauthenticated = client.get("/api/dashboard/handoffs")
    assert unauthenticated.status_code == 401

    authenticated = client.get("/api/dashboard/handoffs", headers={"X-API-Key": "s3cret"})
    assert authenticated.status_code == 200


# --- GET /api/dashboard/activities (Activity Timeline) -----------------------------


def test_list_activities_empty_database(client):
    response = client.get("/api/dashboard/activities")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_list_activities_returns_most_recent_first_with_lead_name(client):
    lead_id = _seed_lead(client, first_name="Jean", last_name="Dupont")

    db = client.session_factory()
    activity_repo = ActivityRepository(db)
    activity_repo.log(lead_id, ActivityType.LEAD_IMPORTED, details="CSV import")
    activity_repo.log(lead_id, ActivityType.QUALIFIED, details=None)
    db.commit()
    db.close()

    response = client.get("/api/dashboard/activities")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    # Most recent (QUALIFIED, logged second) comes first.
    assert items[0]["type"] == "QUALIFIED"
    assert items[0]["lead_id"] == lead_id
    assert items[0]["lead_name"] == "Jean Dupont"
    assert items[1]["type"] == "LEAD_IMPORTED"
    assert items[1]["details"] == "CSV import"


def test_list_activities_respects_limit(client):
    lead_id = _seed_lead(client, first_name="Jean")

    db = client.session_factory()
    activity_repo = ActivityRepository(db)
    for _ in range(3):
        activity_repo.log(lead_id, ActivityType.STATUS_CHANGED, details=None)
    db.commit()
    db.close()

    response = client.get("/api/dashboard/activities", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


def test_dashboard_activities_requires_api_key_once_configured(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")

    unauthenticated = client.get("/api/dashboard/activities")
    assert unauthenticated.status_code == 401

    authenticated = client.get("/api/dashboard/activities", headers={"X-API-Key": "s3cret"})
    assert authenticated.status_code == 200

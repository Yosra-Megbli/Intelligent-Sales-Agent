"""
Integration tests for api/leads_routes.py.

Same TestClient + dependency_overrides technique as tests/test_dashboard_routes.py.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from api.routes import get_db_session
from crm.lead_repository import LeadRepository
from database.postgres import Base
from domain import models  # noqa: F401 - registers models on Base.metadata
from domain.enums import LeadSource


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


CSV_HEADER = "name,phone,email,region,source,provider,notes"


def test_import_preview_does_not_persist(client):
    csv_text = f"{CSV_HEADER}\nKarim Test,0470111222,karim@test.com,Wallonie,,,"
    res = client.post("/api/leads/import/preview", json={"csv_text": csv_text})

    assert res.status_code == 200
    body = res.json()
    assert body["total_rows"] == 1
    assert body["rows"][0]["would_be_duplicate"] is False

    list_res = client.get("/api/dashboard/leads")
    assert list_res.json()["total"] == 0


def test_import_creates_leads_and_returns_report(client):
    csv_text = f"{CSV_HEADER}\nKarim Test,0470111222,karim@test.com,Wallonie,,MetaAds,Une note"
    res = client.post("/api/leads/import", json={"csv_text": csv_text})

    assert res.status_code == 201
    body = res.json()
    assert body["rows_read"] == 1
    assert body["created"] == 1
    assert body["duplicates"] == 0
    assert body["errors"] == 0

    list_res = client.get("/api/dashboard/leads")
    assert list_res.json()["total"] == 1


def test_import_does_not_duplicate_an_existing_lead(client):
    db = client.session_factory()
    LeadRepository(db).create(source=LeadSource.WEBSITE, email="jean@test.com")
    db.commit()

    csv_text = f"{CSV_HEADER}\nJean Dupont,,jean@test.com,Bruxelles,,,"
    res = client.post("/api/leads/import", json={"csv_text": csv_text})

    assert res.status_code == 201
    body = res.json()
    assert body["created"] == 0
    assert body["duplicates"] == 1

    list_res = client.get("/api/dashboard/leads")
    assert list_res.json()["total"] == 1


def test_get_lead_detail_via_leads_router(client):
    db = client.session_factory()
    lead = LeadRepository(db).create(source=LeadSource.WEBSITE, email="jean@test.com")
    db.commit()
    lead_id = str(lead.id)

    res = client.get(f"/api/leads/{lead_id}")

    assert res.status_code == 200
    assert res.json()["lead"]["email"] == "jean@test.com"


def test_get_lead_detail_404_when_missing(client):
    res = client.get("/api/leads/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_get_lead_history_reflects_import_activity(client):
    csv_text = f"{CSV_HEADER}\nKarim Test,0470111222,karim@test.com,,,,"
    client.post("/api/leads/import", json={"csv_text": csv_text})

    list_res = client.get("/api/dashboard/leads")
    lead_id = list_res.json()["items"][0]["id"]

    res = client.get(f"/api/leads/{lead_id}/history")

    assert res.status_code == 200
    activity_types = [a["type"] for a in res.json()]
    assert "LEAD_IMPORTED" in activity_types

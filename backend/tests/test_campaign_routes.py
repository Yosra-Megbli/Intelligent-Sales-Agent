"""
Integration tests for api/campaign_routes.py's PATCH/DELETE endpoints.

Same TestClient + dependency_overrides technique as tests/test_leads_routes.py.
The other campaign_routes verbs (create/list/get/start/pause/resume) are
already covered end-to-end via application/campaign_service.py's own tests
(tests/test_campaign_service.py) - this file only adds the two new routes.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from api.routes import get_db_session
from database.postgres import Base
from domain import models  # noqa: F401 - registers models on Base.metadata


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
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()


def _create_campaign(client, **overrides) -> str:
    payload = {"name": "My campaign", **overrides}
    res = client.post("/api/campaigns", json=payload)
    assert res.status_code == 201
    return res.json()["id"]


def test_update_campaign_renames_via_route(client):
    campaign_id = _create_campaign(client)

    res = client.patch(f"/api/campaigns/{campaign_id}", json={"name": "Renamed"})

    assert res.status_code == 200
    assert res.json()["name"] == "Renamed"


def test_update_campaign_404_when_missing(client):
    res = client.patch(
        "/api/campaigns/00000000-0000-0000-0000-000000000000", json={"name": "x"}
    )
    assert res.status_code == 404


def test_update_campaign_target_rules_rejected_once_running(client):
    campaign_id = _create_campaign(client, target_rules={"region": "Wallonie"})
    client.post(f"/api/campaigns/{campaign_id}/start")

    res = client.patch(f"/api/campaigns/{campaign_id}", json={"target_rules": {"region": "Flandre"}})

    assert res.status_code == 409


def test_delete_campaign_via_route(client):
    campaign_id = _create_campaign(client)

    res = client.delete(f"/api/campaigns/{campaign_id}")

    assert res.status_code == 204
    assert client.get(f"/api/campaigns/{campaign_id}").status_code == 404


def test_delete_campaign_404_when_missing(client):
    res = client.delete("/api/campaigns/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_delete_campaign_blocked_while_running(client):
    campaign_id = _create_campaign(client)
    client.post(f"/api/campaigns/{campaign_id}/start")

    res = client.delete(f"/api/campaigns/{campaign_id}")

    assert res.status_code == 409
    assert client.get(f"/api/campaigns/{campaign_id}").status_code == 200

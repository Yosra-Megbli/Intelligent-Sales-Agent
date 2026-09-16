"""
Integration tests for api/knowledge_routes.py.

Same TestClient + dependency_overrides technique as tests/test_leads_routes.py.
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


def _payload(**overrides):
    payload = {
        "category": "faq",
        "question": "Comment changer de fournisseur ?",
        "keywords": ["changer", "comment"],
        "answer_fr": "Le changement se fait en ligne.",
    }
    payload.update(overrides)
    return payload


def test_create_entry_via_route(client):
    res = client.post("/api/knowledge", json=_payload())

    assert res.status_code == 201
    body = res.json()
    assert body["question"] == "Comment changer de fournisseur ?"
    assert body["keywords"] == ["changer", "comment"]
    assert body["active"] is True


def test_list_entries_via_route(client):
    client.post("/api/knowledge", json=_payload())
    client.post("/api/knowledge", json=_payload(question="Autre question"))

    res = client.get("/api/knowledge")

    assert res.status_code == 200
    assert res.json()["total"] == 2


def test_get_entry_404_when_missing(client):
    res = client.get("/api/knowledge/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_update_entry_via_route(client):
    entry_id = client.post("/api/knowledge", json=_payload()).json()["id"]

    res = client.put(f"/api/knowledge/{entry_id}", json={"answer_fr": "Nouvelle reponse"})

    assert res.status_code == 200
    assert res.json()["answer_fr"] == "Nouvelle reponse"


def test_toggle_active_flips_the_flag(client):
    entry_id = client.post("/api/knowledge", json=_payload()).json()["id"]
    assert client.get(f"/api/knowledge/{entry_id}").json()["active"] is True

    res = client.post(f"/api/knowledge/{entry_id}/toggle-active")

    assert res.status_code == 200
    assert res.json()["active"] is False


def test_delete_entry_via_route(client):
    entry_id = client.post("/api/knowledge", json=_payload()).json()["id"]

    res = client.delete(f"/api/knowledge/{entry_id}")

    assert res.status_code == 204
    assert client.get(f"/api/knowledge/{entry_id}").status_code == 404


def test_knowledge_routes_require_api_key_once_configured(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")

    unauthenticated = client.get("/api/knowledge")
    assert unauthenticated.status_code == 401

    authenticated = client.get("/api/knowledge", headers={"X-API-Key": "s3cret"})
    assert authenticated.status_code == 200

"""
Tests for RAG v2 Admin API (Phase 4):
- GET /api/knowledge/documents
- POST /api/knowledge/documents/upload
- POST /api/knowledge/documents/{id}/publish
- POST /api/knowledge/documents/{id}/archive
- POST /api/knowledge/documents/{id}/unpublish
- GET /api/knowledge/stats
- POST /api/knowledge/test
"""

import io
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ai.providers.embeddings.interface import EmbeddingAuthenticationError, EmbeddingProvider
from api.dependencies import get_embedding_provider
from api.main import app
from api.routes import get_db_session
from database.postgres import Base
from domain.enums import KnowledgeDocumentStatus
from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument


class FakeEmbeddingProvider(EmbeddingProvider):
    @property
    def dimensions(self) -> int:
        return 768

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Return deterministic fake 768-dim embeddings
        return [[0.1] * 768 for _ in texts]


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

    fake_provider = FakeEmbeddingProvider()
    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_embedding_provider] = lambda: fake_provider

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


AUTH_HEADERS = {"X-API-Key": "test-key"}


def test_list_documents_empty(client):
    res = client.get("/api/knowledge/documents", headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert res.json() == []


def test_upload_document_invalid_extension(client):
    file_content = b"not a pdf content"
    files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
    res = client.post("/api/knowledge/documents/upload", files=files, headers=AUTH_HEADERS)
    assert res.status_code == 422
    data = res.json()
    assert data["detail"]["code"] == "invalid_format"


def test_upload_document_empty_file(client):
    files = {"file": ("test.pdf", io.BytesIO(b""), "application/pdf")}
    res = client.post("/api/knowledge/documents/upload", files=files, headers=AUTH_HEADERS)
    assert res.status_code == 422
    data = res.json()
    assert data["detail"]["code"] == "empty_file"


def test_upload_document_success(client, monkeypatch):
    monkeypatch.setattr(
        "rag_v2.ingestion.extract_pdf_text",
        lambda path: "Tarif Flexy Electricite Wallonie 2026. Frais fixes 60 euros.",
    )
    fake_pdf = b"%PDF-1.4 simulated pdf data"
    files = {"file": ("flexy.pdf", io.BytesIO(fake_pdf), "application/pdf")}
    data = {"title": "Flexy Wallonie", "source_type": "tariff_card", "language": "fr"}

    res = client.post("/api/knowledge/documents/upload", files=files, data=data, headers=AUTH_HEADERS)
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "draft"
    assert payload["chunks_created"] >= 1
    assert "document_id" in payload

    # List documents now includes this document
    list_res = client.get("/api/knowledge/documents", headers=AUTH_HEADERS)
    assert list_res.status_code == 200
    docs = list_res.json()
    assert len(docs) == 1
    assert docs[0]["id"] == payload["document_id"]
    assert docs[0]["title"] == "Flexy Wallonie"
    assert docs[0]["status"] == "draft"
    assert docs[0]["chunk_count"] >= 1


def test_upload_document_provider_error(client, monkeypatch):
    class FailingProvider(EmbeddingProvider):
        @property
        def dimensions(self) -> int:
            return 768

        def embed(self, texts: list[str]) -> list[list[float]]:
            raise EmbeddingAuthenticationError("Invalid API key")

    app.dependency_overrides[get_embedding_provider] = lambda: FailingProvider()
    monkeypatch.setattr("rag_v2.ingestion.extract_pdf_text", lambda path: "Some extracted text.")

    files = {"file": ("terms.pdf", io.BytesIO(b"%PDF simulated"), "application/pdf")}
    res = client.post("/api/knowledge/documents/upload", files=files, headers=AUTH_HEADERS)
    assert res.status_code == 503
    err = res.json()["detail"]
    assert err["code"] == "provider_unavailable"
    assert err["retryable"] is True


def test_publish_archive_unpublish_lifecycle(client, db_session):
    doc = KnowledgeDocument(
        id=uuid4(),
        title="Test Document",
        source_type="faq",
        filename="test.pdf",
        language="fr",
        status=KnowledgeDocumentStatus.DRAFT,
        version=1,
    )
    db_session.add(doc)
    db_session.commit()

    # Publish
    pub_res = client.post(f"/api/knowledge/documents/{doc.id}/publish", headers=AUTH_HEADERS)
    assert pub_res.status_code == 200
    assert pub_res.json()["status"] == "published"
    assert pub_res.json()["published_at"] is not None

    # Archive
    arch_res = client.post(f"/api/knowledge/documents/{doc.id}/archive", headers=AUTH_HEADERS)
    assert arch_res.status_code == 200
    assert arch_res.json()["status"] == "archived"

    # Unpublish (back to draft)
    unpub_res = client.post(f"/api/knowledge/documents/{doc.id}/unpublish", headers=AUTH_HEADERS)
    assert unpub_res.status_code == 200
    assert unpub_res.json()["status"] == "draft"

    # Not found case
    missing_id = uuid4()
    assert client.post(f"/api/knowledge/documents/{missing_id}/publish", headers=AUTH_HEADERS).status_code == 404


def test_stats_endpoint(client, db_session):
    doc = KnowledgeDocument(
        id=uuid4(),
        title="Published Doc",
        source_type="tariff_card",
        filename="pub.pdf",
        language="fr",
        status=KnowledgeDocumentStatus.PUBLISHED,
        version=1,
    )
    db_session.add(doc)
    db_session.flush()

    chunk = KnowledgeChunk(
        id=uuid4(),
        document_id=doc.id,
        chunk_index=0,
        content="Chunk content test",
        embedding=[0.1] * 768,
    )
    db_session.add(chunk)
    db_session.commit()

    res = client.get("/api/knowledge/stats", headers=AUTH_HEADERS)
    assert res.status_code == 200
    stats = res.json()
    assert stats["documents_by_status"]["published"] == 1
    assert stats["total_chunks"] == 1
    assert stats["chunks_by_language"].get("fr") == 1
    assert stats["estimated_embedding_cost_eur"] >= 0
    assert "obsolescence_summary" in stats


def test_test_retrieval_endpoint(client, db_session):
    doc = KnowledgeDocument(
        id=uuid4(),
        title="Tarif Flexy",
        source_type="tariff_card",
        filename="flexy.pdf",
        language="fr",
        status=KnowledgeDocumentStatus.PUBLISHED,
        version=1,
    )
    db_session.add(doc)
    db_session.flush()

    chunk = KnowledgeChunk(
        id=uuid4(),
        document_id=doc.id,
        chunk_index=0,
        content="Tarif Flexy pour l'electricite en Wallonie avec redevance fixe de 60 euros.",
        embedding=[0.1] * 768,
    )
    db_session.add(chunk)
    db_session.commit()

    payload = {"query": "Quel est le prix du tarif flexy ?", "language": "fr"}
    res = client.post("/api/knowledge/test", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "chunks" in data
    assert len(data["chunks"]) == 1
    assert data["would_refuse"] is False
    assert data["chunks"][0]["document_title"] == "Tarif Flexy"
    assert data["chunks"][0]["score"] > 0
    assert "60 euros" in data["chunks"][0]["content_preview"]

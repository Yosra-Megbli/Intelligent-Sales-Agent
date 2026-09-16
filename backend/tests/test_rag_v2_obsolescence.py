"""
Tests for RAG v2 Phase 3: Obsolescence (ZEN W3 pattern).
"""

from datetime import date, timedelta
import uuid

import pytest

from ai.providers.embeddings.interface import EmbeddingProvider
from domain.enums import KnowledgeDocumentStatus
from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument
from rag_v2.obsolescence import (
    auto_archive_expired,
    detect_version_conflict,
    get_obsolescence_status,
    review_due_documents,
    run_obsolescence_cycle,
)
from rag_v2.retrieval import retrieve


class FakeEmbeddingProvider(EmbeddingProvider):
    @property
    def dimensions(self) -> int:
        return 2

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def _create_doc(db_session, *, title="Tarifs", status=KnowledgeDocumentStatus.PUBLISHED, review_date=None, version=1):
    doc = KnowledgeDocument(
        id=uuid.uuid4(),
        title=title,
        source_type="tariff_card",
        filename="test.pdf",
        language="fr",
        status=status,
        version=version,
        review_date=review_date,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


def test_review_due_documents_flags_upcoming_reviews(db_session):
    today = date.today()
    doc_due_soon = _create_doc(db_session, title="Due Soon", review_date=today + timedelta(days=3))
    doc_far_away = _create_doc(db_session, title="Far Away", review_date=today + timedelta(days=20))
    doc_draft = _create_doc(
        db_session, title="Draft Due", status=KnowledgeDocumentStatus.DRAFT, review_date=today + timedelta(days=2)
    )

    due = review_due_documents(db_session, within_days=7)
    due_ids = [d.id for d in due]

    assert doc_due_soon.id in due_ids
    assert doc_far_away.id not in due_ids
    assert doc_draft.id not in due_ids  # only PUBLISHED docs


def test_grace_expiry_auto_archives_and_is_idempotent(db_session):
    today = date.today()
    doc_expired = _create_doc(db_session, title="Expired", review_date=today - timedelta(days=35))
    doc_recent = _create_doc(db_session, title="Recent", review_date=today - timedelta(days=10))

    # Grace period 30 days
    archived_first = auto_archive_expired(db_session, grace_days=30)
    assert len(archived_first) == 1
    assert archived_first[0].id == doc_expired.id
    assert doc_expired.status == KnowledgeDocumentStatus.ARCHIVED
    assert doc_recent.status == KnowledgeDocumentStatus.PUBLISHED

    # Second call is a no-op (idempotent)
    archived_second = auto_archive_expired(db_session, grace_days=30)
    assert archived_second == []


def test_archived_docs_leave_retrieval_after_auto_archive(db_session):
    today = date.today()
    doc = _create_doc(db_session, title="Tarif Expire", review_date=today - timedelta(days=40))
    chunk = KnowledgeChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=0,
        content="Tarif de 50 euros.",
        embedding=[1.0, 0.0],
    )
    db_session.add(chunk)
    db_session.commit()

    provider = FakeEmbeddingProvider()
    # Before auto-archive: document is published, so it's retrievable
    matches_before = retrieve(db_session, "tarif", embedding_provider=provider)
    assert len(matches_before) == 1

    # Auto-archive
    auto_archive_expired(db_session, grace_days=30)
    assert doc.status == KnowledgeDocumentStatus.ARCHIVED

    # After auto-archive: document is archived, retrieval returns nothing
    matches_after = retrieve(db_session, "tarif", embedding_provider=provider)
    assert matches_after == []


def test_detect_version_conflict_warns_on_duplicate_products(db_session):
    doc1 = _create_doc(db_session, title="Flexy v1", version=1)
    chunk1 = KnowledgeChunk(
        id=uuid.uuid4(), document_id=doc1.id, chunk_index=0, content="c1", embedding=[1.0, 0.0]
    )
    chunk1.set_metadata({"product": "flexy"})
    db_session.add(chunk1)

    doc2 = _create_doc(db_session, title="Flexy v2", version=2)
    chunk2 = KnowledgeChunk(
        id=uuid.uuid4(), document_id=doc2.id, chunk_index=0, content="c2", embedding=[1.0, 0.0]
    )
    chunk2.set_metadata({"product": "flexy"})
    db_session.add(chunk2)
    db_session.commit()

    conflicts = detect_version_conflict(db_session, product_key="flexy")
    assert len(conflicts) == 1
    assert conflicts[0]["product"] == "flexy"
    conflicting_ids = [d["id"] for d in conflicts[0]["conflicting_documents"]]
    assert str(doc1.id) in conflicting_ids
    assert str(doc2.id) in conflicting_ids

    # No conflict for an unshared product
    assert detect_version_conflict(db_session, product_key="motion") == []


def test_get_obsolescence_status(db_session):
    today = date.today()
    _create_doc(db_session, title="Due Soon", review_date=today + timedelta(days=2))
    _create_doc(db_session, title="Overdue", review_date=today - timedelta(days=5))

    status = get_obsolescence_status(db_session)
    assert len(status["due_soon"]) >= 1
    assert len(status["overdue"]) >= 1
    assert "archived_count" in status


def test_run_obsolescence_cycle_summary(db_session):
    today = date.today()
    _create_doc(db_session, title="To Archive", review_date=today - timedelta(days=45))

    result = run_obsolescence_cycle(db_session, grace_days=30)
    assert result["archived_now_count"] == 1
    assert "due_soon_count" in result
    assert "overdue_count" in result


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from api.main import app
    from api.routes import get_db_session
    from database.postgres import Base
    from domain import models  # noqa: F401

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


def test_obsolescence_api_endpoint(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    response = client.get("/api/knowledge/obsolescence")
    assert response.status_code == 200
    data = response.json()
    assert "due_soon" in data
    assert "overdue" in data
    assert "archived_count" in data

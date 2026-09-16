"""
Tests for rag_v2/documents.py - the publish-explicit lifecycle.

This is the actual proof for the Phase 1 acceptance criterion: a draft
chunk is never retrievable, only publish_document() makes it so.
"""

import uuid

import pytest

from domain.enums import KnowledgeDocumentStatus
from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument
from rag_v2.documents import (
    KnowledgeDocumentNotFoundError,
    archive_document,
    list_published_chunks,
    publish_document,
)


def _make_document(db_session, *, status=KnowledgeDocumentStatus.DRAFT, language="fr", chunks=1):
    document = KnowledgeDocument(
        id=uuid.uuid4(),
        title="Test doc",
        source_type="tariff_card",
        filename="test.pdf",
        language=language,
        status=status,
        version=1,
    )
    db_session.add(document)
    db_session.flush()
    for i in range(chunks):
        chunk = KnowledgeChunk(
            id=uuid.uuid4(),
            document_id=document.id,
            chunk_index=i,
            content=f"chunk {i} content",
        )
        db_session.add(chunk)
    db_session.flush()
    return document


def test_a_fresh_draft_documents_chunks_are_never_returned(db_session):
    document = _make_document(db_session, status=KnowledgeDocumentStatus.DRAFT, chunks=3)

    assert list_published_chunks(db_session) == []
    assert document.status == KnowledgeDocumentStatus.DRAFT  # ingestion never auto-publishes


def test_publishing_makes_its_chunks_retrievable(db_session):
    document = _make_document(db_session, status=KnowledgeDocumentStatus.DRAFT, chunks=3)

    publish_document(db_session, document.id)

    chunks = list_published_chunks(db_session)
    assert len(chunks) == 3
    assert all(c.document_id == document.id for c in chunks)


def test_publish_document_sets_published_at(db_session):
    document = _make_document(db_session)
    assert document.published_at is None

    published = publish_document(db_session, document.id)

    assert published.status == KnowledgeDocumentStatus.PUBLISHED
    assert published.published_at is not None


def test_archiving_a_published_document_removes_its_chunks_from_retrieval(db_session):
    document = _make_document(db_session, chunks=2)
    publish_document(db_session, document.id)
    assert len(list_published_chunks(db_session)) == 2

    archive_document(db_session, document.id)

    assert list_published_chunks(db_session) == []


def test_archived_document_row_and_chunks_are_not_deleted(db_session):
    document = _make_document(db_session, chunks=2)
    publish_document(db_session, document.id)
    archive_document(db_session, document.id)

    still_there = db_session.get(KnowledgeDocument, document.id)
    assert still_there is not None
    assert still_there.status == KnowledgeDocumentStatus.ARCHIVED
    assert db_session.query(KnowledgeChunk).filter_by(document_id=document.id).count() == 2


def test_list_published_chunks_filters_by_language(db_session):
    fr_doc = _make_document(db_session, language="fr", chunks=1)
    nl_doc = _make_document(db_session, language="nl", chunks=1)
    publish_document(db_session, fr_doc.id)
    publish_document(db_session, nl_doc.id)

    fr_chunks = list_published_chunks(db_session, language="fr")

    assert len(fr_chunks) == 1
    assert fr_chunks[0].document_id == fr_doc.id


def test_publish_document_404_when_missing(db_session):
    with pytest.raises(KnowledgeDocumentNotFoundError):
        publish_document(db_session, uuid.uuid4())


def test_archive_document_404_when_missing(db_session):
    with pytest.raises(KnowledgeDocumentNotFoundError):
        archive_document(db_session, uuid.uuid4())


def test_two_documents_one_draft_one_published_only_the_published_ones_chunks_appear(db_session):
    draft = _make_document(db_session, status=KnowledgeDocumentStatus.DRAFT, chunks=2)
    published = _make_document(db_session, status=KnowledgeDocumentStatus.DRAFT, chunks=2)
    publish_document(db_session, published.id)

    chunks = list_published_chunks(db_session)

    document_ids = {c.document_id for c in chunks}
    assert document_ids == {published.id}
    assert draft.id not in document_ids

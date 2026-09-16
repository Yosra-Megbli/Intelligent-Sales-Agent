"""
Publish-explicit document lifecycle - RAG v2 Phase 1 (docs/RAG_BACKLOG.md,
ZEN Knowledge pattern).

Ingesting a document (rag_v2/ingestion.py) never publishes it - a
KnowledgeDocument always starts DRAFT. `publish_document` is the one and
only action that makes a document's chunks retrievable;
`list_published_chunks` is the one and only read path Phase 2's real
similarity-search retrieval will layer on top of, and it is the
enforcement point for that rule: a DRAFT or ARCHIVED document's chunks
never come back from it, full stop, no matter how a caller got here.

No admin API/UI wraps these yet (that is Phase 4, not built) - these are
plain functions a script or a future route can call directly.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from domain.enums import KnowledgeDocumentStatus
from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument


class KnowledgeDocumentNotFoundError(Exception):
    pass


def _require_document(db_session, document_id: UUID) -> KnowledgeDocument:
    document = db_session.get(KnowledgeDocument, document_id)
    if document is None:
        raise KnowledgeDocumentNotFoundError(f"KnowledgeDocument {document_id} not found")
    return document


def publish_document(db_session, document_id: UUID) -> KnowledgeDocument:
    document = _require_document(db_session, document_id)
    document.status = KnowledgeDocumentStatus.PUBLISHED
    document.published_at = datetime.utcnow()
    db_session.commit()
    return document


def archive_document(db_session, document_id: UUID) -> KnowledgeDocument:
    """Withdraws a document from retrieval (superseded version, expired
    review) without deleting it - the row and its chunks stay for audit,
    they just stop matching list_published_chunks."""
    document = _require_document(db_session, document_id)
    document.status = KnowledgeDocumentStatus.ARCHIVED
    db_session.commit()
    return document


def list_published_chunks(db_session, *, language: str | None = None) -> list[KnowledgeChunk]:
    """The one enforcement point for publish-explicit: a chunk is only
    ever returned here if its parent document is PUBLISHED. DRAFT and
    ARCHIVED are excluded by the same join condition, not two rules."""
    stmt = (
        select(KnowledgeChunk)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeDocument.status == KnowledgeDocumentStatus.PUBLISHED)
    )
    if language:
        stmt = stmt.where(KnowledgeDocument.language == language)
    return list(db_session.scalars(stmt).all())

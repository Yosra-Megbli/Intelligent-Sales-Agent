"""
Knowledge Entries & Documents Service (Application layer, Sprint 4b & RAG v2 Phase 4).

Same layering discipline as application/lead_service.py and
application/campaign_service.py: api/knowledge_routes.py never touches
crm/knowledge_repository.py or database models directly, only this service.
This module never imports ai/rag.py, ai/extractor.py, ai/responder.py or
conversation_engine/* (enforced by tests/test_architecture_boundaries.py).
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select

from ai.providers.embeddings.google import GoogleEmbeddingProvider
from ai.providers.embeddings.interface import EmbeddingError, EmbeddingProvider
from crm.knowledge_repository import KnowledgeRepository
from domain.enums import KnowledgeDocumentStatus
from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument
from domain.models.knowledge_entry import KnowledgeEntry
from rag_v2.documents import (
    KnowledgeDocumentNotFoundError,
    archive_document as _archive_doc,
    publish_document as _publish_doc,
    unpublish_document as _unpublish_doc,
)
from rag_v2.ingestion import IngestionError, ingest_document
from rag_v2.obsolescence import get_obsolescence_status as _get_obsolescence_status
from rag_v2.retrieval import ScoredChunk, retrieve_relevant_chunks

# Pricing truth / cost estimation constants for RAG v2
AVG_TOKENS_PER_CHUNK = 500
EMBEDDING_COST_PER_1K_TOKENS_EUR = 0.00002


class KnowledgeEntryNotFoundError(Exception):
    pass


class InvalidPdfError(Exception):
    def __init__(self, message: str, code: str = "no_text_layer"):
        super().__init__(message)
        self.code = code


class EmbeddingUnavailableError(Exception):
    def __init__(self, message: str, code: str = "provider_unavailable", retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class KnowledgeService:
    def __init__(self, db_session):
        self.db = db_session
        self.repo = KnowledgeRepository(db_session)

    # ── Keyword RAG v1 Entry CRUD ──────────────────────────────────────────

    def list_entries(self, *, limit: int = 200, offset: int = 0) -> tuple[list[KnowledgeEntry], int]:
        return self.repo.list_all(limit=limit, offset=offset)

    def get_entry(self, entry_id: UUID) -> KnowledgeEntry:
        entry = self.repo.get_by_id(entry_id)
        if entry is None:
            raise KnowledgeEntryNotFoundError(f"KnowledgeEntry {entry_id} not found")
        return entry

    def create_entry(self, **fields) -> KnowledgeEntry:
        entry = self.repo.create(**fields)
        self.db.commit()
        return entry

    def update_entry(self, entry_id: UUID, **fields) -> KnowledgeEntry:
        entry = self.get_entry(entry_id)
        self.repo.update_fields(entry, **fields)
        self.db.commit()
        return entry

    def toggle_active(self, entry_id: UUID) -> KnowledgeEntry:
        entry = self.get_entry(entry_id)
        self.repo.update_fields(entry, active=not entry.active)
        self.db.commit()
        return entry

    def delete_entry(self, entry_id: UUID) -> None:
        entry = self.get_entry(entry_id)
        self.repo.delete(entry)
        self.db.commit()

    # ── RAG v2 Document Lifecycle & Admin (Phase 4) ─────────────────────────

    def list_documents(self) -> list[dict[str, Any]]:
        stmt = (
            select(
                KnowledgeDocument,
                func.count(KnowledgeChunk.id).label("chunk_count"),
            )
            .outerjoin(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .group_by(KnowledgeDocument.id)
            .order_by(KnowledgeDocument.created_at.desc())
        )
        rows = self.db.execute(stmt).all()
        result = []
        for doc, chunk_count in rows:
            status_str = (doc.status.value if hasattr(doc.status, "value") else str(doc.status)).lower()
            result.append(
                {
                    "id": doc.id,
                    "title": doc.title,
                    "source_type": doc.source_type,
                    "language": doc.language,
                    "status": status_str,
                    "version": doc.version,
                    "review_date": doc.review_date,
                    "chunk_count": chunk_count,
                    "created_at": doc.created_at,
                    "published_at": doc.published_at,
                }
            )
        return result

    def get_document(self, document_id: UUID) -> dict[str, Any]:
        stmt = (
            select(
                KnowledgeDocument,
                func.count(KnowledgeChunk.id).label("chunk_count"),
            )
            .outerjoin(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.id == document_id)
            .group_by(KnowledgeDocument.id)
        )
        row = self.db.execute(stmt).first()
        if not row:
            raise KnowledgeDocumentNotFoundError(f"KnowledgeDocument {document_id} not found")
        doc, chunk_count = row
        status_str = (doc.status.value if hasattr(doc.status, "value") else str(doc.status)).lower()
        return {
            "id": doc.id,
            "title": doc.title,
            "source_type": doc.source_type,
            "language": doc.language,
            "status": status_str,
            "version": doc.version,
            "review_date": doc.review_date,
            "chunk_count": chunk_count,
            "created_at": doc.created_at,
            "published_at": doc.published_at,
        }

    def publish_document(self, document_id: UUID) -> dict[str, Any]:
        _publish_doc(self.db, document_id)
        return self.get_document(document_id)

    def archive_document(self, document_id: UUID) -> dict[str, Any]:
        _archive_doc(self.db, document_id)
        return self.get_document(document_id)

    def unpublish_document(self, document_id: UUID) -> dict[str, Any]:
        _unpublish_doc(self.db, document_id)
        return self.get_document(document_id)

    def upload_document(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        title: Optional[str] = None,
        source_type: str = "tariff_card",
        language: str = "fr",
        review_date: Optional[date] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> dict[str, Any]:
        if embedding_provider is None:
            try:
                embedding_provider = GoogleEmbeddingProvider()
            except EmbeddingError as exc:
                raise EmbeddingUnavailableError(
                    f"Embedding provider unavailable: {exc}",
                    code="provider_unavailable",
                    retryable=True,
                )

        doc_title = title.strip() if title and title.strip() else os.path.splitext(filename)[0]

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name

        try:
            res = ingest_document(
                self.db,
                file_path=tmp_path,
                title=doc_title,
                source_type=source_type,
                language=language,
                embedding_provider=embedding_provider,
                review_date=review_date,
            )
            return {
                "document_id": str(res.document.id),
                "chunks_created": res.chunks_created,
                "status": "draft",
            }
        except IngestionError as exc:
            raise InvalidPdfError(str(exc), code="no_text_layer")
        except EmbeddingError as exc:
            raise EmbeddingUnavailableError(str(exc), code="provider_unavailable", retryable=True)
        except Exception as exc:
            raise InvalidPdfError(f"Failed to process PDF: {exc}", code="corrupted_pdf")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def get_stats(self) -> dict[str, Any]:
        status_counts = {"draft": 0, "published": 0, "archived": 0}
        for status_enum, count in self.db.execute(
            select(KnowledgeDocument.status, func.count(KnowledgeDocument.id)).group_by(KnowledgeDocument.status)
        ):
            key = (status_enum.value if hasattr(status_enum, "value") else str(status_enum)).lower()
            status_counts[key] = count

        total_chunks = self.db.scalar(select(func.count(KnowledgeChunk.id))) or 0

        lang_counts: dict[str, int] = {}
        for lang, count in self.db.execute(
            select(KnowledgeDocument.language, func.count(KnowledgeChunk.id))
            .join(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .group_by(KnowledgeDocument.language)
        ):
            if lang:
                lang_counts[lang] = count

        estimated_cost_eur = round(
            (total_chunks * AVG_TOKENS_PER_CHUNK / 1000) * EMBEDDING_COST_PER_1K_TOKENS_EUR, 4
        )

        obsolescence_summary = self.get_obsolescence_status()

        return {
            "documents_by_status": status_counts,
            "total_chunks": total_chunks,
            "chunks_by_language": lang_counts,
            "estimated_embedding_cost_eur": estimated_cost_eur,
            "obsolescence_summary": obsolescence_summary,
        }

    def test_query(
        self,
        *,
        query: str,
        language: str = "fr",
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> dict[str, Any]:
        if embedding_provider is None:
            try:
                embedding_provider = GoogleEmbeddingProvider()
            except EmbeddingError:
                embedding_provider = None

        if embedding_provider is None:
            return {"chunks": [], "would_refuse": True}

        matches = retrieve_relevant_chunks(
            self.db,
            query=query,
            language=language,
            embedding_provider=embedding_provider,
        )

        chunk_results = [
            {
                "content_preview": m.chunk.content[:250] + ("..." if len(m.chunk.content) > 250 else ""),
                "score": round(m.similarity, 4),
                "document_title": m.document.title,
                "version": m.document.version,
            }
            for m in matches
        ]

        return {
            "chunks": chunk_results,
            "would_refuse": len(chunk_results) == 0,
        }

    def get_obsolescence_status(self) -> dict[str, Any]:
        return _get_obsolescence_status(self.db)

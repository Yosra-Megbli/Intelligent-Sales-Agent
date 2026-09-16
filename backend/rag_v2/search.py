"""
Cross-dialect similarity search for RAG v2.

This module provides a unified `VectorSearch` interface to allow:
1. `PgVectorSearch`: Production-grade PostgreSQL vector search using pgvector's
   cosine distance operator `<=>` and the HNSW cosine index created in migration 0011
   (`ORDER BY embedding <=> :query_vector LIMIT :top_k`).
2. `InMemoryCosineSearch`: Pure Python cosine similarity over published chunks fetched
   via `list_published_chunks_with_documents()`. Used on SQLite (where pgvector is
   unavailable, such as in the CI / pytest test suite) or when dialect != postgresql.

The `get_vector_search(db_session)` factory automatically picks the native
`PgVectorSearch` when running on PostgreSQL, and degrades cleanly to `InMemoryCosineSearch`
on SQLite / other dialects. This also serves as the seam for future index/broker changes.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy import text

from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument
from rag_v2.documents import list_published_chunks_with_documents


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorSearch(ABC):
    @abstractmethod
    def search(
        self,
        db_session,
        query_vector: list[float],
        *,
        language: Optional[str] = None,
        top_k: int = 20,
    ) -> list[tuple[KnowledgeChunk, KnowledgeDocument, float]]:
        """Search published chunks against query_vector.
        Returns a list of (chunk, document, similarity) tuples sorted descending by similarity.
        """
        pass


class InMemoryCosineSearch(VectorSearch):
    """Pure Python cosine similarity over published chunks.
    Used for SQLite testing and non-PostgreSQL dialects."""

    def search(
        self,
        db_session,
        query_vector: list[float],
        *,
        language: Optional[str] = None,
        top_k: int = 20,
    ) -> list[tuple[KnowledgeChunk, KnowledgeDocument, float]]:
        candidates = [
            (chunk, doc)
            for chunk, doc in list_published_chunks_with_documents(db_session, language=language)
            if chunk.embedding
        ]
        if not candidates:
            return []

        scored = [
            (chunk, doc, _cosine_similarity(query_vector, chunk.embedding))
            for chunk, doc in candidates
        ]
        scored.sort(key=lambda item: item[2], reverse=True)
        return scored[:top_k]


class PgVectorSearch(VectorSearch):
    """PostgreSQL-native vector search using pgvector cosine distance operator `<=>`."""

    def search(
        self,
        db_session,
        query_vector: list[float],
        *,
        language: Optional[str] = None,
        top_k: int = 20,
    ) -> list[tuple[KnowledgeChunk, KnowledgeDocument, float]]:
        query_str = "[" + ",".join(str(f) for f in query_vector) + "]"
        lang_filter = "AND d.language = :language" if language else ""
        sql = text(f"""
            SELECT c.id AS chunk_id, d.id AS doc_id,
                   (1 - (c.embedding <=> :query_vector::vector)) AS similarity
            FROM knowledge_chunks c
            JOIN knowledge_documents d ON c.document_id = d.id
            WHERE d.status = 'PUBLISHED'
              AND c.embedding IS NOT NULL
              {lang_filter}
            ORDER BY c.embedding <=> :query_vector::vector
            LIMIT :top_k
        """)
        params: dict = {"query_vector": query_str, "top_k": top_k}
        if language:
            params["language"] = language

        rows = db_session.execute(sql, params).fetchall()
        if not rows:
            return []

        chunk_ids = [r.chunk_id for r in rows]
        doc_ids = [r.doc_id for r in rows]

        chunks_by_id = {
            c.id: c
            for c in db_session.query(KnowledgeChunk).filter(KnowledgeChunk.id.in_(chunk_ids)).all()
        }
        docs_by_id = {
            d.id: d
            for d in db_session.query(KnowledgeDocument).filter(KnowledgeDocument.id.in_(doc_ids)).all()
        }

        results = []
        for r in rows:
            chunk = chunks_by_id.get(r.chunk_id)
            doc = docs_by_id.get(r.doc_id)
            if chunk and doc:
                results.append((chunk, doc, float(r.similarity)))
        return results


def get_vector_search(db_session) -> VectorSearch:
    """Factory returning PgVectorSearch when on PostgreSQL, InMemoryCosineSearch otherwise."""
    bind = getattr(db_session, "bind", None)
    if bind is None:
        try:
            bind = db_session.get_bind()
        except Exception:
            bind = None

    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect_name == "postgresql":
        return PgVectorSearch()
    return InMemoryCosineSearch()

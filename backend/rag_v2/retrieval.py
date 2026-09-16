"""
Similarity-search retrieval - RAG v2 Phase 2 (docs/RAG_BACKLOG.md).

Scoring uses `rag_v2.search.get_vector_search()`:
- On PostgreSQL: `PgVectorSearch` leveraging the native pgvector `<=>` operator and HNSW index.
- On SQLite (tests) or non-Postgres: `InMemoryCosineSearch` pure Python scoring.

Publish-explicit lifecycle is strictly enforced: only chunks belonging to
PUBLISHED documents are retrievable.

Validity filter: when chunk or document metadata contains `valid_until`,
expired content (`valid_until < today`) is excluded.

Relevance gate: chunks below `RAG_MIN_SIMILARITY` (default 0.30) are excluded.
When retrieval finds no matches, the application layer falls back to keyword RAG v1,
or finally to deterministic refusal without LLM call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import os
from typing import Optional

from ai.providers.embeddings.interface import EmbeddingProvider
from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument
from rag_v2.search import get_vector_search

RAG_MIN_SIMILARITY_DEFAULT = 0.30
RAG_TOP_K_DEFAULT = 20


def _min_similarity() -> float:
    return float(os.getenv("RAG_MIN_SIMILARITY", RAG_MIN_SIMILARITY_DEFAULT))


def _top_k() -> int:
    return int(os.getenv("RAG_TOP_K", RAG_TOP_K_DEFAULT))


@dataclass(frozen=True)
class ScoredChunk:
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    similarity: float


# Backward compatibility alias
RetrievalMatch = ScoredChunk


def _is_valid_date(val: Optional[str]) -> bool:
    if not val:
        return True
    try:
        # Handles YYYY-MM-DD or ISO strings
        exp_date = datetime.fromisoformat(str(val).split("T")[0]).date()
        return exp_date >= date.today()
    except Exception:
        return True


def retrieve_relevant_chunks(
    db_session,
    query: Optional[str],
    *,
    embedding_provider: EmbeddingProvider,
    language: Optional[str] = None,
    top_k: Optional[int] = None,
    min_similarity: Optional[float] = None,
) -> list[ScoredChunk]:
    """Embed `query`, search published chunks, filter by validity & similarity threshold."""
    if not query or not query.strip():
        return []

    limit = top_k if top_k is not None else _top_k()
    threshold = min_similarity if min_similarity is not None else _min_similarity()

    query_embeddings = embedding_provider.embed([query])
    if not query_embeddings or not query_embeddings[0]:
        return []
    query_vector = query_embeddings[0]

    searcher = get_vector_search(db_session)
    # Fetch a wider candidate pool to allow metadata filtering
    candidates = searcher.search(db_session, query_vector, language=language, top_k=limit * 2)

    results: list[ScoredChunk] = []
    for chunk, document, similarity in candidates:
        if similarity < threshold:
            continue

        # Check valid_until in chunk metadata_json
        chunk_meta = chunk.get_metadata() if hasattr(chunk, "get_metadata") else {}
        valid_until = chunk_meta.get("valid_until")
        if not _is_valid_date(valid_until):
            continue

        results.append(ScoredChunk(chunk=chunk, document=document, similarity=similarity))
        if len(results) >= limit:
            break

    return results


def retrieve(
    db_session,
    query_text: Optional[str],
    *,
    embedding_provider: EmbeddingProvider,
    language: Optional[str] = None,
    top_k: Optional[int] = None,
    min_similarity: Optional[float] = None,
) -> list[ScoredChunk]:
    """Compatibility alias for retrieve_relevant_chunks."""
    return retrieve_relevant_chunks(
        db_session,
        query_text,
        embedding_provider=embedding_provider,
        language=language,
        top_k=top_k,
        min_similarity=min_similarity,
    )

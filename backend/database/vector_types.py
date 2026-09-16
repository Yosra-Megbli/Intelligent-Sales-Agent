"""
Cross-dialect embedding vector column type - RAG v2.

Same reasoning as `database.postgres.GUID`: production runs on PostgreSQL
(Neon, with the pgvector extension), the test suite runs on SQLite
in-memory (`tests/conftest.py`'s `Base.metadata.create_all()`), and SQLite
has no vector type at all. `EmbeddingVector` stores a real pgvector
`vector(N)` column on PostgreSQL (so Phase 2's retrieval can use cosine
similarity + an HNSW index), and falls back to a JSON-encoded float array
in a TEXT column on every other dialect, so the exact same
`KnowledgeChunk` model works in both places. Tests built on SQLite can
therefore exercise storage/publish-explicit gating, but never real
similarity search - that needs a real Postgres with the pgvector
extension enabled (see `database/migrations/0011_*.sql`).
"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

try:
    from pgvector.sqlalchemy import Vector as _PgVector
except ImportError:  # pragma: no cover - exercised via the SQLite fallback in tests
    _PgVector = None  # type: ignore[assignment,misc]


class EmbeddingVector(TypeDecorator):
    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            if _PgVector is None:
                raise RuntimeError(
                    "pgvector is not installed but a PostgreSQL dialect was used - "
                    "add 'pgvector' to requirements.txt."
                )
            return dialect.type_descriptor(_PgVector(self.dimensions))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Optional[list[float]], dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value  # pgvector.sqlalchemy.Vector accepts list[float] natively
        return json.dumps(value)

    def process_result_value(self, value, dialect) -> Optional[list[float]]:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        return json.loads(value)

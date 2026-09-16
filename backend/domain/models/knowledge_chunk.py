"""
KnowledgeChunk model - RAG v2 (docs/RAG_BACKLOG.md).

One row per chunk of a `KnowledgeDocument` (deterministic ~500-token
paragraphs, 50-token overlap - see `rag_v2/chunking.py`), each with its own
embedding. `metadata_json` follows `Campaign.target_rules`'s existing
convention in this codebase (JSON-serialized into a Text column via
json.dumps/json.loads, not a dialect-specific JSON/JSONB column type) for
the same reason: one representation that behaves identically on SQLite
(tests) and PostgreSQL (production).

PUBLISH-EXPLICIT: a chunk's visibility to retrieval is entirely driven by
its parent `KnowledgeDocument.status` (see KnowledgeDocumentStatus's
docstring) - there is deliberately no separate per-chunk status. A chunk
never becomes retrievable on its own; only publishing the whole document
does.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text

from database.postgres import Base, GUID
from database.vector_types import EmbeddingVector

# text-embedding-004 (Google AI, free tier) output dimensionality - see
# docs/RAG_BACKLOG.md's settled decisions. Changing embedding provider to
# one with a different dimensionality requires a new migration (the
# pgvector column width is fixed at creation) and re-embedding every
# existing chunk - there is no in-place resize.
EMBEDDING_DIMENSIONS = 768


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID(), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)

    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(EmbeddingVector(EMBEDDING_DIMENSIONS), nullable=True)

    # JSON-serialized dict: {product, energy_type, region, valid_from,
    # valid_until, source_type, language} - denormalized from the parent
    # document at ingestion time so a retrieval-time metadata filter (e.g.
    # "language=fr AND valid_until > now") never needs a join, per
    # docs/RAG_BACKLOG.md's metadata schema.
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def get_metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json) if self.metadata_json else {}

    def set_metadata(self, value: Optional[dict[str, Any]]) -> None:
        self.metadata_json = json.dumps(value) if value else None

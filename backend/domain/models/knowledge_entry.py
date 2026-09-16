"""
KnowledgeEntry model - keyword-RAG v1 admin surface (Sprint 4b).

NOT to be confused with RAG v2's KnowledgeDocument/KnowledgeChunk
(domain/models/knowledge_document.py, knowledge_chunk.py) - this table
backs the EXISTING keyword-matching ai/rag.py, giving it a DB-editable
source of entries instead of only backend/ai/knowledge_base.yaml. RAG v2
(vector search, PDF ingestion) is a separate, later system - see
docs/RAG_BACKLOG.md.

PURITY: ai/rag.py never imports this model or touches a database (AST-
enforced by tests/test_rag.py::test_rag_module_never_touches_the_database_or_crm).
This table is read by application/conversation_service.py (the one module
allowed to import both the Engine/ai/* and a repository) and converted
into ai.rag.KnowledgeEntry tuples, which get INJECTED into a fresh
Rag(entries=...) instance - never read by ai/rag.py itself. See
crm/knowledge_repository.py and conversation_service.py's _build_rag().
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, String, Text

from database.postgres import Base, GUID


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id = Column(GUID(), primary_key=True)
    # "faq" or "objection" - matches ai.rag.KnowledgeEntry.category exactly,
    # since a DB row here becomes one of those at read time.
    category = Column(String(32), nullable=False, index=True)
    # Human-readable label for the admin table ("what is this entry about") -
    # NOT matched against customer messages; ai.rag.py matches on `keywords`.
    question = Column(String(255), nullable=False)
    # JSON-encoded list[str] - mirrors ai.rag.KnowledgeEntry.keywords (a
    # tuple), stored as JSON in a Text column, same convention as
    # domain/models/campaign.py's target_rules and knowledge_chunk.py's
    # metadata_json (one representation, works identically on SQLite and
    # PostgreSQL).
    keywords_json = Column(Text, nullable=False)
    answer_fr = Column(Text, nullable=False)
    answer_nl = Column(Text, nullable=True)
    answer_en = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def get_keywords(self) -> list[str]:
        return json.loads(self.keywords_json) if self.keywords_json else []

    def set_keywords(self, value: list[str]) -> None:
        self.keywords_json = json.dumps(value)

    def answer_for_language(self, language: str) -> str:
        """NL/EN fall back to the French answer when not filled in yet -
        never an empty string reaching ai/rag.py's Rag.answer() contract."""
        by_language: dict[str, Any] = {"fr": self.answer_fr, "nl": self.answer_nl, "en": self.answer_en}
        return by_language.get(language) or self.answer_fr

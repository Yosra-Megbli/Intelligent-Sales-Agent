"""
KnowledgeDocument model - RAG v2 (docs/RAG_BACKLOG.md).

One row per ingested source file (a tariff card PDF, a terms-and-conditions
PDF, a FAQ markdown note...). A document owns many `KnowledgeChunk` rows
(see knowledge_chunk.py). Nothing in `ai/rag.py` ever reads this table
directly - purity guarantee (test_rag.py::test_rag_module_never_touches_the_database_or_crm)
means the application layer reads published chunks and injects them into
`Rag.answer()`, exactly the same pattern the keyword-based v1 RAG already
uses for `knowledge_entries` (Sprint 4).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Enum as SAEnum, Integer, String

from database.postgres import Base, GUID
from domain.enums import KnowledgeDocumentStatus


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    title = Column(String(255), nullable=False)
    # e.g. "tariff_card", "terms", "faq", "regulatory" - source-of-truth
    # hierarchy tariff card > terms > helpdesk > regulator > marketing,
    # per docs/RAG_BACKLOG.md; not an enum yet since the hierarchy itself
    # is still evolving.
    source_type = Column(String(64), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    language = Column(String(2), nullable=False, default="fr")

    status = Column(
        SAEnum(KnowledgeDocumentStatus, name="knowledge_document_status"),
        nullable=False,
        default=KnowledgeDocumentStatus.DRAFT,
        index=True,
    )

    # Monotonically increasing per (product, energy_type, region, language)
    # identity - tariff cards are monthly, so a re-ingestion of the same
    # product/region/language is a new version, not an edit in place.
    version = Column(Integer, nullable=False, default=1)

    # Obsolescence (ZEN "W3" pattern, docs/RAG_BACKLOG.md): when this
    # document should next be reviewed. NULL = no review cadence set.
    review_date = Column(Date, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    published_at = Column(DateTime, nullable=True)

"""
Knowledge entries repository (Sprint 4b - keyword-RAG v1 admin surface).

Same discipline as every other crm/*.py repository: persistence only,
zero business logic, never imports ai/* or conversation_engine/*. The
"which entries are active" decision is a plain boolean column, not a
business rule this layer interprets - application/conversation_service.py
is where an active row becomes an ai.rag.KnowledgeEntry.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.models.knowledge_entry import KnowledgeEntry


class KnowledgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        category: str,
        question: str,
        keywords: list[str],
        answer_fr: str,
        answer_nl: Optional[str] = None,
        answer_en: Optional[str] = None,
        active: bool = True,
    ) -> KnowledgeEntry:
        entry = KnowledgeEntry(
            id=uuid.uuid4(),
            category=category,
            question=question,
            answer_fr=answer_fr,
            answer_nl=answer_nl,
            answer_en=answer_en,
            active=active,
        )
        entry.set_keywords(keywords)
        self.db.add(entry)
        self.db.flush()
        return entry

    def get_by_id(self, entry_id: uuid.UUID) -> Optional[KnowledgeEntry]:
        return self.db.get(KnowledgeEntry, entry_id)

    def list_all(self, *, limit: int = 200, offset: int = 0) -> tuple[list[KnowledgeEntry], int]:
        from sqlalchemy import func

        stmt = select(KnowledgeEntry)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = stmt.order_by(KnowledgeEntry.category, KnowledgeEntry.question).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all()), total

    def list_active(self) -> list[KnowledgeEntry]:
        """The one read path application/conversation_service.py's
        _build_rag() uses - re-queried on every call, never cached, so
        toggling `active` off takes effect on the very next message."""
        stmt = select(KnowledgeEntry).where(KnowledgeEntry.active.is_(True))
        return list(self.db.scalars(stmt).all())

    def update_fields(self, entry: KnowledgeEntry, **fields) -> KnowledgeEntry:
        keywords = fields.pop("keywords", None)
        for key, value in fields.items():
            if not hasattr(entry, key):
                raise AttributeError(f"KnowledgeEntry has no field '{key}'")
            setattr(entry, key, value)
        if keywords is not None:
            entry.set_keywords(keywords)
        self.db.flush()
        return entry

    def delete(self, entry: KnowledgeEntry) -> None:
        self.db.delete(entry)
        self.db.flush()

    def count(self) -> int:
        from sqlalchemy import func

        return self.db.scalar(select(func.count()).select_from(KnowledgeEntry)) or 0

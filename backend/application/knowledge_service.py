"""
Knowledge Entries Service (Application layer, Sprint 4b).

Same layering discipline as application/lead_service.py and
application/campaign_service.py: api/knowledge_routes.py never touches
crm/knowledge_repository.py directly, only this service. This module never
imports ai/* or conversation_engine/* - it only manages the CRUD rows;
turning an active row into something ai/rag.py's Rag can use is
application/conversation_service.py's job (the one place allowed to import
both), not this one's.
"""

from __future__ import annotations

from uuid import UUID

from crm.knowledge_repository import KnowledgeRepository
from domain.models.knowledge_entry import KnowledgeEntry


class KnowledgeEntryNotFoundError(Exception):
    pass


class KnowledgeService:
    def __init__(self, db_session):
        self.db = db_session
        self.repo = KnowledgeRepository(db_session)

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
        """Same convention as LeadService.update_lead: the caller (the
        route) is responsible for only passing fields the request actually
        included (Pydantic's model_dump(exclude_unset=True)) - this method
        applies exactly what it's given, so explicitly clearing a field to
        null is distinguishable from simply not mentioning it."""
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

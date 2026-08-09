"""
Lead Service (Application layer).

Same layering discipline as application/campaign_service.py and
application/lead_import_service.py: the HTTP layer (api/leads_routes.py)
never touches LeadRepository/ConversationRepository/ActivityRepository
directly, only this service.

Kept separate from LeadImportService: that module owns bulk CSV
create-or-merge semantics (a bad row must never abort the whole file); this
one owns single-lead write actions triggered directly from the Dashboard
(edit a field, delete a lead) - different failure model (each call either
fully succeeds or raises, no per-row report to build).

Deleting a Lead never happens as a plain DB delete: this module never
imports conversation_engine or ai/* (enforced by
tests/test_architecture_boundaries.py, same rule as every other
application/*.py service) - it only sequences repository calls in the
right order (messages -> conversations -> activities -> lead) so the
FK constraints (no ON DELETE CASCADE - see each repository's own
docstring) never get violated.
"""

from __future__ import annotations

from uuid import UUID

from crm.activity_repository import ActivityRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.models.lead import Lead

# Fields the Dashboard's "edit lead" form is allowed to change. Deliberately
# excludes status/qualification_score/rejection_reason/campaign_id and
# everything else the Business Rules Engine owns (see domain/models/lead.py's
# module docstring: "this model only stores data... all decisions are made
# by conversation_engine") - editing a lead from the Dashboard is a CRM data
# correction, never a qualification decision.
_EDITABLE_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "email",
        "phone",
        "telegram_chat_id",
        "region",
        "city",
        "current_supplier",
        "provider",
        "notes",
    }
)


class LeadNotFoundError(Exception):
    pass


class InvalidLeadFieldError(Exception):
    pass


class LeadService:
    def __init__(self, db_session):
        self.db = db_session
        self.lead_repo = LeadRepository(db_session)
        self.conversation_repo = ConversationRepository(db_session)
        self.activity_repo = ActivityRepository(db_session)

    def update_lead(self, lead_id: UUID, **fields) -> Lead:
        lead = self._require_lead(lead_id)
        unknown = set(fields) - _EDITABLE_FIELDS
        if unknown:
            raise InvalidLeadFieldError(f"Cannot edit field(s) from the Dashboard: {sorted(unknown)}")
        # Only apply fields actually provided (None is a valid value to set,
        # e.g. clearing a phone number) - callers pass exactly what the
        # request body included, see api/leads_routes.py.
        self.lead_repo.update_fields(lead, **fields)
        self.db.commit()
        return lead

    def delete_lead(self, lead_id: UUID) -> None:
        self._require_lead(lead_id)
        self.conversation_repo.delete_all_for_lead(lead_id)
        self.activity_repo.delete_for_lead(lead_id)
        lead = self._require_lead(lead_id)
        self.lead_repo.delete(lead)
        self.db.commit()

    def _require_lead(self, lead_id: UUID) -> Lead:
        lead = self.lead_repo.get_by_id(lead_id)
        if lead is None:
            raise LeadNotFoundError(f"Lead {lead_id} not found")
        return lead

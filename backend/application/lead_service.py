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

import logging
from typing import Optional
from uuid import UUID

from business_rules.validators import (
    is_region_covered,
    looks_like_rijksregisternummer,
    validate_date_of_birth,
    validate_ean,
    validate_email,
    validate_phone,
)
from crm.activity_repository import ActivityRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ActivityType, LeadSource
from domain.models.lead import Lead

logger = logging.getLogger(__name__)

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


class DuplicateLeadError(Exception):
    def __init__(self, existing_lead_id: UUID):
        self.existing_lead_id = existing_lead_id
        super().__init__(f"A lead with this email or phone already exists: {existing_lead_id}")


class RijksregisternummerRejectedError(Exception):
    """AGENTS.md golden rule: never ask for / store a Rijksregisternummer.
    The live conversation flow enforces this by simply never asking; manual
    creation is a human typing into a form, so it needs an actual check -
    see business_rules/validators.py's looks_like_rijksregisternummer."""


# Fields POST /api/leads (manual creation) accepts, beyond what
# LeadRepository.create() already takes directly (first_name/last_name/
# email/phone/language) - applied via LeadRepository.update_fields() right
# after creation, same generic updater update_lead() below already uses.
_CREATABLE_EXTRA_FIELDS = frozenset(
    {"region", "city", "customer_type", "current_supplier", "ean", "date_of_birth"}
)

# Every field a human could plausibly paste a Rijksregisternummer into -
# free-text-shaped fields, not e.g. a UUID or enum value.
_RRN_SCANNED_FIELDS = ("first_name", "last_name", "email", "phone", "ean", "city", "current_supplier")


class LeadService:
    def __init__(self, db_session):
        self.db = db_session
        self.lead_repo = LeadRepository(db_session)
        self.conversation_repo = ConversationRepository(db_session)
        self.activity_repo = ActivityRepository(db_session)

    def create_lead(
        self,
        *,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        region: Optional[str] = None,
        city: Optional[str] = None,
        customer_type: Optional[str] = None,
        current_supplier: Optional[str] = None,
        ean: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        language: Optional[str] = "fr",
    ) -> Lead:
        """Manual single-lead creation from the Dashboard (Prospects page -
        "Ajouter un prospect"). Reuses the exact same validators the live
        conversation flow uses (business_rules/validators.py, itself reused
        by conversation_engine/rules.py) rather than a second copy of the
        rules, and the exact same duplicate-detection path CSV import and
        the live flow both already use (LeadRepository.find_duplicate)."""
        candidate_values = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "ean": ean,
            "city": city,
            "current_supplier": current_supplier,
        }
        for field_name in _RRN_SCANNED_FIELDS:
            if looks_like_rijksregisternummer(candidate_values.get(field_name)):
                raise RijksregisternummerRejectedError(
                    f"Field '{field_name}' looks like a Rijksregisternummer - never collected or stored."
                )

        if email is not None and not validate_email(email):
            raise InvalidLeadFieldError(f"Invalid email: {email!r}")
        if phone is not None and not validate_phone(phone):
            raise InvalidLeadFieldError(f"Invalid Belgian phone number: {phone!r}")
        if ean is not None and not validate_ean(ean):
            raise InvalidLeadFieldError(f"Invalid EAN (must be {18} numeric digits): {ean!r}")
        if date_of_birth is not None and not validate_date_of_birth(date_of_birth):
            raise InvalidLeadFieldError(f"Invalid date of birth (expected DD/MM/YYYY): {date_of_birth!r}")
        if region is not None and not is_region_covered(region):
            raise InvalidLeadFieldError(f"Region not covered (OUT_OF_COVERAGE): {region!r}")

        duplicate = self.lead_repo.find_duplicate(email, phone)
        if duplicate is not None:
            raise DuplicateLeadError(duplicate.id)

        lead = self.lead_repo.create(
            source=LeadSource.MANUAL,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            language=language,
        )
        extra_fields = {
            "region": region,
            "city": city,
            "customer_type": customer_type,
            "current_supplier": current_supplier,
            "ean": ean,
            "date_of_birth": date_of_birth,
        }
        self.lead_repo.update_fields(lead, **{k: v for k, v in extra_fields.items() if v is not None})
        self.activity_repo.log(lead.id, ActivityType.LEAD_CREATED, details="Créé manuellement depuis la console")
        self.db.commit()
        return lead

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
        """Hard delete (demo mode) - conversations, activities, then the
        lead itself. GDPR audit trail: NOT an Activity row - one would be
        destroyed in the same operation it's meant to record, since
        ActivityRepository.delete_for_lead(lead_id) below removes every
        activity for this lead (including one logged moments earlier) and
        Lead has no ON DELETE CASCADE for a row that outlived it anyway.
        Logged to the application logger instead (same convention as
        application/contract_service.py) - a record that survives the
        delete without inventing a new table decoupled from the leads FK
        just for this, which is a real feature beyond this demo's scope."""
        lead = self._require_lead(lead_id)
        logger.info(
            "GDPR lead deletion: lead_id=%s status=%s source=%s created_at=%s",
            lead.id,
            lead.status.value if lead.status else None,
            lead.source.value if lead.source else None,
            lead.created_at,
        )
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

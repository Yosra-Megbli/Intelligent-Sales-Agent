"""
Lead Import Service (Application layer).

Same layering discipline as `dashboard_service.py` and `conversation_service.py`:
the HTTP layer (`api/leads_routes.py`) never touches `LeadRepository` or
`ActivityRepository` directly, only this service.

DEDUPLICATION (Feature 2): this is the *only* place CSV rows become Leads,
and it never creates a duplicate. Before creating anything it calls
`LeadRepository.find_duplicate(email, phone)` - the exact same method the
Business Rules Engine uses during DATA_VALIDATION (see
conversation_engine/rules.py) - so "a lead with this email/phone already
exists" means the same thing everywhere in the system. If a duplicate is
found, the existing Lead is updated (non-empty CSV fields only - a blank
CSV cell never erases existing data) instead of a new row being inserted.

This module never imports conversation_engine or ai/* - importing a CSV row
only ever creates/updates CRM data, it never makes a qualification/dialogue
decision (enforced by tests/test_architecture_boundaries.py, same rule as
DashboardService and CampaignEngine).
"""

from __future__ import annotations

import csv
import io
import time
from dataclasses import dataclass, field
from typing import Optional

from crm.activity_repository import ActivityRepository
from crm.lead_repository import LeadRepository
from domain.enums import ActivityType, LeadSource
from domain.models.lead import Lead

# CSV columns this importer understands (Feature 1). Anything else in the
# file is ignored. `name` is split on the first space into first/last name;
# every other column maps straight onto a Lead field of the same name,
# except `source` (see _resolve_source below).
_KNOWN_COLUMNS = {"name", "phone", "email", "region", "source", "provider", "notes", "telegram_chat_id"}


@dataclass
class ImportRowError:
    row_number: int
    message: str


@dataclass
class ImportReport:
    rows_read: int = 0
    created: int = 0
    updated: int = 0
    duplicates: int = 0  # rows that matched an existing Lead (subset counted in `updated` when a field actually changed)
    skipped: int = 0  # no email AND no phone - can't identify or dedupe this row at all
    errors: int = 0
    duration_seconds: float = 0.0
    error_details: list[ImportRowError] = field(default_factory=list)


@dataclass
class ImportPreviewRow:
    row_number: int
    data: dict
    would_be_duplicate: bool
    missing_identifier: bool  # true if neither email nor phone is present


@dataclass
class ImportPreview:
    headers: list[str]
    rows: list[ImportPreviewRow]
    total_rows: int
    rows_missing_identifier: int


class LeadImportService:
    def __init__(self, db_session):
        self.db = db_session
        self.lead_repo = LeadRepository(db_session)
        self.activity_repo = ActivityRepository(db_session)

    # --- Step 1/2 of the workflow: Upload -> Preview -----------------------
    def preview_csv(self, csv_text: str, limit: int = 20) -> ImportPreview:
        """Parses the CSV and reports what *would* happen, without writing
        anything to the database - powers the dashboard's Preview +
        Validation steps before the user confirms the import."""
        rows = list(self._parse_rows(csv_text))
        preview_rows: list[ImportPreviewRow] = []
        missing = 0

        for row_number, raw in rows[:limit]:
            email = _clean(raw.get("email"))
            phone = _clean(raw.get("phone"))
            missing_identifier = not email and not phone
            if missing_identifier:
                missing += 1
            duplicate = None if missing_identifier else self.lead_repo.find_duplicate(email=email, phone=phone)
            preview_rows.append(
                ImportPreviewRow(
                    row_number=row_number,
                    data=raw,
                    would_be_duplicate=duplicate is not None,
                    missing_identifier=missing_identifier,
                )
            )

        # Count missing-identifier rows across the *whole* file, not just the
        # previewed slice, so the report the user sees before confirming is
        # accurate even for large files.
        if len(rows) > limit:
            missing += sum(
                1 for _, raw in rows[limit:] if not _clean(raw.get("email")) and not _clean(raw.get("phone"))
            )

        headers = list(rows[0][1].keys()) if rows else []
        return ImportPreview(
            headers=headers, rows=preview_rows, total_rows=len(rows), rows_missing_identifier=missing
        )

    # --- Step 3/4/5: Validation -> Dedup -> Import Report -> Save ----------
    def import_csv(self, csv_text: str) -> ImportReport:
        report = ImportReport()
        started = time.perf_counter()

        for row_number, raw in self._parse_rows(csv_text):
            report.rows_read += 1
            try:
                self._import_row(row_number, raw, report)
            except Exception as exc:  # noqa: BLE001 - one bad row must never abort the whole import
                report.errors += 1
                report.error_details.append(ImportRowError(row_number=row_number, message=str(exc)))

        report.duration_seconds = time.perf_counter() - started
        return report

    def _import_row(self, row_number: int, raw: dict, report: ImportReport) -> None:
        email = _clean(raw.get("email"))
        phone = _clean(raw.get("phone"))

        if not email and not phone:
            report.skipped += 1
            return

        existing = self.lead_repo.find_duplicate(email=email, phone=phone)
        extra_fields = self._extract_fields(raw)

        if existing is not None:
            report.duplicates += 1
            changed_fields = {k: v for k, v in extra_fields.items() if v is not None}
            if changed_fields:
                self.lead_repo.update_fields(existing, **changed_fields)
                report.updated += 1
            self.activity_repo.log(
                existing.id,
                ActivityType.LEAD_IMPORTED,
                details=f"CSV import row {row_number}: matched existing lead, fields merged: {sorted(changed_fields)}",
            )
            return

        first_name, last_name = _split_name(raw.get("name"))
        lead: Lead = self.lead_repo.create(
            source=LeadSource.CSV,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
        )
        model_fields = {k: v for k, v in extra_fields.items() if v is not None}
        if model_fields:
            self.lead_repo.update_fields(lead, **model_fields)

        report.created += 1
        self.activity_repo.log(
            lead.id, ActivityType.LEAD_IMPORTED, details=f"CSV import row {row_number}: new lead created"
        )

    @staticmethod
    def _extract_fields(raw: dict) -> dict:
        """Maps recognised CSV columns (besides name/phone/email, already
        handled separately) onto Lead model fields. A blank cell maps to
        None here and is filtered out by the caller, so it never overwrites
        existing data on an update."""
        return {
            "region": _clean(raw.get("region")),
            "provider": _clean(raw.get("provider")),
            "notes": _clean(raw.get("notes")),
            "telegram_chat_id": _clean(raw.get("telegram_chat_id")),
        }

    @staticmethod
    def _parse_rows(csv_text: str):
        reader = csv.DictReader(io.StringIO(csv_text))
        for row_number, raw in enumerate(reader, start=1):
            normalized = {
                (key or "").strip().lower(): value for key, value in raw.items() if key is not None
            }
            yield row_number, normalized


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _split_name(name: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    name = _clean(name)
    if not name:
        return None, None
    parts = name.split(" ", 1)
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]

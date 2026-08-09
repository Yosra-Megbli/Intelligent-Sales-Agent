"""
Leads routes - CSV import (Feature 1/2/12) and lead detail/history
(Feature 3/8/11).

Same discipline as `api/dashboard_routes.py`: this module never imports a
repository or the Engine/ai directly, only `LeadImportService` and
`DashboardService` (enforced by tests/test_architecture_boundaries.py).

Kept as its own router (prefix `/api/leads`), separate from
`api/dashboard_routes.py`, because that module is documented and tested as
strictly read-only (GET) - import is a write action and belongs in its own,
equally `require_api_key`-guarded, surface.

`GET /api/leads/{id}` and `GET /api/leads/{id}/history` intentionally reuse
`DashboardService.get_lead_detail()` - the exact same read path
`/api/dashboard/leads/{id}` already uses - rather than adding a second way
to fetch the same data, per the "no duplicated logic" rule.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dashboard_schemas import ActivitySummary, ConversationSummary, LeadDetailResponse, LeadSummary
from api.dependencies import require_api_key
from api.leads_schemas import (
    ImportCsvRequest,
    ImportPreviewResponse,
    ImportPreviewRowResponse,
    ImportReportResponse,
    ImportRowErrorResponse,
    UpdateLeadRequest,
)
from api.routes import get_db_session
from application.dashboard_service import DashboardService
from application.lead_import_service import LeadImportService
from application.lead_service import InvalidLeadFieldError, LeadNotFoundError, LeadService

router = APIRouter(prefix="/api/leads", tags=["leads"], dependencies=[Depends(require_api_key)])


@router.post("/import/preview", response_model=ImportPreviewResponse)
def preview_import(payload: ImportCsvRequest, db: Session = Depends(get_db_session)) -> ImportPreviewResponse:
    """Step 2 of the workflow (Upload -> Preview): parses the CSV and shows
    what would happen (created/duplicate/skipped) without writing anything."""
    preview = LeadImportService(db).preview_csv(payload.csv_text)
    return ImportPreviewResponse(
        headers=preview.headers,
        rows=[
            ImportPreviewRowResponse(
                row_number=row.row_number,
                data=row.data,
                would_be_duplicate=row.would_be_duplicate,
                missing_identifier=row.missing_identifier,
            )
            for row in preview.rows
        ],
        total_rows=preview.total_rows,
        rows_missing_identifier=preview.rows_missing_identifier,
    )


@router.post("/import", response_model=ImportReportResponse, status_code=201)
def import_leads(payload: ImportCsvRequest, db: Session = Depends(get_db_session)) -> ImportReportResponse:
    """Steps 3-5 of the workflow (Validation -> Dedup -> Import Report ->
    Save): actually persists the leads. Never creates a duplicate Lead - see
    `LeadImportService`/`LeadRepository.find_duplicate`."""
    report = LeadImportService(db).import_csv(payload.csv_text)
    return ImportReportResponse(
        rows_read=report.rows_read,
        created=report.created,
        updated=report.updated,
        duplicates=report.duplicates,
        skipped=report.skipped,
        errors=report.errors,
        duration_seconds=report.duration_seconds,
        error_details=[
            ImportRowErrorResponse(row_number=e.row_number, message=e.message) for e in report.error_details
        ],
    )


@router.get("/{lead_id}", response_model=LeadDetailResponse)
def get_lead(lead_id: UUID, db: Session = Depends(get_db_session)) -> LeadDetailResponse:
    detail = DashboardService(db).get_lead_detail(lead_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadDetailResponse(
        lead=LeadSummary.from_model(detail.lead, campaign_name=detail.campaign.name if detail.campaign else None),
        conversations=[ConversationSummary.from_model(c) for c in detail.conversations],
        activities=[ActivitySummary.from_model(a) for a in detail.activities],
    )


@router.get("/{lead_id}/history", response_model=list[ActivitySummary])
def get_lead_history(lead_id: UUID, db: Session = Depends(get_db_session)) -> list[ActivitySummary]:
    """Feature 8: chronological event history for a lead - the same
    Activity log already shown on the dashboard drawer, exposed as its own
    endpoint for callers that only need the timeline."""
    detail = DashboardService(db).get_lead_detail(lead_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return [ActivitySummary.from_model(a) for a in detail.activities]


@router.patch("/{lead_id}", response_model=LeadSummary)
def update_lead(lead_id: UUID, payload: UpdateLeadRequest, db: Session = Depends(get_db_session)) -> LeadSummary:
    """CRM data correction only - see application/lead_service.py's
    `_EDITABLE_FIELDS`; a lead's status/qualification is never editable
    from here, only the Business Rules Engine sets those.
    `exclude_unset=True` so an omitted field is left untouched rather than
    overwritten with null."""
    try:
        lead = LeadService(db).update_lead(lead_id, **payload.model_dump(exclude_unset=True))
    except LeadNotFoundError:
        raise HTTPException(status_code=404, detail="Lead not found")
    except InvalidLeadFieldError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return LeadSummary.from_model(lead)


@router.delete("/{lead_id}", status_code=204, response_model=None)
def delete_lead(lead_id: UUID, db: Session = Depends(get_db_session)) -> None:
    try:
        LeadService(db).delete_lead(lead_id)
    except LeadNotFoundError:
        raise HTTPException(status_code=404, detail="Lead not found")

"""
Dashboard routes (Phase 7).

Thin HTTP wrapper around `application/dashboard_service.py`'s
`DashboardService` - same discipline as `api/routes.py` around
`channels/web.py`: this module never imports a repository or the domain
models' write paths directly, only `DashboardService` and the schemas that
serialize what it returns. Enforced by
`tests/test_architecture_boundaries.py`.

Every route here is read-only (GET). Nothing in this file can change a
Lead's status, a Conversation's state, or trigger a message - that's
`api/routes.py` (customer-facing turns), `outbound/`, or `followup/`'s job,
never the dashboard's.

SECURITY: every route below requires `require_api_key` - these endpoints
return a lead's name, email and phone number. Without `API_KEY` configured,
`require_api_key` degrades to logging a warning and allowing the request
through (see api/dependencies.py) - that keeps local dev/tests working, but
it means this PII is unauthenticated until API_KEY is set. Set it before
deploying anywhere the dashboard is reachable from outside a trusted network.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.dashboard_schemas import (
    ActivityFeedListResponse,
    ActivityFeedEntryResponse,
    ActivitySummary,
    ConversationSummary,
    HandoffEntryResponse,
    HandoffListResponse,
    LeadDetailResponse,
    LeadListResponse,
    LeadSummary,
    OverviewResponse,
    StatsSummaryResponse,
)
from api.dependencies import require_api_key
from api.routes import get_db_session
from application.dashboard_service import DashboardService
from domain.enums import LeadSource, LeadStatus

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_api_key)])


@router.get("/leads", response_model=LeadListResponse)
def list_leads(
    db: Session = Depends(get_db_session),
    status: Optional[LeadStatus] = None,
    region: Optional[str] = None,
    source: Optional[LeadSource] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LeadListResponse:
    page = DashboardService(db).list_leads(
        status=status, region=region, source=source, search=search, limit=limit, offset=offset
    )
    return LeadListResponse(
        items=[LeadSummary.from_model(lead) for lead in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/leads/{lead_id}", response_model=LeadDetailResponse)
def get_lead_detail(lead_id: UUID, db: Session = Depends(get_db_session)) -> LeadDetailResponse:
    detail = DashboardService(db).get_lead_detail(lead_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadDetailResponse(
        lead=LeadSummary.from_model(detail.lead, campaign_name=detail.campaign.name if detail.campaign else None),
        conversations=[ConversationSummary.from_model(c) for c in detail.conversations],
        activities=[ActivitySummary.from_model(a) for a in detail.activities],
    )


@router.get("/handoffs", response_model=HandoffListResponse)
def list_handoffs(
    db: Session = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> HandoffListResponse:
    """P04 - Handoff Queue: leads currently waiting on a human sales rep,
    most recently handed off first. Same read-only discipline as every other
    route in this file - only reaches `DashboardService`, never a repository."""
    page = DashboardService(db).list_handoffs(limit=limit, offset=offset)
    return HandoffListResponse(
        items=[HandoffEntryResponse.from_service(entry) for entry in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/stats", response_model=StatsSummaryResponse)
def get_stats(db: Session = Depends(get_db_session)) -> StatsSummaryResponse:
    summary = DashboardService(db).get_stats_summary()
    return StatsSummaryResponse(
        total_leads=summary.total_leads,
        by_status={status.value: count for status, count in summary.by_status.items()},
    )


@router.get("/overview", response_model=OverviewResponse)
def get_overview(db: Session = Depends(get_db_session)) -> OverviewResponse:
    """Priority 2 (Overview Dashboard) - thin wrapper around
    `DashboardService.get_overview()`, same pattern as `get_stats` above."""
    overview = DashboardService(db).get_overview()
    return OverviewResponse(**overview.__dict__)


@router.get("/activities", response_model=ActivityFeedListResponse)
def list_activities(
    db: Session = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> ActivityFeedListResponse:
    """Dashboard Activity Timeline: recent events (imports, status changes,
    qualifications, handoffs...) across every lead, most recent first. Same
    read-only discipline as every other route in this file - only reaches
    `DashboardService`, never a repository."""
    entries = DashboardService(db).list_recent_activities(limit=limit)
    return ActivityFeedListResponse(items=[ActivityFeedEntryResponse.from_service(e) for e in entries])

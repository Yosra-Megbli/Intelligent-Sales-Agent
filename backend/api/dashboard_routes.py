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
    ComplianceOverviewResponse,
    ConversationDetailItemResponse,
    ConversationListResponse,
    ConversationSummary,
    HandoffEntryResponse,
    HandoffListResponse,
    LeadDetailResponse,
    LeadListResponse,
    LeadSummary,
    OptOutJournalEntry,
    OverviewResponse,
    StatsSummaryResponse,
)
from api.dependencies import require_api_key
from api.routes import get_db_session
from application.dashboard_service import DashboardService
from domain.enums import ConversationChannel, ConversationState, LeadSource, LeadStatus

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


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    db: Session = Depends(get_db_session),
    state: Optional[ConversationState] = None,
    channel: Optional[ConversationChannel] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ConversationListResponse:
    """List conversations with replay metadata, filterable by state/channel/search."""
    page = DashboardService(db).list_conversations(
        state=state, channel=channel, search=search, limit=limit, offset=offset
    )
    return ConversationListResponse(
        items=[ConversationDetailItemResponse.from_item(item) for item in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailItemResponse)
def get_conversation(
    conversation_id: UUID, db: Session = Depends(get_db_session)
) -> ConversationDetailItemResponse:
    """Get single conversation detail with all messages and lead context."""
    item = DashboardService(db).get_conversation(conversation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetailItemResponse.from_item(item)


@router.get("/compliance", response_model=ComplianceOverviewResponse)
def get_compliance_overview(db: Session = Depends(get_db_session)) -> ComplianceOverviewResponse:
    """Compliance Center statistics and opt-out journal."""
    overview = DashboardService(db).get_compliance_overview()
    journal = []
    for e in overview.opt_out_events:
        lead = e.lead
        name = " ".join(filter(None, [lead.first_name, lead.last_name])).strip() or "Prospect (RGPD)"
        channel_name = lead.source.value if lead.source else "TELEGRAM"
        journal.append(
            OptOutJournalEntry(
                id=e.activity.id,
                lead_id=lead.id,
                lead_name=name,
                channel=channel_name,
                timestamp=e.activity.created_at,
                details=e.activity.details,
                confirmation_sent=True,
            )
        )
    return ComplianceOverviewResponse(
        guard_status=overview.guard_status,
        guard_tests_count=overview.guard_tests_count,
        guard_last_run=overview.guard_last_run,
        retention_months=overview.retention_months,
        auto_purge_enabled=overview.auto_purge_enabled,
        suppression_list_count=overview.suppression_list_count,
        groq_dpa_signed=overview.groq_dpa_signed,
        scc_status=overview.scc_status,
        anonymization_before_llm=overview.anonymization_before_llm,
        opt_out_events=journal,
    )


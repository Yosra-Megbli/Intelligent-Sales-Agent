"""
Campaign Management routes (Phase 8).

Thin HTTP wrapper around `application/campaign_service.py`'s
`CampaignService` - same discipline as `api/dashboard_routes.py` around
`DashboardService`: this module never imports a repository, `CampaignEngine`,
`OutboundSender`/`OutboundScheduler`, the Conversation Engine or `ai/*`
directly, only `CampaignService` and the schemas that serialize what it
returns. Enforced by `tests/test_architecture_boundaries.py`.

This is what makes the Dashboard's campaign management "no longer
read-only" (per the architecture requirement): list/create/inspect a
campaign, and start/pause/resume it - all through the Application layer,
never by manipulating a repository directly from here.

SECURITY: every route below requires `require_api_key`, same as
`api/dashboard_routes.py` and `api/leads_routes.py`.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.campaign_schemas import (
    CampaignAnalyticsResponse,
    CampaignDetailResponse,
    CampaignListResponse,
    CampaignSummary,
    CreateCampaignRequest,
)
from api.dashboard_schemas import LeadSummary
from api.dependencies import require_api_key
from api.routes import get_db_session
from application.campaign_service import (
    CampaignNotFoundError,
    CampaignService,
    InvalidCampaignTransitionError,
)

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=CampaignSummary, status_code=201)
def create_campaign(payload: CreateCampaignRequest, db: Session = Depends(get_db_session)) -> CampaignSummary:
    campaign = CampaignService(db).create_campaign(
        name=payload.name, target_rules=payload.target_rules, channel=payload.channel
    )
    return CampaignSummary.from_model(campaign)


@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    db: Session = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CampaignListResponse:
    page = CampaignService(db).list_campaigns(limit=limit, offset=offset)
    return CampaignListResponse(
        items=[CampaignSummary.from_model(c) for c in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
def get_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db_session),
    leads_limit: int = Query(default=50, ge=1, le=200),
    leads_offset: int = Query(default=0, ge=0),
) -> CampaignDetailResponse:
    detail = CampaignService(db).get_campaign_detail(
        campaign_id, leads_limit=leads_limit, leads_offset=leads_offset
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignDetailResponse(
        campaign=CampaignSummary.from_model(detail.campaign),
        leads=[LeadSummary.from_model(lead) for lead in detail.leads.items],
        leads_total=detail.leads.total,
        leads_limit=detail.leads.limit,
        leads_offset=detail.leads.offset,
    )


@router.get("/{campaign_id}/analytics", response_model=CampaignAnalyticsResponse)
def get_campaign_analytics(campaign_id: UUID, db: Session = Depends(get_db_session)) -> CampaignAnalyticsResponse:
    analytics = CampaignService(db).get_campaign_analytics(campaign_id)
    if analytics is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignAnalyticsResponse(campaign_id=campaign_id, **analytics.__dict__)


@router.post("/{campaign_id}/start", response_model=CampaignSummary)
def start_campaign(campaign_id: UUID, db: Session = Depends(get_db_session)) -> CampaignSummary:
    return CampaignSummary.from_model(_apply_transition(CampaignService(db).start_campaign, campaign_id))


@router.post("/{campaign_id}/pause", response_model=CampaignSummary)
def pause_campaign(campaign_id: UUID, db: Session = Depends(get_db_session)) -> CampaignSummary:
    return CampaignSummary.from_model(_apply_transition(CampaignService(db).pause_campaign, campaign_id))


@router.post("/{campaign_id}/resume", response_model=CampaignSummary)
def resume_campaign(campaign_id: UUID, db: Session = Depends(get_db_session)) -> CampaignSummary:
    return CampaignSummary.from_model(_apply_transition(CampaignService(db).resume_campaign, campaign_id))


def _apply_transition(action, campaign_id: UUID):
    try:
        return action(campaign_id)
    except CampaignNotFoundError:
        raise HTTPException(status_code=404, detail="Campaign not found")
    except InvalidCampaignTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

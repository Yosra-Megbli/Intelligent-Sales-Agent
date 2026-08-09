"""
Request/response schemas for the Campaign Management HTTP API (Phase 8).

Same discipline as `api/dashboard_schemas.py`: pure serialization shapes,
no business logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from api.dashboard_schemas import LeadSummary
from domain.enums import ConversationChannel
from domain.models.campaign import Campaign


class CreateCampaignRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    # e.g. {"region": "Wallonie"} - matches Campaign.target_rules (Phase 5).
    target_rules: Optional[dict] = None
    # Which channel every lead in this campaign is contacted on - see
    # domain/models/campaign.py's Campaign.channel and
    # outbound/scheduler.py's OutboundScheduler. Defaults to WhatsApp,
    # unchanged from this endpoint's behaviour before this field existed.
    channel: ConversationChannel = ConversationChannel.WHATSAPP


class UpdateCampaignRequest(BaseModel):
    """Both optional and unset-by-default - a PATCH only touches what's
    included (see api/campaign_routes.py's `.model_dump(exclude_unset=True)`).
    `target_rules` is only actually applied while the campaign is still
    DRAFT - see CampaignService.update_campaign's docstring for why."""

    model_config = {"extra": "forbid"}

    name: Optional[str] = Field(default=None, min_length=1, max_length=180)
    target_rules: Optional[dict] = None


class CampaignSummary(BaseModel):
    """Lightweight campaign shape for the list/detail/start/pause/resume
    endpoints. Deliberately does NOT include `replied`/`qualified`: those
    columns on `Campaign` are never incremented by the real flow (only
    `sent` is - see `outbound/sender.py`), so exposing them here would
    silently report 0 forever next to `GET /{campaign_id}/analytics`'s
    correct, derived numbers. Analytics-consumers must call
    `GET /api/campaigns/{campaign_id}/analytics` instead - see
    `CampaignAnalyticsResponse` below. Keeping this endpoint's per-row
    payload free of an analytics query also avoids an N+1 query cost on
    `list_campaigns`, which can return up to 200 rows at once.
    """

    id: UUID
    name: str
    status: str
    channel: str
    total_leads: int
    sent: int
    target_rules: Optional[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, campaign: Campaign) -> "CampaignSummary":
        return cls(
            id=campaign.id,
            name=campaign.name,
            status=campaign.status.value,
            channel=campaign.channel.value,
            total_leads=campaign.total_leads,
            sent=campaign.sent,
            target_rules=campaign.target_rules,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )


class CampaignListResponse(BaseModel):
    items: list[CampaignSummary]
    total: int
    limit: int
    offset: int


class CampaignDetailResponse(BaseModel):
    campaign: CampaignSummary
    leads: list[LeadSummary]
    leads_total: int
    leads_limit: int
    leads_offset: int


class CampaignAnalyticsResponse(BaseModel):
    """Priority 1 (Campaign Dashboard/Analytics) - see
    CampaignService.get_campaign_analytics for how each field is derived
    from real Lead/Conversation data rather than the Campaign.replied/
    qualified counters (which nothing in this codebase keeps in sync)."""

    campaign_id: UUID
    total: int
    pending: int
    contacted: int
    replied: int
    qualified: int
    rejected: int
    handoff: int
    response_rate: float
    qualification_rate: float

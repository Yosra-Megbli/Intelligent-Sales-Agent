"""
Request/response schemas for the Dashboard HTTP API (Phase 7).

Same discipline as `api/schemas.py`: pure serialization shapes, no business
logic. Every field here is something the Business Engine already decided
and persisted - this layer only reads it back.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class LeadSummary(BaseModel):
    id: UUID
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    telegram_chat_id: Optional[str]
    source: str
    status: str
    rejection_reason: Optional[str]
    customer_type: Optional[str]
    region: Optional[str]
    city: Optional[str]
    date_of_birth: Optional[datetime]
    current_supplier: Optional[str]
    provider: Optional[str]
    notes: Optional[str]
    qualification_score: Optional[int]
    created_at: datetime
    updated_at: datetime
    # Feature 3 (Lead Details): upcoming follow-up + campaign this lead
    # belongs to. `campaign_name` is only populated by the detail views
    # (dashboard_routes.get_lead_detail / leads_routes.get_lead), which do
    # the extra CampaignRepository lookup - the list view leaves it None to
    # avoid an N+1 query per row.
    next_follow_up_date: Optional[datetime]
    follow_up_category: Optional[str]
    campaign_id: Optional[UUID]
    campaign_name: Optional[str]
    # Outbound visibility (audit finding #10): the field already existed on
    # the Lead model but was never surfaced to the dashboard - the sales
    # team had no way to see "when did we last actually reach this person"
    # without opening raw activity logs.
    last_contact_date: Optional[datetime]

    @classmethod
    def from_model(cls, lead, campaign_name: Optional[str] = None) -> "LeadSummary":
        return cls(
            id=lead.id,
            first_name=lead.first_name,
            last_name=lead.last_name,
            email=lead.email,
            phone=lead.phone,
            telegram_chat_id=lead.telegram_chat_id,
            source=lead.source.value,
            status=lead.status.value,
            rejection_reason=lead.rejection_reason.value if lead.rejection_reason else None,
            customer_type=lead.customer_type,
            region=lead.region,
            city=lead.city,
            date_of_birth=lead.date_of_birth,
            current_supplier=lead.current_supplier,
            provider=lead.provider,
            notes=lead.notes,
            qualification_score=lead.qualification_score,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
            next_follow_up_date=lead.next_follow_up_date,
            follow_up_category=lead.follow_up_category.value if lead.follow_up_category else None,
            campaign_id=lead.campaign_id,
            campaign_name=campaign_name,
            last_contact_date=lead.last_contact_date,
        )


class LeadListResponse(BaseModel):
    items: list[LeadSummary]
    total: int
    limit: int
    offset: int


class MessageSummary(BaseModel):
    """Audit finding #8 (Conversation content): the `Message` model already
    stores the full text of every turn, but the dashboard never returned it
    - `ConversationSummary` exposed only channel/state/timestamps, so the
    sales team could see *that* Sophie talked to a lead but never *what was
    said*. This is a pure read of already-persisted data - no new write
    path, nothing decided here."""

    id: UUID
    role: str
    content: str
    intent_detected: Optional[str]
    timestamp: datetime

    @classmethod
    def from_model(cls, message) -> "MessageSummary":
        return cls(
            id=message.id,
            role=message.role.value,
            content=message.content,
            intent_detected=message.intent_detected,
            timestamp=message.timestamp,
        )


class ConversationSummary(BaseModel):
    id: UUID
    channel: str
    current_state: str
    started_at: datetime
    last_message_at: datetime
    messages: list[MessageSummary]

    @classmethod
    def from_model(cls, conversation) -> "ConversationSummary":
        return cls(
            id=conversation.id,
            channel=conversation.channel.value,
            current_state=conversation.current_state.value,
            started_at=conversation.started_at,
            last_message_at=conversation.last_message_at,
            messages=[MessageSummary.from_model(m) for m in conversation.messages],
        )


class ActivitySummary(BaseModel):
    id: UUID
    type: str
    details: Optional[str]
    created_at: datetime

    @classmethod
    def from_model(cls, activity) -> "ActivitySummary":
        return cls(id=activity.id, type=activity.type.value, details=activity.details, created_at=activity.created_at)


class LeadDetailResponse(BaseModel):
    lead: LeadSummary
    conversations: list[ConversationSummary]
    activities: list[ActivitySummary]


class HandoffEntryResponse(BaseModel):
    """One row of the Handoff Queue (P04) - a lead currently waiting on a
    human sales rep, plus enough context (phone, campaign, qualification
    score, when, why) that the sales team doesn't have to open the lead
    detail page just to triage the queue."""

    lead: LeadSummary
    conversation_id: UUID
    channel: str
    handoff_at: datetime
    reason: Optional[str]

    @classmethod
    def from_service(cls, entry) -> "HandoffEntryResponse":
        return cls(
            lead=LeadSummary.from_model(entry.lead, campaign_name=entry.campaign_name),
            conversation_id=entry.conversation.id,
            channel=entry.conversation.channel.value,
            handoff_at=entry.conversation.last_message_at,
            reason=entry.reason,
        )


class HandoffListResponse(BaseModel):
    items: list[HandoffEntryResponse]
    total: int
    limit: int
    offset: int


class StatsSummaryResponse(BaseModel):
    total_leads: int
    by_status: dict[str, int]


class ActivityFeedEntryResponse(BaseModel):
    """One row of the dashboard's Activity Timeline - an Activity plus just
    enough about the Lead it belongs to (id + display name) to render
    'X happened to Y' without a client-side lookup."""

    id: UUID
    type: str
    details: Optional[str]
    created_at: datetime
    lead_id: UUID
    lead_name: str

    @classmethod
    def from_service(cls, entry) -> "ActivityFeedEntryResponse":
        lead = entry.lead
        name = " ".join(filter(None, [lead.first_name, lead.last_name])).strip() or lead.phone or lead.email or "—"
        return cls(
            id=entry.activity.id,
            type=entry.activity.type.value,
            details=entry.activity.details,
            created_at=entry.activity.created_at,
            lead_id=lead.id,
            lead_name=name,
        )


class ActivityFeedListResponse(BaseModel):
    items: list[ActivityFeedEntryResponse]


class OverviewResponse(BaseModel):
    """Priority 2 (Overview Dashboard) - the eight headline metrics for the
    sales team's landing view. See `application/dashboard_service.py`'s
    `OverviewStats` for how each field is derived."""

    total_leads: int
    active_conversations: int
    active_campaigns: int
    contacted: int
    qualified: int
    rejected: int
    human_handoff: int
    conversion_rate: float

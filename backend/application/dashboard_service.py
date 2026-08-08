"""
Dashboard Service (Application layer, Phase 7).

Same layering discipline as `application/conversation_service.py`: the HTTP
layer (`api/dashboard_routes.py`) never touches a repository or a domain
model directly - it only calls this service and serializes what it returns.
Unlike `ConversationService`, this one never imports `conversation_engine`
or `ai/*` at all - it has nothing to decide, only leads/conversations/
activities to read back. `tests/test_architecture_boundaries.py` enforces
both halves of that: `api/dashboard_routes.py` never imports a repository
directly, and this module never imports the Engine or `ai/*`.

Read-only by design: every method here is a query, never a write. Anything
that changes a Lead/Conversation still only ever happens through
`ConversationService`, `CampaignEngine`, or `FollowUpEngine` - a dashboard
is a window, not another place business decisions get made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from crm.activity_repository import ActivityRepository
from crm.campaign_repository import CampaignRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ActivityType, ConversationState, LeadSource, LeadStatus
from domain.models.activity import Activity
from domain.models.campaign import Campaign
from domain.models.conversation import Conversation
from domain.models.lead import Lead


@dataclass
class LeadPage:
    items: list[Lead]
    total: int
    limit: int
    offset: int


@dataclass
class LeadDetail:
    lead: Lead
    conversations: list[Conversation]
    activities: list[Activity]
    campaign: Optional[Campaign] = None


@dataclass
class StatsSummary:
    total_leads: int
    by_status: dict[LeadStatus, int] = field(default_factory=dict)


@dataclass
class OverviewStats:
    """Priority 2 (Overview Dashboard). Same discipline as
    `application/campaign_service.py`'s `CampaignAnalytics`: every count is
    derived from real, already-persisted Lead.status / Conversation.current_state
    data - nothing here is decided, only read back and aggregated.

    Bucketing mirrors `CampaignService.get_campaign_analytics` exactly
    (global instead of scoped to one campaign):
    - contacted     = everything except NEW (an opening message went out,
                       whether the lead reached us first or we reached them)
    - qualified     = QUALIFIED and everything further down the funnel
                       (APPOINTMENT/CONTRACT/CUSTOMER) - once qualified,
                       always counted as qualified even after progressing
    - rejected      = REJECTED
    - human_handoff = distinct leads with a conversation currently in
                       ConversationState.HANDOFF (HANDOFF is a
                       ConversationState, not a LeadStatus, so it can't be
                       read off Lead.status - see
                       ConversationRepository.count_distinct_leads_in_state)
    """

    total_leads: int
    active_conversations: int
    active_campaigns: int
    contacted: int
    qualified: int
    rejected: int
    human_handoff: int
    conversion_rate: float


@dataclass
class HandoffEntry:
    """One row of the Handoff Queue (P04): a lead currently waiting on a
    human sales rep, paired with the conversation that put them there."""

    lead: Lead
    conversation: Conversation
    campaign_name: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class HandoffPage:
    items: list[HandoffEntry]
    total: int
    limit: int
    offset: int


@dataclass
class ActivityFeedEntry:
    """One row of the dashboard's global Activity Timeline: an Activity
    paired with the Lead it happened to, so the UI can show 'who' without a
    second round-trip per row."""

    activity: Activity
    lead: Lead


class DashboardService:
    """The Application layer's read side: list/inspect leads and their
    conversation + activity history for the sales team's dashboard."""

    def __init__(self, db_session):
        self.lead_repo = LeadRepository(db_session)
        self.conversation_repo = ConversationRepository(db_session)
        self.activity_repo = ActivityRepository(db_session)
        self.campaign_repo = CampaignRepository(db_session)

    def list_leads(
        self,
        *,
        status: Optional[LeadStatus] = None,
        region: Optional[str] = None,
        source: Optional[LeadSource] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> LeadPage:
        leads, total = self.lead_repo.list_leads(
            status=status, region=region, source=source, search=search, limit=limit, offset=offset
        )
        return LeadPage(items=leads, total=total, limit=limit, offset=offset)

    def get_lead_detail(self, lead_id: UUID) -> Optional[LeadDetail]:
        lead = self.lead_repo.get_by_id(lead_id)
        if lead is None:
            return None
        conversations = self.conversation_repo.list_for_lead(lead_id)
        activities = self.activity_repo.list_for_lead(lead_id)
        campaign = self.campaign_repo.get_by_id(lead.campaign_id) if lead.campaign_id else None
        return LeadDetail(lead=lead, conversations=conversations, activities=activities, campaign=campaign)

    def get_stats_summary(self) -> StatsSummary:
        by_status = self.lead_repo.count_by_status()
        return StatsSummary(total_leads=sum(by_status.values()), by_status=by_status)

    def get_overview(self) -> OverviewStats:
        """Priority 2 (Overview Dashboard) - the sales team's top-of-page
        summary: leads, in-flight conversations, running campaigns and the
        funnel's headline numbers, all in one call so the Overview view
        doesn't have to fire off `/leads`, `/campaigns` and `/stats`
        separately just to fill in eight numbers.
        """
        by_status = self.lead_repo.count_by_status()
        total_leads = sum(by_status.values())
        pending = by_status.get(LeadStatus.NEW, 0)
        contacted = total_leads - pending
        rejected = by_status.get(LeadStatus.REJECTED, 0)
        qualified = sum(
            by_status.get(s, 0)
            for s in (LeadStatus.QUALIFIED, LeadStatus.APPOINTMENT, LeadStatus.CONTRACT, LeadStatus.CUSTOMER)
        )

        active_conversations = self.conversation_repo.count_active()
        active_campaigns = self.campaign_repo.count_running()
        human_handoff = self.conversation_repo.count_distinct_leads_in_state(ConversationState.HANDOFF)

        conversion_rate = (qualified / total_leads * 100) if total_leads else 0.0

        return OverviewStats(
            total_leads=total_leads,
            active_conversations=active_conversations,
            active_campaigns=active_campaigns,
            contacted=contacted,
            qualified=qualified,
            rejected=rejected,
            human_handoff=human_handoff,
            conversion_rate=conversion_rate,
        )

    # --- Reason labels for the Handoff Queue's "why" column ---------------
    # Derived purely from the STATE_CHANGED Activity that `conversation_engine
    # /engine.py::_log_activity` already writes on every transition
    # ("PREVIOUS_STATE -> HANDOFF") - no new write path, no touching
    # conversation_engine itself (Phase-0-Freeze). HANDOFF is reached two
    # ways today (see conversation_engine/state_machine.py): normally from
    # QUALIFIED once qualification finishes, or from any state the moment the
    # customer explicitly asks for a human (EventType.REQUEST_HUMAN).
    _HANDOFF_REASON_LABELS: dict[str, str] = {
        "QUALIFIED": "Qualified — ready for appointment",
    }
    _DEFAULT_HANDOFF_REASON = "Customer asked to speak with a human"

    def _infer_handoff_reason(self, lead_id: UUID) -> Optional[str]:
        for activity in self.activity_repo.list_for_lead(lead_id, limit=20):
            if (
                activity.type == ActivityType.STATE_CHANGED
                and activity.details
                and activity.details.endswith("-> HANDOFF")
            ):
                previous_state = activity.details.split(" -> ")[0]
                return self._HANDOFF_REASON_LABELS.get(previous_state, self._DEFAULT_HANDOFF_REASON)
        return None

    def list_handoffs(self, *, limit: int = 50, offset: int = 0) -> HandoffPage:
        """Dashboard Priority 3 (P04 - Handoff Queue): the actual prospects
        behind the Overview's `human_handoff` count, not just the number -
        so the sales team can see who is waiting, not only how many.
        """
        conversations, total = self.conversation_repo.list_handoff_leads(limit=limit, offset=offset)

        campaign_ids = {c.lead.campaign_id for c in conversations if c.lead.campaign_id}
        campaign_names: dict[UUID, str] = {}
        for campaign_id in campaign_ids:
            campaign = self.campaign_repo.get_by_id(campaign_id)
            if campaign is not None:
                campaign_names[campaign_id] = campaign.name

        items = [
            HandoffEntry(
                lead=conversation.lead,
                conversation=conversation,
                campaign_name=campaign_names.get(conversation.lead.campaign_id),
                reason=self._infer_handoff_reason(conversation.lead.id),
            )
            for conversation in conversations
        ]
        return HandoffPage(items=items, total=total, limit=limit, offset=offset)

    def list_recent_activities(self, *, limit: int = 50) -> list[ActivityFeedEntry]:
        """Dashboard Activity Timeline: every meaningful event (imports,
        status changes, qualifications, handoffs...) across *all* leads,
        most recent first - the same Activity log already shown per-lead
        (`get_lead_detail`), just not scoped to one lead. Read-only, same as
        every other method here: nothing is decided or written, only read
        back via `ActivityRepository.list_recent`.
        """
        activities = self.activity_repo.list_recent(limit=limit)
        return [ActivityFeedEntry(activity=activity, lead=activity.lead) for activity in activities]

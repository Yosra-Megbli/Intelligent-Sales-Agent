"""
Campaign Service (Application layer, Phase 8).

Same layering discipline as `application/dashboard_service.py` and
`application/conversation_service.py`: the HTTP layer
(`api/campaign_routes.py`) never touches a repository, `CampaignEngine`,
`OutboundSender` or `OutboundScheduler` directly - it only calls this
service and serializes what it returns. `tests/test_architecture_boundaries.py`
enforces that `api/campaign_routes.py` imports nothing except this module
and its schemas.

This is the ONLY place campaign write-actions (create/start/pause/resume)
are allowed to happen from the Dashboard - it never manipulates a
repository's write methods directly from a route, and it never invents a
second sales agent: starting/resuming a campaign runs the exact same
`OutboundScheduler` -> `OutboundSender` -> `ConversationService` pipeline
`run_outbound.py` and a cron/worker tick would use.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from conversation_engine.compliance import disclosure_for
from crm.campaign_repository import CampaignRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import CampaignStatus, ConversationChannel, ConversationState, LeadStatus
from domain.models.campaign import Campaign
from domain.models.lead import Lead
from outbound.scheduler import OutboundScheduler

# Channels a campaign may actually send on. WhatsApp and Voice are built
# end-to-end (see AGENTS.md) but not activated in this deployment - no
# Twilio WhatsApp/Voice credentials configured - so a campaign created on
# either would compute replies that are never sent. SMS is deliberately
# NOT in this set: AGENTS.md documents it as complete and live, same tier
# as Telegram/Web, not a "built but not activated" channel.
_ACTIVATED_CAMPAIGN_CHANNELS = frozenset(
    {ConversationChannel.TELEGRAM, ConversationChannel.WEB, ConversationChannel.SMS}
)


@dataclass
class CampaignPage:
    items: list[Campaign]
    total: int
    limit: int
    offset: int


@dataclass
class LeadPage:
    items: list[Lead]
    total: int
    limit: int
    offset: int


@dataclass
class CampaignDetail:
    campaign: Campaign
    leads: LeadPage


@dataclass
class CampaignAnalytics:
    """Priority 1 (Campaign Dashboard/Analytics). Every count here is
    derived from real Lead.status (and, for `handoff`, Conversation.current_state)
    data for this campaign's assigned leads - not from Campaign.sent/replied/
    qualified, which nothing in this codebase actually keeps in sync (see
    CampaignService.get_campaign_analytics's docstring). `total` intentionally
    also comes from the same grouped-by-status query rather than
    Campaign.total_leads, so the numbers below always sum to it exactly."""

    total: int
    pending: int
    contacted: int
    replied: int
    qualified: int
    rejected: int
    handoff: int
    response_rate: float
    qualification_rate: float


class CampaignNotFoundError(Exception):
    pass


class InvalidCampaignTransitionError(Exception):
    pass


class ChannelNotActivatedError(Exception):
    """Raised by `create_campaign` for a channel that is built but not
    activated in this deployment (see `_ACTIVATED_CAMPAIGN_CHANNELS`).
    `api/campaign_routes.py` turns this into a 422 with a typed error code
    ("channel_not_activated") the frontend can key off of to show its
    honest-stub tooltip, rather than a generic validation error."""

    def __init__(self, channel: ConversationChannel):
        self.channel = channel
        super().__init__(f"Channel {channel.value} is not activated in this deployment.")


@dataclass
class CampaignPreview:
    """Read-only projection of what starting this campaign would do -
    computed the same way `CampaignEngine.select_and_assign_leads` selects
    leads (NEW status, unassigned, matching target_rules), but without
    assigning anything. Opted-out leads never appear here: they are never
    LeadStatus.NEW to begin with, so there is no separate "excluded" count
    to compute - they simply never entered the candidate pool."""

    campaign_id: UUID
    matched_leads: int
    channel: ConversationChannel
    disclosure_preview: str


class CampaignService:
    """The Application layer's write+read side for Campaigns: everything
    the Dashboard's campaign management UI needs, without ever reaching
    around into a repository or the Outbound pipeline's internals."""

    def __init__(self, db_session):
        self.db = db_session
        self.campaign_repo = CampaignRepository(db_session)
        self.lead_repo = LeadRepository(db_session)
        self.conversation_repo = ConversationRepository(db_session)

    def create_campaign(
        self,
        *,
        name: str,
        target_rules: Optional[dict] = None,
        channel: ConversationChannel = ConversationChannel.TELEGRAM,
    ) -> Campaign:
        if channel not in _ACTIVATED_CAMPAIGN_CHANNELS:
            raise ChannelNotActivatedError(channel)
        rules_json = json.dumps(target_rules) if target_rules else None
        campaign = self.campaign_repo.create(name=name, target_rules=rules_json, channel=channel)
        self.db.commit()
        return campaign

    def preview_campaign(self, campaign_id: UUID, *, limit: int = 100) -> CampaignPreview:
        """Dry run of what `start_campaign`/`resume_campaign` would select
        and send, for the Dashboard's launch-confirmation step - never
        assigns or sends anything. Language for the disclosure preview is
        French: campaigns don't carry a per-campaign language today (leads
        do, individually), so this shows the FR disclosure as the
        representative sample the confirmation modal quotes."""
        campaign = self._require_campaign(campaign_id)
        target_rules = json.loads(campaign.target_rules) if campaign.target_rules else {}
        region = target_rules.get("region")
        matched = self.lead_repo.list_new_for_campaign(region=region, limit=limit)
        return CampaignPreview(
            campaign_id=campaign_id,
            matched_leads=len(matched),
            channel=campaign.channel,
            disclosure_preview=disclosure_for("fr"),
        )

    def list_campaigns(self, *, limit: int = 50, offset: int = 0) -> CampaignPage:
        campaigns, total = self.campaign_repo.list_all(limit=limit, offset=offset)
        return CampaignPage(items=campaigns, total=total, limit=limit, offset=offset)

    def get_campaign(self, campaign_id: UUID) -> Optional[Campaign]:
        return self.campaign_repo.get_by_id(campaign_id)

    def get_campaign_detail(
        self, campaign_id: UUID, *, leads_limit: int = 50, leads_offset: int = 0
    ) -> Optional[CampaignDetail]:
        campaign = self.campaign_repo.get_by_id(campaign_id)
        if campaign is None:
            return None
        leads, total = self.lead_repo.list_by_campaign(campaign_id, limit=leads_limit, offset=leads_offset)
        return CampaignDetail(
            campaign=campaign,
            leads=LeadPage(items=leads, total=total, limit=leads_limit, offset=leads_offset),
        )

    def start_campaign(self, campaign_id: UUID) -> Campaign:
        """DRAFT/PAUSED -> RUNNING, then immediately assigns + sends one
        paced batch via the same `OutboundScheduler` a cron tick uses -
        so pressing "Start" in the Dashboard has a visible effect right
        away rather than waiting for the next scheduled tick.

        The batch is sent on `campaign.channel` (set at creation time, see
        `create_campaign`) - a fresh `OutboundScheduler` is built for that
        channel on every call rather than reused across campaigns, since
        two campaigns can run on two different channels at once.

        `sleep_between_sends=False` here: this runs synchronously inside
        the HTTP request, so the human pacing delay (`outbound_rules.yaml`)
        is skipped for THIS batch - a production deployment should also run
        `OutboundScheduler` from a background worker/cron for ongoing,
        paced sends beyond this first batch (see `run_outbound.py`).
        """
        campaign = self._require_campaign(campaign_id)
        if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
            raise InvalidCampaignTransitionError(
                f"Campaign {campaign_id} is {campaign.status.value}, cannot start."
            )
        self.campaign_repo.set_status(campaign, CampaignStatus.RUNNING)
        self.db.commit()
        OutboundScheduler(self.db, channel=campaign.channel).process_campaign(campaign, sleep_between_sends=False)
        self.db.commit()
        self._emit_campaign_progress(campaign_id)
        return campaign

    def pause_campaign(self, campaign_id: UUID) -> Campaign:
        campaign = self._require_campaign(campaign_id)
        if campaign.status != CampaignStatus.RUNNING:
            raise InvalidCampaignTransitionError(
                f"Campaign {campaign_id} is {campaign.status.value}, cannot pause."
            )
        self.campaign_repo.set_status(campaign, CampaignStatus.PAUSED)
        self.db.commit()
        return campaign

    def resume_campaign(self, campaign_id: UUID) -> Campaign:
        """PAUSED -> RUNNING, then triggers another synchronous batch, same
        as `start_campaign` - resuming picks up exactly where the campaign
        left off (no leads are re-sent: see `OutboundScheduler`'s duplicate
        protection notes), on the same `campaign.channel` it was created
        with."""
        campaign = self._require_campaign(campaign_id)
        if campaign.status != CampaignStatus.PAUSED:
            raise InvalidCampaignTransitionError(
                f"Campaign {campaign_id} is {campaign.status.value}, cannot resume."
            )
        self.campaign_repo.set_status(campaign, CampaignStatus.RUNNING)
        self.db.commit()
        OutboundScheduler(self.db, channel=campaign.channel).process_campaign(campaign, sleep_between_sends=False)
        self.db.commit()
        self._emit_campaign_progress(campaign_id)
        return campaign

    def cancel_campaign(self, campaign_id: UUID) -> Campaign:
        """Cancels a campaign (sets status to CANCELLED)."""
        campaign = self._require_campaign(campaign_id)
        if campaign.status == CampaignStatus.CANCELLED:
            return campaign
        self.campaign_repo.set_status(campaign, CampaignStatus.CANCELLED)
        self.db.commit()
        self._emit_campaign_progress(campaign_id)
        return campaign

    def _emit_campaign_progress(self, campaign_id: UUID) -> None:
        try:
            import logging
            from live.broker import get_live_broker
            analytics = self.get_campaign_analytics(campaign_id)
            if analytics:
                get_live_broker().publish_sync(
                    "campaign_progress",
                    {
                        "campaign_id": str(campaign_id),
                        "sent": analytics.contacted,
                        "responded": analytics.replied,
                        "qualified": analytics.qualified,
                        "opted_out": analytics.rejected,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning("Failed to emit campaign_progress (non-blocking): %s", exc)

    def update_campaign(
        self, campaign_id: UUID, *, name: Optional[str] = None, target_rules: Optional[dict] = None
    ) -> Campaign:
        """Renaming is safe at any status (it's just a label - never read by
        CampaignEngine/OutboundScheduler). Re-targeting (`target_rules`) is
        only allowed while DRAFT: once a campaign has started, leads may
        already be assigned under the old rules, and silently changing what
        "matches" this campaign after the fact would make that assignment
        history impossible to reason about - pause and create a new
        campaign instead of re-targeting a live one."""
        campaign = self._require_campaign(campaign_id)
        fields: dict = {}
        if name is not None:
            fields["name"] = name
        if target_rules is not None:
            if campaign.status != CampaignStatus.DRAFT:
                raise InvalidCampaignTransitionError(
                    f"Campaign {campaign_id} is {campaign.status.value}, cannot change target_rules "
                    "(only allowed while DRAFT - pause and create a new campaign instead)."
                )
            fields["target_rules"] = json.dumps(target_rules) if target_rules else None
        if fields:
            self.campaign_repo.update_fields(campaign, **fields)
            self.db.commit()
        return campaign

    def delete_campaign(self, campaign_id: UUID) -> None:
        """Blocked while RUNNING (pause first - see class docstring's
        compromise: deleting mid-send would cut off a batch OutboundScheduler
        is actively working through). DRAFT/PAUSED campaigns can be deleted;
        their assigned leads are released (LeadRepository.release_from_campaign)
        rather than deleted themselves - a lead's own CRM record/status is
        never collateral damage of removing the campaign that once targeted
        it."""
        campaign = self._require_campaign(campaign_id)
        if campaign.status == CampaignStatus.RUNNING:
            raise InvalidCampaignTransitionError(
                f"Campaign {campaign_id} is RUNNING, cannot delete - pause it first."
            )
        self.lead_repo.release_from_campaign(campaign_id)
        self.campaign_repo.delete(campaign)
        self.db.commit()

    def get_campaign_analytics(self, campaign_id: UUID) -> Optional[CampaignAnalytics]:
        """Priority 1 (Campaign Dashboard/Analytics).

        Deliberately does NOT read Campaign.sent/replied/qualified:
        `increment_sent` is called from outbound/sender.py, but
        `increment_replied`/`increment_qualified` (crm/campaign_repository.py)
        are defined and tested in isolation yet never called anywhere in the
        real flow - the same "dead code" shape as WAITING_CUSTOMER before
        Phase 6 and rate_limit_hit before the Phase 7 security pass. Rather
        than surface that gap as a silently-always-zero metric, every count
        below is derived from the one thing that IS kept correct end-to-end:
        Lead.status (set exclusively by conversation_engine/engine.py's
        `_sync_lead_status`), plus Conversation.current_state for `handoff`
        (HANDOFF is a ConversationState, not a LeadStatus - it can't be read
        off Lead.status at all).

        Bucketing, from the Lead Lifecycle (NEW -> CONTACTED -> ENGAGED ->
        QUALIFICATION -> QUALIFIED -> APPOINTMENT -> CONTRACT -> CUSTOMER,
        REJECTED possible at any step):
        - pending    = NEW (assigned but not yet sent an opening message)
        - contacted  = everything except NEW (an opening message went out)
        - replied    = contacted minus still-plain-CONTACTED (i.e. the
                       customer's own first message moved them to ENGAGED
                       or further - see engine.py's ENGAGED transition)
        - qualified  = QUALIFIED and everything further down the funnel
                       (APPOINTMENT/CONTRACT/CUSTOMER) - once qualified,
                       always counted as qualified even after progressing
        - rejected   = REJECTED
        - handoff    = leads with a conversation currently in
                       ConversationState.HANDOFF (via the join query above)
        """
        campaign = self.campaign_repo.get_by_id(campaign_id)
        if campaign is None:
            return None

        by_status = self.lead_repo.count_by_status(campaign_id=campaign_id)
        total = sum(by_status.values())
        pending = by_status.get(LeadStatus.NEW, 0)
        still_contacted_only = by_status.get(LeadStatus.CONTACTED, 0)
        rejected = by_status.get(LeadStatus.REJECTED, 0)
        qualified = sum(
            by_status.get(s, 0)
            for s in (LeadStatus.QUALIFIED, LeadStatus.APPOINTMENT, LeadStatus.CONTRACT, LeadStatus.CUSTOMER)
        )

        contacted = total - pending
        replied = contacted - still_contacted_only
        handoff = self.conversation_repo.count_distinct_leads_in_state_for_campaign(
            campaign_id, ConversationState.HANDOFF
        )

        response_rate = (replied / contacted * 100) if contacted else 0.0
        qualification_rate = (qualified / replied * 100) if replied else 0.0

        return CampaignAnalytics(
            total=total,
            pending=pending,
            contacted=contacted,
            replied=replied,
            qualified=qualified,
            rejected=rejected,
            handoff=handoff,
            response_rate=response_rate,
            qualification_rate=qualification_rate,
        )

    def _require_campaign(self, campaign_id: UUID) -> Campaign:
        campaign = self.campaign_repo.get_by_id(campaign_id)
        if campaign is None:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        return campaign

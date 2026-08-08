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

from crm.campaign_repository import CampaignRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import CampaignStatus, ConversationChannel, ConversationState, LeadStatus
from domain.models.campaign import Campaign
from domain.models.lead import Lead
from outbound.scheduler import OutboundScheduler


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
        channel: ConversationChannel = ConversationChannel.WHATSAPP,
    ) -> Campaign:
        rules_json = json.dumps(target_rules) if target_rules else None
        campaign = self.campaign_repo.create(name=name, target_rules=rules_json, channel=channel)
        self.db.commit()
        return campaign

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
        return campaign

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

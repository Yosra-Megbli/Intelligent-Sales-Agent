"""
Campaign Engine.

Its one job, per the architecture docs: "who do we contact, when, how many
times, which campaign" - never the language (that's ai/responder.py) and
never the actual sending (that's outbound/sender.py). This module only
selects and assigns leads to a Campaign; it does not talk to any channel.

PURITY GUARANTEE (same discipline as conversation_engine/rules.py): this
module reads target_rules (declarative JSON, e.g. {"region": "Wallonie"})
and calls repository methods to select/assign leads - it never decides a
lead's qualification or conversation state, and it never imports an LLM
client. Everything it changes (Lead.campaign_id, Campaign.total_leads) is
bookkeeping about *who is in the campaign*, not a business decision about
that lead's sales journey.
"""

from __future__ import annotations

import json
from typing import Optional

from crm.campaign_repository import CampaignRepository
from crm.lead_repository import LeadRepository
from domain.enums import CampaignStatus
from domain.models.campaign import Campaign
from domain.models.lead import Lead


class CampaignEngine:
    def __init__(self, db_session):
        self.lead_repo = LeadRepository(db_session)
        self.campaign_repo = CampaignRepository(db_session)

    def select_and_assign_leads(self, campaign: Campaign, limit: int = 100) -> list[Lead]:
        """Select up to `limit` eligible NEW leads (not already assigned to
        any campaign) matching `campaign.target_rules`, assign them to this
        campaign, and update `campaign.total_leads`. Does not send anything -
        see outbound/sender.py for that.
        """
        if campaign.status != CampaignStatus.RUNNING:
            raise ValueError(
                f"Campaign {campaign.id} is {campaign.status.value}, not RUNNING - "
                "start it (CampaignRepository.set_status) before selecting leads."
            )

        target_rules = self._parse_target_rules(campaign.target_rules)
        region = target_rules.get("region")

        leads = self.lead_repo.list_new_for_campaign(region=region, limit=limit)
        for lead in leads:
            self.lead_repo.assign_to_campaign(lead, campaign.id)

        if leads:
            self.campaign_repo.add_to_total_leads(campaign, len(leads))

        return leads

    @staticmethod
    def _parse_target_rules(target_rules: Optional[str]) -> dict:
        if not target_rules:
            return {}
        return json.loads(target_rules)

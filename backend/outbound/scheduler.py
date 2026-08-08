"""
Outbound Scheduler.

Ties `CampaignEngine` (who to assign) and `OutboundSender` (how to send)
together into the repeatable, batched unit of work a cron job / worker tick
calls: "top up every RUNNING campaign with eligible leads, then send one
paced batch of opening messages per campaign."

PACING: reads `business_rules/outbound_rules.yaml` for `batch_size`,
`delay_seconds_between_sends` and `max_leads_assigned_per_tick` - same
"declarative config, never hardcoded" discipline as `followup/engine.py`
reading `followup_rules.yaml`.

DUPLICATE PROTECTION: a lead can only ever be picked up by
`list_pending_for_send` while it is still `LeadStatus.NEW` - the instant
`OutboundSender.send_opening_message` succeeds it flips the lead to
CONTACTED, permanently removing it from every future tick's query. There is
no separate "already sent" flag to get out of sync; the lead's own status
*is* the send record.

PURITY BOUNDARY: like `CampaignEngine` and `OutboundSender`, this module
never imports `ai/*` or `conversation_engine` directly - it only sequences
calls to those two, which is what actually talks to `ConversationService`.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from crm.campaign_repository import CampaignRepository
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel
from domain.models.campaign import Campaign
from outbound.campaign_engine import CampaignEngine
from outbound.sender import OutboundSender
from outbound.senders import build_default_senders

logger = logging.getLogger(__name__)

_RULES_DIR = Path(__file__).resolve().parent.parent / "business_rules"


def _load_yaml(filename: str) -> dict:
    with open(_RULES_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


_OUTBOUND_CONFIG = _load_yaml("outbound_rules.yaml")
BATCH_SIZE: int = _OUTBOUND_CONFIG["batch_size"]
DELAY_SECONDS_BETWEEN_SENDS: int = _OUTBOUND_CONFIG["delay_seconds_between_sends"]
MAX_LEADS_ASSIGNED_PER_TICK: int = _OUTBOUND_CONFIG["max_leads_assigned_per_tick"]


@dataclass
class CampaignTickResult:
    campaign_id: uuid.UUID
    assigned: int = 0
    sent: int = 0
    errors: list[str] = field(default_factory=list)


class OutboundScheduler:
    def __init__(
        self,
        db_session,
        sender: Optional[OutboundSender] = None,
        channel: ConversationChannel = ConversationChannel.WHATSAPP,
    ):
        """`channel` picks which channel every lead in this tick is
        contacted on (a campaign is single-channel per tick, same as
        before - defaults to WhatsApp, unchanged from prior behaviour).
        Pass `ConversationChannel.TELEGRAM` to run a Telegram campaign
        instead; `external_id` for each lead still has to actually resolve
        to something that channel can reach (see `process_campaign`'s
        docstring on this) - picking the channel here doesn't change that.

        When `sender` isn't supplied, this builds one wired with
        `outbound.senders.build_default_senders()` - i.e. real delivery for
        whichever channel(s) have credentials configured in the
        environment, computed-only for the rest (see `OutboundSender`'s own
        docstring). Pass an explicit `OutboundSender` (e.g. one built with
        `senders={}` or a test fake) to opt out of that.
        """
        self.db = db_session
        self.campaign_repo = CampaignRepository(db_session)
        self.lead_repo = LeadRepository(db_session)
        self.engine = CampaignEngine(db_session)
        self.channel = channel
        self.sender = (
            sender if sender is not None else OutboundSender(db_session, senders=build_default_senders())
        )

    def run_tick(self, *, sleep_between_sends: bool = True) -> list[CampaignTickResult]:
        """One scheduler tick across every RUNNING campaign. Commits after
        each campaign so a failure partway through one campaign never rolls
        back progress already made on another."""
        results = []
        for campaign in self.campaign_repo.list_running():
            result = self.process_campaign(campaign, sleep_between_sends=sleep_between_sends)
            results.append(result)
        return results

    def process_campaign(
        self, campaign: Campaign, *, batch_size: Optional[int] = None, sleep_between_sends: bool = True
    ) -> CampaignTickResult:
        result = CampaignTickResult(campaign_id=campaign.id)
        batch_size = batch_size if batch_size is not None else BATCH_SIZE

        # 1. Top up the campaign's assigned leads (idempotent: only ever
        # picks unassigned NEW leads, see CampaignEngine).
        try:
            assigned = self.engine.select_and_assign_leads(campaign, limit=MAX_LEADS_ASSIGNED_PER_TICK)
            result.assigned = len(assigned)
        except ValueError as exc:
            # Campaign isn't RUNNING (e.g. paused between the list_running()
            # call and now) - nothing to do this tick.
            result.errors.append(str(exc))
            return result

        # 2. Send one paced batch of opening messages to leads already
        # assigned but not yet contacted.
        pending = self.lead_repo.list_pending_for_send(campaign.id, limit=batch_size)
        for i, lead in enumerate(pending):
            try:
                self.sender.send_opening_message(
                    lead,
                    campaign,
                    self.channel,
                    external_id=self._resolve_external_id(lead),
                )
                result.sent += 1
                self.db.commit()
            except Exception as exc:  # pragma: no cover - defensive, logged and skipped
                self.db.rollback()
                logger.exception("Failed to send opening message to lead %s: %s", lead.id, exc)
                result.errors.append(f"lead {lead.id}: {exc}")

            if sleep_between_sends and i < len(pending) - 1 and DELAY_SECONDS_BETWEEN_SENDS:
                time.sleep(DELAY_SECONDS_BETWEEN_SENDS)

        if result.assigned and not pending:
            self.db.commit()

        return result

    def _resolve_external_id(self, lead) -> str:
        """What identifies this lead on `self.channel`'s transport.

        - WhatsApp/SMS-shaped channels: the lead's phone number (or its own
          id as a last resort, unchanged from prior behaviour) - a fresh
          WhatsApp message can be sent cold to any phone number.
        - Telegram: Telegram's Bot API can only message a `chat_id` that
          has already started a conversation with the bot (there is no
          "cold DM by phone number" on Telegram) - so an outbound Telegram
          send only actually reaches the customer if this lead already has
          a prior Telegram conversation on file (e.g. they messaged the bot
          inbound first, became a lead via `LeadSource.TELEGRAM`, and this
          campaign is a *re-engagement* send). If no such conversation
          exists yet, this falls back to the lead's own id - `OutboundSender`
          still computes and records the greeting either way, it just has
          nothing real to hand its Telegram sender, exactly like today's
          `TELEGRAM_BOT_TOKEN`-not-configured case.
        """
        if self.channel == ConversationChannel.TELEGRAM:
            from crm.conversation_repository import ConversationRepository

            conversations = ConversationRepository(self.db).list_for_lead(lead.id)
            for conversation in conversations:
                if conversation.channel == ConversationChannel.TELEGRAM and conversation.external_id:
                    return conversation.external_id
            return str(lead.id)
        return lead.phone or str(lead.id)

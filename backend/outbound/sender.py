"""
Outbound Sender.

Given a lead already assigned to a campaign (by `CampaignEngine`), this
module's job is to actually start the conversation, generate the opening
message - via `ConversationService.start_and_greet()`, the exact same
engine/responder pipeline every inbound turn uses - and then, if a real
transport is wired in for that channel (see `outbound/senders.py`), push
that opening message out over it. It then records the CRM side-effects of
"we just contacted this lead": `LeadStatus.CONTACTED`, `last_contact_date`,
`follow_up_attempts`, and `Campaign.sent`.

DELIVERY (full wiring vs. compute-only): `senders` is a plain
`{ConversationChannel: send_message}` dict, `send_message` being a
`(external_id: str, text: str) -> None` callable - exactly the same shape
`channels/telegram.py`'s `TelegramChannel`/`channels/whatsapp.py`'s
`WhatsAppChannel` accept for their own inbound replies. Pass
`outbound.senders.build_default_senders()` (or your own dict, e.g. in
tests, a fake that records calls) to actually deliver; pass nothing (the
default) and this class computes the greeting and updates the CRM exactly
as before, without ever attempting a network call - the same
degrade-gracefully default every other integration in this codebase uses
when its credentials aren't configured.

PURITY BOUNDARY: this module decides nothing about qualification, dialogue
state, or wording - all of that is `conversation_engine`/`ai`'s job via
`ConversationService`. It only sequences "start + greet, deliver over the
wire if we can, then record that we did".
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

from application.conversation_service import ConversationService
from crm.campaign_repository import CampaignRepository
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel, FollowUpCategory, LeadStatus
from domain.models.campaign import Campaign
from domain.models.lead import Lead

logger = logging.getLogger(__name__)


class OutboundSender:
    def __init__(
        self,
        db_session,
        service: Optional[ConversationService] = None,
        senders: Optional[dict[ConversationChannel, Callable[[str, str], None]]] = None,
    ):
        self.db = db_session
        self.service = service if service is not None else ConversationService(db_session)
        self.lead_repo = LeadRepository(db_session)
        self.campaign_repo = CampaignRepository(db_session)
        # Deliberately NOT auto-built from the environment here (unlike
        # `outbound/senders.py`'s own factory) - keeps this class trivially
        # testable/pure by default, same as `TelegramChannel(send_message=None)`.
        # The composition root (`outbound/scheduler.py`, `run_outbound.py`,
        # a future API trigger) decides whether real delivery is wanted.
        self.senders = senders if senders is not None else {}

    def send_opening_message(
        self,
        lead: Lead,
        campaign: Campaign,
        channel: ConversationChannel,
        *,
        external_id: Optional[str] = None,
        language: str = "fr",
    ):
        """Starts a conversation on `channel` for `lead`, generates the
        opening message, and - if a real sender is wired in for `channel`
        (see class docstring) - actually delivers it to `external_id` over
        that channel's transport before returning. Returns the
        `ConversationResponse` from `ConversationService.start_and_greet()`
        either way, so a caller that only wants the computed text (no
        sender configured) still gets it back unchanged.
        """
        _, conversation, response = self.service.start_and_greet(
            channel,
            existing_lead_id=lead.id,
            language=language,
            external_id=external_id,
        )

        send_message = self.senders.get(channel)
        if send_message is not None and external_id and response.response_text:
            try:
                send_message(external_id, response.response_text)
            except Exception:
                # A delivery failure (network, invalid chat_id, provider
                # outage...) must not roll back the CRM bookkeeping below
                # into an inconsistent retry loop, nor crash the caller
                # (e.g. `OutboundScheduler.process_campaign`'s per-lead
                # try/except already handles this too, but this class must
                # behave correctly even when called directly, outside the
                # Scheduler). Logged loudly rather than swallowed silently.
                logger.exception(
                    "Failed to deliver outbound %s message to %s (lead %s) - "
                    "conversation was started and the greeting was recorded, "
                    "but the customer likely never received it.",
                    channel.value,
                    external_id,
                    lead.id,
                )

        lead.last_contact_date = datetime.utcnow()
        lead.follow_up_attempts = (lead.follow_up_attempts or 0) + 1
        if lead.follow_up_category is None:
            lead.follow_up_category = FollowUpCategory.WARM
        self.lead_repo.set_status(lead, LeadStatus.CONTACTED)

        self.campaign_repo.increment_sent(campaign)

        return response

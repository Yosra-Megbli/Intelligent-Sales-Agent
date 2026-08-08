"""
Outbound Voice Sender (dial-out).

Sibling to `outbound/sender.py`, for the Voice channel specifically -
kept as its own module rather than folded into `OutboundSender` because
the two shapes are genuinely different, not just a different transport:

- `OutboundSender.send_opening_message` first generates the greeting (via
  `ConversationService.start_and_greet()`) and then, optionally, delivers
  that already-known text over the wire.
- `OutboundVoiceSender.place_outbound_call` only makes the phone ring.
  There is no text to generate yet and no `Conversation` row created here
  either - Sophie's opening line is only generated once the call is
  *answered* and Twilio requests the (still not-yet-built, see
  `channels/voice/providers/telephony_interface.py`'s module docstring)
  TwiML answer webhook, which is what would call
  `VoiceSessionManager.start_call()` -> `ConversationService.start_and_greet()`
  the same way `OutboundSender` does today for text channels. This module
  stops at "the call is ringing" and records that CRM side-effect; it does
  not itself talk to `ConversationService`, `ai/*`, or
  `conversation_engine` at all.

CRM SIDE-EFFECTS: mirrors `OutboundSender` exactly - `LeadStatus.CONTACTED`,
`last_contact_date`, `follow_up_attempts`, `Campaign.sent` - "we attempted
to reach this lead" is true the moment the call is placed, independent of
whether it's ever answered (same as a WhatsApp/Telegram message being
"sent" regardless of whether it's ever read).

PURITY BOUNDARY: like `OutboundSender`, this module never imports
`ai/*` or `conversation_engine` - it only talks to a `TelephonyProvider`
and the CRM repositories.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from channels.voice.providers.telephony_interface import (
    CallRequest,
    CallResult,
    InvalidPhoneNumberError,
    TelephonyNotConfiguredError,
    TelephonyProvider,
)
from crm.campaign_repository import CampaignRepository
from crm.lead_repository import LeadRepository
from domain.enums import FollowUpCategory, LeadStatus
from domain.models.campaign import Campaign
from domain.models.lead import Lead


class OutboundVoiceSender:
    def __init__(self, db_session, telephony_provider: Optional[TelephonyProvider] = None):
        self.db = db_session
        self.lead_repo = LeadRepository(db_session)
        self.campaign_repo = CampaignRepository(db_session)
        # Unlike `OutboundSender.senders` (which defaults to `{}` and
        # silently skips delivery), there is deliberately no default here:
        # a call either has a real provider to place it with, or this
        # class cannot do its one job at all - see
        # `TelephonyNotConfiguredError`'s docstring for why that has to be
        # an explicit error rather than a silent no-op for Voice.
        self.telephony_provider = telephony_provider

    def place_outbound_call(
        self,
        lead: Lead,
        campaign: Campaign,
        *,
        webhook_url: str,
        from_number: Optional[str] = None,
    ) -> CallResult:
        """Places one outbound call to `lead.phone` via the configured
        `TelephonyProvider`, then records the same "we just contacted this
        lead" CRM bookkeeping `OutboundSender.send_opening_message` does
        for text channels. Raises `TelephonyNotConfiguredError` if no
        provider was supplied, and lets any other `TelephonyError` subclass
        the provider raises propagate - CRM bookkeeping only happens after
        `initiate_call` succeeds (unlike `OutboundSender`, where the
        greeting is generated - and so must be recorded - regardless of
        whether delivery succeeds; here nothing happened at all if the
        call was never placed).
        """
        if self.telephony_provider is None:
            raise TelephonyNotConfiguredError(
                "No TelephonyProvider configured - cannot place an outbound call. "
                "Set TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_VOICE_NUMBER "
                "(see api/dependencies.py's get_telephony_provider)."
            )

        if not lead.phone:
            raise InvalidPhoneNumberError(f"Lead {lead.id} has no phone number - cannot place an outbound call.")

        result = self.telephony_provider.initiate_call(
            CallRequest(to_number=lead.phone, webhook_url=webhook_url, from_number=from_number)
        )

        lead.last_contact_date = datetime.utcnow()
        lead.follow_up_attempts = (lead.follow_up_attempts or 0) + 1
        if lead.follow_up_category is None:
            lead.follow_up_category = FollowUpCategory.WARM
        self.lead_repo.set_status(lead, LeadStatus.CONTACTED)

        self.campaign_repo.increment_sent(campaign)

        return result

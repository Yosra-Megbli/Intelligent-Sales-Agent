"""
Voice Outbound Service (Application layer).

Same layering discipline as `application/campaign_service.py`: the HTTP
layer (`api/voice_routes.py`) never touches a repository or
`OutboundVoiceSender` directly - it only calls this service. This is the
one place that resolves a `lead_id`/`campaign_id` pair into real `Lead`/
`Campaign` rows and hands them to `outbound/voice_sender.py`'s
`OutboundVoiceSender`, the same shape `CampaignService` already uses around
`OutboundScheduler`.

Building `webhook_url` (where Twilio should request TwiML once the call is
answered) is this layer's job, not the route's and not the
`TelephonyProvider`'s - it's plain configuration (a public base URL), not a
telephony-provider concern (see `telephony_interface.py`'s `CallRequest`
docstring) and not an HTTP-parsing concern.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from channels.voice.providers.telephony_interface import CallResult, TelephonyProvider
from crm.campaign_repository import CampaignRepository
from crm.lead_repository import LeadRepository
from outbound.voice_sender import OutboundVoiceSender

# Path Twilio will request once an outbound call is answered - see
# `api/voice_routes.py`'s TwiML answer webhook. Kept as a bare path
# constant (not read from YAML) since it's a fixed URL shape, not a tunable
# business rule, mirroring how `api/routes.py`'s webhook paths are plain
# `@router.post(...)` string literals rather than config.
_TWIML_ANSWER_WEBHOOK_PATH = "/api/voice/twiml"


class LeadNotFoundError(Exception):
    pass


class CampaignNotFoundError(Exception):
    pass


class VoiceOutboundNotConfiguredError(Exception):
    """No `TelephonyProvider` was supplied - see
    `api/dependencies.py`'s `get_telephony_provider()`."""


@dataclass
class OutboundCallOutcome:
    lead_id: UUID
    campaign_id: UUID
    provider_call_id: str
    status: str


class VoiceOutboundService:
    def __init__(self, db_session, telephony_provider: Optional[TelephonyProvider] = None):
        self.db = db_session
        self.lead_repo = LeadRepository(db_session)
        self.campaign_repo = CampaignRepository(db_session)
        self.telephony_provider = telephony_provider

    def initiate_outbound_call(self, lead_id: UUID, campaign_id: UUID) -> OutboundCallOutcome:
        if self.telephony_provider is None:
            raise VoiceOutboundNotConfiguredError(
                "Voice outbound calling isn't configured - set TWILIO_ACCOUNT_SID/"
                "TWILIO_AUTH_TOKEN/TWILIO_VOICE_NUMBER and PUBLIC_BASE_URL."
            )

        lead = self.lead_repo.get_by_id(lead_id)
        if lead is None:
            raise LeadNotFoundError(f"Lead {lead_id} not found")

        campaign = self.campaign_repo.get_by_id(campaign_id)
        if campaign is None:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")

        sender = OutboundVoiceSender(self.db, telephony_provider=self.telephony_provider)
        result: CallResult = sender.place_outbound_call(
            lead, campaign, webhook_url=self._build_webhook_url(lead_id)
        )
        self.db.commit()

        return OutboundCallOutcome(
            lead_id=lead.id,
            campaign_id=campaign.id,
            provider_call_id=result.provider_call_id,
            status=result.status,
        )

    @staticmethod
    def _build_webhook_url(lead_id: UUID) -> str:
        """`lead_id` is carried as a query param so the (still not-yet-built,
        see `outbound/voice_sender.py`'s module docstring) TwiML answer
        webhook can eventually resume this specific lead's conversation
        without needing its own separate lookup mechanism - mirrors how
        Telegram/WhatsApp correlate a webhook back to a conversation via
        `external_id`.
        """
        base_url = (os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")
        return f"{base_url}{_TWIML_ANSWER_WEBHOOK_PATH}?lead_id={lead_id}"

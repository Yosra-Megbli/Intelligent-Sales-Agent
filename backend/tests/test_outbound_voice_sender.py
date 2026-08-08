"""
Tests for outbound/voice_sender.py's OutboundVoiceSender.
"""

import pytest

from channels.voice.providers.telephony_interface import (
    CallRequest,
    CallResult,
    InvalidPhoneNumberError,
    TelephonyError,
    TelephonyNotConfiguredError,
    TelephonyProvider,
)
from crm.campaign_repository import CampaignRepository
from crm.lead_repository import LeadRepository
from domain.enums import CampaignStatus, LeadSource, LeadStatus
from outbound.voice_sender import OutboundVoiceSender


class _FakeTelephonyProvider(TelephonyProvider):
    def __init__(self, result=None, error=None):
        self.result = result or CallResult(provider_call_id="CA123", status="queued")
        self.error = error
        self.calls: list[CallRequest] = []

    def initiate_call(self, request: CallRequest) -> CallResult:
        self.calls.append(request)
        if self.error:
            raise self.error
        return self.result


def _lead_and_campaign(db_session, phone="+32491234567"):
    lead = LeadRepository(db_session).create(source=LeadSource.CSV, first_name="Jean", phone=phone)
    campaign = CampaignRepository(db_session).create(name="Voice campaign")
    CampaignRepository(db_session).set_status(campaign, CampaignStatus.RUNNING)
    return lead, campaign


def test_place_outbound_call_calls_the_provider_with_the_leads_phone_number(db_session):
    lead, campaign = _lead_and_campaign(db_session)
    provider = _FakeTelephonyProvider()
    sender = OutboundVoiceSender(db_session, telephony_provider=provider)

    sender.place_outbound_call(lead, campaign, webhook_url="https://api.ecofix.be/api/voice/twiml")

    assert len(provider.calls) == 1
    assert provider.calls[0].to_number == "+32491234567"
    assert provider.calls[0].webhook_url == "https://api.ecofix.be/api/voice/twiml"


def test_place_outbound_call_marks_the_lead_contacted_and_increments_campaign_sent(db_session):
    lead, campaign = _lead_and_campaign(db_session)
    sender = OutboundVoiceSender(db_session, telephony_provider=_FakeTelephonyProvider())

    result = sender.place_outbound_call(lead, campaign, webhook_url="https://x/twiml")

    assert result.provider_call_id == "CA123"
    assert lead.status == LeadStatus.CONTACTED
    assert lead.last_contact_date is not None
    assert lead.follow_up_attempts == 1
    assert campaign.sent == 1


def test_place_outbound_call_without_a_provider_raises_not_configured(db_session):
    lead, campaign = _lead_and_campaign(db_session)
    sender = OutboundVoiceSender(db_session, telephony_provider=None)

    with pytest.raises(TelephonyNotConfiguredError):
        sender.place_outbound_call(lead, campaign, webhook_url="https://x/twiml")


def test_place_outbound_call_without_a_phone_number_raises_invalid_phone_number(db_session):
    lead, campaign = _lead_and_campaign(db_session, phone=None)
    sender = OutboundVoiceSender(db_session, telephony_provider=_FakeTelephonyProvider())

    with pytest.raises(InvalidPhoneNumberError):
        sender.place_outbound_call(lead, campaign, webhook_url="https://x/twiml")


def test_a_provider_failure_propagates_and_does_not_update_crm_bookkeeping(db_session):
    """Unlike OutboundSender (text), where the greeting is already
    generated/recorded regardless of delivery, nothing happened at all here
    if the call was never placed - so CRM bookkeeping must NOT run."""
    lead, campaign = _lead_and_campaign(db_session)
    provider = _FakeTelephonyProvider(error=TelephonyError("simulated Twilio outage"))
    sender = OutboundVoiceSender(db_session, telephony_provider=provider)

    with pytest.raises(TelephonyError):
        sender.place_outbound_call(lead, campaign, webhook_url="https://x/twiml")

    assert lead.status == LeadStatus.NEW
    assert campaign.sent == 0

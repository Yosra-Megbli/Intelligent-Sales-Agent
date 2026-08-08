"""
Tests for application/voice_outbound_service.py's VoiceOutboundService.
"""

import uuid

import pytest

from channels.voice.providers.telephony_interface import CallRequest, CallResult, TelephonyProvider
from crm.campaign_repository import CampaignRepository
from crm.lead_repository import LeadRepository
from domain.enums import CampaignStatus, LeadSource
from application.voice_outbound_service import (
    CampaignNotFoundError,
    LeadNotFoundError,
    VoiceOutboundNotConfiguredError,
    VoiceOutboundService,
)


class _FakeTelephonyProvider(TelephonyProvider):
    def __init__(self):
        self.calls: list[CallRequest] = []

    def initiate_call(self, request: CallRequest) -> CallResult:
        self.calls.append(request)
        return CallResult(provider_call_id="CA999", status="queued")


def _lead_and_campaign(db_session):
    lead = LeadRepository(db_session).create(source=LeadSource.CSV, first_name="Jean", phone="+32491234567")
    campaign = CampaignRepository(db_session).create(name="Voice campaign")
    CampaignRepository(db_session).set_status(campaign, CampaignStatus.RUNNING)
    db_session.commit()
    return lead, campaign


def test_initiate_outbound_call_returns_the_provider_call_id(db_session):
    lead, campaign = _lead_and_campaign(db_session)
    service = VoiceOutboundService(db_session, telephony_provider=_FakeTelephonyProvider())

    outcome = service.initiate_outbound_call(lead.id, campaign.id)

    assert outcome.provider_call_id == "CA999"
    assert outcome.status == "queued"
    assert outcome.lead_id == lead.id
    assert outcome.campaign_id == campaign.id


def test_initiate_outbound_call_builds_a_webhook_url_carrying_the_lead_id(db_session, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://api.ecofix.be")
    lead, campaign = _lead_and_campaign(db_session)
    provider = _FakeTelephonyProvider()
    service = VoiceOutboundService(db_session, telephony_provider=provider)

    service.initiate_outbound_call(lead.id, campaign.id)

    assert provider.calls[0].webhook_url == f"https://api.ecofix.be/api/voice/twiml?lead_id={lead.id}"


def test_initiate_outbound_call_without_a_provider_raises_not_configured(db_session):
    lead, campaign = _lead_and_campaign(db_session)
    service = VoiceOutboundService(db_session, telephony_provider=None)

    with pytest.raises(VoiceOutboundNotConfiguredError):
        service.initiate_outbound_call(lead.id, campaign.id)


def test_initiate_outbound_call_raises_lead_not_found(db_session):
    _, campaign = _lead_and_campaign(db_session)
    service = VoiceOutboundService(db_session, telephony_provider=_FakeTelephonyProvider())

    with pytest.raises(LeadNotFoundError):
        service.initiate_outbound_call(uuid.uuid4(), campaign.id)


def test_initiate_outbound_call_raises_campaign_not_found(db_session):
    lead, _ = _lead_and_campaign(db_session)
    service = VoiceOutboundService(db_session, telephony_provider=_FakeTelephonyProvider())

    with pytest.raises(CampaignNotFoundError):
        service.initiate_outbound_call(lead.id, uuid.uuid4())

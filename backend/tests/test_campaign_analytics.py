"""
Tests for CampaignService.get_campaign_analytics (Dashboard Priority 1).

Seeds Lead.status / Conversation.current_state directly through the
repositories - no Business Engine involved, same style as
tests/test_dashboard_service.py.
"""

import uuid

import pytest

from application.campaign_service import CampaignService
from crm.campaign_repository import CampaignRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel, ConversationState, LeadSource, LeadStatus


def _make_campaign(db_session, name="Wallonie Juillet"):
    campaign = CampaignRepository(db_session).create(name=name)
    db_session.commit()
    return campaign


def _make_lead(db_session, campaign, status: LeadStatus):
    repo = LeadRepository(db_session)
    lead = repo.create(source=LeadSource.CAMPAIGN)
    repo.assign_to_campaign(lead, campaign.id)
    repo.set_status(lead, status)
    db_session.commit()
    return lead


def test_analytics_for_unknown_campaign_returns_none(db_session):
    assert CampaignService(db_session).get_campaign_analytics(uuid.uuid4()) is None


def test_analytics_on_campaign_with_no_leads(db_session):
    campaign = _make_campaign(db_session)

    analytics = CampaignService(db_session).get_campaign_analytics(campaign.id)

    assert analytics.total == 0
    assert analytics.pending == 0
    assert analytics.contacted == 0
    assert analytics.replied == 0
    assert analytics.qualified == 0
    assert analytics.rejected == 0
    assert analytics.handoff == 0
    assert analytics.response_rate == 0.0
    assert analytics.qualification_rate == 0.0


def test_analytics_bucketing_pending_contacted_replied_qualified_rejected(db_session):
    campaign = _make_campaign(db_session)
    _make_lead(db_session, campaign, LeadStatus.NEW)  # pending
    _make_lead(db_session, campaign, LeadStatus.NEW)  # pending
    _make_lead(db_session, campaign, LeadStatus.CONTACTED)  # contacted, not replied
    _make_lead(db_session, campaign, LeadStatus.ENGAGED)  # contacted + replied
    _make_lead(db_session, campaign, LeadStatus.QUALIFIED)  # contacted + replied + qualified
    _make_lead(db_session, campaign, LeadStatus.CUSTOMER)  # contacted + replied + qualified (funnel)
    _make_lead(db_session, campaign, LeadStatus.REJECTED)  # rejected (still counted as replied/contacted)

    analytics = CampaignService(db_session).get_campaign_analytics(campaign.id)

    assert analytics.total == 7
    assert analytics.pending == 2
    assert analytics.contacted == 5  # everything except the 2 NEW
    assert analytics.replied == 4  # contacted minus the still-plain-CONTACTED one
    assert analytics.qualified == 2  # QUALIFIED + CUSTOMER
    assert analytics.rejected == 1
    assert analytics.response_rate == pytest.approx(4 / 5 * 100)
    assert analytics.qualification_rate == pytest.approx(2 / 4 * 100)


def test_analytics_handoff_counts_leads_with_a_conversation_in_handoff_state(db_session):
    campaign = _make_campaign(db_session)
    lead = _make_lead(db_session, campaign, LeadStatus.QUALIFICATION)
    conversation_repo = ConversationRepository(db_session)
    conversation = conversation_repo.create(lead_id=lead.id, channel=ConversationChannel.WEB)
    conversation_repo.transition_state(conversation, ConversationState.HANDOFF)
    db_session.commit()

    # A second lead on the same campaign not in HANDOFF must not be counted.
    other_lead = _make_lead(db_session, campaign, LeadStatus.QUALIFICATION)
    other_conversation = conversation_repo.create(lead_id=other_lead.id, channel=ConversationChannel.WEB)
    conversation_repo.transition_state(other_conversation, ConversationState.DISCOVERY)
    db_session.commit()

    analytics = CampaignService(db_session).get_campaign_analytics(campaign.id)

    assert analytics.handoff == 1


def test_analytics_scoped_to_a_single_campaign_ignores_other_campaigns_leads(db_session):
    campaign_a = _make_campaign(db_session, name="A")
    campaign_b = _make_campaign(db_session, name="B")
    _make_lead(db_session, campaign_a, LeadStatus.QUALIFIED)
    _make_lead(db_session, campaign_b, LeadStatus.NEW)
    _make_lead(db_session, campaign_b, LeadStatus.NEW)

    analytics_a = CampaignService(db_session).get_campaign_analytics(campaign_a.id)
    analytics_b = CampaignService(db_session).get_campaign_analytics(campaign_b.id)

    assert analytics_a.total == 1
    assert analytics_a.qualified == 1
    assert analytics_b.total == 2
    assert analytics_b.pending == 2


def test_analytics_zero_denominators_handled_safely(db_session):
    campaign = _make_campaign(db_session)
    _make_lead(db_session, campaign, LeadStatus.NEW)  # only a pending lead: contacted == 0

    analytics = CampaignService(db_session).get_campaign_analytics(campaign.id)

    assert analytics.contacted == 0
    assert analytics.response_rate == 0.0
    assert analytics.replied == 0
    assert analytics.qualification_rate == 0.0

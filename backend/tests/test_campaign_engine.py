import json

import pytest

from crm.campaign_repository import CampaignRepository
from crm.lead_repository import LeadRepository
from domain.enums import CampaignStatus, LeadSource, LeadStatus
from outbound.campaign_engine import CampaignEngine


def _running_campaign(db_session, target_rules=None):
    campaign = CampaignRepository(db_session).create(
        name="Wallonie July 2026",
        target_rules=json.dumps(target_rules) if target_rules else None,
    )
    CampaignRepository(db_session).set_status(campaign, CampaignStatus.RUNNING)
    return campaign


def test_selects_new_leads_matching_region(db_session):
    lead_repo = LeadRepository(db_session)
    wallonie_lead = lead_repo.create(source=LeadSource.CSV, email="jean@test.com")
    wallonie_lead.region = "Wallonie"
    flandre_lead = lead_repo.create(source=LeadSource.CSV, email="piet@test.com")
    flandre_lead.region = "Flandre"
    db_session.flush()

    campaign = _running_campaign(db_session, target_rules={"region": "Wallonie"})
    engine = CampaignEngine(db_session)

    selected = engine.select_and_assign_leads(campaign)

    assert [l.id for l in selected] == [wallonie_lead.id]
    assert wallonie_lead.campaign_id == campaign.id
    assert flandre_lead.campaign_id is None


def test_selects_all_new_leads_without_target_rules(db_session):
    lead_repo = LeadRepository(db_session)
    lead_repo.create(source=LeadSource.CSV, email="a@test.com")
    lead_repo.create(source=LeadSource.CSV, email="b@test.com")

    campaign = _running_campaign(db_session)
    engine = CampaignEngine(db_session)

    selected = engine.select_and_assign_leads(campaign)

    assert len(selected) == 2
    assert campaign.total_leads == 2


def test_does_not_reselect_a_lead_already_assigned_to_a_campaign(db_session):
    lead_repo = LeadRepository(db_session)
    lead_repo.create(source=LeadSource.CSV, email="jean@test.com")

    campaign_1 = _running_campaign(db_session)
    campaign_2 = _running_campaign(db_session)
    engine = CampaignEngine(db_session)

    first_batch = engine.select_and_assign_leads(campaign_1)
    second_batch = engine.select_and_assign_leads(campaign_2)

    assert len(first_batch) == 1
    assert len(second_batch) == 0


def test_does_not_select_leads_that_are_not_new(db_session):
    lead_repo = LeadRepository(db_session)
    lead = lead_repo.create(source=LeadSource.CSV, email="jean@test.com")
    lead_repo.set_status(lead, LeadStatus.QUALIFIED)

    campaign = _running_campaign(db_session)
    engine = CampaignEngine(db_session)

    selected = engine.select_and_assign_leads(campaign)

    assert selected == []


def test_raises_if_campaign_is_not_running(db_session):
    campaign = CampaignRepository(db_session).create(name="Draft campaign")
    engine = CampaignEngine(db_session)

    with pytest.raises(ValueError):
        engine.select_and_assign_leads(campaign)


def test_respects_limit(db_session):
    lead_repo = LeadRepository(db_session)
    for i in range(5):
        lead_repo.create(source=LeadSource.CSV, email=f"lead{i}@test.com")

    campaign = _running_campaign(db_session)
    engine = CampaignEngine(db_session)

    selected = engine.select_and_assign_leads(campaign, limit=3)

    assert len(selected) == 3
    assert campaign.total_leads == 3

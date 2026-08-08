"""
Tests for DashboardService (Phase 7) - list/filter/paginate leads, lead
detail (conversations + activities), and the status overview. Seeds data
directly through the repositories (no Business Engine involved - this is a
pure reporting layer over whatever the Engine already persisted).
"""

from datetime import datetime, timedelta

from application.dashboard_service import DashboardService
from crm.activity_repository import ActivityRepository
from crm.campaign_repository import CampaignRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import (
    ActivityType,
    CampaignStatus,
    ConversationChannel,
    ConversationState,
    LeadSource,
    LeadStatus,
)


def _make_lead(db_session, **overrides):
    repo = LeadRepository(db_session)
    lead = repo.create(
        source=overrides.pop("source", LeadSource.WEBSITE),
        first_name=overrides.pop("first_name", None),
        last_name=overrides.pop("last_name", None),
        email=overrides.pop("email", None),
        phone=overrides.pop("phone", None),
    )
    if overrides:
        repo.update_fields(lead, **overrides)
    db_session.commit()
    return lead


# --- list_leads / pagination / filters ------------------------------------------------------


def test_list_leads_returns_everything_by_default(db_session):
    _make_lead(db_session, first_name="Jean")
    _make_lead(db_session, first_name="Marie")

    page = DashboardService(db_session).list_leads()

    assert page.total == 2
    assert len(page.items) == 2


def test_list_leads_filters_by_status(db_session):
    qualified = _make_lead(db_session, first_name="Jean")
    LeadRepository(db_session).set_status(qualified, LeadStatus.QUALIFIED)
    _make_lead(db_session, first_name="Marie")  # stays NEW
    db_session.commit()

    page = DashboardService(db_session).list_leads(status=LeadStatus.QUALIFIED)

    assert page.total == 1
    assert page.items[0].first_name == "Jean"


def test_list_leads_filters_by_region(db_session):
    _make_lead(db_session, first_name="Jean", region="Wallonie")
    _make_lead(db_session, first_name="Marie", region="Flandre")

    page = DashboardService(db_session).list_leads(region="Wallonie")

    assert page.total == 1
    assert page.items[0].first_name == "Jean"


def test_list_leads_filters_by_source(db_session):
    _make_lead(db_session, first_name="Jean", source=LeadSource.WEBSITE)
    _make_lead(db_session, first_name="Marie", source=LeadSource.TELEGRAM)

    page = DashboardService(db_session).list_leads(source=LeadSource.TELEGRAM)

    assert page.total == 1
    assert page.items[0].first_name == "Marie"


def test_list_leads_search_matches_name_email_or_phone_case_insensitively(db_session):
    _make_lead(db_session, first_name="Jean", last_name="Dupont", email="jean.dupont@test.com")
    _make_lead(db_session, first_name="Marie", last_name="Martin", phone="0488112233")

    by_name = DashboardService(db_session).list_leads(search="dupont")
    by_email = DashboardService(db_session).list_leads(search="JEAN.DUPONT")
    by_phone = DashboardService(db_session).list_leads(search="0488112233")

    assert by_name.total == 1 and by_name.items[0].last_name == "Dupont"
    assert by_email.total == 1 and by_email.items[0].last_name == "Dupont"
    assert by_phone.total == 1 and by_phone.items[0].last_name == "Martin"


def test_list_leads_combines_filters_with_and(db_session):
    _make_lead(db_session, first_name="Jean", region="Wallonie", source=LeadSource.WEBSITE)
    _make_lead(db_session, first_name="Marie", region="Wallonie", source=LeadSource.TELEGRAM)

    page = DashboardService(db_session).list_leads(region="Wallonie", source=LeadSource.WEBSITE)

    assert page.total == 1
    assert page.items[0].first_name == "Jean"


def test_list_leads_paginates_and_reports_total_independent_of_page_size(db_session):
    for i in range(5):
        _make_lead(db_session, first_name=f"Lead{i}")

    first_page = DashboardService(db_session).list_leads(limit=2, offset=0)
    second_page = DashboardService(db_session).list_leads(limit=2, offset=2)

    assert first_page.total == 5
    assert len(first_page.items) == 2
    assert second_page.total == 5
    assert len(second_page.items) == 2
    assert {lead.id for lead in first_page.items}.isdisjoint({lead.id for lead in second_page.items})


def test_list_leads_orders_most_recently_created_first(db_session):
    older = _make_lead(db_session, first_name="Older")
    older.created_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()
    newer = _make_lead(db_session, first_name="Newer")

    page = DashboardService(db_session).list_leads()

    assert [lead.id for lead in page.items] == [newer.id, older.id]


# --- get_lead_detail ------------------------------------------------------


def test_get_lead_detail_returns_none_for_unknown_lead(db_session):
    import uuid

    assert DashboardService(db_session).get_lead_detail(uuid.uuid4()) is None


def test_get_lead_detail_includes_conversations_and_activities(db_session):
    lead = _make_lead(db_session, first_name="Jean")
    conversation_repo = ConversationRepository(db_session)
    conversation = conversation_repo.create(lead_id=lead.id, channel=ConversationChannel.WEB)
    ActivityRepository(db_session).log(lead.id, ActivityType.MESSAGE_RECEIVED, details="Bonjour")
    db_session.commit()

    detail = DashboardService(db_session).get_lead_detail(lead.id)

    assert detail.lead.id == lead.id
    assert len(detail.conversations) == 1
    assert detail.conversations[0].id == conversation.id
    assert len(detail.activities) == 1
    assert detail.activities[0].details == "Bonjour"


def test_get_lead_detail_lists_every_conversation_across_channels(db_session):
    lead = _make_lead(db_session, first_name="Jean")
    conversation_repo = ConversationRepository(db_session)
    conversation_repo.create(lead_id=lead.id, channel=ConversationChannel.WEB)
    conversation_repo.create(lead_id=lead.id, channel=ConversationChannel.TELEGRAM, external_id="12345")
    db_session.commit()

    detail = DashboardService(db_session).get_lead_detail(lead.id)

    assert len(detail.conversations) == 2
    assert {c.channel for c in detail.conversations} == {ConversationChannel.WEB, ConversationChannel.TELEGRAM}


# --- get_stats_summary ------------------------------------------------------


def test_get_stats_summary_counts_by_status(db_session):
    lead_repo = LeadRepository(db_session)
    a = _make_lead(db_session, first_name="A")
    b = _make_lead(db_session, first_name="B")
    _make_lead(db_session, first_name="C")  # stays NEW
    lead_repo.set_status(a, LeadStatus.QUALIFIED)
    lead_repo.set_status(b, LeadStatus.QUALIFIED)
    db_session.commit()

    summary = DashboardService(db_session).get_stats_summary()

    assert summary.total_leads == 3
    assert summary.by_status[LeadStatus.QUALIFIED] == 2
    assert summary.by_status[LeadStatus.NEW] == 1


def test_get_stats_summary_on_empty_database(db_session):
    summary = DashboardService(db_session).get_stats_summary()

    assert summary.total_leads == 0
    assert summary.by_status == {}


# --- get_overview (Priority 2, Overview Dashboard) --------------------------------------


def test_get_overview_on_empty_database(db_session):
    overview = DashboardService(db_session).get_overview()

    assert overview.total_leads == 0
    assert overview.active_conversations == 0
    assert overview.active_campaigns == 0
    assert overview.contacted == 0
    assert overview.qualified == 0
    assert overview.rejected == 0
    assert overview.human_handoff == 0
    assert overview.conversion_rate == 0.0


def test_get_overview_computes_headline_metrics(db_session):
    lead_repo = LeadRepository(db_session)
    conversation_repo = ConversationRepository(db_session)
    campaign_repo = CampaignRepository(db_session)

    # Leads across the funnel.
    _make_lead(db_session, first_name="New")  # stays NEW
    contacted_lead = _make_lead(db_session, first_name="Contacted")
    lead_repo.set_status(contacted_lead, LeadStatus.CONTACTED)
    qualified_lead = _make_lead(db_session, first_name="Qualified")
    lead_repo.set_status(qualified_lead, LeadStatus.QUALIFIED)
    customer_lead = _make_lead(db_session, first_name="Customer")
    lead_repo.set_status(customer_lead, LeadStatus.CUSTOMER)
    rejected_lead = _make_lead(db_session, first_name="Rejected")
    lead_repo.set_status(rejected_lead, LeadStatus.REJECTED)
    db_session.commit()

    # Conversations: one active, one handed off to a human, one closed.
    conversation_repo.create(lead_id=contacted_lead.id, channel=ConversationChannel.WEB)
    handoff_conversation = conversation_repo.create(
        lead_id=qualified_lead.id, channel=ConversationChannel.TELEGRAM
    )
    conversation_repo.transition_state(handoff_conversation, ConversationState.HANDOFF)
    closed_conversation = conversation_repo.create(
        lead_id=customer_lead.id, channel=ConversationChannel.WHATSAPP
    )
    conversation_repo.transition_state(closed_conversation, ConversationState.CLOSED)
    db_session.commit()

    # Campaigns: one running, one draft.
    running_campaign = campaign_repo.create(name="Running campaign")
    campaign_repo.set_status(running_campaign, CampaignStatus.RUNNING)
    campaign_repo.create(name="Draft campaign")
    db_session.commit()

    overview = DashboardService(db_session).get_overview()

    assert overview.total_leads == 5
    assert overview.active_conversations == 2  # WEB + HANDOFF, not the CLOSED one
    assert overview.active_campaigns == 1
    assert overview.contacted == 4  # everything except the NEW lead
    assert overview.qualified == 2  # QUALIFIED + CUSTOMER
    assert overview.rejected == 1
    assert overview.human_handoff == 1
    assert overview.conversion_rate == 40.0  # 2 qualified / 5 total leads


# --- list_handoffs (P04, Handoff Queue) --------------------------------------


def test_list_handoffs_on_empty_database(db_session):
    page = DashboardService(db_session).list_handoffs()

    assert page.total == 0
    assert page.items == []


def test_list_handoffs_only_includes_conversations_in_handoff_state(db_session):
    lead = _make_lead(db_session, first_name="Jean")
    other_lead = _make_lead(db_session, first_name="Marie")
    conversation_repo = ConversationRepository(db_session)
    handoff = conversation_repo.create(lead_id=lead.id, channel=ConversationChannel.WHATSAPP)
    conversation_repo.transition_state(handoff, ConversationState.HANDOFF)
    conversation_repo.create(lead_id=other_lead.id, channel=ConversationChannel.WEB)  # still in START
    db_session.commit()

    page = DashboardService(db_session).list_handoffs()

    assert page.total == 1
    assert page.items[0].lead.id == lead.id
    assert page.items[0].conversation.id == handoff.id


def test_list_handoffs_orders_most_recently_handed_off_first(db_session):
    older_lead = _make_lead(db_session, first_name="Older")
    newer_lead = _make_lead(db_session, first_name="Newer")
    conversation_repo = ConversationRepository(db_session)

    older_conv = conversation_repo.create(lead_id=older_lead.id, channel=ConversationChannel.WEB)
    conversation_repo.transition_state(older_conv, ConversationState.HANDOFF)
    older_conv.last_message_at = datetime.utcnow() - timedelta(hours=2)

    newer_conv = conversation_repo.create(lead_id=newer_lead.id, channel=ConversationChannel.WEB)
    conversation_repo.transition_state(newer_conv, ConversationState.HANDOFF)
    db_session.commit()

    page = DashboardService(db_session).list_handoffs()

    assert [entry.lead.id for entry in page.items] == [newer_lead.id, older_lead.id]


def test_list_handoffs_includes_campaign_name(db_session):
    campaign = CampaignRepository(db_session).create(name="Winter push")
    lead = _make_lead(db_session, first_name="Jean", campaign_id=campaign.id)
    conversation_repo = ConversationRepository(db_session)
    conv = conversation_repo.create(lead_id=lead.id, channel=ConversationChannel.WEB)
    conversation_repo.transition_state(conv, ConversationState.HANDOFF)
    db_session.commit()

    page = DashboardService(db_session).list_handoffs()

    assert page.items[0].campaign_name == "Winter push"


def test_list_handoffs_infers_qualified_reason_from_state_changed_activity(db_session):
    lead = _make_lead(db_session, first_name="Jean")
    conversation_repo = ConversationRepository(db_session)
    conv = conversation_repo.create(lead_id=lead.id, channel=ConversationChannel.WEB)
    conversation_repo.transition_state(conv, ConversationState.HANDOFF)
    ActivityRepository(db_session).log(
        lead.id, ActivityType.STATE_CHANGED, details="QUALIFIED -> HANDOFF"
    )
    db_session.commit()

    page = DashboardService(db_session).list_handoffs()

    assert page.items[0].reason == "Qualified — ready for appointment"


def test_list_handoffs_defaults_to_request_human_reason_for_other_transitions(db_session):
    lead = _make_lead(db_session, first_name="Jean")
    conversation_repo = ConversationRepository(db_session)
    conv = conversation_repo.create(lead_id=lead.id, channel=ConversationChannel.WEB)
    conversation_repo.transition_state(conv, ConversationState.HANDOFF)
    ActivityRepository(db_session).log(
        lead.id, ActivityType.STATE_CHANGED, details="DISCOVERY -> HANDOFF"
    )
    db_session.commit()

    page = DashboardService(db_session).list_handoffs()

    assert page.items[0].reason == "Customer asked to speak with a human"


def test_list_handoffs_paginates(db_session):
    conversation_repo = ConversationRepository(db_session)
    for i in range(3):
        lead = _make_lead(db_session, first_name=f"Lead{i}")
        conv = conversation_repo.create(lead_id=lead.id, channel=ConversationChannel.WEB)
        conversation_repo.transition_state(conv, ConversationState.HANDOFF)
    db_session.commit()

    first_page = DashboardService(db_session).list_handoffs(limit=2, offset=0)
    second_page = DashboardService(db_session).list_handoffs(limit=2, offset=2)

    assert first_page.total == 3
    assert len(first_page.items) == 2
    assert second_page.total == 3
    assert len(second_page.items) == 1

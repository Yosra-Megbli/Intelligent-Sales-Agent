import uuid

import pytest

from application.lead_service import InvalidLeadFieldError, LeadNotFoundError, LeadService
from crm.activity_repository import ActivityRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ActivityType, ConversationChannel, LeadSource, MessageRole


def _lead(db_session, **overrides):
    return LeadRepository(db_session).create(source=overrides.pop("source", LeadSource.CSV), **overrides)


def test_update_lead_changes_only_provided_fields(db_session):
    lead = _lead(db_session, first_name="Jean", phone="0611223344")
    db_session.commit()

    updated = LeadService(db_session).update_lead(lead.id, notes="Interesse", region="Wallonie")

    assert updated.notes == "Interesse"
    assert updated.region == "Wallonie"
    assert updated.first_name == "Jean"  # untouched
    assert updated.phone == "0611223344"  # untouched


def test_update_lead_raises_for_unknown_lead(db_session):
    with pytest.raises(LeadNotFoundError):
        LeadService(db_session).update_lead(uuid.uuid4(), notes="x")


def test_update_lead_rejects_engine_owned_fields(db_session):
    """status/qualification_score/campaign_id etc. belong to the Business
    Rules Engine, never the Dashboard's edit-lead form - see
    application/lead_service.py's _EDITABLE_FIELDS."""
    lead = _lead(db_session, first_name="Jean")
    db_session.commit()

    with pytest.raises(InvalidLeadFieldError):
        LeadService(db_session).update_lead(lead.id, status="QUALIFIED")


def test_delete_lead_removes_it(db_session):
    lead = _lead(db_session, first_name="ToDelete")
    db_session.commit()
    lead_id = lead.id

    LeadService(db_session).delete_lead(lead_id)

    assert LeadRepository(db_session).get_by_id(lead_id) is None


def test_delete_lead_raises_for_unknown_lead(db_session):
    with pytest.raises(LeadNotFoundError):
        LeadService(db_session).delete_lead(uuid.uuid4())


def test_delete_lead_cascades_conversations_messages_and_activities(db_session):
    """A lead with real history (conversation + messages + activity log)
    must be fully removable - these rows have a NOT NULL FK to leads.id
    with no ON DELETE CASCADE at the DB level, so the service has to clean
    them up itself in the right order (see LeadRepository.delete's
    docstring) before the lead row itself can go."""
    lead = _lead(db_session, first_name="WithHistory")
    conv_repo = ConversationRepository(db_session)
    conversation = conv_repo.create(lead_id=lead.id, channel=ConversationChannel.WEB)
    conv_repo.add_message(conversation, MessageRole.USER, "Bonjour")
    conv_repo.add_message(conversation, MessageRole.ASSISTANT, "Bonjour !")
    ActivityRepository(db_session).log(lead.id, ActivityType.STATE_CHANGED, details="test")
    db_session.commit()
    lead_id = lead.id
    conversation_id = conversation.id

    LeadService(db_session).delete_lead(lead_id)

    assert LeadRepository(db_session).get_by_id(lead_id) is None
    assert conv_repo.get_by_id(conversation_id) is None
    assert ActivityRepository(db_session).list_for_lead(lead_id) == []

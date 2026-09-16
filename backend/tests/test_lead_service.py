import uuid

import pytest

from application.lead_service import (
    DuplicateLeadError,
    InvalidLeadFieldError,
    LeadNotFoundError,
    LeadService,
    RijksregisternummerRejectedError,
)
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


def test_delete_lead_logs_a_gdpr_record_that_survives_the_delete(db_session, caplog):
    """The Activity table can't hold this record - it's deleted along with
    every other activity for this lead in the same operation. The GDPR
    trail lives in the application logger instead (see delete_lead's
    docstring) - assert it's actually written, not just documented."""
    import logging

    lead = _lead(db_session, first_name="ToDelete")
    db_session.commit()
    lead_id = lead.id

    with caplog.at_level(logging.INFO, logger="application.lead_service"):
        LeadService(db_session).delete_lead(lead_id)

    assert any(str(lead_id) in record.message for record in caplog.records)


# --- create_lead (manual creation) ----------------------------------------------------


def test_create_lead_persists_core_and_extra_fields(db_session):
    lead = LeadService(db_session).create_lead(
        first_name="Marie",
        last_name="Lambert",
        email="marie@example.com",
        phone="0491234567",
        region="Wallonie",
        city="Namur",
        customer_type="particulier",
        current_supplier="Engie",
        ean="541448911001234567",
        date_of_birth="15/03/1990",
    )

    assert lead.source == LeadSource.MANUAL
    assert lead.first_name == "Marie"
    assert lead.region == "Wallonie"
    assert lead.city == "Namur"
    assert lead.ean == "541448911001234567"
    assert lead.date_of_birth == "15/03/1990"


def test_create_lead_logs_a_lead_created_activity(db_session):
    lead = LeadService(db_session).create_lead(first_name="Marie", email="marie@example.com")

    activities = ActivityRepository(db_session).list_for_lead(lead.id)
    assert any(a.type == ActivityType.LEAD_CREATED for a in activities)


def test_create_lead_with_no_fields_at_all(db_session):
    """Every field is optional - a bare lead (name added later) must not
    be rejected just because nothing was filled in yet."""
    lead = LeadService(db_session).create_lead()
    assert lead.source == LeadSource.MANUAL
    assert lead.email is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("email", "not-an-email"),
        ("phone", "123"),
        ("ean", "12345"),
        ("date_of_birth", "1990-03-15"),
        ("region", "Bruxelles"),
    ],
)
def test_create_lead_rejects_invalid_fields(db_session, field, value):
    with pytest.raises(InvalidLeadFieldError):
        LeadService(db_session).create_lead(**{field: value})


def test_create_lead_rejects_duplicate_via_find_duplicate(db_session):
    LeadService(db_session).create_lead(email="dup@example.com")

    with pytest.raises(DuplicateLeadError):
        LeadService(db_session).create_lead(email="dup@example.com")


def test_create_lead_rejects_a_rijksregisternummer_looking_value(db_session):
    with pytest.raises(RijksregisternummerRejectedError):
        LeadService(db_session).create_lead(first_name="85073003328")  # valid RRN checksum


def test_create_lead_accepts_an_11_digit_value_that_fails_the_rrn_checksum(db_session):
    """Not every 11-digit string is a Rijksregisternummer - only one whose
    checksum actually validates. A coincidental 11-digit reference number
    must not be falsely rejected."""
    lead = LeadService(db_session).create_lead(first_name="12345678901")
    assert lead.first_name == "12345678901"

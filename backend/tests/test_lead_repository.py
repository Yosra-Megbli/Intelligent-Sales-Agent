from datetime import datetime, timedelta

from crm.lead_repository import LeadRepository
from domain.enums import FollowUpCategory, LeadSource, LeadStatus, RejectionReason


def test_create_lead_defaults_to_new(db_session):
    repo = LeadRepository(db_session)
    lead = repo.create(source=LeadSource.WEBSITE, email="jean@test.com")

    assert lead.status == LeadStatus.NEW
    assert lead.source == LeadSource.WEBSITE
    assert lead.follow_up_attempts == 0


def test_find_duplicate_by_email(db_session):
    repo = LeadRepository(db_session)
    repo.create(source=LeadSource.CSV, email="jean@test.com")

    duplicate = repo.find_duplicate(email="jean@test.com", phone=None)
    assert duplicate is not None
    assert duplicate.email == "jean@test.com"


def test_find_duplicate_returns_none_when_no_match(db_session):
    repo = LeadRepository(db_session)
    repo.create(source=LeadSource.CSV, email="jean@test.com")

    duplicate = repo.find_duplicate(email="other@test.com", phone="0488000000")
    assert duplicate is None


def test_find_duplicate_matches_email_case_insensitively(db_session):
    repo = LeadRepository(db_session)
    existing = repo.create(source=LeadSource.CSV, email="Existing@Email.com")

    duplicate = repo.find_duplicate(email="existing@email.com", phone=None)
    assert duplicate is not None
    assert duplicate.id == existing.id


def test_create_populates_dedup_columns_from_email_and_phone(db_session):
    """P1-2: dedup_email/dedup_phone are what the unique indexes actually
    constrain (see domain/models/lead.py) - creation must always keep them
    in sync with email/phone (lowercased for email)."""
    repo = LeadRepository(db_session)
    lead = repo.create(source=LeadSource.WEBSITE, email="Jean@Test.com", phone=" 0499998877 ")

    assert lead.dedup_email == "jean@test.com"
    assert lead.dedup_phone == "0499998877"


def test_find_duplicate_excludes_the_leads_own_id(db_session):
    """Part of the F-003 fix: by the time DATA_VALIDATION runs, the lead
    being validated already has its own email/phone saved - without
    exclude_lead_id, find_duplicate() would always "find" the lead itself
    and every qualification would be rejected as a duplicate of itself."""
    repo = LeadRepository(db_session)
    lead = repo.create(source=LeadSource.WEBSITE, email="jean@test.com", phone="0488112233")

    duplicate = repo.find_duplicate(email="jean@test.com", phone="0488112233", exclude_lead_id=lead.id)

    assert duplicate is None


def test_find_duplicate_still_finds_a_different_lead_with_the_same_contact_info(db_session):
    """The second lead acquires the colliding email the same way the live
    F-003 flow does - via update_fields() mid-conversation, after being
    created with none - not via create(), which is the one place
    dedup_email/dedup_phone (and their unique indexes, P1-2) are set. Two
    leads both *created* with the same email is exactly what P1-2 now
    prevents at the DB level (see test_conversation_service.py's race-
    condition test); this test is about find_duplicate() still finding a
    same-email lead that legitimately holds it for another reason."""
    repo = LeadRepository(db_session)
    existing = repo.create(source=LeadSource.CSV, email="jean@test.com")
    new_lead = repo.create(source=LeadSource.WEBSITE)
    repo.update_fields(new_lead, email="jean@test.com")

    duplicate = repo.find_duplicate(email="jean@test.com", phone=None, exclude_lead_id=new_lead.id)

    assert duplicate is not None
    assert duplicate.id == existing.id


def test_set_status_to_rejected_records_reason(db_session):
    repo = LeadRepository(db_session)
    lead = repo.create(source=LeadSource.WEBSITE)

    repo.set_status(lead, LeadStatus.REJECTED, rejection_reason=RejectionReason.OUT_OF_COVERAGE)

    assert lead.status == LeadStatus.REJECTED
    assert lead.rejection_reason == RejectionReason.OUT_OF_COVERAGE


def test_set_status_to_qualified_stamps_qualified_at(db_session):
    repo = LeadRepository(db_session)
    lead = repo.create(source=LeadSource.WEBSITE)
    assert lead.qualified_at is None

    repo.set_status(lead, LeadStatus.QUALIFIED)

    assert lead.status == LeadStatus.QUALIFIED
    assert lead.qualified_at is not None


def test_schedule_follow_up_does_not_increment_attempts_regression_f015(db_session):
    """Regression test for F-015 (BAT SC-104-106): scheduling a follow-up
    date/category must never bump follow_up_attempts by itself - only an
    actual send should (see increment_follow_up_attempts below). Before the
    fix, this call alone silently consumed one of max_follow_up_attempts
    before any message had ever been sent."""
    repo = LeadRepository(db_session)
    lead = repo.create(source=LeadSource.WEBSITE)

    next_date = datetime.utcnow() + timedelta(days=3)
    repo.schedule_follow_up(lead, next_date, FollowUpCategory.WARM)
    repo.schedule_follow_up(lead, next_date, FollowUpCategory.WARM)

    assert lead.follow_up_attempts == 0
    assert lead.follow_up_category == FollowUpCategory.WARM


def test_increment_follow_up_attempts(db_session):
    repo = LeadRepository(db_session)
    lead = repo.create(source=LeadSource.WEBSITE)

    repo.increment_follow_up_attempts(lead)
    repo.increment_follow_up_attempts(lead)

    assert lead.follow_up_attempts == 2


def test_list_due_for_follow_up(db_session):
    repo = LeadRepository(db_session)
    due_lead = repo.create(source=LeadSource.WEBSITE, email="due@test.com")
    repo.schedule_follow_up(due_lead, datetime.utcnow() - timedelta(days=1), FollowUpCategory.WARM)

    future_lead = repo.create(source=LeadSource.WEBSITE, email="future@test.com")
    repo.schedule_follow_up(future_lead, datetime.utcnow() + timedelta(days=1), FollowUpCategory.WARM)

    stopped_lead = repo.create(source=LeadSource.WEBSITE, email="stopped@test.com")
    repo.schedule_follow_up(stopped_lead, datetime.utcnow() - timedelta(days=1), FollowUpCategory.STOPPED)

    due = repo.list_due_for_follow_up()
    due_emails = {lead.email for lead in due}

    assert "due@test.com" in due_emails
    assert "future@test.com" not in due_emails
    assert "stopped@test.com" not in due_emails

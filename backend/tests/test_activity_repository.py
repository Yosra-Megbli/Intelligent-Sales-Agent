from crm.activity_repository import ActivityRepository
from crm.lead_repository import LeadRepository
from domain.enums import ActivityType, LeadSource


def test_log_and_list_activities_for_lead(db_session):
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE)
    repo = ActivityRepository(db_session)

    repo.log(lead.id, ActivityType.MESSAGE_SENT, details="Bonjour Jean...")
    repo.log(lead.id, ActivityType.MESSAGE_RECEIVED, details="Oui je suis intéressé")
    repo.log(lead.id, ActivityType.STATUS_CHANGED, details="NEW -> CONTACTED")

    activities = repo.list_for_lead(lead.id)
    assert len(activities) == 3
    # most recent first
    assert activities[0].type == ActivityType.STATUS_CHANGED

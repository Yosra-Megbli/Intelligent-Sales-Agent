from application.lead_import_service import LeadImportService
from crm.lead_repository import LeadRepository
from domain.enums import LeadSource


def _csv(*rows: str, header: str = "name,phone,email,region,source,provider,notes") -> str:
    return "\n".join([header, *rows])


def test_import_creates_new_lead_with_extra_fields(db_session):
    csv_text = _csv("Karim Test,0470111222,karim@test.com,Wallonie,Website,MetaAds,Interesse par le solaire")

    report = LeadImportService(db_session).import_csv(csv_text)

    assert report.rows_read == 1
    assert report.created == 1
    assert report.updated == 0
    assert report.duplicates == 0
    assert report.skipped == 0
    assert report.errors == 0

    lead = LeadRepository(db_session).get_by_email("karim@test.com")
    assert lead is not None
    assert lead.first_name == "Karim"
    assert lead.last_name == "Test"
    assert lead.source == LeadSource.CSV
    assert lead.region == "Wallonie"
    assert lead.provider == "MetaAds"
    assert lead.notes == "Interesse par le solaire"


def test_import_never_creates_a_duplicate_lead_when_email_already_exists(db_session):
    repo = LeadRepository(db_session)
    repo.create(source=LeadSource.WEBSITE, email="jean@test.com", phone="0488000000")

    report = LeadImportService(db_session).import_csv(
        _csv("Jean Dupont,0488000000,jean@test.com,Bruxelles,,,")
    )

    assert report.created == 0
    assert report.duplicates == 1

    all_leads = db_session.query(type(repo.get_by_email("jean@test.com"))).all()
    assert len(all_leads) == 1


def test_import_updates_existing_lead_found_by_phone_with_non_empty_fields_only(db_session):
    repo = LeadRepository(db_session)
    lead = repo.create(source=LeadSource.WHATSAPP, phone="0499887766")
    repo.update_fields(lead, region="Flandre")

    report = LeadImportService(db_session).import_csv(
        _csv(",0499887766,,,,ProviderX,Rappeler la semaine prochaine")
    )

    assert report.duplicates == 1
    assert report.updated == 1
    # region wasn't in the CSV row (blank) - must NOT be erased
    assert lead.region == "Flandre"
    assert lead.provider == "ProviderX"
    assert lead.notes == "Rappeler la semaine prochaine"


def test_import_skips_row_without_email_or_phone(db_session):
    report = LeadImportService(db_session).import_csv(_csv("Sans Contact,,,,,,"))

    assert report.skipped == 1
    assert report.created == 0


def test_import_report_has_correct_totals_across_mixed_rows(db_session):
    repo = LeadRepository(db_session)
    repo.create(source=LeadSource.WEBSITE, email="existing@test.com")

    csv_text = _csv(
        "New One,0470000001,new1@test.com,,,,",
        "Existing One,,existing@test.com,,,,",
        "No Contact,,,,,,",
    )
    report = LeadImportService(db_session).import_csv(csv_text)

    assert report.rows_read == 3
    assert report.created == 1
    assert report.duplicates == 1
    assert report.skipped == 1
    assert report.errors == 0


def test_preview_csv_does_not_write_to_the_database(db_session):
    preview = LeadImportService(db_session).preview_csv(
        _csv("Karim Test,0470111222,karim@test.com,Wallonie,,,")
    )

    assert preview.total_rows == 1
    assert preview.rows[0].would_be_duplicate is False
    assert preview.rows_missing_identifier == 0
    assert LeadRepository(db_session).get_by_email("karim@test.com") is None


def test_preview_csv_flags_duplicates_and_missing_identifiers(db_session):
    repo = LeadRepository(db_session)
    repo.create(source=LeadSource.WEBSITE, email="jean@test.com")

    preview = LeadImportService(db_session).preview_csv(
        _csv(
            "Jean Dupont,,jean@test.com,,,,",
            "No Contact,,,,,,",
        )
    )

    assert preview.rows[0].would_be_duplicate is True
    assert preview.rows[1].missing_identifier is True
    assert preview.rows_missing_identifier == 1

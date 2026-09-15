from datetime import date

from crm.lead_repository import LeadRepository
from conversation_engine import rules
from conversation_engine.actions import ActionType
from domain.enums import CustomerType, LeadSource, Region


def _lead(db_session, **overrides):
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE)
    for key, value in overrides.items():
        setattr(lead, key, value)
    db_session.flush()
    return lead


def test_missing_field_groups_all_missing_on_fresh_lead(db_session):
    lead = _lead(db_session)
    assert rules.missing_field_groups(lead) == [
        "customer_type",
        "location",
        "current_supplier",
        "contact",
        "ean",
    ]


def test_next_qualification_action_follows_fixed_order(db_session):
    lead = _lead(db_session)
    action = rules.next_qualification_action(lead)
    assert action.type == ActionType.ASK_FIELD
    assert action.field == "customer_type"

    lead.customer_type = CustomerType.PARTICULIER
    action = rules.next_qualification_action(lead)
    assert action.field == "location"

    lead.region = Region.WALLONIE
    lead.city = "Charleroi"
    action = rules.next_qualification_action(lead)
    assert action.field == "current_supplier"

    lead.current_supplier = "Engie"
    action = rules.next_qualification_action(lead)
    assert action.field == "contact"

    lead.first_name = "Jean"
    lead.last_name = "Dupont"
    lead.email = "jean@test.com"
    lead.phone = "0488112233"
    # date_of_birth still missing -> contact still incomplete
    action = rules.next_qualification_action(lead)
    assert action.field == "contact"

    lead.date_of_birth = "15/05/1990"
    action = rules.next_qualification_action(lead)
    assert action.field == "ean"

    lead.ean = "541234567890123456"
    action = rules.next_qualification_action(lead)
    assert action.type == ActionType.VALIDATE
    assert action.field is None


def test_ean_is_last_in_collection_order():
    assert rules.REQUIRED_FIELD_ORDER[-1] == "ean"


def test_validate_ean_valid():
    assert rules.validate_ean("541234567890123456") is True


def test_validate_ean_wrong_length():
    assert rules.validate_ean("54123") is False


def test_validate_ean_non_numeric():
    assert rules.validate_ean("54123ABC90123456") is False


def test_validate_email():
    assert rules.validate_email("jean@test.com") is True
    assert rules.validate_email("jean-at-test.com") is False
    assert rules.validate_email(None) is False


def test_validate_phone():
    assert rules.validate_phone("0488112233") is True
    assert rules.validate_phone("+32488112233") is False  # MVP pattern expects local format
    assert rules.validate_phone(None) is False


def test_validate_date_of_birth():
    assert rules.validate_date_of_birth("15/05/1990") is True
    assert rules.validate_date_of_birth("01/01/2000") is True
    assert rules.validate_date_of_birth("31/02/1990") is False  # invalid calendar date
    assert rules.validate_date_of_birth("1990-05-15") is False  # not DD/MM/YYYY
    assert rules.validate_date_of_birth("15/5/1990") is False   # not strict 2-digit month
    assert rules.validate_date_of_birth("abc") is False
    assert rules.validate_date_of_birth(None) is False


def test_is_adult():
    ref = date(2026, 9, 15)
    # 26 years old -> adult
    assert rules.is_adult("15/05/2000", min_age=18, reference_date=ref) is True
    # Exactly 18 years old today (born 15/09/2008) -> adult
    assert rules.is_adult("15/09/2008", min_age=18, reference_date=ref) is True
    # Turns 18 tomorrow (born 16/09/2008) -> underage
    assert rules.is_adult("16/09/2008", min_age=18, reference_date=ref) is False
    # 11 years old -> underage
    assert rules.is_adult("15/05/2015", min_age=18, reference_date=ref) is False
    # Invalid date -> not adult
    assert rules.is_adult("invalid", min_age=18, reference_date=ref) is False


def test_region_coverage():
    assert rules.is_region_covered("Wallonie") is True
    assert rules.is_region_covered("Flandre") is True
    assert rules.is_region_covered("Bruxelles") is False  # Ecofix does not serve Brussels (AGENTS.md rule #4)
    assert rules.is_region_covered("Paris") is False


def test_decide_validation_brussels_rejected_out_of_coverage(db_session):
    lead = _lead(
        db_session,
        customer_type=CustomerType.PARTICULIER,
        region="Bruxelles",
        city="Ixelles",
        current_supplier="Total Energies",
        first_name="Claire",
        last_name="Dupont",
        email="claire@test.be",
        phone="0477112233",
        date_of_birth="15/05/1988",
        ean="541448911001234567",
    )
    action = rules.decide_validation(lead)
    assert action.type == ActionType.REJECT
    assert action.reason.value == "OUT_OF_COVERAGE"


def test_decide_validation_out_of_coverage_takes_priority(db_session):
    lead = _lead(
        db_session,
        customer_type=CustomerType.PARTICULIER,
        region="Paris",
        city="Paris",
        current_supplier="EDF",
        first_name="Jean",
        last_name="Dupont",
        email="jean@test.com",
        phone="0488112233",
        date_of_birth="15/05/1990",
        ean="541234567890123456",
    )
    action = rules.decide_validation(lead)
    assert action.type == ActionType.REJECT
    assert action.reason.value == "OUT_OF_COVERAGE"


def test_decide_validation_rejects_duplicate_regression_f003(db_session):
    lead = _lead(
        db_session,
        customer_type=CustomerType.PARTICULIER,
        region=Region.WALLONIE,
        city="Namur",
        current_supplier="Engie",
        first_name="Jean",
        last_name="Dupont",
        email="jean@test.com",
        phone="0488112233",
        date_of_birth="15/05/1990",
        ean="541234567890123456",
    )
    action = rules.decide_validation(lead, is_duplicate=True)
    assert action.type == ActionType.REJECT
    assert action.reason.value == "DUPLICATE_LEAD"


def test_decide_validation_out_of_coverage_still_takes_priority_over_duplicate(db_session):
    lead = _lead(
        db_session,
        customer_type=CustomerType.PARTICULIER,
        region="Paris",
        city="Paris",
        current_supplier="EDF",
        first_name="Jean",
        last_name="Dupont",
        email="jean@test.com",
        phone="0488112233",
        date_of_birth="15/05/1990",
        ean="541234567890123456",
    )
    action = rules.decide_validation(lead, is_duplicate=True)
    assert action.type == ActionType.REJECT
    assert action.reason.value == "OUT_OF_COVERAGE"


def test_decide_validation_not_a_duplicate_by_default(db_session):
    lead = _lead(
        db_session,
        customer_type=CustomerType.PARTICULIER,
        region=Region.WALLONIE,
        city="Namur",
        current_supplier="Engie",
        first_name="Jean",
        last_name="Dupont",
        email="jean@test.com",
        phone="0488112233",
        date_of_birth="15/05/1990",
        ean="541234567890123456",
    )
    action = rules.decide_validation(lead)
    assert action.type == ActionType.QUALIFY


def test_decide_validation_invalid_date_of_birth_routes_back_to_contact(db_session):
    lead = _lead(
        db_session,
        customer_type=CustomerType.PARTICULIER,
        region=Region.WALLONIE,
        city="Namur",
        current_supplier="Engie",
        first_name="Jean",
        last_name="Dupont",
        email="jean@test.com",
        phone="0488112233",
        date_of_birth="31/02/1990",
        ean="541234567890123456",
    )
    action = rules.decide_validation(lead)
    assert action.type == ActionType.CORRECT_FIELD
    assert action.field == "contact"


def test_decide_validation_underage_rejects_as_invalid_customer(db_session):
    lead = _lead(
        db_session,
        customer_type=CustomerType.PARTICULIER,
        region=Region.WALLONIE,
        city="Namur",
        current_supplier="Engie",
        first_name="Jean",
        last_name="Dupont",
        email="jean@test.com",
        phone="0488112233",
        date_of_birth="15/05/2015",
        ean="541234567890123456",
    )
    action = rules.decide_validation(lead)
    assert action.type == ActionType.REJECT
    assert action.reason.value == "INVALID_CUSTOMER"


def test_decide_validation_invalid_ean_routes_back_to_ean(db_session):
    lead = _lead(
        db_session,
        customer_type=CustomerType.PARTICULIER,
        region=Region.WALLONIE,
        city="Charleroi",
        current_supplier="Engie",
        first_name="Jean",
        last_name="Dupont",
        email="jean@test.com",
        phone="0488112233",
        date_of_birth="15/05/1990",
        ean="12345",
    )
    action = rules.decide_validation(lead)
    assert action.type == ActionType.CORRECT_FIELD
    assert action.field == "ean"


def test_decide_validation_all_valid(db_session):
    lead = _lead(
        db_session,
        customer_type=CustomerType.PARTICULIER,
        region=Region.WALLONIE,
        city="Charleroi",
        current_supplier="Engie",
        first_name="Jean",
        last_name="Dupont",
        email="jean@test.com",
        phone="0488112233",
        date_of_birth="15/05/1990",
        ean="541234567890123456",
    )
    action = rules.decide_validation(lead)
    assert action.type == ActionType.QUALIFY


def test_rules_module_never_touches_the_database():
    import ast
    import inspect

    from conversation_engine import rules as rules_module

    tree = ast.parse(inspect.getsource(rules_module))

    forbidden_call_names = {"flush", "commit", "add", "save"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            assert "crm" not in module_name and not any("repository" in n.lower() for n in names), (
                f"rules.py must not import repositories, found: {module_name or names}"
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_call_names, (
                f"rules.py must stay pure, found a call to '.{node.func.attr}()'"
            )


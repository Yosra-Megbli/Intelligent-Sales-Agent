from crm.lead_repository import LeadRepository
from conversation_engine import state_machine
from conversation_engine.transitions import Event, EventType
from domain.enums import ConversationChannel, ConversationState, CustomerType, LeadSource, Region, RejectionReason
from domain.models.conversation import Conversation


def _lead(db_session, **overrides):
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE)
    for key, value in overrides.items():
        setattr(lead, key, value)
    db_session.flush()
    return lead


def _conversation(db_session, lead, consecutive_detour_count=0):
    conversation = Conversation(
        lead_id=lead.id,
        channel=ConversationChannel.WEB,
        current_state=ConversationState.FAQ,
        consecutive_detour_count=consecutive_detour_count,
    )
    db_session.add(conversation)
    db_session.flush()
    return conversation


def test_start_goes_to_greeting(db_session):
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.START, Event(EventType.CUSTOMER_MESSAGE), lead
    )
    assert decision.next_state == ConversationState.GREETING


def test_greeting_goes_to_discovery(db_session):
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.GREETING, Event(EventType.CUSTOMER_MESSAGE), lead
    )
    assert decision.next_state == ConversationState.DISCOVERY


def test_discovery_goes_to_intent_confirmation_on_information(db_session):
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.DISCOVERY, Event(EventType.PROVIDE_INFORMATION), lead
    )
    assert decision.next_state == ConversationState.INTENT_CONFIRMATION


def test_discovery_goes_to_intent_confirmation_on_change_intent_no_regression_f001(db_session):
    """Regression test for F-001 (BAT SC-059): a customer who answers
    DISCOVERY's open question with a direct "no" must still reach
    INTENT_CONFIRMATION for the formal confirmation - not get stuck being
    asked ASK_INTENT forever. Before the fix, CHANGE_INTENT_NO here fell
    through to the "ask again" fallback and never advanced."""
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.DISCOVERY, Event(EventType.CHANGE_INTENT_NO), lead
    )
    assert decision.next_state == ConversationState.INTENT_CONFIRMATION
    assert decision.required_action == "CONFIRM_INTENT"


def test_discovery_goes_to_intent_confirmation_on_change_intent_yes_regression_f001(db_session):
    """Symmetric case to the F-001 regression test above - CHANGE_INTENT_YES
    at DISCOVERY had the exact same bug."""
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.DISCOVERY, Event(EventType.CHANGE_INTENT_YES), lead
    )
    assert decision.next_state == ConversationState.INTENT_CONFIRMATION
    assert decision.required_action == "CONFIRM_INTENT"


def test_discovery_still_reasks_on_a_type_it_genuinely_does_not_expect(db_session):
    """The defensive fallback (re-ask ASK_INTENT) is intentionally kept for
    event types DISCOVERY has no real answer for - FOLLOW_UP_DUE is
    scheduler-only and should never actually reach DISCOVERY in practice,
    but this confirms the fallback still works rather than crashing if it
    somehow did."""
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.DISCOVERY, Event(EventType.FOLLOW_UP_DUE), lead
    )
    assert decision.next_state == ConversationState.DISCOVERY
    assert decision.required_action == "ASK_INTENT"


def test_intent_confirmation_yes_moves_to_first_qualification_state(db_session):
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.INTENT_CONFIRMATION, Event(EventType.CHANGE_INTENT_YES), lead
    )
    assert decision.next_state == ConversationState.COLLECT_CUSTOMER_TYPE
    assert lead.change_intent is True


def test_intent_confirmation_no_rejects_with_no_change_intent(db_session):
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.INTENT_CONFIRMATION, Event(EventType.CHANGE_INTENT_NO), lead
    )
    assert decision.next_state == ConversationState.REJECTED
    assert decision.rejection_reason == RejectionReason.NO_CHANGE_INTENT


def test_qualification_step_progresses_field_by_field(db_session):
    lead = _lead(db_session, customer_type=CustomerType.PARTICULIER)
    decision = state_machine.decide(
        ConversationState.COLLECT_CUSTOMER_TYPE, Event(EventType.PROVIDE_INFORMATION), lead
    )
    assert decision.next_state == ConversationState.COLLECT_LOCATION


def test_location_group_asks_only_for_city_when_region_already_known(db_session):
    lead = _lead(db_session, customer_type=CustomerType.PARTICULIER, region=Region.WALLONIE)
    decision = state_machine.decide(
        ConversationState.COLLECT_CUSTOMER_TYPE, Event(EventType.PROVIDE_INFORMATION), lead
    )
    assert decision.next_state == ConversationState.COLLECT_LOCATION
    assert decision.required_action == "ASK_CITY_ONLY"


def test_data_validation_success_moves_to_qualified(db_session):
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
        ean="541234567890123456",
    )
    decision = state_machine.decide(
        ConversationState.DATA_VALIDATION, Event(EventType.PROVIDE_INFORMATION), lead
    )
    assert decision.next_state == ConversationState.QUALIFIED


def test_data_validation_invalid_ean_routes_back_to_collect_ean(db_session):
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
        ean="12345",
    )
    decision = state_machine.decide(
        ConversationState.DATA_VALIDATION, Event(EventType.PROVIDE_INFORMATION), lead
    )
    assert decision.next_state == ConversationState.COLLECT_EAN
    assert decision.required_action == "ASK_EAN_CORRECTION"


def test_data_validation_out_of_coverage_rejects(db_session):
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
        ean="541234567890123456",
    )
    decision = state_machine.decide(
        ConversationState.DATA_VALIDATION, Event(EventType.PROVIDE_INFORMATION), lead
    )
    assert decision.next_state == ConversationState.REJECTED
    assert decision.rejection_reason == RejectionReason.OUT_OF_COVERAGE


def test_data_validation_rejects_duplicate_when_flagged_regression_f003(db_session):
    """Regression test for F-003: confirms decide() actually forwards
    is_duplicate to rules.decide_validation() rather than silently dropping
    it - the full live-flow proof (ConversationEngine really calling
    find_duplicate()) lives in test_conversation_engine.py."""
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
        ean="541234567890123456",
    )
    decision = state_machine.decide(
        ConversationState.DATA_VALIDATION, Event(EventType.PROVIDE_INFORMATION), lead, is_duplicate=True
    )
    assert decision.next_state == ConversationState.REJECTED
    assert decision.rejection_reason == RejectionReason.DUPLICATE_LEAD


def test_data_validation_is_duplicate_defaults_to_false(db_session):
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
        ean="541234567890123456",
    )
    decision = state_machine.decide(
        ConversationState.DATA_VALIDATION, Event(EventType.PROVIDE_INFORMATION), lead
    )
    assert decision.next_state == ConversationState.QUALIFIED


def test_qualified_moves_to_handoff(db_session):
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.QUALIFIED, Event(EventType.PROVIDE_INFORMATION), lead
    )
    assert decision.next_state == ConversationState.HANDOFF


def test_handoff_stays_handoff_and_reassures_regression_f016(db_session):
    """Regression test for F-016 (BAT SC-090): a customer message arriving
    while waiting for a human used to unconditionally and silently close the
    conversation - even someone just checking in ("Are you still there?").
    HANDOFF must now stay HANDOFF and reassure the customer, never close on
    its own; only a human agent should ever end a HANDOFF conversation."""
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.HANDOFF, Event(EventType.CUSTOMER_MESSAGE), lead
    )
    assert decision.next_state == ConversationState.HANDOFF
    assert decision.required_action == "STILL_WAITING_FOR_HUMAN"


def test_handoff_reassures_regardless_of_message_content_regression_f016(db_session):
    """Any ordinary message type gets the same reassurance while waiting -
    this isn't a per-content decision, just "the conversation is on hold"."""
    lead = _lead(db_session)
    for event_type in (EventType.PROVIDE_INFORMATION, EventType.CUSTOMER_MESSAGE, EventType.CHANGE_INTENT_YES):
        decision = state_machine.decide(ConversationState.HANDOFF, Event(event_type), lead)
        assert decision.next_state == ConversationState.HANDOFF
        assert decision.required_action == "STILL_WAITING_FOR_HUMAN"


def test_question_always_detours_to_faq_and_remembers_state(db_session):
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.COLLECT_SUPPLIER, Event(EventType.QUESTION), lead
    )
    assert decision.next_state == ConversationState.FAQ
    assert decision.remember_previous is True


def test_objection_always_detours_and_remembers_state(db_session):
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.COLLECT_EAN, Event(EventType.OBJECTION), lead
    )
    assert decision.next_state == ConversationState.OBJECTION
    assert decision.remember_previous is True


def test_faq_state_resumes_previous_after_answering(db_session):
    lead = _lead(db_session)
    conversation = _conversation(db_session, lead, consecutive_detour_count=0)
    decision = state_machine.decide(
        ConversationState.FAQ, Event(EventType.PROVIDE_INFORMATION), lead, conversation
    )
    assert decision.resume_previous is True


def test_faq_state_escalates_to_handoff_after_too_many_detours(db_session):
    lead = _lead(db_session)
    conversation = _conversation(db_session, lead, consecutive_detour_count=3)
    decision = state_machine.decide(
        ConversationState.FAQ, Event(EventType.PROVIDE_INFORMATION), lead, conversation
    )
    assert decision.next_state == ConversationState.HANDOFF
    assert decision.resume_previous is False


def test_faq_state_without_conversation_defaults_to_resume(db_session):
    """Unit tests that don't care about detour policy can omit `conversation`."""
    lead = _lead(db_session)
    decision = state_machine.decide(ConversationState.FAQ, Event(EventType.PROVIDE_INFORMATION), lead)
    assert decision.resume_previous is True


def test_unknown_event_type_is_normalized_to_extraction_failed(db_session):
    """The Intent Classifier is the seam Phase 3 plugs into: anything it
    doesn't recognize must never reach the transition table as-is."""
    lead = _lead(db_session)

    class _FakeUnknownEvent:
        type = "SOMETHING_NOT_IN_THE_ENUM"
        entities = {}

    decision = state_machine.decide(ConversationState.COLLECT_SUPPLIER, _FakeUnknownEvent(), lead)
    assert decision.next_state == ConversationState.COLLECT_SUPPLIER
    assert decision.required_action == "ASK_CLARIFICATION"


def test_request_human_goes_straight_to_handoff_from_anywhere(db_session):
    lead = _lead(db_session)
    for state in (
        ConversationState.DISCOVERY,
        ConversationState.COLLECT_EAN,
        ConversationState.DATA_VALIDATION,
    ):
        decision = state_machine.decide(state, Event(EventType.REQUEST_HUMAN), lead)
        assert decision.next_state == ConversationState.HANDOFF


def test_extraction_failed_never_changes_state(db_session):
    lead = _lead(db_session)
    for state in (ConversationState.COLLECT_SUPPLIER, ConversationState.DISCOVERY):
        decision = state_machine.decide(state, Event(EventType.EXTRACTION_FAILED), lead)
        assert decision.next_state == state
        assert decision.required_action == "ASK_CLARIFICATION"


def test_rejected_state_does_not_crash_and_auto_closes_on_next_turn(db_session):
    """Regression test: current_state=REJECTED previously had no transition
    branch and crashed with ValueError on any event."""
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.REJECTED, Event(EventType.CUSTOMER_MESSAGE), lead
    )
    assert decision.next_state == ConversationState.CLOSED


def test_waiting_customer_resumes_qualification_on_reply(db_session):
    lead = _lead(db_session, customer_type=CustomerType.PARTICULIER)
    decision = state_machine.decide(
        ConversationState.WAITING_CUSTOMER, Event(EventType.PROVIDE_INFORMATION), lead
    )
    assert decision.next_state == ConversationState.COLLECT_LOCATION


def test_waiting_customer_sends_follow_up_on_scheduler_event(db_session):
    lead = _lead(db_session)
    decision = state_machine.decide(
        ConversationState.WAITING_CUSTOMER, Event(EventType.FOLLOW_UP_DUE), lead
    )
    assert decision.next_state == ConversationState.WAITING_CUSTOMER
    assert decision.required_action == "SEND_FOLLOW_UP"

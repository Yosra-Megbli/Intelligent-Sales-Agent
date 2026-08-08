"""
Integration tests for ConversationEngine.process_turn().

Redis is mocked out here (patched to an in-memory dict) so these tests run
anywhere without a real Redis instance - only the *behavioural contract* of
ConversationMemory.save_last_question / load is exercised, not Redis itself.
"""

import json

import pytest

from ai.providers.interface import LLMProvider, LLMResponse
from conversation_engine.engine import ConversationEngine
from conversation_engine.transitions import Event, EventType
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel, ConversationState, LeadSource, LeadStatus


class _FakeProvider(LLMProvider):
    """Records every call so tests can assert the classifier actually reached it."""

    def __init__(self, content: str):
        self.content = content
        self.calls: list[dict] = []

    def generate(self, messages, *, temperature=0.0, max_tokens=1024, json_mode=False):
        self.calls.append({"messages": messages, "json_mode": json_mode})
        return LLMResponse(content=self.content, model="fake-model")


@pytest.fixture(autouse=True)
def fake_redis_cache(monkeypatch):
    store: dict[str, dict] = {}

    def fake_cache(conversation_id, context, ttl_seconds=3600):
        store[conversation_id] = context

    def fake_get(conversation_id):
        return store.get(conversation_id)

    monkeypatch.setattr("conversation_engine.memory.cache_conversation_context", fake_cache)
    monkeypatch.setattr("conversation_engine.memory.get_cached_conversation_context", fake_get)
    yield store


def _new_conversation(db_session):
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE, email="jean@test.com")
    conversation = ConversationRepository(db_session).create(
        lead_id=lead.id, channel=ConversationChannel.WEB
    )
    db_session.commit()
    return lead, conversation


def test_full_happy_path_reaches_handoff(db_session):
    lead, conversation = _new_conversation(db_session)
    engine = ConversationEngine(db_session)

    # START -> GREETING
    result = engine.process_turn(conversation.id, Event(EventType.CUSTOMER_MESSAGE))
    assert result.next_state == ConversationState.GREETING

    # GREETING -> DISCOVERY
    result = engine.process_turn(conversation.id, Event(EventType.CUSTOMER_MESSAGE))
    assert result.next_state == ConversationState.DISCOVERY

    # DISCOVERY -> INTENT_CONFIRMATION
    result = engine.process_turn(conversation.id, Event(EventType.PROVIDE_INFORMATION))
    assert result.next_state == ConversationState.INTENT_CONFIRMATION

    # INTENT_CONFIRMATION -> COLLECT_CUSTOMER_TYPE
    result = engine.process_turn(conversation.id, Event(EventType.CHANGE_INTENT_YES))
    assert result.next_state == ConversationState.COLLECT_CUSTOMER_TYPE
    assert lead.status == LeadStatus.QUALIFICATION

    # Provide fields one by one, following the fixed order
    result = engine.process_turn(
        conversation.id,
        Event(EventType.PROVIDE_INFORMATION, entities={"customer_type": "particulier"}),
    )
    assert result.next_state == ConversationState.COLLECT_LOCATION

    result = engine.process_turn(
        conversation.id,
        Event(
            EventType.PROVIDE_INFORMATION,
            entities={"region": "Wallonie", "city": "Charleroi"},
        ),
    )
    assert result.next_state == ConversationState.COLLECT_SUPPLIER

    result = engine.process_turn(
        conversation.id,
        Event(EventType.PROVIDE_INFORMATION, entities={"current_supplier": "Engie"}),
    )
    assert result.next_state == ConversationState.COLLECT_CONTACT

    result = engine.process_turn(
        conversation.id,
        Event(
            EventType.PROVIDE_INFORMATION,
            entities={
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean@test.com",
                "phone": "0488112233",
            },
        ),
    )
    assert result.next_state == ConversationState.COLLECT_EAN

    result = engine.process_turn(
        conversation.id,
        Event(EventType.PROVIDE_INFORMATION, entities={"ean": "541234567890123456"}),
    )
    assert result.next_state == ConversationState.DATA_VALIDATION

    result = engine.process_turn(conversation.id, Event(EventType.PROVIDE_INFORMATION))
    assert result.next_state == ConversationState.QUALIFIED
    assert lead.status == LeadStatus.QUALIFIED
    assert lead.qualified_at is not None

    result = engine.process_turn(conversation.id, Event(EventType.PROVIDE_INFORMATION))
    assert result.next_state == ConversationState.HANDOFF
    assert lead.status == LeadStatus.APPOINTMENT


def test_handoff_does_not_silently_close_on_a_customer_checking_in_regression_f016(db_session):
    """End-to-end regression test for F-016 (BAT SC-090): once in HANDOFF, a
    customer sending one more message ("Bonjour, vous etes toujours la ?")
    must not silently close the conversation - it stays HANDOFF and Sophie
    reassures them a human is still coming."""
    lead, conversation = _new_conversation(db_session)
    engine = ConversationEngine(db_session)
    ConversationRepository(db_session).transition_state(conversation, ConversationState.HANDOFF)
    db_session.commit()

    result = engine.process_turn(conversation.id, Event(EventType.CUSTOMER_MESSAGE))

    assert result.next_state == ConversationState.HANDOFF
    assert result.required_action == "STILL_WAITING_FOR_HUMAN"
    assert conversation.current_state == ConversationState.HANDOFF
    assert lead.status == LeadStatus.APPOINTMENT  # unchanged - still waiting, not closed


def test_question_detour_returns_to_exact_same_collection_state(db_session):
    lead, conversation = _new_conversation(db_session)
    engine = ConversationEngine(db_session)
    ConversationRepository(db_session).transition_state(
        conversation, ConversationState.COLLECT_SUPPLIER
    )
    db_session.commit()

    result = engine.process_turn(conversation.id, Event(EventType.QUESTION))
    assert result.next_state == ConversationState.FAQ

    # Answering the FAQ resumes exactly where it stopped - no re-asking earlier fields
    result = engine.process_turn(conversation.id, Event(EventType.PROVIDE_INFORMATION))
    assert result.next_state == ConversationState.COLLECT_SUPPLIER


def test_invalid_ean_asks_for_correction_without_losing_other_data(db_session):
    lead, conversation = _new_conversation(db_session)
    engine = ConversationEngine(db_session)
    ConversationRepository(db_session).transition_state(
        conversation, ConversationState.DATA_VALIDATION
    )
    lead.customer_type = "particulier"
    lead.region = "Wallonie"
    lead.city = "Charleroi"
    lead.current_supplier = "Engie"
    lead.first_name = "Jean"
    lead.last_name = "Dupont"
    lead.email = "jean@test.com"
    lead.phone = "0488112233"
    lead.ean = "12345"  # invalid on purpose
    db_session.commit()

    result = engine.process_turn(conversation.id, Event(EventType.PROVIDE_INFORMATION))
    assert result.next_state == ConversationState.COLLECT_EAN
    assert result.required_action == "ASK_EAN_CORRECTION"
    # Everything else the customer already gave is untouched
    assert lead.email == "jean@test.com"
    assert lead.current_supplier == "Engie"


def test_out_of_coverage_rejects_lead(db_session):
    lead, conversation = _new_conversation(db_session)
    engine = ConversationEngine(db_session)
    ConversationRepository(db_session).transition_state(
        conversation, ConversationState.DATA_VALIDATION
    )
    lead.customer_type = "particulier"
    lead.region = "Paris"
    lead.city = "Paris"
    lead.current_supplier = "EDF"
    lead.first_name = "Jean"
    lead.last_name = "Dupont"
    lead.email = "jean@test.com"
    lead.phone = "0488112233"
    lead.ean = "541234567890123456"
    db_session.commit()

    result = engine.process_turn(conversation.id, Event(EventType.PROVIDE_INFORMATION))
    assert result.next_state == ConversationState.REJECTED
    assert result.rejection_reason == "OUT_OF_COVERAGE"
    assert lead.status == LeadStatus.REJECTED
    assert lead.rejection_reason.value == "OUT_OF_COVERAGE"


def test_duplicate_lead_rejected_at_data_validation_regression_f003(db_session):
    """End-to-end regression test for F-003 (BAT SC-021): before this fix,
    LeadRepository.find_duplicate() was fully implemented but never called
    anywhere in the live flow, so the exact same person could be qualified
    as a lead twice. This is the test that actually proves the fix reaches
    production behaviour, not just that rules.decide_validation() can
    handle an is_duplicate flag someone remembers to pass it - it drives two
    *real* leads/conversations through the real ConversationEngine and
    confirms the second one gets rejected."""
    existing_lead, _ = _new_conversation(db_session)  # email="jean@test.com", already in the CRM

    new_lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE)
    new_conversation = ConversationRepository(db_session).create(
        lead_id=new_lead.id, channel=ConversationChannel.WEB
    )
    ConversationRepository(db_session).transition_state(new_conversation, ConversationState.DATA_VALIDATION)
    new_lead.customer_type = "particulier"
    new_lead.region = "Wallonie"
    new_lead.city = "Namur"
    new_lead.current_supplier = "Engie"
    new_lead.first_name = "Jean"
    new_lead.last_name = "Dupont"
    new_lead.email = "jean@test.com"  # same email as existing_lead
    new_lead.phone = "0499998877"
    new_lead.ean = "541234567890123456"
    db_session.commit()

    engine = ConversationEngine(db_session)
    result = engine.process_turn(new_conversation.id, Event(EventType.PROVIDE_INFORMATION))

    assert result.next_state == ConversationState.REJECTED
    assert result.rejection_reason == "DUPLICATE_LEAD"
    assert new_lead.status == LeadStatus.REJECTED
    assert new_lead.rejection_reason.value == "DUPLICATE_LEAD"


def test_lead_own_saved_contact_info_never_flags_itself_as_duplicate(db_session):
    """Guards the exclude_lead_id half of the F-003 fix specifically: by the
    time DATA_VALIDATION runs, the lead being validated already has its own
    email/phone persisted - without excluding its own id, every single
    qualification would incorrectly reject as "duplicate of itself"."""
    lead, conversation = _new_conversation(db_session)  # already has email="jean@test.com"
    engine = ConversationEngine(db_session)
    ConversationRepository(db_session).transition_state(conversation, ConversationState.DATA_VALIDATION)
    lead.customer_type = "particulier"
    lead.region = "Wallonie"
    lead.city = "Namur"
    lead.current_supplier = "Engie"
    lead.first_name = "Jean"
    lead.last_name = "Dupont"
    lead.phone = "0488112233"
    lead.ean = "541234567890123456"
    db_session.commit()

    result = engine.process_turn(conversation.id, Event(EventType.PROVIDE_INFORMATION))

    assert result.next_state == ConversationState.QUALIFIED
    assert result.rejection_reason is None


def test_no_change_intent_rejects_lead(db_session):
    lead, conversation = _new_conversation(db_session)
    engine = ConversationEngine(db_session)
    ConversationRepository(db_session).transition_state(
        conversation, ConversationState.INTENT_CONFIRMATION
    )
    db_session.commit()

    result = engine.process_turn(conversation.id, Event(EventType.CHANGE_INTENT_NO))
    assert result.next_state == ConversationState.REJECTED
    assert result.rejection_reason == "NO_CHANGE_INTENT"
    assert lead.status == LeadStatus.REJECTED


def test_request_human_short_circuits_to_handoff(db_session):
    lead, conversation = _new_conversation(db_session)
    engine = ConversationEngine(db_session)
    ConversationRepository(db_session).transition_state(
        conversation, ConversationState.COLLECT_EAN
    )
    db_session.commit()

    result = engine.process_turn(conversation.id, Event(EventType.REQUEST_HUMAN))
    assert result.next_state == ConversationState.HANDOFF
    assert lead.status == LeadStatus.APPOINTMENT


def test_extraction_failed_does_not_change_conversation_state(db_session):
    lead, conversation = _new_conversation(db_session)
    engine = ConversationEngine(db_session)
    ConversationRepository(db_session).transition_state(
        conversation, ConversationState.COLLECT_LOCATION
    )
    db_session.commit()

    result = engine.process_turn(conversation.id, Event(EventType.EXTRACTION_FAILED))

    # ConversationState is untouched - that's the actual guarantee.
    assert result.next_state == ConversationState.COLLECT_LOCATION
    assert result.required_action == "ASK_CLARIFICATION"
    # LeadStatus reflects wherever the conversation already was (QUALIFICATION,
    # since we're in a COLLECT_* state) - the engine keeps CRM status and
    # dialogue state in sync on every turn, this event included.
    assert lead.status == LeadStatus.QUALIFICATION


def test_repeated_detours_escalate_to_handoff_via_dialogue_policy(db_session):
    lead, conversation = _new_conversation(db_session)
    engine = ConversationEngine(db_session)
    ConversationRepository(db_session).transition_state(
        conversation, ConversationState.COLLECT_SUPPLIER
    )
    db_session.commit()

    # Detour 1: question -> FAQ, then "answered" -> resume
    engine.process_turn(conversation.id, Event(EventType.QUESTION))
    result = engine.process_turn(conversation.id, Event(EventType.PROVIDE_INFORMATION))
    assert result.next_state == ConversationState.COLLECT_SUPPLIER
    assert conversation.consecutive_detour_count == 1

    # Detour 2: objection -> OBJECTION, then resume again
    engine.process_turn(conversation.id, Event(EventType.OBJECTION))
    result = engine.process_turn(conversation.id, Event(EventType.PROVIDE_INFORMATION))
    assert result.next_state == ConversationState.COLLECT_SUPPLIER
    assert conversation.consecutive_detour_count == 2

    # Detour 3: another question -> FAQ, then resume -> hits the threshold (3) -> escalate
    engine.process_turn(conversation.id, Event(EventType.QUESTION))
    result = engine.process_turn(conversation.id, Event(EventType.PROVIDE_INFORMATION))
    assert result.next_state == ConversationState.HANDOFF
    # Escalating to HANDOFF is real progress out of the detour loop, so the
    # counter resets - it's not still "stuck" once a human is taking over.
    assert conversation.consecutive_detour_count == 0


def test_answering_a_real_qualification_question_resets_detour_count(db_session):
    lead, conversation = _new_conversation(db_session)
    engine = ConversationEngine(db_session)
    ConversationRepository(db_session).transition_state(
        conversation, ConversationState.COLLECT_SUPPLIER
    )
    db_session.commit()

    engine.process_turn(conversation.id, Event(EventType.QUESTION))
    engine.process_turn(conversation.id, Event(EventType.PROVIDE_INFORMATION))
    assert conversation.consecutive_detour_count == 1

    # Customer actually answers the supplier question -> real progress -> reset
    engine.process_turn(
        conversation.id,
        Event(EventType.PROVIDE_INFORMATION, entities={"current_supplier": "Engie"}),
    )
    assert conversation.consecutive_detour_count == 0


def test_activity_log_records_state_changes(db_session):
    lead, conversation = _new_conversation(db_session)
    engine = ConversationEngine(db_session)
    from crm.activity_repository import ActivityRepository

    engine.process_turn(conversation.id, Event(EventType.CUSTOMER_MESSAGE))  # START -> GREETING
    engine.process_turn(conversation.id, Event(EventType.CUSTOMER_MESSAGE))  # GREETING -> DISCOVERY

    activities = ActivityRepository(db_session).list_for_lead(lead.id)
    details = [a.details for a in activities]
    assert "START -> GREETING" in details
    assert "GREETING -> DISCOVERY" in details


def test_engine_provider_actually_reaches_the_intent_classifier(db_session):
    """Regression test: ConversationEngine(db_session, provider=...) must
    thread that provider into state_machine.decide() via IntentClassifier,
    or Phase 3C's LLM-backed disambiguation silently never fires in
    production (the bug this test guards against)."""
    lead, conversation = _new_conversation(db_session)
    ConversationRepository(db_session).transition_state(
        conversation, ConversationState.INTENT_CONFIRMATION
    )
    db_session.commit()

    fake_provider = _FakeProvider(content=json.dumps({"event_type": "CHANGE_INTENT_YES"}))
    engine = ConversationEngine(db_session, provider=fake_provider)

    # A bare "oui" only resolves to CHANGE_INTENT_YES via the LLM-backed
    # disambiguation call - the no-provider passthrough would leave it as
    # CUSTOMER_MESSAGE and the state machine would just ask for clarification.
    result = engine.process_turn(
        conversation.id, Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="oui")
    )

    assert fake_provider.calls, "the fake provider was never called - the classifier has no provider wired in"
    assert result.next_state == ConversationState.COLLECT_CUSTOMER_TYPE
    assert lead.change_intent is True


def test_engine_without_provider_never_calls_disambiguation(db_session):
    """Sanity check the test above is meaningful: without a provider, the
    engine must NOT be able to resolve a bare 'oui' via LLM disambiguation."""
    lead, conversation = _new_conversation(db_session)
    ConversationRepository(db_session).transition_state(
        conversation, ConversationState.INTENT_CONFIRMATION
    )
    db_session.commit()

    engine = ConversationEngine(db_session)  # no provider

    result = engine.process_turn(
        conversation.id, Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="oui")
    )

    # Without disambiguation, CUSTOMER_MESSAGE isn't CHANGE_INTENT_YES/NO,
    # so INTENT_CONFIRMATION's default branch just asks for clarification.
    assert result.next_state == ConversationState.INTENT_CONFIRMATION
    assert result.required_action == "ASK_CLARIFICATION"

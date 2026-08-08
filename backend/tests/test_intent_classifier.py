"""
Tests for Phase 3C: state-aware second-pass disambiguation added to
IntentClassifier, on top of the unchanged Phase 2 passthrough contract.
"""

import json

from ai.providers.interface import LLMError, LLMMessage, LLMProvider, LLMResponse, LLMRole
from conversation_engine.intent_classifier import IntentClassifier
from conversation_engine.transitions import Event, EventType
from domain.enums import ConversationState


class FakeProvider(LLMProvider):
    def __init__(self, content: str = "", raise_error: Exception | None = None):
        self.content = content
        self.raise_error = raise_error
        self.calls: list[dict] = []

    def generate(self, messages, *, temperature=0.0, max_tokens=1024, json_mode=False):
        self.calls.append({"messages": messages, "json_mode": json_mode})
        if self.raise_error is not None:
            raise self.raise_error
        return LLMResponse(content=self.content, model="fake-model")


# --- Phase 2 contract, unchanged ------------------------------------------------------


def test_known_event_passes_through_unchanged():
    classifier = IntentClassifier()
    event = Event(EventType.PROVIDE_INFORMATION, entities={"city": "Charleroi"})
    result = classifier.classify(event)
    assert result is event


def test_unrecognized_event_type_becomes_extraction_failed():
    classifier = IntentClassifier()

    class _Bogus:
        type = "NOT_A_REAL_EVENT_TYPE"
        entities = {}

    result = classifier.classify(_Bogus())
    assert result.type == EventType.EXTRACTION_FAILED


def test_confidently_classified_event_is_never_sent_to_the_llm_even_with_a_provider():
    provider = FakeProvider(content=json.dumps({"event_type": "QUESTION"}))
    classifier = IntentClassifier(provider)
    event = Event(EventType.OBJECTION, raw_answer_text="non merci")

    result = classifier.classify(event, current_state=ConversationState.COLLECT_EAN)

    assert result is event
    assert provider.calls == []


def test_customer_message_without_provider_passes_through_unchanged():
    classifier = IntentClassifier()  # no provider - Phase 2 behaviour
    event = Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="oui")

    result = classifier.classify(event, current_state=ConversationState.INTENT_CONFIRMATION)

    assert result is event


def test_customer_message_without_raw_text_passes_through_unchanged():
    provider = FakeProvider(content=json.dumps({"event_type": "CHANGE_INTENT_YES"}))
    classifier = IntentClassifier(provider)
    event = Event(EventType.CUSTOMER_MESSAGE, raw_answer_text=None)

    result = classifier.classify(event, current_state=ConversationState.INTENT_CONFIRMATION)

    assert result is event
    assert provider.calls == []


# --- Phase 3C: state-aware disambiguation ------------------------------------------------------


def test_disambiguates_bare_oui_using_current_state():
    provider = FakeProvider(content=json.dumps({"event_type": "CHANGE_INTENT_YES"}))
    classifier = IntentClassifier(provider)
    event = Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="oui")

    result = classifier.classify(event, current_state=ConversationState.INTENT_CONFIRMATION)

    assert result.type == EventType.CHANGE_INTENT_YES
    assert result.raw_answer_text == "oui"


def test_current_state_is_passed_as_context_to_the_prompt():
    provider = FakeProvider(content=json.dumps({"event_type": "CHANGE_INTENT_NO"}))
    classifier = IntentClassifier(provider)
    event = Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="non")

    classifier.classify(event, current_state=ConversationState.INTENT_CONFIRMATION)

    system_message = provider.calls[0]["messages"][0]
    assert system_message.role == LLMRole.SYSTEM
    assert "INTENT_CONFIRMATION" in system_message.content
    assert provider.calls[0]["json_mode"] is True


def test_preserves_entities_when_reclassifying():
    provider = FakeProvider(content=json.dumps({"event_type": "PROVIDE_INFORMATION"}))
    classifier = IntentClassifier(provider)
    event = Event(EventType.CUSTOMER_MESSAGE, entities={"city": "Namur"}, raw_answer_text="Namur")

    result = classifier.classify(event, current_state=ConversationState.COLLECT_LOCATION)

    assert result.entities == {"city": "Namur"}


def test_still_uncertain_stays_customer_message():
    provider = FakeProvider(content=json.dumps({"event_type": "CUSTOMER_MESSAGE"}))
    classifier = IntentClassifier(provider)
    event = Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="hmm peut-être")

    result = classifier.classify(event, current_state=ConversationState.INTENT_CONFIRMATION)

    assert result.type == EventType.CUSTOMER_MESSAGE


def test_no_current_state_still_attempts_disambiguation():
    provider = FakeProvider(content=json.dumps({"event_type": "QUESTION"}))
    classifier = IntentClassifier(provider)
    event = Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="c'est quoi Ecofix ?")

    result = classifier.classify(event)

    assert result.type == EventType.QUESTION


# --- Phase 3C: graceful fallback, never worse than Phase 2 ------------------------------------------------------


def test_llm_error_falls_back_to_original_event():
    provider = FakeProvider(raise_error=LLMError("boom"))
    classifier = IntentClassifier(provider)
    event = Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="oui")

    result = classifier.classify(event, current_state=ConversationState.INTENT_CONFIRMATION)

    assert result is event


def test_malformed_json_falls_back_to_original_event():
    provider = FakeProvider(content="not json")
    classifier = IntentClassifier(provider)
    event = Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="oui")

    result = classifier.classify(event, current_state=ConversationState.INTENT_CONFIRMATION)

    assert result is event


def test_unknown_event_type_from_llm_falls_back_to_original_event():
    provider = FakeProvider(content=json.dumps({"event_type": "SOMETHING_MADE_UP"}))
    classifier = IntentClassifier(provider)
    event = Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="oui")

    result = classifier.classify(event, current_state=ConversationState.INTENT_CONFIRMATION)

    assert result is event


def test_llm_cannot_fabricate_extraction_failed_or_follow_up_due_via_disambiguation():
    for fabricated in ("EXTRACTION_FAILED", "FOLLOW_UP_DUE"):
        provider = FakeProvider(content=json.dumps({"event_type": fabricated}))
        classifier = IntentClassifier(provider)
        event = Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="oui")

        result = classifier.classify(event, current_state=ConversationState.INTENT_CONFIRMATION)

        assert result is event


def test_non_dict_json_falls_back_to_original_event():
    provider = FakeProvider(content=json.dumps(["oui"]))
    classifier = IntentClassifier(provider)
    event = Event(EventType.CUSTOMER_MESSAGE, raw_answer_text="oui")

    result = classifier.classify(event, current_state=ConversationState.INTENT_CONFIRMATION)

    assert result is event


# --- purity ------------------------------------------------------


def test_intent_classifier_never_touches_the_database_or_crm():
    import ast
    import inspect

    from conversation_engine import intent_classifier as intent_classifier_module

    tree = ast.parse(inspect.getsource(intent_classifier_module))

    forbidden_call_names = {"flush", "commit", "add", "save"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            assert "crm" not in module_name and not any("repository" in n.lower() for n in names), (
                f"intent_classifier.py must not import repositories, found: {module_name or names}"
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_call_names, (
                f"intent_classifier.py must stay pure, found a call to '.{node.func.attr}()'"
            )

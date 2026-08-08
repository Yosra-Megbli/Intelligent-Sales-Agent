"""
Tests for the Phase 3B extractor.

Uses a fake `LLMProvider` (no real Groq call, no network) so these tests
run fast and deterministically. What's under test is the extractor's own
logic: prompt construction context, JSON parsing, entity whitelisting/
normalization, and graceful fallback to EXTRACTION_FAILED - never the LLM's
actual judgement.
"""

import json

import pytest

from ai.extractor import Extractor
from ai.providers.interface import LLMError, LLMMessage, LLMProvider, LLMResponse, LLMRole
from conversation_engine.transitions import EventType


class FakeProvider(LLMProvider):
    """Returns pre-baked content, or raises a given LLMError subclass."""

    def __init__(self, content: str = "", raise_error: Exception | None = None):
        self.content = content
        self.raise_error = raise_error
        self.calls: list[dict] = []

    def generate(self, messages, *, temperature=0.0, max_tokens=1024, json_mode=False):
        self.calls.append(
            {"messages": messages, "temperature": temperature, "max_tokens": max_tokens, "json_mode": json_mode}
        )
        if self.raise_error is not None:
            raise self.raise_error
        return LLMResponse(content=self.content, model="fake-model")


def make_extractor(payload: dict) -> tuple[Extractor, FakeProvider]:
    provider = FakeProvider(content=json.dumps(payload))
    return Extractor(provider), provider


# --- happy paths ------------------------------------------------------


def test_extracts_provide_information_with_entities():
    extractor, provider = make_extractor(
        {
            "event_type": "PROVIDE_INFORMATION",
            "entities": {"first_name": "Jean", "last_name": "Dupont", "email": "jean@test.com"},
        }
    )

    event = extractor.extract("Je m'appelle Jean Dupont, jean@test.com")

    assert event.type == EventType.PROVIDE_INFORMATION
    assert event.entities == {"first_name": "Jean", "last_name": "Dupont", "email": "jean@test.com"}
    assert event.raw_answer_text == "Je m'appelle Jean Dupont, jean@test.com"
    assert provider.calls[0]["json_mode"] is True


def test_extracts_question_with_no_entities():
    extractor, _ = make_extractor({"event_type": "QUESTION", "entities": {}})

    event = extractor.extract("C'est quoi Ecofix ?")

    assert event.type == EventType.QUESTION
    assert event.entities == {}


def test_extracts_objection():
    extractor, _ = make_extractor({"event_type": "OBJECTION", "entities": {}})
    event = extractor.extract("Non merci, je suis satisfait de mon fournisseur actuel")
    assert event.type == EventType.OBJECTION


def test_extracts_change_intent_yes():
    extractor, _ = make_extractor({"event_type": "CHANGE_INTENT_YES", "entities": {}})
    event = extractor.extract("Oui, ça m'intéresse")
    assert event.type == EventType.CHANGE_INTENT_YES


def test_extracts_request_human():
    extractor, _ = make_extractor({"event_type": "REQUEST_HUMAN", "entities": {}})
    event = extractor.extract("Je veux parler à un humain")
    assert event.type == EventType.REQUEST_HUMAN


# --- entity normalization ------------------------------------------------------


def test_drops_null_and_blank_entities():
    extractor, _ = make_extractor(
        {
            "event_type": "PROVIDE_INFORMATION",
            "entities": {"first_name": "Jean", "last_name": None, "email": "  ", "city": "Namur"},
        }
    )

    event = extractor.extract("Jean, Namur")

    assert event.entities == {"first_name": "Jean", "city": "Namur"}


def test_drops_unknown_entity_keys():
    extractor, _ = make_extractor(
        {"event_type": "PROVIDE_INFORMATION", "entities": {"first_name": "Jean", "favorite_color": "blue"}}
    )

    event = extractor.extract("Jean, j'aime le bleu")

    assert event.entities == {"first_name": "Jean"}


def test_normalizes_customer_type_case():
    extractor, _ = make_extractor(
        {"event_type": "PROVIDE_INFORMATION", "entities": {"customer_type": "Particulier"}}
    )

    event = extractor.extract("Je suis un particulier")

    assert event.entities == {"customer_type": "particulier"}


def test_rejects_invalid_customer_type_value():
    extractor, _ = make_extractor(
        {"event_type": "PROVIDE_INFORMATION", "entities": {"customer_type": "not_a_real_type"}}
    )

    event = extractor.extract("...")

    assert event.entities == {}


def test_region_outside_belgium_is_kept_not_dropped_regression_f002():
    """Regression test for F-002 (BAT SC-013): region must be captured as
    free text, exactly like city/current_supplier - never pre-filtered to a
    fixed set. Before the fix, "Paris" (and any other out-of-coverage
    region) was silently dropped here, so rules.decide_validation()'s own
    is_region_covered() check never got a region to actually reject - the
    customer just got stuck being asked for "location" forever instead of
    ever being told Ecofix doesn't serve their area. Whether a region is
    servable is business_rules/qualification_rules.yaml's decision, not
    this module's."""
    extractor, _ = make_extractor({"event_type": "PROVIDE_INFORMATION", "entities": {"region": "Paris"}})

    event = extractor.extract("Je suis à Paris")

    assert event.entities == {"region": "Paris"}


def test_accepts_valid_region_value():
    extractor, _ = make_extractor({"event_type": "PROVIDE_INFORMATION", "entities": {"region": "Wallonie"}})

    event = extractor.extract("Je suis en Wallonie")

    assert event.entities == {"region": "Wallonie"}


def test_strips_spaces_from_ean_and_phone():
    extractor, _ = make_extractor(
        {
            "event_type": "PROVIDE_INFORMATION",
            "entities": {"ean": "5412 3456 7890 1234 56", "phone": "0488 11 22 33"},
        }
    )

    event = extractor.extract("mon ean est 5412 3456 7890 1234 56")

    assert event.entities == {"ean": "541234567890123456", "phone": "0488112233"}


# --- context / prompt wiring ------------------------------------------------------


def test_expected_field_is_passed_as_context():
    extractor, provider = make_extractor({"event_type": "PROVIDE_INFORMATION", "entities": {"ean": "1"}})

    extractor.extract("541234567890123456", expected_field="ean")

    system_message = provider.calls[0]["messages"][0]
    assert system_message.role == LLMRole.SYSTEM
    assert "ean" in system_message.content


def test_raw_text_is_sent_as_user_message():
    extractor, provider = make_extractor({"event_type": "CUSTOMER_MESSAGE", "entities": {}})

    extractor.extract("bonjour")

    user_message = provider.calls[0]["messages"][1]
    assert user_message.role == LLMRole.USER
    assert user_message.content == "bonjour"


# --- failure handling ------------------------------------------------------


def test_empty_message_is_extraction_failed_without_calling_llm():
    extractor, provider = make_extractor({"event_type": "CUSTOMER_MESSAGE", "entities": {}})

    event = extractor.extract("")

    assert event.type == EventType.EXTRACTION_FAILED
    assert provider.calls == []


def test_none_message_is_extraction_failed_without_calling_llm():
    extractor, provider = make_extractor({"event_type": "CUSTOMER_MESSAGE", "entities": {}})

    event = extractor.extract(None)

    assert event.type == EventType.EXTRACTION_FAILED
    assert provider.calls == []


def test_whitespace_only_message_is_extraction_failed():
    extractor, provider = make_extractor({"event_type": "CUSTOMER_MESSAGE", "entities": {}})

    event = extractor.extract("   ")

    assert event.type == EventType.EXTRACTION_FAILED
    assert provider.calls == []


def test_malformed_json_is_extraction_failed():
    provider = FakeProvider(content="not json at all")
    extractor = Extractor(provider)

    event = extractor.extract("bonjour")

    assert event.type == EventType.EXTRACTION_FAILED
    assert event.raw_answer_text == "bonjour"


def test_json_but_not_an_object_is_extraction_failed():
    provider = FakeProvider(content=json.dumps(["not", "an", "object"]))
    extractor = Extractor(provider)

    event = extractor.extract("bonjour")

    assert event.type == EventType.EXTRACTION_FAILED


def test_unknown_event_type_is_extraction_failed():
    extractor, _ = make_extractor({"event_type": "SOMETHING_MADE_UP", "entities": {}})

    event = extractor.extract("???")

    assert event.type == EventType.EXTRACTION_FAILED


def test_model_cannot_produce_extraction_failed_or_follow_up_due_directly():
    """Defense in depth: even if the model hallucinates one of the two
    system-only EventTypes, it must not pass through - EXTRACTION_FAILED is
    this module's own fallback and FOLLOW_UP_DUE is scheduler-only (Phase 6),
    never something a customer message maps to.
    """
    for fabricated in ("EXTRACTION_FAILED", "FOLLOW_UP_DUE"):
        extractor, _ = make_extractor({"event_type": fabricated, "entities": {}})
        event = extractor.extract("bonjour")
        assert event.type == EventType.EXTRACTION_FAILED


def test_llm_error_is_extraction_failed():
    provider = FakeProvider(raise_error=LLMError("boom"))
    extractor = Extractor(provider)

    event = extractor.extract("bonjour")

    assert event.type == EventType.EXTRACTION_FAILED
    assert event.raw_answer_text == "bonjour"


def test_missing_entities_key_defaults_to_empty_dict():
    provider = FakeProvider(content=json.dumps({"event_type": "QUESTION"}))
    extractor = Extractor(provider)

    event = extractor.extract("c'est quoi ?")

    assert event.entities == {}


# --- purity ------------------------------------------------------


def test_extractor_module_never_touches_the_database_or_crm():
    """Golden rule, same technique as
    test_rules_module_never_touches_the_database and
    test_groq_module_never_touches_the_database_or_crm: the extractor reads
    text and produces an Event, nothing else."""
    import ast
    import inspect

    from ai import extractor as extractor_module

    tree = ast.parse(inspect.getsource(extractor_module))

    forbidden_call_names = {"flush", "commit", "add", "save"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            assert "crm" not in module_name and not any("repository" in n.lower() for n in names), (
                f"ai/extractor.py must not import repositories, found: {module_name or names}"
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_call_names, (
                f"ai/extractor.py must stay pure, found a call to '.{node.func.attr}()'"
            )

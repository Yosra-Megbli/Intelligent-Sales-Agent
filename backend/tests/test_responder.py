"""
Tests for the Phase 3D responder.

Uses a fake `LLMProvider` (no real Groq call, no network) so these tests run
fast and deterministically. What's under test is the responder's own logic:
talking-point selection per required_action, rejection-reason routing,
graceful fallback to fixed text when the LLM fails or is absent, and that
ANSWER_FAQ/ANSWER_OBJECTION only speak the RAG answer they're given - never
their own facts.
"""

import pytest

from ai.providers.interface import LLMError, LLMMessage, LLMProvider, LLMResponse, LLMRole
from ai.responder import Responder, _FALLBACK_TEXT, _TALKING_POINTS
from domain.enums import ConversationChannel, RejectionReason
from domain.models.conversation import Conversation


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


def make_conversation(language: str = "fr") -> Conversation:
    return Conversation(channel=ConversationChannel.WEB, language=language)


# --- happy paths, one per talking-point action ------------------------------------------------------


@pytest.mark.parametrize("required_action", sorted(_TALKING_POINTS.keys()))
def test_every_talking_point_action_produces_llm_text(required_action):
    provider = FakeProvider(content="Bonjour, comment puis-je vous aider ?")
    responder = Responder(provider)

    result = responder.respond(required_action, conversation=make_conversation())

    assert result == "Bonjour, comment puis-je vous aider ?"
    assert provider.calls[0]["json_mode"] is False
    assert provider.calls[0]["temperature"] == 0.7


def test_llm_receives_the_conversation_language():
    provider = FakeProvider(content="Hallo!")
    responder = Responder(provider)

    responder.respond("ASK_INTENT", conversation=make_conversation(language="nl"))

    system_message = provider.calls[0]["messages"][0]
    assert system_message.role == LLMRole.SYSTEM
    assert "nl" in system_message.content


def test_talking_point_never_leaks_business_facts_like_allowed_regions():
    provider = FakeProvider(content="...")
    responder = Responder(provider)

    responder.respond("ASK_LOCATION", conversation=make_conversation())

    system_message = provider.calls[0]["messages"][0]
    # The coverage list itself (Wallonie/Flandre/Bruxelles as *allowed* values)
    # lives only in qualification_rules.yaml - the responder just asks the
    # open question, it doesn't validate or enumerate what's acceptable.
    assert "allowed" not in system_message.content.lower()


# --- fallback behaviour ------------------------------------------------------


def test_no_provider_always_uses_fallback_text():
    responder = Responder(provider=None)

    result = responder.respond("ASK_EAN", conversation=make_conversation())

    assert result == _FALLBACK_TEXT["ASK_EAN"]


def test_still_waiting_for_human_has_a_fallback_and_talking_point_regression_f016():
    """Part of the F-016 fix: HANDOFF no longer closes silently on the next
    customer message - it now uses this action instead. Confirms it
    actually produces text, with and without an LLM available, not just
    that state_machine.py returns the string."""
    assert "STILL_WAITING_FOR_HUMAN" in _TALKING_POINTS
    assert "STILL_WAITING_FOR_HUMAN" in _FALLBACK_TEXT

    responder = Responder(provider=None)
    result = responder.respond("STILL_WAITING_FOR_HUMAN", conversation=make_conversation())

    assert result == _FALLBACK_TEXT["STILL_WAITING_FOR_HUMAN"]


def test_llm_error_falls_back_to_fixed_text():
    provider = FakeProvider(raise_error=LLMError("boom"))
    responder = Responder(provider)

    result = responder.respond("SEND_GREETING", conversation=make_conversation())

    assert result == _FALLBACK_TEXT["SEND_GREETING"]


def test_empty_llm_response_falls_back_to_fixed_text():
    provider = FakeProvider(content="   ")
    responder = Responder(provider)

    result = responder.respond("ASK_SUPPLIER", conversation=make_conversation())

    assert result == _FALLBACK_TEXT["ASK_SUPPLIER"]


def test_unknown_required_action_returns_generic_fallback_without_crashing():
    responder = Responder(provider=None)

    result = responder.respond("SOME_FUTURE_ACTION", conversation=make_conversation())

    assert isinstance(result, str) and result


# --- silent actions ------------------------------------------------------


@pytest.mark.parametrize("required_action", ["NONE", None])
def test_silent_actions_return_none_and_never_call_the_llm(required_action):
    provider = FakeProvider(content="should never be used")
    responder = Responder(provider)

    result = responder.respond(required_action, conversation=make_conversation())

    assert result is None
    assert provider.calls == []


# --- SEND_REJECTION routing ------------------------------------------------------


@pytest.mark.parametrize("reason", list(RejectionReason))
def test_every_rejection_reason_has_a_talking_point_and_fallback(reason):
    responder = Responder(provider=None)

    result = responder.respond(
        "SEND_REJECTION", conversation=make_conversation(), rejection_reason=reason.value
    )

    assert isinstance(result, str) and result


def test_rejection_reason_selects_a_different_talking_point_per_reason():
    provider = FakeProvider(content="text")
    responder = Responder(provider)

    responder.respond(
        "SEND_REJECTION", conversation=make_conversation(), rejection_reason=RejectionReason.OUT_OF_COVERAGE.value
    )
    responder.respond(
        "SEND_REJECTION", conversation=make_conversation(), rejection_reason=RejectionReason.NO_INTENT.value
    )

    first_prompt = provider.calls[0]["messages"][0].content
    second_prompt = provider.calls[1]["messages"][0].content
    assert first_prompt != second_prompt


def test_send_rejection_without_a_reason_uses_generic_fallback():
    responder = Responder(provider=None)

    result = responder.respond("SEND_REJECTION", conversation=make_conversation(), rejection_reason=None)

    assert isinstance(result, str) and result


# --- ANSWER_FAQ / ANSWER_OBJECTION ------------------------------------------------------


@pytest.mark.parametrize("required_action", ["ANSWER_FAQ", "ANSWER_OBJECTION"])
def test_faq_and_objection_without_rag_answer_use_generic_fallback(required_action):
    provider = FakeProvider(content="should not be reached")
    responder = Responder(provider)

    result = responder.respond(required_action, conversation=make_conversation(), rag_answer=None)

    assert result == _FALLBACK_TEXT[required_action]
    assert provider.calls == []


def test_faq_with_rag_answer_passes_it_to_the_llm_as_the_only_fact_source():
    provider = FakeProvider(content="Nos contrats n'ont pas de frais de resiliation.")
    responder = Responder(provider)

    result = responder.respond(
        "ANSWER_FAQ",
        conversation=make_conversation(),
        rag_answer="Ecofix contracts have no early termination fees.",
    )

    assert result == "Nos contrats n'ont pas de frais de resiliation."
    system_message = provider.calls[0]["messages"][0].content
    assert "Ecofix contracts have no early termination fees." in system_message


def test_faq_rag_llm_failure_falls_back_to_generic_text():
    provider = FakeProvider(raise_error=LLMError("down"))
    responder = Responder(provider)

    result = responder.respond("ANSWER_OBJECTION", conversation=make_conversation(), rag_answer="Some answer.")

    assert result == _FALLBACK_TEXT["ANSWER_OBJECTION"]


# --- purity ------------------------------------------------------


def test_responder_module_never_touches_the_database_or_crm():
    """Golden rule, same technique as
    test_extractor_module_never_touches_the_database_or_crm and
    test_rules_module_never_touches_the_database: the responder reads a
    decision and produces text, nothing else."""
    import ast
    import inspect

    from ai import responder as responder_module

    tree = ast.parse(inspect.getsource(responder_module))

    forbidden_call_names = {"flush", "commit", "add", "save"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            assert "crm" not in module_name and not any("repository" in n.lower() for n in names), (
                f"ai/responder.py must not import repositories, found: {module_name or names}"
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_call_names, (
                f"ai/responder.py must stay pure, found a call to '.{node.func.attr}()'"
            )


def test_every_state_machine_required_action_is_handled():
    """Cross-check against state_machine.py's literal required_action strings
    (plus SEND_FOLLOW_UP, which engine.py's WAITING_CUSTOMER branch uses) so a
    future new action can't silently fall through to the generic fallback
    unnoticed."""
    known_actions = set(_TALKING_POINTS.keys()) | {
        "NONE",
        "SEND_REJECTION",
        "ANSWER_FAQ",
        "ANSWER_OBJECTION",
    }
    expected_actions = {
        "SEND_GREETING",
        "ASK_INTENT",
        "CONFIRM_INTENT",
        "ASK_CLARIFICATION",
        "ANSWER_FAQ",
        "ANSWER_OBJECTION",
        "ASK_CUSTOMER_TYPE",
        "ASK_LOCATION",
        "ASK_SUPPLIER",
        "ASK_CONTACT",
        "ASK_EAN",
        "SEND_QUALIFIED_CONFIRMATION",
        "SEND_REJECTION",
        "ASK_EAN_CORRECTION",
        "ASK_CONTACT_CORRECTION",
        "NOTIFY_HUMAN",
        "NOTIFY_SALES_TEAM",
        "STILL_WAITING_FOR_HUMAN",
        "NONE",
        "SEND_FOLLOW_UP",
    }
    assert expected_actions <= known_actions

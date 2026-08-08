"""
Integration tests for ConversationService.handle_message() (Application
layer, Phase 4A).

This is the first test file that exercises `ai/*` and `conversation_engine/`
together, through the one module allowed to import both. Redis is mocked out
(same technique as test_conversation_engine.py) so these run anywhere
without a real Redis instance. `channels/web.py`'s own tests
(tests/test_web_channel.py) only check that it correctly delegates to this
service - the real behaviour is tested once, here.
"""

import json

import pytest

from ai.providers.interface import LLMError, LLMMessage, LLMProvider, LLMResponse, LLMRole
from application.conversation_service import ConversationRequest, ConversationService
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel, ConversationState, LeadSource, MessageRole


class ScriptedProvider(LLMProvider):
    """Returns JSON for extraction calls (json_mode=True) and a fixed
    sentence for phrasing calls (json_mode=False) - a fake that behaves
    like a real provider would for each of the two distinct jobs it's
    asked to do in one conversation turn."""

    def __init__(self, extraction_payload: dict, response_text: str = "Voici ma reponse."):
        self.extraction_payload = extraction_payload
        self.response_text = response_text
        self.calls: list[dict] = []
        self.raise_on_extraction: Exception | None = None

    def generate(self, messages, *, temperature=0.0, max_tokens=1024, json_mode=False):
        self.calls.append({"messages": messages, "json_mode": json_mode})
        if json_mode:
            if self.raise_on_extraction is not None:
                raise self.raise_on_extraction
            return LLMResponse(content=json.dumps(self.extraction_payload), model="fake-model")
        return LLMResponse(content=self.response_text, model="fake-model")


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


def _new_conversation(db_session, language: str = "fr"):
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE)
    conversation = ConversationRepository(db_session).create(
        lead_id=lead.id, channel=ConversationChannel.WEB, language=language
    )
    db_session.commit()
    return lead, conversation


# --- basic happy path ------------------------------------------------------


def test_handle_message_advances_state_and_returns_response_text(db_session):
    _, conversation = _new_conversation(db_session)
    provider = ScriptedProvider(
        extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}},
        response_text="Bonjour ! Comment puis-je vous aider ?",
    )
    service = ConversationService(db_session, provider=provider)

    reply = service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Bonjour"))

    assert reply.engine_result.next_state == ConversationState.GREETING
    assert reply.response_text == "Bonjour ! Comment puis-je vous aider ?"


def test_handle_message_persists_both_customer_and_assistant_messages(db_session):
    _, conversation = _new_conversation(db_session)
    provider = ScriptedProvider(
        extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}},
        response_text="Bonjour !",
    )
    service = ConversationService(db_session, provider=provider)

    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Bonjour"))

    history = ConversationRepository(db_session).get_history(conversation)
    assert [m.role for m in history] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert history[0].content == "Bonjour"
    assert history[1].content == "Bonjour !"


def test_extraction_entities_are_applied_to_the_lead(db_session):
    lead, conversation = _new_conversation(db_session)
    # START -> GREETING -> DISCOVERY -> INTENT_CONFIRMATION -> COLLECT_CUSTOMER_TYPE
    setup_provider = ScriptedProvider(extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}})
    service = ConversationService(db_session, provider=setup_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Bonjour"))  # START -> GREETING
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Je veux changer"))  # GREETING -> DISCOVERY (event ignored here)

    # DISCOVERY only advances to INTENT_CONFIRMATION on an unambiguous signal
    # (PROVIDE_INFORMATION/CHANGE_INTENT_YES/CHANGE_INTENT_NO), not a generic
    # CUSTOMER_MESSAGE - see state_machine.py's DISCOVERY branch (F-001).
    intent_provider = ScriptedProvider(extraction_payload={"event_type": "PROVIDE_INFORMATION", "entities": {}})
    service = ConversationService(db_session, provider=intent_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Oui je veux changer"))  # DISCOVERY -> INTENT_CONFIRMATION

    yes_provider = ScriptedProvider(extraction_payload={"event_type": "CHANGE_INTENT_YES", "entities": {}})
    service = ConversationService(db_session, provider=yes_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Oui"))  # -> COLLECT_CUSTOMER_TYPE

    type_provider = ScriptedProvider(
        extraction_payload={"event_type": "PROVIDE_INFORMATION", "entities": {"customer_type": "particulier"}}
    )
    service = ConversationService(db_session, provider=type_provider)
    reply = service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Je suis un particulier"))

    assert lead.customer_type == "particulier"
    assert reply.engine_result.next_state == ConversationState.COLLECT_LOCATION


# --- expected_field context threading ------------------------------------------------------


def test_last_question_action_becomes_expected_field_context_on_next_turn(db_session):
    _, conversation = _new_conversation(db_session)
    setup_provider = ScriptedProvider(extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}})
    service = ConversationService(db_session, provider=setup_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Bonjour"))  # -> GREETING, asked ASK_INTENT

    follow_up_provider = ScriptedProvider(extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}})
    service = ConversationService(db_session, provider=follow_up_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="changer de fournisseur"))

    extraction_call = next(c for c in follow_up_provider.calls if c["json_mode"] is True)
    system_message = extraction_call["messages"][0]
    assert isinstance(system_message, LLMMessage)
    # GREETING's required_action is ASK_INTENT, which has no entry in
    # _REQUIRED_ACTION_TO_EXPECTED_FIELD (it's not a qualification field) -
    # so no spurious context should be added.
    assert "Context:" not in system_message.content


def test_ask_ean_state_threads_ean_as_expected_field(db_session):
    lead, conversation = _new_conversation(db_session)
    setup_provider = ScriptedProvider(extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}})
    service = ConversationService(db_session, provider=setup_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Bonjour"))  # START -> GREETING
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="changer"))  # GREETING -> DISCOVERY
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="je veux changer"))  # DISCOVERY -> INTENT_CONFIRMATION

    yes_provider = ScriptedProvider(extraction_payload={"event_type": "CHANGE_INTENT_YES", "entities": {}})
    service = ConversationService(db_session, provider=yes_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Oui"))  # -> COLLECT_CUSTOMER_TYPE

    fill_provider = ScriptedProvider(
        extraction_payload={
            "event_type": "PROVIDE_INFORMATION",
            "entities": {
                "customer_type": "particulier",
                "region": "Wallonie",
                "city": "Namur",
                "current_supplier": "Engie",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean@test.com",
                "phone": "0470123456",
            },
        }
    )
    service = ConversationService(db_session, provider=fill_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="voici mes infos"))  # fills everything up to EAN

    ean_provider = ScriptedProvider(extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}})
    service = ConversationService(db_session, provider=ean_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="je ne sais pas"))

    extraction_call = next(c for c in ean_provider.calls if c["json_mode"] is True)
    assert "ean" in extraction_call["messages"][0].content


def test_reaching_qualified_also_notifies_sales_team_in_the_same_turn(db_session):
    """F-011 regression test.

    Before the fix, `state_machine.py`'s QUALIFIED -> HANDOFF
    (NOTIFY_SALES_TEAM) transition only fired on the *next* `process_turn()`
    call, so a customer who had just been qualified saw only the
    confirmation message and never the "sales team notified" one unless
    they happened to send another message afterwards. `handle_message()`
    must now chain that second, server-triggered turn automatically within
    the same request.
    """
    lead, conversation = _new_conversation(db_session)
    setup_provider = ScriptedProvider(extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}})
    service = ConversationService(db_session, provider=setup_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Bonjour"))  # START -> GREETING
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="changer"))  # GREETING -> DISCOVERY

    # DISCOVERY only advances to INTENT_CONFIRMATION on an unambiguous signal
    # (PROVIDE_INFORMATION/CHANGE_INTENT_YES/CHANGE_INTENT_NO), not a generic
    # CUSTOMER_MESSAGE - see state_machine.py's DISCOVERY branch (F-001).
    intent_provider = ScriptedProvider(extraction_payload={"event_type": "PROVIDE_INFORMATION", "entities": {}})
    service = ConversationService(db_session, provider=intent_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="je veux changer"))  # DISCOVERY -> INTENT_CONFIRMATION

    yes_provider = ScriptedProvider(extraction_payload={"event_type": "CHANGE_INTENT_YES", "entities": {}})
    service = ConversationService(db_session, provider=yes_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Oui"))  # -> COLLECT_CUSTOMER_TYPE

    fill_provider = ScriptedProvider(
        extraction_payload={
            "event_type": "PROVIDE_INFORMATION",
            "entities": {
                "customer_type": "particulier",
                "region": "Wallonie",
                "city": "Namur",
                "current_supplier": "Engie",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean@test.com",
                "phone": "0470123456",
            },
        }
    )
    service = ConversationService(db_session, provider=fill_provider)
    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="voici mes infos"))  # -> COLLECT_EAN

    ean_provider = ScriptedProvider(
        extraction_payload={"event_type": "PROVIDE_INFORMATION", "entities": {"ean": "541234567890123456"[:18]}},
        response_text="Merci, vous etes qualifie !",
    )
    service = ConversationService(db_session, provider=ean_provider)
    reply = service.handle_message(ConversationRequest(conversation_id=conversation.id, text="541234567890123456"))

    # The turn must land on HANDOFF (post-QUALIFIED), not stop at QUALIFIED.
    assert reply.engine_result.next_state == ConversationState.HANDOFF
    assert reply.engine_result.required_action == "NOTIFY_SALES_TEAM"
    assert reply.state == ConversationState.HANDOFF.value

    # Both the confirmation and the notification must be persisted as two
    # separate assistant messages, and both surfaced in this one response.
    history = ConversationRepository(db_session).get_history(conversation)
    assistant_messages = [m.content for m in history if m.role == MessageRole.ASSISTANT]
    assert len(assistant_messages) >= 2
    assert assistant_messages[-2] in reply.response_text
    assert assistant_messages[-1] in reply.response_text


# --- FAQ / objection via RAG ------------------------------------------------------


def test_question_event_triggers_rag_lookup_and_llm_phrasing(db_session):
    _, conversation = _new_conversation(db_session)
    provider = ScriptedProvider(
        extraction_payload={"event_type": "QUESTION", "entities": {}},
        response_text="Le changement est gratuit chez Ecofix.",
    )
    service = ConversationService(db_session, provider=provider)

    reply = service.handle_message(ConversationRequest(conversation_id=conversation.id, text="C'est gratuit ou il y a des frais ?"))

    assert reply.engine_result.next_state == ConversationState.FAQ
    assert reply.response_text == "Le changement est gratuit chez Ecofix."
    phrasing_call = next(c for c in provider.calls if c["json_mode"] is False)
    assert "gratuit" in phrasing_call["messages"][0].content.lower()


def test_question_with_no_rag_match_uses_generic_fallback_without_llm_call(db_session):
    _, conversation = _new_conversation(db_session)
    provider = ScriptedProvider(extraction_payload={"event_type": "QUESTION", "entities": {}})
    service = ConversationService(db_session, provider=provider)

    reply = service.handle_message(ConversationRequest(conversation_id=conversation.id, text="xyzabc nonsense words"))

    assert reply.engine_result.next_state == ConversationState.FAQ
    phrasing_calls = [c for c in provider.calls if c["json_mode"] is False]
    assert phrasing_calls == []  # generic fallback text, no LLM call needed


# --- degraded mode: no provider ------------------------------------------------------


def test_no_provider_still_advances_state_and_replies_with_fallback_text(db_session):
    _, conversation = _new_conversation(db_session)
    service = ConversationService(db_session, provider=None)

    reply = service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Bonjour"))

    assert reply.engine_result.next_state == ConversationState.GREETING
    assert reply.response_text  # fixed fallback text, non-empty
    assert isinstance(reply.response_text, str)


def test_no_provider_never_leaves_a_turn_without_a_persisted_reply(db_session):
    _, conversation = _new_conversation(db_session)
    service = ConversationService(db_session, provider=None)

    service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Bonjour"))

    history = ConversationRepository(db_session).get_history(conversation)
    assert len(history) == 2


# --- resilience: extraction failure ------------------------------------------------------


def test_extraction_failure_falls_back_to_clarification_not_a_crash(db_session):
    _, conversation = _new_conversation(db_session)
    provider = ScriptedProvider(extraction_payload={}, response_text="Pouvez-vous reformuler ?")
    provider.raise_on_extraction = LLMError("provider down")
    service = ConversationService(db_session, provider=provider)

    reply = service.handle_message(ConversationRequest(conversation_id=conversation.id, text="Bonjour"))

    # EXTRACTION_FAILED never changes state - engine stays at START and asks
    # for clarification instead of crashing the turn.
    assert reply.engine_result.required_action == "ASK_CLARIFICATION"
    assert reply.response_text == "Pouvez-vous reformuler ?"

"""
Tests for channels/web.py's WebChannel.

Since Phase 4A, all real orchestration logic (extractor -> engine -> rag ->
responder -> persistence) lives in `application/conversation_service.py`'s
`ConversationService` and is tested there (see tests/test_conversation_
service.py). WebChannel is now a thin adapter, so these tests only check
that it delegates correctly - constructs a `ConversationService`, builds a
`ConversationRequest` from the plain (conversation_id, text) shape the Web
transport already has, and passes through `start_conversation` /
`get_conversation` / `get_history` unchanged.
"""

import json

import pytest

from ai.providers.interface import LLMProvider, LLMResponse
from channels.web import WebChannel
from crm.conversation_repository import ConversationRepository
from domain.enums import ConversationChannel, ConversationState, LeadSource, MessageRole


class ScriptedProvider(LLMProvider):
    def __init__(self, extraction_payload: dict, response_text: str = "Bonjour !"):
        self.extraction_payload = extraction_payload
        self.response_text = response_text

    def generate(self, messages, *, temperature=0.0, max_tokens=1024, json_mode=False):
        if json_mode:
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


def test_start_conversation_creates_a_web_lead_and_conversation(db_session):
    channel = WebChannel(db_session, provider=None)

    lead, conversation = channel.start_conversation(email="jean@test.com")

    assert lead.source == LeadSource.WEBSITE
    assert lead.email == "jean@test.com"
    assert conversation.channel == ConversationChannel.WEB
    assert conversation.lead_id == lead.id


def test_get_conversation_returns_what_was_started(db_session):
    channel = WebChannel(db_session, provider=None)
    _, conversation = channel.start_conversation()

    fetched = channel.get_conversation(conversation.id)

    assert fetched is not None
    assert fetched.id == conversation.id


def test_handle_message_delegates_to_conversation_service_and_advances_state(db_session):
    channel = WebChannel(db_session, provider=None)
    _, conversation = channel.start_conversation()

    reply = channel.handle_message(conversation.id, "Bonjour")

    assert reply.state == ConversationState.GREETING.value
    assert reply.response_text  # fixed fallback text in no-provider mode


def test_get_history_returns_persisted_messages_in_order(db_session):
    channel = WebChannel(db_session, provider=None)
    _, conversation = channel.start_conversation()
    channel.handle_message(conversation.id, "Bonjour")

    history = channel.get_history(conversation.id)

    assert [m.role for m in history] == [MessageRole.USER, MessageRole.ASSISTANT]


def test_handle_message_with_a_provider_still_reaches_the_llm(db_session):
    provider = ScriptedProvider(
        extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}},
        response_text="Bonjour, comment puis-je vous aider ?",
    )
    channel = WebChannel(db_session, provider=provider)
    _, conversation = channel.start_conversation()

    reply = channel.handle_message(conversation.id, "Bonjour")

    assert reply.response_text == "Bonjour, comment puis-je vous aider ?"
    assert reply.engine_result.next_state == ConversationState.GREETING


def test_messages_are_visible_via_the_repository_directly(db_session):
    """Sanity check that WebChannel didn't invent its own persistence path -
    it's really going through ConversationService -> ConversationRepository."""
    channel = WebChannel(db_session, provider=None)
    _, conversation = channel.start_conversation()
    channel.handle_message(conversation.id, "Bonjour")

    history = ConversationRepository(db_session).get_history(conversation)
    assert len(history) == 2

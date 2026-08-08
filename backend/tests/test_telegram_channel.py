"""
Tests for channels/telegram.py's TelegramChannel.

Like WebChannel, this is a thin adapter over ConversationService - real
orchestration is tested once in test_conversation_service.py. What's unique
to Telegram and needs its own coverage here: parsing the webhook Update
shape, finding-or-creating a conversation by chat_id (external_id) so a
returning customer resumes instead of restarting, and the injectable
send_message callback.
"""

import json

import pytest

from ai.providers.interface import LLMProvider, LLMResponse
from channels.telegram import TelegramChannel
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


def _update(chat_id: int, text: str, first_name: str = "Jean", last_name: str = "Dupont") -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
            "from": {"id": chat_id, "first_name": first_name, "last_name": last_name},
        },
    }


def test_first_update_from_a_chat_id_creates_a_telegram_lead_and_conversation(db_session):
    channel = TelegramChannel(db_session, provider=None)

    response = channel.handle_update(_update(chat_id=12345, text="Bonjour"))

    assert response is not None
    assert response.state == ConversationState.GREETING.value

    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.TELEGRAM, "12345"
    )
    assert conversation is not None
    assert conversation.channel == ConversationChannel.TELEGRAM
    assert conversation.lead.source == LeadSource.TELEGRAM
    assert conversation.lead.first_name == "Jean"


def test_second_update_from_same_chat_id_resumes_the_same_conversation(db_session):
    channel = TelegramChannel(db_session, provider=None)

    channel.handle_update(_update(chat_id=999, text="Bonjour"))  # START -> GREETING
    channel.handle_update(_update(chat_id=999, text="Je veux changer de fournisseur"))  # -> DISCOVERY

    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.TELEGRAM, "999"
    )
    # Only ever one conversation for this chat_id - not a new one per message.
    assert conversation.current_state == ConversationState.DISCOVERY

    history = ConversationRepository(db_session).get_history(conversation)
    assert len(history) == 4  # 2 user + 2 assistant messages, all on one conversation


def test_different_chat_ids_get_different_conversations(db_session):
    channel = TelegramChannel(db_session, provider=None)

    channel.handle_update(_update(chat_id=1, text="Bonjour"))
    channel.handle_update(_update(chat_id=2, text="Bonjour"))

    repo = ConversationRepository(db_session)
    conv_1 = repo.get_by_external_id(ConversationChannel.TELEGRAM, "1")
    conv_2 = repo.get_by_external_id(ConversationChannel.TELEGRAM, "2")

    assert conv_1.id != conv_2.id
    assert conv_1.lead_id != conv_2.lead_id


def test_update_without_a_text_message_is_ignored(db_session):
    channel = TelegramChannel(db_session, provider=None)

    response = channel.handle_update({"update_id": 1, "edited_message": {"text": "oops"}})

    assert response is None


def test_send_message_callback_is_invoked_with_the_reply(db_session):
    sent: list[tuple[str, str]] = []

    channel = TelegramChannel(db_session, provider=None, send_message=lambda chat_id, text: sent.append((chat_id, text)))
    channel.handle_update(_update(chat_id=42, text="Bonjour"))

    assert len(sent) == 1
    chat_id, text = sent[0]
    assert chat_id == "42"
    assert text  # the fallback greeting text in no-provider mode


def test_handle_update_with_a_provider_still_reaches_the_llm(db_session):
    provider = ScriptedProvider(
        extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}},
        response_text="Bonjour, comment puis-je vous aider ?",
    )
    channel = TelegramChannel(db_session, provider=provider)

    response = channel.handle_update(_update(chat_id=7, text="Bonjour"))

    assert response.response_text == "Bonjour, comment puis-je vous aider ?"


def test_get_history_delegates_to_conversation_service(db_session):
    channel = TelegramChannel(db_session, provider=None)
    channel.handle_update(_update(chat_id=55, text="Bonjour"))
    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.TELEGRAM, "55"
    )

    history = channel.get_history(conversation.id)

    assert [m.role for m in history] == [MessageRole.USER, MessageRole.ASSISTANT]

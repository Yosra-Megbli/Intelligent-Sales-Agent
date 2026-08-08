"""
Tests for channels/whatsapp.py's WhatsAppChannel.

Same shape as tests/test_telegram_channel.py - thin adapter, real
orchestration tested once in test_conversation_service.py. What's unique to
WhatsApp: Twilio's flat form-encoded payload shape (not nested JSON like
Telegram), the `whatsapp:` prefix Twilio puts on phone numbers (stripped
before storing as `external_id`), and finding-or-creating a conversation by
phone number so a returning customer resumes instead of restarting.
"""

import json

import pytest

from ai.providers.interface import LLMProvider, LLMResponse
from channels.whatsapp import WhatsAppChannel
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


def _payload(phone: str, text: str, profile_name: str = "Jean") -> dict:
    return {
        "MessageSid": "SM123",
        "From": f"whatsapp:{phone}",
        "To": "whatsapp:+14155238886",
        "Body": text,
        "ProfileName": profile_name,
        "NumMedia": "0",
    }


def test_first_message_from_a_phone_creates_a_whatsapp_lead_and_conversation(db_session):
    channel = WhatsAppChannel(db_session, provider=None)

    response = channel.handle_update(_payload("+15551234567", "Bonjour"))

    assert response is not None
    assert response.state == ConversationState.GREETING.value

    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.WHATSAPP, "+15551234567"
    )
    assert conversation is not None
    assert conversation.channel == ConversationChannel.WHATSAPP
    assert conversation.lead.source == LeadSource.WHATSAPP
    assert conversation.lead.first_name == "Jean"


def test_external_id_is_stored_without_the_whatsapp_prefix(db_session):
    channel = WhatsAppChannel(db_session, provider=None)
    channel.handle_update(_payload("+15551234567", "Bonjour"))

    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.WHATSAPP, "+15551234567"
    )
    assert conversation is not None  # lookup by the bare number, not "whatsapp:+1555..."


def test_second_message_from_same_phone_resumes_the_same_conversation(db_session):
    channel = WhatsAppChannel(db_session, provider=None)

    channel.handle_update(_payload("+15559990000", "Bonjour"))  # START -> GREETING
    channel.handle_update(_payload("+15559990000", "Je veux changer de fournisseur"))  # -> DISCOVERY

    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.WHATSAPP, "+15559990000"
    )
    assert conversation.current_state == ConversationState.DISCOVERY

    history = ConversationRepository(db_session).get_history(conversation)
    assert len(history) == 4  # 2 user + 2 assistant messages, all on one conversation


def test_different_phone_numbers_get_different_conversations(db_session):
    channel = WhatsAppChannel(db_session, provider=None)

    channel.handle_update(_payload("+15550001111", "Bonjour"))
    channel.handle_update(_payload("+15552223333", "Bonjour"))

    repo = ConversationRepository(db_session)
    conv_1 = repo.get_by_external_id(ConversationChannel.WHATSAPP, "+15550001111")
    conv_2 = repo.get_by_external_id(ConversationChannel.WHATSAPP, "+15552223333")

    assert conv_1.id != conv_2.id
    assert conv_1.lead_id != conv_2.lead_id


def test_payload_without_a_body_is_ignored(db_session):
    """e.g. a Twilio delivery-status callback, not an inbound message."""
    channel = WhatsAppChannel(db_session, provider=None)

    response = channel.handle_update({"MessageSid": "SM999", "MessageStatus": "delivered"})

    assert response is None


def test_send_message_callback_is_invoked_with_the_reply(db_session):
    sent: list[tuple[str, str]] = []

    channel = WhatsAppChannel(
        db_session, provider=None, send_message=lambda phone, text: sent.append((phone, text))
    )
    channel.handle_update(_payload("+15551112222", "Bonjour"))

    assert len(sent) == 1
    phone, text = sent[0]
    assert phone == "+15551112222"  # no whatsapp: prefix passed to the sender
    assert text  # the fallback greeting text in no-provider mode


def test_handle_update_with_a_provider_still_reaches_the_llm(db_session):
    provider = ScriptedProvider(
        extraction_payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}},
        response_text="Bonjour, comment puis-je vous aider ?",
    )
    channel = WhatsAppChannel(db_session, provider=provider)

    response = channel.handle_update(_payload("+15557778888", "Bonjour"))

    assert response.response_text == "Bonjour, comment puis-je vous aider ?"


def test_get_history_delegates_to_conversation_service(db_session):
    channel = WhatsAppChannel(db_session, provider=None)
    channel.handle_update(_payload("+15559990001", "Bonjour"))
    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.WHATSAPP, "+15559990001"
    )

    history = channel.get_history(conversation.id)

    assert [m.role for m in history] == [MessageRole.USER, MessageRole.ASSISTANT]


def test_extract_phone_returns_none_for_a_payload_with_no_body():
    assert WhatsAppChannel.extract_phone({"MessageStatus": "delivered"}) is None


def test_extract_phone_strips_the_whatsapp_prefix():
    assert WhatsAppChannel.extract_phone(_payload("+15551234567", "Bonjour")) == "+15551234567"

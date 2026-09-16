"""
Tests for channels/sms.py's SmsChannel (Twilio SMS integration).

Invariants (AGENTS.md):
- Deterministic core: State Machine decides states; Rules Engine decides actions.
  The LLM only phrases replies.
- Compliance: AI disclosure mandatory on greeting, STOP/STOPT/ARRÊT immediate opt-out.
- Thin adapter over ConversationService.
"""

import json
import pytest

from ai.providers.interface import LLMProvider, LLMResponse
from channels.sms import SmsChannel
from crm.conversation_repository import ConversationRepository
from domain.enums import ConversationChannel, ConversationState, LeadSource, LeadStatus, MessageRole


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


def _sms_payload(phone: str, text: str) -> dict:
    return {
        "MessageSid": "SM_SMS_123",
        "From": phone,
        "To": "+32488000000",
        "Body": text,
    }


def test_first_message_from_a_phone_creates_an_sms_lead_and_conversation(db_session):
    channel = SmsChannel(db_session, provider=None)

    response = channel.handle_update(_sms_payload("+32488111222", "Bonjour"))

    assert response is not None
    assert response.state == ConversationState.GREETING.value

    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.SMS, "+32488111222"
    )
    assert conversation is not None
    assert conversation.channel == ConversationChannel.SMS
    assert conversation.lead.source == LeadSource.SMS
    assert conversation.lead.phone == "+32488111222"


def test_second_message_from_same_phone_resumes_the_same_conversation(db_session):
    channel = SmsChannel(db_session, provider=None)

    channel.handle_update(_sms_payload("+32488333444", "Bonjour"))
    channel.handle_update(_sms_payload("+32488333444", "Je veux changer d'énergie"))

    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.SMS, "+32488333444"
    )
    assert conversation.current_state == ConversationState.DISCOVERY

    history = ConversationRepository(db_session).get_history(conversation)
    assert len(history) == 4  # 2 user + 2 assistant


def test_different_phone_numbers_get_different_conversations(db_session):
    channel = SmsChannel(db_session, provider=None)

    channel.handle_update(_sms_payload("+32488555666", "Bonjour"))
    channel.handle_update(_sms_payload("+32488777888", "Bonjour"))

    repo = ConversationRepository(db_session)
    conv_1 = repo.get_by_external_id(ConversationChannel.SMS, "+32488555666")
    conv_2 = repo.get_by_external_id(ConversationChannel.SMS, "+32488777888")

    assert conv_1.id != conv_2.id
    assert conv_1.lead_id != conv_2.lead_id


def test_sms_payload_without_body_is_ignored(db_session):
    channel = SmsChannel(db_session, provider=None)
    response = channel.handle_update({"MessageSid": "SM_STATUS", "MessageStatus": "delivered"})
    assert response is None


def test_send_message_callback_is_invoked_with_sms_reply(db_session):
    sent: list[tuple[str, str]] = []

    channel = SmsChannel(
        db_session, provider=None, send_message=lambda phone, text: sent.append((phone, text))
    )
    channel.handle_update(_sms_payload("+32488999000", "Bonjour"))

    assert len(sent) == 1
    phone, text = sent[0]
    assert phone == "+32488999000"
    assert "assistante virtuelle" in text  # Mandatory compliance disclosure present


def test_sms_stop_keyword_triggers_immediate_opt_out(db_session):
    channel = SmsChannel(db_session, provider=None)
    channel.handle_update(_sms_payload("+32488123987", "Bonjour"))

    # Customer replies STOP
    response = channel.handle_update(_sms_payload("+32488123987", "STOP"))

    assert response is not None
    assert response.state == ConversationState.CLOSED.value

    conversation = ConversationRepository(db_session).get_by_external_id(
        ConversationChannel.SMS, "+32488123987"
    )
    assert conversation.current_state == ConversationState.CLOSED
    assert conversation.lead.status == LeadStatus.REJECTED
    assert conversation.lead.opt_out_at is not None


def test_sms_extract_phone_helper():
    assert SmsChannel.extract_phone({"From": "+32488111222", "Body": "Hello"}) == "+32488111222"
    assert SmsChannel.extract_phone({"MessageStatus": "delivered"}) is None

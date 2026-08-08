"""
Tests for Voice C: VoiceSessionManager.

Two layers, deliberately:
- Pure unit tests (the bulk of this file) against a `FakeConversationService`
  stub - fast, isolated, exercise every branch of the turn-taking logic
  (silence, low-confidence, confirmation accept/reject/unclear, hangup
  states) without needing a database, an LLM, or the real Engine.
- A handful of true integration tests against the real
  `ConversationService` + `db_session` + a `ScriptedProvider`, confirming
  the wiring actually works end-to-end (mirrors tests/
  test_conversation_service.py's own style), including a full EAN
  confirm-then-forward round trip.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from application.conversation_service import ConversationResponse, ConversationService
from channels.voice.providers.interface import TranscriptionResult
from channels.voice.session_manager import (
    DEFAULT_VOICE_POLICY,
    VoicePolicy,
    VoiceSessionManager,
    VoiceTurnState,
    _classify_yes_no,
)
from conversation_engine.engine import EngineResult
from domain.enums import ConversationChannel, ConversationState


# --- test helpers ------------------------------------------------------


def make_response(
    text="Bonjour", state=ConversationState.GREETING.value, required_action="ASK_INTENT"
) -> ConversationResponse:
    return ConversationResponse(
        response_text=text,
        state=state,
        required_action=required_action,
        engine_result=EngineResult(
            previous_state=ConversationState.START,
            next_state=ConversationState(state),
            required_action=required_action,
        ),
    )


class FakeConversationService:
    """Stub implementing only what VoiceSessionManager calls. Scripted
    per-test via `start_and_greet_response` / `handle_message_responses`
    (a list popped in call order) so each unit test controls exactly what
    the "Engine" appears to say back, without any real Engine/DB/LLM."""

    def __init__(self):
        self.start_and_greet_response: ConversationResponse = make_response()
        self.start_and_greet_conversation_id = uuid4()
        self.handle_message_responses: list[ConversationResponse] = []
        self.handle_message_calls: list[str] = []

    def start_and_greet(self, channel, *, external_id, language="fr", existing_lead_id=None):
        fake_conversation = SimpleNamespace(id=self.start_and_greet_conversation_id)
        return None, fake_conversation, self.start_and_greet_response

    def handle_message(self, request):
        self.handle_message_calls.append(request.text)
        return self.handle_message_responses.pop(0)


def make_transcription(text: str, confidence: float = 0.9) -> TranscriptionResult:
    return TranscriptionResult(text=text, confidence=confidence)


CONVERSATION_ID = uuid4()


# --- yes/no classification ------------------------------------------------------


@pytest.mark.parametrize("text", ["oui", "Oui !", "oui c'est ca", "exact", "d'accord", "ok"])
def test_classify_yes_no_recognizes_affirmatives(text):
    assert _classify_yes_no(text) is True


@pytest.mark.parametrize("text", ["non", "Non merci", "c'est faux", "incorrect"])
def test_classify_yes_no_recognizes_negatives(text):
    assert _classify_yes_no(text) is False


@pytest.mark.parametrize("text", ["peut-etre", "je ne sais pas", "allo", ""])
def test_classify_yes_no_returns_none_for_unclear_input(text):
    assert _classify_yes_no(text) is None


def test_classify_yes_no_prefers_none_when_both_appear():
    # "non non c'est correct" mixes signals - safer to treat as unclear
    # than to guess.
    assert _classify_yes_no("non non c'est correct") is None


# --- start_call ------------------------------------------------------


def test_start_call_speaks_the_greeting_and_tracks_required_action():
    service = FakeConversationService()
    service.start_and_greet_response = make_response(
        text="Bonjour, je suis Sophie.", state=ConversationState.GREETING.value, required_action="ASK_INTENT"
    )
    manager = VoiceSessionManager(service)

    result = manager.start_call(ConversationChannel.VOICE, external_id="+32470000000")

    assert result.speech_to_render == "Bonjour, je suis Sophie."
    assert result.should_hangup is False
    assert result.next_state.last_required_action == "ASK_INTENT"
    assert result.next_state.silence_attempts == 0


def test_start_call_hangs_up_immediately_if_engine_already_rejects():
    service = FakeConversationService()
    service.start_and_greet_response = make_response(
        text="Merci, au revoir.", state="REJECTED", required_action="SEND_REJECTION"
    )
    manager = VoiceSessionManager(service)

    result = manager.start_call(ConversationChannel.VOICE, external_id="+32470000000")

    assert result.should_hangup is True


# --- silence policy ------------------------------------------------------


def test_silence_reprompts_below_the_attempt_limit():
    manager = VoiceSessionManager(FakeConversationService())
    state = VoiceTurnState(last_required_action="ASK_LOCATION")

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=None)

    assert result.speech_to_render == DEFAULT_VOICE_POLICY.silence_reprompt_text
    assert result.should_hangup is False
    assert result.next_state.silence_attempts == 1
    # last_required_action carries forward unchanged - still the same
    # pending question.
    assert result.next_state.last_required_action == "ASK_LOCATION"


def test_blank_transcript_is_treated_the_same_as_none():
    manager = VoiceSessionManager(FakeConversationService())
    state = VoiceTurnState(last_required_action="ASK_LOCATION")

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("   "))

    assert result.speech_to_render == DEFAULT_VOICE_POLICY.silence_reprompt_text


def test_silence_hangs_up_after_exceeding_max_attempts():
    manager = VoiceSessionManager(FakeConversationService())
    state = VoiceTurnState(last_required_action="ASK_LOCATION", silence_attempts=DEFAULT_VOICE_POLICY.max_silence_attempts)

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=None)

    assert result.should_hangup is True
    assert result.speech_to_render == DEFAULT_VOICE_POLICY.goodbye_after_silence_text


def test_custom_policy_silence_limit_is_respected():
    policy = VoicePolicy(max_silence_attempts=1)
    manager = VoiceSessionManager(FakeConversationService(), policy=policy)
    state = VoiceTurnState(silence_attempts=1)

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=None)

    assert result.should_hangup is True


# --- low confidence ------------------------------------------------------


def test_low_confidence_transcript_triggers_reprompt_not_forwarded():
    service = FakeConversationService()
    manager = VoiceSessionManager(service)
    state = VoiceTurnState(last_required_action="ASK_EAN")

    result = manager.handle_turn(
        CONVERSATION_ID, state, transcription=make_transcription("cinq quatre un", confidence=0.1)
    )

    assert result.speech_to_render == DEFAULT_VOICE_POLICY.low_confidence_reprompt_text
    assert service.handle_message_calls == []  # never forwarded


def test_low_confidence_counts_toward_the_same_attempt_budget_as_silence():
    manager = VoiceSessionManager(FakeConversationService())
    state = VoiceTurnState(silence_attempts=DEFAULT_VOICE_POLICY.max_silence_attempts)

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("bruit", confidence=0.05))

    assert result.should_hangup is True


def test_confidence_exactly_at_threshold_is_accepted_not_treated_as_low():
    service = FakeConversationService()
    service.handle_message_responses = [make_response()]
    manager = VoiceSessionManager(service)
    state = VoiceTurnState(last_required_action="ASK_INTENT")

    result = manager.handle_turn(
        CONVERSATION_ID, state, transcription=make_transcription("oui", confidence=DEFAULT_VOICE_POLICY.min_confidence)
    )

    assert service.handle_message_calls == ["oui"]
    assert result.should_hangup is False


# --- normal turn (no confirmation needed) ------------------------------------------------------


def test_normal_turn_forwards_transcript_and_speaks_the_response():
    service = FakeConversationService()
    service.handle_message_responses = [
        make_response(text="Quel est votre fournisseur ?", state="COLLECT_SUPPLIER", required_action="ASK_SUPPLIER")
    ]
    manager = VoiceSessionManager(service)
    state = VoiceTurnState(last_required_action="ASK_LOCATION")

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("Namur, Wallonie"))

    assert service.handle_message_calls == ["Namur, Wallonie"]
    assert result.speech_to_render == "Quel est votre fournisseur ?"
    assert result.next_state.last_required_action == "ASK_SUPPLIER"
    assert result.next_state.silence_attempts == 0


def test_normal_turn_hangs_up_when_engine_reaches_a_terminal_state():
    service = FakeConversationService()
    service.handle_message_responses = [
        make_response(text="Au revoir.", state="CLOSED", required_action="NONE")
    ]
    manager = VoiceSessionManager(service)
    state = VoiceTurnState(last_required_action="ASK_SUPPLIER")

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("laissez tomber"))

    assert result.should_hangup is True


def test_normal_turn_with_no_response_text_speaks_empty_string_not_none():
    service = FakeConversationService()
    service.handle_message_responses = [make_response(text=None, state="FAQ", required_action="ANSWER_FAQ")]
    manager = VoiceSessionManager(service)
    state = VoiceTurnState(last_required_action="ASK_SUPPLIER")

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("bonjour"))

    assert result.speech_to_render == ""


# --- confirmation: entering the flow ------------------------------------------------------


def test_ean_answer_triggers_confirmation_instead_of_forwarding():
    service = FakeConversationService()
    manager = VoiceSessionManager(service)
    state = VoiceTurnState(last_required_action="ASK_EAN")

    result = manager.handle_turn(
        CONVERSATION_ID, state, transcription=make_transcription("541448860000000001")
    )

    assert service.handle_message_calls == []  # not forwarded yet
    assert "541448860000000001" in result.speech_to_render
    assert result.next_state.pending_confirmation_field == "ASK_EAN"
    assert result.next_state.pending_confirmation_text == "541448860000000001"


def test_ean_correction_action_also_triggers_confirmation():
    manager = VoiceSessionManager(FakeConversationService())
    state = VoiceTurnState(last_required_action="ASK_EAN_CORRECTION")

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("541448860000000002"))

    assert result.next_state.pending_confirmation_field == "ASK_EAN_CORRECTION"


def test_non_confirmation_field_is_never_gated_by_confirmation():
    service = FakeConversationService()
    service.handle_message_responses = [make_response()]
    manager = VoiceSessionManager(service)
    state = VoiceTurnState(last_required_action="ASK_SUPPLIER")

    manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("Engie"))

    assert service.handle_message_calls == ["Engie"]


# --- confirmation: accept ------------------------------------------------------


def test_confirming_yes_forwards_the_original_transcript_not_the_word_oui():
    service = FakeConversationService()
    service.handle_message_responses = [
        make_response(text="Merci.", state="DATA_VALIDATION", required_action="SEND_QUALIFIED_CONFIRMATION")
    ]
    manager = VoiceSessionManager(service)
    state = VoiceTurnState(
        last_required_action="ASK_EAN",
        pending_confirmation_field="ASK_EAN",
        pending_confirmation_text="541448860000000001",
    )

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("oui"))

    assert service.handle_message_calls == ["541448860000000001"]
    assert result.next_state.pending_confirmation_field is None
    assert result.next_state.pending_confirmation_text is None


# --- confirmation: reject ------------------------------------------------------


def test_confirming_no_re_asks_without_ever_calling_conversation_service():
    service = FakeConversationService()
    manager = VoiceSessionManager(service)
    state = VoiceTurnState(
        last_required_action="ASK_EAN",
        last_prompt_text="Pouvez-vous me communiquer votre code EAN ?",
        pending_confirmation_field="ASK_EAN",
        pending_confirmation_text="541448860000000001",
    )

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("non"))

    assert service.handle_message_calls == []
    assert result.speech_to_render == "Pouvez-vous me communiquer votre code EAN ?"
    assert result.next_state.pending_confirmation_field is None


# --- confirmation: unclear / bounded retries ------------------------------------------------------


def test_unclear_confirmation_response_reprompts_without_forwarding():
    service = FakeConversationService()
    manager = VoiceSessionManager(service)
    state = VoiceTurnState(pending_confirmation_field="ASK_EAN", pending_confirmation_text="123")

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("hein ?"))

    assert service.handle_message_calls == []
    assert result.speech_to_render == DEFAULT_VOICE_POLICY.unclear_confirmation_reprompt_text
    assert result.next_state.confirmation_attempts == 1
    # still pending - not cleared
    assert result.next_state.pending_confirmation_field == "ASK_EAN"


def test_repeated_unclear_confirmations_eventually_hang_up():
    manager = VoiceSessionManager(FakeConversationService())
    state = VoiceTurnState(
        pending_confirmation_field="ASK_EAN",
        pending_confirmation_text="123",
        confirmation_attempts=DEFAULT_VOICE_POLICY.max_confirmation_attempts,
    )

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("quoi ?"))

    assert result.should_hangup is True
    assert result.speech_to_render == DEFAULT_VOICE_POLICY.goodbye_after_confirmation_confusion_text


def test_confirmation_attempts_reset_after_a_successful_confirmation():
    service = FakeConversationService()
    service.handle_message_responses = [make_response()]
    manager = VoiceSessionManager(service)
    state = VoiceTurnState(
        pending_confirmation_field="ASK_EAN", pending_confirmation_text="123", confirmation_attempts=1
    )

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("oui"))

    assert result.next_state.confirmation_attempts == 0


# --- custom policy: extending confirmation fields ------------------------------------------------------


def test_custom_policy_can_extend_which_fields_require_confirmation():
    policy = VoicePolicy(fields_requiring_confirmation=frozenset({"ASK_CONTACT"}))
    service = FakeConversationService()
    manager = VoiceSessionManager(service, policy=policy)
    state = VoiceTurnState(last_required_action="ASK_CONTACT")

    result = manager.handle_turn(CONVERSATION_ID, state, transcription=make_transcription("Jean Dupont"))

    assert service.handle_message_calls == []
    assert result.next_state.pending_confirmation_field == "ASK_CONTACT"


# --- integration: real ConversationService ------------------------------------------------------


@pytest.fixture(autouse=True)
def fake_redis_cache(monkeypatch):
    store: dict = {}

    def fake_cache(conversation_id, context, ttl_seconds=3600):
        store[conversation_id] = context

    def fake_get(conversation_id):
        return store.get(conversation_id)

    monkeypatch.setattr("conversation_engine.memory.cache_conversation_context", fake_cache)
    monkeypatch.setattr("conversation_engine.memory.get_cached_conversation_context", fake_get)
    yield store


def test_integration_start_call_creates_a_real_voice_lead_and_conversation(db_session):
    service = ConversationService(db_session, provider=None)
    manager = VoiceSessionManager(service)

    result = manager.start_call(ConversationChannel.VOICE, external_id="+32470000001")

    assert result.speech_to_render  # fixed fallback greeting in no-provider mode
    conversation = service.get_conversation_by_external_id(ConversationChannel.VOICE, "+32470000001")
    assert conversation is not None
    assert conversation.channel == ConversationChannel.VOICE


def test_integration_ean_confirmation_round_trip_reaches_the_real_engine(db_session):
    import json

    from ai.providers.interface import LLMProvider, LLMResponse

    class ScriptedProvider(LLMProvider):
        def __init__(self, payload, text="D'accord."):
            self.payload = payload
            self.text = text

        def generate(self, messages, *, temperature=0.0, max_tokens=1024, json_mode=False):
            if json_mode:
                return LLMResponse(content=json.dumps(self.payload), model="fake")
            return LLMResponse(content=self.text, model="fake")

    provider = ScriptedProvider(payload={"event_type": "CUSTOMER_MESSAGE", "entities": {}})
    service = ConversationService(db_session, provider=provider)
    manager = VoiceSessionManager(service)

    _, conversation = service.start_conversation(ConversationChannel.VOICE, external_id="+32470000002")
    state = VoiceTurnState(last_required_action="ASK_EAN", last_prompt_text="Quel est votre code EAN ?")

    # Turn 1: customer speaks the EAN - should trigger a confirmation
    # read-back, NOT reach the real Engine yet.
    turn1 = manager.handle_turn(conversation.id, state, make_transcription("541448860000000001"))
    assert turn1.next_state.pending_confirmation_field == "ASK_EAN"

    # Turn 2: customer confirms - NOW it reaches ConversationService, which
    # reaches the real Engine/Extractor/Responder.
    turn2 = manager.handle_turn(conversation.id, turn1.next_state, make_transcription("oui"))
    assert turn2.conversation_response is not None
    assert turn2.next_state.pending_confirmation_field is None

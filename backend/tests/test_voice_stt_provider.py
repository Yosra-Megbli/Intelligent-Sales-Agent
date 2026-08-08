"""
Tests for Voice A: the SpeechToTextProvider interface and its Tier A
concrete implementation, TwilioVoiceSpeechToText.

No network access, no real Twilio call - `TwilioVoiceSpeechToText` never
makes one (it's a pure parser over an already-decoded webhook payload), so
these are plain unit tests, same spirit as tests/test_llm_provider.py.
"""

import pytest

from channels.voice.providers.interface import (
    MalformedSpeechInputError,
    SpeechInput,
    SpeechToTextError,
    SpeechToTextProvider,
    TranscriptionResult,
)
from channels.voice.providers.twilio_stt import TwilioVoiceSpeechToText


# --- interface-level contracts ------------------------------------------------------


def test_speech_to_text_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        SpeechToTextProvider()


def test_all_stt_errors_are_catchable_as_speech_to_text_error():
    from channels.voice.providers.interface import (
        SpeechToTextAuthenticationError,
        SpeechToTextTimeoutError,
        SpeechToTextUnavailableError,
    )

    for error_cls in (
        SpeechToTextTimeoutError,
        SpeechToTextUnavailableError,
        SpeechToTextAuthenticationError,
        MalformedSpeechInputError,
    ):
        assert issubclass(error_cls, SpeechToTextError)


def test_speech_input_defaults_to_neither_field_set():
    speech_input = SpeechInput()
    assert speech_input.webhook_payload is None
    assert speech_input.audio_bytes is None


# --- TwilioVoiceSpeechToText: happy path ------------------------------------------------------


def test_transcribes_a_normal_webhook_payload():
    provider = TwilioVoiceSpeechToText()
    payload = {"SpeechResult": "Je voudrais changer de fournisseur", "Confidence": "0.93"}

    result = provider.transcribe(SpeechInput(webhook_payload=payload))

    assert isinstance(result, TranscriptionResult)
    assert result.text == "Je voudrais changer de fournisseur"
    assert result.confidence == pytest.approx(0.93)
    assert result.is_final is True


def test_strips_surrounding_whitespace_from_the_transcript():
    provider = TwilioVoiceSpeechToText()
    payload = {"SpeechResult": "  Namur, Wallonie  ", "Confidence": "0.8"}

    result = provider.transcribe(SpeechInput(webhook_payload=payload))

    assert result.text == "Namur, Wallonie"


def test_captures_the_language_field_when_present():
    provider = TwilioVoiceSpeechToText()
    payload = {"SpeechResult": "Bonjour", "Confidence": "0.9", "Language": "fr-FR"}

    result = provider.transcribe(SpeechInput(webhook_payload=payload))

    assert result.language_detected == "fr-FR"


def test_language_is_none_when_absent():
    provider = TwilioVoiceSpeechToText()
    payload = {"SpeechResult": "Bonjour", "Confidence": "0.9"}

    result = provider.transcribe(SpeechInput(webhook_payload=payload))

    assert result.language_detected is None


def test_raw_payload_is_preserved_for_logging():
    provider = TwilioVoiceSpeechToText()
    payload = {"SpeechResult": "Bonjour", "Confidence": "0.9", "CallSid": "CA123"}

    result = provider.transcribe(SpeechInput(webhook_payload=payload))

    assert result.raw == payload


# --- no speech captured (silence / timed-out gather) ------------------------------------------------------


def test_missing_speech_result_returns_none_not_an_error():
    provider = TwilioVoiceSpeechToText()
    payload = {"CallSid": "CA123"}  # Twilio still posts other fields on a timeout

    result = provider.transcribe(SpeechInput(webhook_payload=payload))

    assert result is None


def test_blank_speech_result_returns_none():
    provider = TwilioVoiceSpeechToText()
    payload = {"SpeechResult": "   "}

    result = provider.transcribe(SpeechInput(webhook_payload=payload))

    assert result is None


def test_empty_string_speech_result_returns_none():
    provider = TwilioVoiceSpeechToText()
    payload = {"SpeechResult": ""}

    result = provider.transcribe(SpeechInput(webhook_payload=payload))

    assert result is None


# --- confidence parsing edge cases ------------------------------------------------------


def test_missing_confidence_defaults_to_fully_confident():
    provider = TwilioVoiceSpeechToText()
    payload = {"SpeechResult": "Oui"}

    result = provider.transcribe(SpeechInput(webhook_payload=payload))

    assert result.confidence == 1.0


def test_non_numeric_confidence_defaults_to_fully_confident_rather_than_crashing():
    provider = TwilioVoiceSpeechToText()
    payload = {"SpeechResult": "Oui", "Confidence": "not-a-number"}

    result = provider.transcribe(SpeechInput(webhook_payload=payload))

    assert result.confidence == 1.0


def test_out_of_range_confidence_is_clamped_not_rejected():
    provider = TwilioVoiceSpeechToText()
    over = provider.transcribe(SpeechInput(webhook_payload={"SpeechResult": "Oui", "Confidence": "1.5"}))
    under = provider.transcribe(SpeechInput(webhook_payload={"SpeechResult": "Oui", "Confidence": "-0.2"}))

    assert over.confidence == 1.0
    assert under.confidence == 0.0


def test_zero_confidence_is_a_valid_value_not_treated_as_missing():
    provider = TwilioVoiceSpeechToText()
    payload = {"SpeechResult": "Oui", "Confidence": "0.0"}

    result = provider.transcribe(SpeechInput(webhook_payload=payload))

    assert result.confidence == 0.0


# --- malformed input ------------------------------------------------------


def test_audio_bytes_input_raises_malformed_error_since_this_is_tier_a():
    provider = TwilioVoiceSpeechToText()

    with pytest.raises(MalformedSpeechInputError):
        provider.transcribe(SpeechInput(audio_bytes=b"\x00\x01\x02"))


def test_neither_field_set_raises_malformed_error():
    provider = TwilioVoiceSpeechToText()

    with pytest.raises(MalformedSpeechInputError):
        provider.transcribe(SpeechInput())


def test_malformed_error_is_catchable_as_the_base_speech_to_text_error():
    provider = TwilioVoiceSpeechToText()

    with pytest.raises(SpeechToTextError):
        provider.transcribe(SpeechInput())


# --- architecture purity ------------------------------------------------------


def test_twilio_stt_module_never_imports_conversation_engine_or_application_layer():
    """Same discipline as tests/test_architecture_boundaries.py: even a
    Tier A, zero-network STT provider must not know ConversationService,
    the Engine, or ai/* exist - it only ever produces a TranscriptionResult
    and hands it back to whatever calls it (the future Voice Session
    Manager, Voice C)."""
    import ast
    import inspect

    from channels.voice.providers import twilio_stt as twilio_stt_module

    tree = ast.parse(inspect.getsource(twilio_stt_module))
    forbidden_prefixes = ("conversation_engine", "application", "ai.extractor", "ai.rag", "ai.responder", "crm")

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            assert not any(module_name.startswith(p) for p in forbidden_prefixes), (
                f"channels/voice/providers/twilio_stt.py must not import: {module_name or names}"
            )

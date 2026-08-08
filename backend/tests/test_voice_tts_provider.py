"""
Tests for Voice B: the TextToSpeechProvider interface and its Tier A
concrete implementation, TwilioVoiceTextToSpeech.

No network access, no real Twilio call - `TwilioVoiceTextToSpeech` never
makes one (it's a pure markup builder), same spirit as
tests/test_voice_stt_provider.py.
"""

import pytest

from channels.voice.providers.interface import (
    RenderedSpeech,
    TextToSpeechAuthenticationError,
    TextToSpeechError,
    TextToSpeechProvider,
    TextToSpeechUnavailableError,
    UnsupportedLanguageError,
)
from channels.voice.providers.twilio_tts import TwilioVoiceTextToSpeech


# --- interface-level contracts ------------------------------------------------------


def test_text_to_speech_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        TextToSpeechProvider()


def test_all_tts_errors_are_catchable_as_text_to_speech_error():
    for error_cls in (
        TextToSpeechUnavailableError,
        TextToSpeechAuthenticationError,
        UnsupportedLanguageError,
    ):
        assert issubclass(error_cls, TextToSpeechError)


def test_rendered_speech_defaults_to_neither_field_set():
    rendered = RenderedSpeech()
    assert rendered.markup is None
    assert rendered.audio_bytes is None
    assert rendered.content_type is None


# --- TwilioVoiceTextToSpeech: happy path ------------------------------------------------------


def test_renders_french_text_with_the_french_locale():
    provider = TwilioVoiceTextToSpeech()

    result = provider.render("Bonjour, je suis Sophie.", language="fr")

    assert isinstance(result, RenderedSpeech)
    assert result.audio_bytes is None
    assert result.markup == '<Say language="fr-FR">Bonjour, je suis Sophie.</Say>'


def test_renders_english_text_with_the_english_locale():
    provider = TwilioVoiceTextToSpeech()

    result = provider.render("Hello, how can I help?", language="en")

    assert result.markup == '<Say language="en-US">Hello, how can I help?</Say>'


def test_renders_dutch_text_with_the_dutch_locale():
    provider = TwilioVoiceTextToSpeech()

    result = provider.render("Hallo, hoe kan ik helpen?", language="nl")

    assert result.markup == '<Say language="nl-NL">Hallo, hoe kan ik helpen?</Say>'


def test_unrecognized_language_falls_back_to_french_default():
    provider = TwilioVoiceTextToSpeech()

    result = provider.render("Ciao!", language="it")

    assert 'language="fr-FR"' in result.markup


def test_strips_surrounding_whitespace_before_rendering():
    provider = TwilioVoiceTextToSpeech()

    result = provider.render("   Bonjour   ", language="fr")

    assert result.markup == '<Say language="fr-FR">Bonjour</Say>'


# --- XML escaping ------------------------------------------------------


def test_ampersand_is_escaped():
    provider = TwilioVoiceTextToSpeech()

    result = provider.render("Ecofix & vous", language="fr")

    assert "&amp;" in result.markup
    assert "Ecofix & vous" not in result.markup


def test_angle_brackets_are_escaped():
    provider = TwilioVoiceTextToSpeech()

    result = provider.render("moins de <18 ans", language="fr")

    assert "&lt;18" in result.markup


def test_escaping_does_not_break_valid_xml_structure():
    import xml.etree.ElementTree as ET

    provider = TwilioVoiceTextToSpeech()
    result = provider.render('Tom & Jerry <said> "hello"', language="fr")

    # Wrapping in a dummy root to parse just the fragment - if escaping is
    # correct this must not raise ET.ParseError.
    ET.fromstring(f"<root>{result.markup}</root>")


# --- empty/blank input ------------------------------------------------------


def test_empty_text_raises_rather_than_producing_a_silent_empty_say():
    provider = TwilioVoiceTextToSpeech()

    with pytest.raises(TextToSpeechError):
        provider.render("", language="fr")


def test_blank_text_raises():
    provider = TwilioVoiceTextToSpeech()

    with pytest.raises(TextToSpeechError):
        provider.render("   ", language="fr")


# --- architecture purity ------------------------------------------------------


def test_twilio_tts_module_never_imports_conversation_engine_or_application_layer():
    """Same discipline as tests/test_architecture_boundaries.py and
    test_voice_stt_provider.py: a Tier A, zero-network TTS provider must
    not know ConversationService, the Engine, or ai/* exist."""
    import ast
    import inspect

    from channels.voice.providers import twilio_tts as twilio_tts_module

    tree = ast.parse(inspect.getsource(twilio_tts_module))
    forbidden_prefixes = ("conversation_engine", "application", "ai.extractor", "ai.rag", "ai.responder", "crm")

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            assert not any(module_name.startswith(p) for p in forbidden_prefixes), (
                f"channels/voice/providers/twilio_tts.py must not import: {module_name or names}"
            )

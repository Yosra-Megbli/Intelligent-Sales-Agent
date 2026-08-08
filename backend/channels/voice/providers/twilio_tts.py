"""
Twilio Voice Text-to-Speech (Tier A concrete implementation of Voice B).

Twilio Voice's `<Say>` verb performs speech synthesis server-side from a
plain (optionally SSML-flavoured) markup string embedded directly in the
TwiML response - there is no separate audio file to generate or upload.
This class makes **no network call of its own**: it is a pure, synchronous
markup builder. It never talks to Twilio's API directly; it only produces
the `<Say>` fragment that whatever assembles the full TwiML response (the
future Voice Session Manager / Voice Adapter, Voice C) will embed.

Deliberately the simplest possible `TextToSpeechProvider` implementation,
matching this codebase's established preference for raw vendor-native
markup over a heavy SDK (see `channels/whatsapp.py`'s docstring making the
same choice for messaging, and `twilio_stt.py`'s equivalent choice for
Voice A).

This provider does **not** rewrite, reformat, or digit-group the text it's
given - that's `ai/responder.py`'s voice-mode prompt tightening (see
voice_agent_architecture.md section 12). This class's only job is turning
already-final text into valid, correctly-escaped, correctly-localized
TwiML markup.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from channels.voice.providers.interface import (
    RenderedSpeech,
    TextToSpeechError,
    TextToSpeechProvider,
)

# Twilio's <Say> `language` attribute wants a BCP-47 locale, not the bare
# 2-letter code `Conversation.language` stores. Falls back to French for
# anything unrecognized - the same default the rest of the system uses
# (see ai/responder.py's own conversation.language handling).
_TWILIO_LOCALE_BY_LANGUAGE: dict[str, str] = {
    "fr": "fr-FR",
    "nl": "nl-NL",
    "en": "en-US",
}
_DEFAULT_TWILIO_LOCALE = "fr-FR"


class TwilioVoiceTextToSpeech(TextToSpeechProvider):
    """Tier A: builds a `<Say>` TwiML fragment. Holds no per-call state -
    construct one per process, same as `TwilioVoiceSpeechToText`."""

    def render(self, text: str, language: str) -> RenderedSpeech:
        if not text or not text.strip():
            # A caller bug, not a runtime provider failure - there is
            # nothing meaningful to say, and a silent, empty <Say></Say>
            # would leave the caller hearing nothing with no indication why.
            raise TextToSpeechError("TwilioVoiceTextToSpeech.render() was given empty/blank text.")

        locale = _TWILIO_LOCALE_BY_LANGUAGE.get(language, _DEFAULT_TWILIO_LOCALE)
        markup = f'<Say language="{locale}">{escape(text.strip())}</Say>'
        return RenderedSpeech(markup=markup)

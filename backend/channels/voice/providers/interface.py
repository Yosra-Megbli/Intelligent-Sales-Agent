"""
Voice Provider interfaces: Speech-to-Text (Voice A) and Text-to-Speech
(Voice B).

This is the abstraction boundary between the Voice Session Manager (Voice C,
not yet built) and any concrete STT/TTS integration. Everything above this
layer talks to a `SpeechToTextProvider`/`TextToSpeechProvider`, never to a
vendor SDK or a raw webhook shape directly. Swapping providers, or moving
from a Tier A to a Tier B integration (see below), means writing a new class
in this package; nothing else in the codebase changes.

Both interfaces mirror the exact shape of `ai/providers/interface.py`'s
`LLMProvider` deliberately - same reasoning, same discipline: one abstract
method per provider type, a dedicated exception hierarchy callers can catch
without knowing which vendor is configured, and plain-data result types.

Reference: `docs/architecture/voice_agent_architecture.md`, sections 4-5.

Two integration tiers must fit through both `transcribe()` and `render()`:

- **Tier A — provider-embedded** (e.g. Twilio Voice's
  `<Gather input="speech">` for STT, `<Say>` for TTS): the transcript (or
  spoken output) is produced by the telephony provider itself as part of
  the same webhook/response cycle. A Tier A provider's methods make no
  network call of their own.
- **Tier B — decoupled** (e.g. raw audio piped to Deepgram/Whisper for STT,
  or to Amazon Polly/ElevenLabs for TTS): a real network call is made to an
  external service and its result (transcript, or synthesized audio) is
  returned.

Golden rule (mirrors ai/README.md's for LLMProvider): this package only
converts between audio and text in each direction. It never decides what to
do with that text - not whether a transcript is confident enough to act on
(the Voice Session Manager's Error Recovery policy, section 10), not what
`ConversationState` anything relates to, not anything about a Lead. This
layer doesn't know what a "Lead" is.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SpeechInput:
    """What a `SpeechToTextProvider.transcribe()` call receives. Exactly one
    of the two fields is populated, depending on which integration tier the
    provider represents - never both, never neither.

    - Tier A providers expect `webhook_payload` set, `audio_bytes` None.
    - Tier B providers expect `audio_bytes` set, `webhook_payload` None.

    A provider implementation is responsible for raising `SpeechToTextError`
    if handed the shape it doesn't understand, rather than guessing.
    """

    webhook_payload: Optional[dict[str, Any]] = None
    audio_bytes: Optional[bytes] = None


@dataclass
class TranscriptionResult:
    """The result of one transcription attempt. `confidence` is a plain
    0.0-1.0 float regardless of how the underlying provider expresses it
    (some return 0-100, some 0-1, some a qualitative label) - normalizing
    that mapping is each concrete provider's own responsibility, so every
    caller of this interface can compare confidence values the same way no
    matter which provider is configured.
    """

    text: str
    confidence: float
    language_detected: Optional[str] = None
    # False only for a Tier B streaming integration returning a partial,
    # not-yet-finalized transcript (Voice D, not yet built - see
    # docs/architecture/voice_agent_architecture.md section 6). Every Tier A
    # result, and every Tier B result before streaming exists, is final.
    is_final: bool = True
    raw: dict[str, Any] = field(default_factory=dict)


class SpeechToTextError(Exception):
    """Base class for every error this package raises. Callers catch this -
    never a vendor-specific exception - so the Voice Session Manager stays
    decoupled from which STT provider is configured."""


class SpeechToTextTimeoutError(SpeechToTextError):
    """The provider did not respond in time, including after retries. Only
    meaningful for a Tier B provider - a Tier A provider has no network call
    of its own to time out."""


class SpeechToTextUnavailableError(SpeechToTextError):
    """The provider is unreachable or returned a server error. Voice Session
    Manager's Error Recovery policy (section 10) treats this the same way
    as an LLM provider outage: end the call gracefully rather than leave the
    caller on a silent, un-endable line - never let this propagate as an
    unhandled exception to the telephony webhook layer."""


class SpeechToTextAuthenticationError(SpeechToTextError):
    """Missing or invalid credentials for a Tier B provider. Never retried."""


class MalformedSpeechInputError(SpeechToTextError):
    """Raised when a provider is handed a `SpeechInput` shape it cannot
    process (e.g. a Tier A provider given `audio_bytes` instead of a
    `webhook_payload`, or neither field populated at all) - a caller/wiring
    bug, not a runtime provider failure."""


class SpeechToTextProvider(ABC):
    """Every concrete provider (Twilio's embedded STT today; Deepgram,
    Whisper, or another Tier B service later) implements this contract.
    `transcribe` is intentionally the only method - there is no separate
    "start listening" / "stop listening" call on this interface, because
    that session-lifecycle concern belongs to the Voice Session Manager and
    the Telephony Provider abstraction (voice_agent_architecture.md section
    13), not to Speech-to-Text itself.
    """

    @abstractmethod
    def transcribe(self, speech_input: SpeechInput) -> Optional[TranscriptionResult]:
        """Turn `speech_input` into a `TranscriptionResult`, or `None` if
        there was genuinely nothing to transcribe (e.g. a Tier A webhook
        payload with no speech-result field at all - silence or a timed-out
        gather). A `None` result is handled by the Voice Session Manager's
        Silence Policy exactly like a low-confidence result; it is not an
        error and must not raise.

        Must raise a `SpeechToTextError` subclass on an actual failure
        (a Tier B network/API error, a malformed input shape) - never a
        vendor SDK exception directly, and never a fabricated empty
        `TranscriptionResult` used to signal failure silently.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Text-to-Speech (Voice B)
#
# Symmetric to Speech-to-Text above, deliberately: same two integration
# tiers, same "one coherent capability, one abstract method" shape.
#
# - Tier A - provider-native markup (e.g. Twilio Voice's `<Say>`): the
#   provider itself turns marked-up text into spoken audio at call time: a
#   Tier A `render()` call makes no network call of its own, it only builds
#   a provider-specific markup string ready to be embedded in that
#   provider's own response format (a TwiML document, for Twilio).
# - Tier B - a separate TTS service synthesizes actual audio bytes (Amazon
#   Polly, ElevenLabs, ...): `render()` calls out to that service and
#   returns the resulting audio.
#
# Reference: docs/architecture/voice_agent_architecture.md, section 5.
# ---------------------------------------------------------------------------


@dataclass
class RenderedSpeech:
    """The result of one `TextToSpeechProvider.render()` call. Exactly one
    of the two fields is populated, mirroring `SpeechInput`'s own tiering:

    - Tier A providers return `markup` set, `audio_bytes` None.
    - Tier B providers return `audio_bytes` (+ `content_type`) set,
      `markup` None.

    Whatever assembles the full response to the telephony provider (the
    future Voice Session Manager / Voice Adapter, not this package) is
    responsible for knowing which shape its configured provider returns and
    embedding it correctly - this type only carries the result, it doesn't
    interpret it.
    """

    markup: Optional[str] = None
    audio_bytes: Optional[bytes] = None
    content_type: Optional[str] = None  # e.g. "audio/mpeg" - Tier B only


class TextToSpeechError(Exception):
    """Base class for every error this package raises for TTS. Callers
    catch this - never a vendor-specific exception - so the Voice Session
    Manager stays decoupled from which TTS provider is configured."""


class TextToSpeechUnavailableError(TextToSpeechError):
    """The provider is unreachable or returned a server error. Only
    meaningful for a Tier B provider with a real network call - a Tier A
    provider builds markup locally and has nothing to be "unavailable".
    Voice Session Manager's Error Recovery policy (section 10) treats this
    the same way as an STT or LLM provider outage: fail toward a graceful,
    pre-defined spoken apology or hangup, never leave the caller on a
    silent, un-endable line."""


class TextToSpeechAuthenticationError(TextToSpeechError):
    """Missing or invalid credentials for a Tier B provider. Never retried."""


class UnsupportedLanguageError(TextToSpeechError):
    """Raised when asked to render a `language` the provider genuinely
    cannot speak in at all (as opposed to `ai/responder.py`'s own fallback
    of just defaulting to French for an unrecognized locale code - that
    fallback happens *before* this layer is ever called; this error is for
    a provider that was asked for a language it fundamentally has no voice
    for, not a missing mapping this package could resolve on its own)."""


class TextToSpeechProvider(ABC):
    """Every concrete provider (Twilio's `<Say>` today; Amazon Polly,
    ElevenLabs, or another Tier B service later) implements this contract.
    `render` is intentionally the only method, mirroring
    `SpeechToTextProvider.transcribe` - one coherent capability per
    provider abstraction, nothing about call/session lifecycle here."""

    @abstractmethod
    def render(self, text: str, language: str) -> RenderedSpeech:
        """Turn `text` (already fully phrased and voice-formatted by
        `ai/responder.py`'s voice-mode prompt tightening - see
        voice_agent_architecture.md section 12; this method does not do any
        of its own text rewriting, digit-grouping, or pacing) into a
        `RenderedSpeech` for the given 2-letter `language` code (`"fr"`,
        `"en"`, `"nl"` - the same values `Conversation.language` already
        stores; mapping to a provider-specific locale, e.g. `"fr-FR"`, is
        this provider's own responsibility, not the caller's).

        Must raise a `TextToSpeechError` subclass on an actual failure -
        never a vendor SDK exception directly, and never silently return
        empty/fallback audio without raising, since a caller needs to know
        rendering failed in order to run its own Error Recovery policy
        (section 10) rather than unknowingly play nothing.
        """
        raise NotImplementedError

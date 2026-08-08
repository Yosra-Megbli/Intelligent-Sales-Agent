"""
Twilio Voice Speech-to-Text (Tier A concrete implementation of Voice A).

Twilio Voice's `<Gather input="speech">` performs speech recognition
server-side and delivers the result as ordinary form fields on the same
webhook hit that reports the call - `SpeechResult` (the transcript) and
`Confidence` (a 0.0-1.0 float, already in that range - no rescaling needed,
unlike some vendors that report 0-100). This class makes **no network call
of its own**: it is a pure, synchronous parser over a payload the Voice
Adapter has already form-decoded into a plain dict (mirroring exactly how
`channels/whatsapp.py` treats Twilio's WhatsApp webhook body - form-encoded
fields, not JSON).

This is deliberately the simplest possible `SpeechToTextProvider`
implementation, matching this codebase's established preference for raw
HTTP/vendor-native payloads over a heavy SDK (see `channels/whatsapp.py`'s
own docstring making the same choice for messaging). A Tier B provider
(Deepgram, Whisper, ...) would look nothing like this file - it would
actually call out over the network - but implements the exact same
`SpeechToTextProvider` contract, which is the whole point of the
abstraction in `interface.py`.
"""

from __future__ import annotations

from typing import Optional

from channels.voice.providers.interface import (
    MalformedSpeechInputError,
    SpeechInput,
    SpeechToTextProvider,
    TranscriptionResult,
)

# Twilio's own documented range for the Confidence field. Used only to
# defend against a malformed/out-of-range value from a misbehaving payload
# (e.g. a hand-crafted test fixture, or a future Twilio API change) - never
# to apply any business judgement about "is this confident enough", which
# is the Voice Session Manager's job (Error Recovery, section 10), not
# this provider's.
_MIN_CONFIDENCE = 0.0
_MAX_CONFIDENCE = 1.0

# Used when Twilio's webhook includes a SpeechResult but omits Confidence
# entirely - this has been observed to happen for some Gather
# configurations. Treating a present-but-unscored transcript as fully
# confident is the safer default: it is handed onward exactly as a normal
# transcript would be, leaving any further judgement to the Voice Session
# Manager's own confidence threshold rather than this provider inventing a
# specific number that isn't actually known.
_DEFAULT_CONFIDENCE_WHEN_MISSING = 1.0


class TwilioVoiceSpeechToText(SpeechToTextProvider):
    """Tier A: reads `SpeechResult`/`Confidence`/`Language` straight off a
    Twilio Voice webhook payload. Construct one per process, same as
    `TwilioWhatsAppSender` - it holds no per-call state of its own."""

    def transcribe(self, speech_input: SpeechInput) -> Optional[TranscriptionResult]:
        if speech_input.webhook_payload is None:
            raise MalformedSpeechInputError(
                "TwilioVoiceSpeechToText is a Tier A provider and only "
                "accepts SpeechInput.webhook_payload - got audio_bytes (or "
                "neither field set) instead. Check the Voice Adapter is "
                "wiring the webhook payload through, not raw audio."
            )

        payload = speech_input.webhook_payload
        text = payload.get("SpeechResult")
        if not text or not text.strip():
            # No speech captured this turn (silence, or the Gather timed
            # out with nothing said) - not an error, see interface.py's
            # docstring on the None return.
            return None

        confidence = self._parse_confidence(payload.get("Confidence"))
        language_detected = payload.get("Language") or None

        return TranscriptionResult(
            text=text.strip(),
            confidence=confidence,
            language_detected=language_detected,
            is_final=True,
            raw=dict(payload),
        )

    @staticmethod
    def _parse_confidence(raw_value) -> float:
        if raw_value is None:
            return _DEFAULT_CONFIDENCE_WHEN_MISSING
        try:
            confidence = float(raw_value)
        except (TypeError, ValueError):
            return _DEFAULT_CONFIDENCE_WHEN_MISSING
        # Clamp rather than reject - a slightly out-of-range value (e.g.
        # floating-point noise producing 1.0000001) shouldn't crash a live
        # call over a cosmetic issue.
        return max(_MIN_CONFIDENCE, min(_MAX_CONFIDENCE, confidence))

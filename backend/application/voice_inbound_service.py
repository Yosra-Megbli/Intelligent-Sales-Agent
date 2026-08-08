"""
Voice Inbound Service (Application layer).

The missing piece between `api/voice_routes.py`'s TwiML webhook and
`channels/voice/session_manager.py`'s `VoiceSessionManager` (Voice C).
Same layering discipline as `application/voice_outbound_service.py`: the
HTTP layer never touches a repository, a Voice Provider, or
`VoiceSessionManager` directly - it only calls this service and gets back
ready-to-return TwiML (see `tests/test_architecture_boundaries.py`'s
`test_voice_routes_never_import_repositories_engine_or_outbound_internals_directly`).

Turn-taking state (`VoiceTurnState`) is, by `VoiceSessionManager`'s own
design, not persisted anywhere - it is this module's job to thread it
between one HTTP request and the next, since Twilio makes one independent
webhook request per turn. Done here via Redis, keyed by Twilio's `CallSid`
(see `database/redis.py`'s `cache_voice_call_state`), not via the
`<Gather>` action URL - a URL-encoded blob would also work per the module
docstring's suggestion, but would leak turn-taking internals into a URL
Twilio logs and would need to survive query-string length/escaping limits
for an unbounded number of turns; a small Redis-backed session keyed by a
value Twilio already threads through every request for us is simpler.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Optional
from uuid import UUID
from xml.sax.saxutils import escape

from channels.voice.providers.interface import SpeechInput
from channels.voice.providers.twilio_stt import TwilioVoiceSpeechToText
from channels.voice.providers.twilio_tts import TwilioVoiceTextToSpeech
from channels.voice.session_manager import VoiceSessionManager, VoiceTurnState
from application.conversation_service import ConversationService
from crm.lead_repository import LeadRepository
from database.redis import cache_voice_call_state, clear_voice_call_state, get_cached_voice_call_state
from domain.enums import ConversationChannel

_TWIML_ANSWER_WEBHOOK_PATH = "/api/voice/twiml"

_APOLOGY_TWIML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<Response>"
    '<Say language="fr-FR">'
    "Desole, une erreur technique nous empeche de poursuivre. Un conseiller Ecofix vous recontactera. Au revoir."
    "</Say>"
    "<Hangup/>"
    "</Response>"
)

_TWILIO_LOCALE_BY_LANGUAGE: dict[str, str] = {"fr": "fr-FR", "nl": "nl-NL", "en": "en-US"}
_DEFAULT_TWILIO_LOCALE = "fr-FR"


@dataclass
class TwiMLResult:
    xml: str
    should_hangup: bool


class VoiceInboundService:
    def __init__(self, db_session, provider=None):
        self.db = db_session
        self.lead_repo = LeadRepository(db_session)
        self._service = ConversationService(db_session, provider=provider)
        self._manager = VoiceSessionManager(self._service)
        self._stt = TwilioVoiceSpeechToText()
        self._tts = TwilioVoiceTextToSpeech()

    def handle_webhook(
        self,
        payload: dict[str, Any],
        *,
        lead_id: Optional[UUID],
        language: str = "fr",
    ) -> TwiMLResult:
        """One Twilio webhook hit, in or out of an existing call. Never
        raises - any failure degrades to `_APOLOGY_TWIML` (a caller stuck on
        a silent, un-endable line is worse than a mid-call apology), mirroring
        the Error Recovery philosophy `channels/voice/session_manager.py`
        already applies to STT/LLM failures."""
        call_sid = payload.get("CallSid")
        if not call_sid:
            return TwiMLResult(xml=_APOLOGY_TWIML, should_hangup=True)

        cached = get_cached_voice_call_state(call_sid)
        try:
            if cached is None:
                result = self._start(call_sid, lead_id, language)
            else:
                result = self._continue(call_sid, cached, payload)
        except Exception:
            clear_voice_call_state(call_sid)
            return TwiMLResult(xml=_APOLOGY_TWIML, should_hangup=True)

        if result is None:
            return TwiMLResult(xml=_APOLOGY_TWIML, should_hangup=True)

        if result.should_hangup:
            clear_voice_call_state(call_sid)
        else:
            cache_voice_call_state(
                call_sid,
                {"conversation_id": str(result.conversation_id), "state": asdict(result.next_state)},
            )

        return TwiMLResult(xml=self._build_twiml(result, language), should_hangup=result.should_hangup)

    def _start(self, call_sid: str, lead_id: Optional[UUID], language: str):
        if lead_id is None:
            return None
        lead = self.lead_repo.get_by_id(lead_id)
        if lead is None:
            return None
        return self._manager.start_call(
            ConversationChannel.VOICE,
            external_id=f"call:{call_sid}",
            language=language,
            existing_lead_id=lead_id,
        )

    def _continue(self, call_sid: str, cached: dict[str, Any], payload: dict[str, Any]):
        conversation_id = UUID(cached["conversation_id"])
        state = VoiceTurnState(**cached["state"])
        speech_input = SpeechInput(webhook_payload=payload)
        transcription = self._stt.transcribe(speech_input)
        return self._manager.handle_turn(conversation_id, state, transcription)

    def _build_twiml(self, result, language: str) -> str:
        say_markup = self._tts.render(result.speech_to_render, language).markup

        if result.should_hangup:
            return f'<?xml version="1.0" encoding="UTF-8"?><Response>{say_markup}<Hangup/></Response>'

        locale = _TWILIO_LOCALE_BY_LANGUAGE.get(language, _DEFAULT_TWILIO_LOCALE)
        action_url = escape(_build_webhook_url())
        return (
            '<?xml version="1.0" encoding="UTF-8"?><Response>'
            f'<Gather input="speech" action="{action_url}" method="POST" '
            f'speechTimeout="auto" language="{locale}" actionOnEmptyResult="true">'
            f"{say_markup}"
            "</Gather>"
            f"{say_markup}"
            "<Hangup/>"
            "</Response>"
        )


def _build_webhook_url() -> str:
    """Same base path outbound calls already hand Twilio for the first hit
    (`application/voice_outbound_service.py`'s `_build_webhook_url`) - a
    `<Gather>`'s follow-up turns reuse it unchanged since `CallSid` (not a
    query param) is what threads state from here on."""
    base_url = (os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")
    return f"{base_url}{_TWIML_ANSWER_WEBHOOK_PATH}"

"""
Voice Session Manager (Voice C, Tier A only).

See `docs/architecture/voice_c_responsibilities.md` for the authoritative
scope of this module before reading the code - in short: this is the *only*
place voice-communication mechanics (silence, low-confidence recovery,
confirmation read-backs, deciding when to hang up) live. It is not allowed
to import `conversation_engine`/`ai/*` - its only integration point is
`ConversationService`, exactly like every other channel
(`channels/web.py`/`telegram.py`/`whatsapp.py`). Enforced by
`tests/test_architecture_boundaries.py`.

Tier A scope note: no WebSockets, no Media Streams, no real-time barge-in.
Every turn is a discrete request/response. Turn-taking state
(`VoiceTurnState`) is deliberately NOT persisted to PostgreSQL and not
owned by `ConversationService` - it is threaded through by whatever wires
this module to a real Voice Provider (Voice E, not yet built), e.g. encoded
into the `<Gather>` action URL between one HTTP turn and the next.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional
from uuid import UUID

from application.conversation_service import (
    ConversationRequest,
    ConversationResponse,
    ConversationService,
)
from channels.voice.providers.interface import TranscriptionResult
from domain.enums import ConversationChannel

# --- policy -----------------------------------------------------------------


@dataclass(frozen=True)
class VoicePolicy:
    """Every configurable voice-mechanics number/string lives here, not
    scattered through the class below - mirrors how
    `business_rules/dialogue_policy.yaml` centralizes its own thresholds,
    though this is deliberately a plain dataclass rather than a YAML file
    for this iteration (no runtime reason yet to reload it without a
    process restart; revisit if that changes)."""

    max_silence_attempts: int = 2
    silence_reprompt_text: str = "Etes-vous toujours avec moi ?"
    goodbye_after_silence_text: str = (
        "Je vais devoir raccrocher, n'hesitez pas a nous rappeler. Au revoir."
    )

    min_confidence: float = 0.4
    low_confidence_reprompt_text: str = "Desole, je n'ai pas bien compris. Pouvez-vous repeter ?"

    # required_action values whose transcribed value must be read back and
    # explicitly confirmed before ever reaching ConversationService. Starts
    # narrow (EAN only) per voice_c_responsibilities.md's documented scope
    # decision - easy to extend later without touching the logic below.
    fields_requiring_confirmation: frozenset[str] = field(
        default_factory=lambda: frozenset({"ASK_EAN", "ASK_EAN_CORRECTION"})
    )
    confirmation_prompt_template: str = "Je vais vous relire : {value}. Est-ce correct ?"
    max_confirmation_attempts: int = 2
    unclear_confirmation_reprompt_text: str = "Je n'ai pas compris : est-ce correct, oui ou non ?"
    goodbye_after_confirmation_confusion_text: str = (
        "Un conseiller Ecofix va vous recontacter pour finaliser cette information. Merci et au revoir."
    )

    goodbye_after_handoff_text: str = (
        "Un conseiller Ecofix va vous recontacter tres prochainement. Merci et au revoir."
    )

    # ConversationResponse.state values after which the call should end.
    hangup_states: frozenset[str] = field(
        default_factory=lambda: frozenset({"CLOSED", "HANDOFF", "REJECTED"})
    )


DEFAULT_VOICE_POLICY = VoicePolicy()

# Small, fixed, voice-local word lists for detecting a yes/no answer to a
# confirmation read-back. Deliberately NOT the Business Engine's intent
# classifier - confirming a transcript is correct is a voice-mechanics
# question, not a business decision (see voice_c_responsibilities.md).
_AFFIRMATIVE_WORDS = frozenset(
    {"oui", "yes", "correct", "exact", "exactement", "voila", "ja", "d'accord", "daccord", "ok"}
)
_NEGATIVE_WORDS = frozenset({"non", "no", "nee", "incorrect", "faux"})


def _classify_yes_no(text: str) -> Optional[bool]:
    """Returns True (affirmative), False (negative), or None (unclear) -
    never raises, never guesses on genuinely ambiguous input."""
    words = {w.strip(".,!? ").lower() for w in text.split()}
    is_affirmative = bool(words & _AFFIRMATIVE_WORDS)
    is_negative = bool(words & _NEGATIVE_WORDS)
    if is_affirmative and not is_negative:
        return True
    if is_negative and not is_affirmative:
        return False
    return None


# --- turn state / result -----------------------------------------------------------------


@dataclass
class VoiceTurnState:
    """Per-call turn-taking state. See the module docstring: not persisted
    to PostgreSQL, not owned by ConversationService. Passed in and a new
    instance returned by every `VoiceSessionManager` call - immutable in
    spirit even though the dataclass itself isn't frozen (kept simple to
    construct in tests)."""

    last_required_action: Optional[str] = None
    last_prompt_text: str = ""
    silence_attempts: int = 0
    confirmation_attempts: int = 0
    pending_confirmation_field: Optional[str] = None
    pending_confirmation_text: Optional[str] = None


@dataclass
class VoiceTurnResult:
    """What `VoiceSessionManager` hands back each turn. `speech_to_render`
    is plain, final text - handing it to a `TextToSpeechProvider` (Voice B)
    is the caller's job, not this module's; VoiceSessionManager never talks
    to a TTS/STT provider directly, only to `ConversationService` and its
    own policy text."""

    next_state: VoiceTurnState
    speech_to_render: str
    should_hangup: bool = False
    conversation_response: Optional[ConversationResponse] = None
    conversation_id: Optional[UUID] = None


# --- session manager -----------------------------------------------------------------


class VoiceSessionManager:
    """Handles one call's worth of turns, Tier A only (see module
    docstring). Constructed with a `ConversationService` - the *only*
    thing this class is allowed to call to make anything happen."""

    def __init__(self, service: ConversationService, policy: VoicePolicy = DEFAULT_VOICE_POLICY):
        self._service = service
        self._policy = policy

    def start_call(
        self,
        channel: ConversationChannel,
        external_id: str,
        *,
        language: str = "fr",
        existing_lead_id: Optional[UUID] = None,
    ) -> VoiceTurnResult:
        """First turn of a call: no transcription yet, Sophie speaks
        first. Mirrors how outbound chat already opens via
        `ConversationService.start_and_greet()` - a ringing/answered call
        is functionally the same shape as an outbound campaign message.

        Pass `existing_lead_id` for an outbound call (the lead already
        exists - see `application/voice_outbound_service.py`) so this opens
        a new Conversation on that same Lead instead of creating a second
        one; omit it for a hypothetical inbound call with no prior CRM
        record."""
        _, conversation, response = self._service.start_and_greet(
            channel, existing_lead_id=existing_lead_id, external_id=external_id, language=language
        )
        speech = response.response_text or ""
        next_state = VoiceTurnState(last_required_action=response.required_action, last_prompt_text=speech)
        return VoiceTurnResult(
            next_state=next_state,
            speech_to_render=speech,
            should_hangup=response.state in self._policy.hangup_states,
            conversation_response=response,
            conversation_id=conversation.id,
        )

    def handle_turn(
        self,
        conversation_id: UUID,
        state: VoiceTurnState,
        transcription: Optional[TranscriptionResult],
    ) -> VoiceTurnResult:
        """One turn: given the previous turn-taking state and this turn's
        (possibly absent/low-confidence) transcription, decide what to say
        next and whether to hang up."""

        if transcription is None or not transcription.text.strip():
            return self._handle_silence(state)

        if transcription.confidence < self._policy.min_confidence:
            return self._handle_low_confidence(state)

        if state.pending_confirmation_field is not None:
            return self._handle_confirmation_response(conversation_id, state, transcription)

        if state.last_required_action in self._policy.fields_requiring_confirmation:
            return self._start_confirmation(state, transcription)

        return self._forward_to_conversation_service(conversation_id, state, transcription.text)

    # --- silence / low-confidence -----------------------------------------------------------------

    def _handle_silence(self, state: VoiceTurnState) -> VoiceTurnResult:
        attempts = state.silence_attempts + 1
        if attempts > self._policy.max_silence_attempts:
            return VoiceTurnResult(
                next_state=VoiceTurnState(),
                speech_to_render=self._policy.goodbye_after_silence_text,
                should_hangup=True,
            )
        next_state = _replace_turn_state(state, silence_attempts=attempts)
        return VoiceTurnResult(next_state=next_state, speech_to_render=self._policy.silence_reprompt_text)

    def _handle_low_confidence(self, state: VoiceTurnState) -> VoiceTurnResult:
        # Deliberately reuses the silence-attempt counter and threshold -
        # low-confidence and silence are both "nothing usable was said this
        # turn" from the customer's perspective, and a single combined
        # attempt budget is simpler to reason about than two independent
        # ones that could otherwise let a confused call run twice as long
        # before ending gracefully.
        attempts = state.silence_attempts + 1
        if attempts > self._policy.max_silence_attempts:
            return VoiceTurnResult(
                next_state=VoiceTurnState(),
                speech_to_render=self._policy.goodbye_after_silence_text,
                should_hangup=True,
            )
        next_state = _replace_turn_state(state, silence_attempts=attempts)
        return VoiceTurnResult(next_state=next_state, speech_to_render=self._policy.low_confidence_reprompt_text)

    # --- confirmation -----------------------------------------------------------------

    def _start_confirmation(self, state: VoiceTurnState, transcription: TranscriptionResult) -> VoiceTurnResult:
        prompt = self._policy.confirmation_prompt_template.format(value=transcription.text)
        next_state = _replace_turn_state(
            state,
            silence_attempts=0,
            pending_confirmation_field=state.last_required_action,
            pending_confirmation_text=transcription.text,
        )
        return VoiceTurnResult(next_state=next_state, speech_to_render=prompt)

    def _handle_confirmation_response(
        self, conversation_id: UUID, state: VoiceTurnState, transcription: TranscriptionResult
    ) -> VoiceTurnResult:
        answer = _classify_yes_no(transcription.text)

        if answer is True:
            confirmed_text = state.pending_confirmation_text or ""
            cleared_state = _replace_turn_state(
                state,
                silence_attempts=0,
                confirmation_attempts=0,
                pending_confirmation_field=None,
                pending_confirmation_text=None,
            )
            return self._forward_to_conversation_service(conversation_id, cleared_state, confirmed_text)

        if answer is False:
            # Re-ask the original question - nothing was sent to
            # ConversationService, so no business state moved; just repeat
            # the same prompt that led to this (now-rejected) transcript.
            next_state = _replace_turn_state(
                state,
                silence_attempts=0,
                confirmation_attempts=0,
                pending_confirmation_field=None,
                pending_confirmation_text=None,
            )
            return VoiceTurnResult(next_state=next_state, speech_to_render=state.last_prompt_text)

        # Neither a clear yes nor no - bounded retry, mirroring the
        # architecture spec's F-009-avoidance recommendation (section 9):
        # cap confirmation retries rather than looping indefinitely.
        attempts = state.confirmation_attempts + 1
        if attempts > self._policy.max_confirmation_attempts:
            return VoiceTurnResult(
                next_state=VoiceTurnState(),
                speech_to_render=self._policy.goodbye_after_confirmation_confusion_text,
                should_hangup=True,
            )
        next_state = _replace_turn_state(state, confirmation_attempts=attempts)
        return VoiceTurnResult(next_state=next_state, speech_to_render=self._policy.unclear_confirmation_reprompt_text)

    # --- normal turn -----------------------------------------------------------------

    def _forward_to_conversation_service(
        self, conversation_id: UUID, state: VoiceTurnState, text: str
    ) -> VoiceTurnResult:
        response = self._service.handle_message(ConversationRequest(conversation_id=conversation_id, text=text))
        speech = response.response_text or ""
        next_state = VoiceTurnState(last_required_action=response.required_action, last_prompt_text=speech)
        return VoiceTurnResult(
            next_state=next_state,
            speech_to_render=speech,
            should_hangup=response.state in self._policy.hangup_states,
            conversation_response=response,
            conversation_id=conversation_id,
        )


def _replace_turn_state(state: VoiceTurnState, **overrides) -> VoiceTurnState:
    """Small helper so call sites read as "same state, except these
    fields" without hand-copying every untouched field."""
    return replace(state, **overrides)

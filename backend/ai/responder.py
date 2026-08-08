"""
Response Generator.

Phase 3D: turns a `conversation_engine.engine.EngineResult` (specifically its
`required_action` string - see state_machine.py's `_ASK_ACTION_BY_STATE` and
the other `required_action=` literals it returns) into the sentence Sophie
actually sends. This is the mirror image of ai/extractor.py: that module is
the only place free text comes *in*, this is the only place free text goes
*out*.

PURITY GUARANTEE (same discipline as ai/extractor.py and
conversation_engine/rules.py): this module never imports a repository, never
calls `.flush()`/`.commit()`, and never decides a Lead's status, qualification
score, or Conversation's current_state. `required_action` already *is* the
Business Engine's decision (rules.py + state_machine.py); this module's only
job is phrasing it in `conversation.language`.

"Prompts never contain business logic" (MASTER_ARCHITECTURE.md, rule 3): all
prompt text and talking points live under prompts/responder/ and
prompts/system/ (loaded via ai/prompt_loader.py, never hardcoded here). The
per-action entries in `_TALKING_POINTS` name only WHAT Sophie should
communicate (e.g. "ask for the customer's postal city and region") - never
which regions are covered, which EAN length is valid, or why a lead was
rejected. Those facts live exclusively in business_rules/*.yaml and
conversation_engine/rules.py; the one exception is `_REJECTION_TALKING_POINTS`,
which maps a `RejectionReason` the engine already decided to a talking point -
it reads that decision, it does not make it.

Every required_action has a fixed, hardcoded French fallback sentence (see
prompts/responder/fallback_text.yaml). If the LLM call fails for any reason,
or `provider` is None, Responder returns the fallback instead of raising -
Sophie must always be able to reply, even if the phrasing layer is down.
"""

from __future__ import annotations

from typing import Optional

from ai.prompt_loader import load_text, load_yaml
from ai.providers.interface import LLMError, LLMMessage, LLMProvider, LLMRole
from domain.enums import RejectionReason
from domain.models.conversation import Conversation
from domain.models.lead import Lead

# What Sophie should communicate for each `required_action`, in plain English
# instructions to the phrasing model - never the customer-facing text itself.
# "NONE" is deliberately absent: engine.py only calls the responder for
# actions that produce a message (see `respond`).
_TALKING_POINTS: dict[str, str] = load_yaml("responder/talking_points.yaml")

# `SEND_REJECTION` needs the reason the engine already decided (never invent
# or second-guess it here) to pick the right talking point.
_REJECTION_TALKING_POINTS: dict[RejectionReason, str] = {
    RejectionReason(key): value
    for key, value in load_yaml("responder/rejection_talking_points.yaml").items()
}

# Hardcoded French fallback text per action, used verbatim when the LLM call
# fails or no provider is configured. Kept deliberately short and generic -
# this is a safety net, not the primary phrasing path.
_FALLBACK_TEXT: dict[str, str] = load_yaml("responder/fallback_text.yaml")

_REJECTION_FALLBACK_TEXT: dict[RejectionReason, str] = {
    RejectionReason(key): value
    for key, value in load_yaml("responder/rejection_fallback_text.yaml").items()
}

# Actions the engine can produce that never generate a customer-facing
# message. Callers should not invoke `respond` for these.
_SILENT_ACTIONS = frozenset({"NONE", None})

_SYSTEM_PROMPT_TEMPLATE = load_text("responder/system.md")


def _talking_point_for(required_action: str, rejection_reason: Optional[str]) -> Optional[str]:
    if required_action == "SEND_REJECTION":
        if rejection_reason is None:
            return None
        return _REJECTION_TALKING_POINTS.get(RejectionReason(rejection_reason))
    return _TALKING_POINTS.get(required_action)


def _fallback_for(required_action: str, rejection_reason: Optional[str]) -> str:
    if required_action == "SEND_REJECTION":
        if rejection_reason is not None:
            return _REJECTION_FALLBACK_TEXT.get(
                RejectionReason(rejection_reason),
                _REJECTION_FALLBACK_TEXT[RejectionReason.NO_INTENT],
            )
        return _REJECTION_FALLBACK_TEXT[RejectionReason.NO_INTENT]
    return _FALLBACK_TEXT.get(required_action, "Un instant, je reviens vers vous.")


class Responder:
    """Wraps an `LLMProvider` to turn a `required_action` into a sentence.

    Usage: `Responder(provider).respond("ASK_EAN", conversation=conversation)`.
    `provider` may be `None` (or omitted) to always use the fixed fallback
    text - useful for tests or a degraded-mode deployment with no LLM
    configured.
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        self._provider = provider

    def respond(
        self,
        required_action: Optional[str],
        *,
        conversation: Conversation,
        lead: Optional[Lead] = None,
        rejection_reason: Optional[str] = None,
        rag_answer: Optional[str] = None,
    ) -> Optional[str]:
        """Return the sentence Sophie should send, or None for silent actions.

        `lead` is accepted but never inspected for facts (no name-dropping,
        no field values) - keeping the phrasing layer free of anything the
        Business Engine didn't already decide to include in the talking
        point. `rag_answer` carries Phase 3E's answer for ANSWER_FAQ /
        ANSWER_OBJECTION; without it those two actions fall back to a
        generic "handing this to a colleague" message.
        """
        if required_action in _SILENT_ACTIONS:
            return None

        if required_action in ("ANSWER_FAQ", "ANSWER_OBJECTION"):
            return self._respond_with_rag_answer(required_action, conversation, rag_answer)

        talking_point = _talking_point_for(required_action, rejection_reason)
        fallback = _fallback_for(required_action, rejection_reason)
        if talking_point is None:
            return fallback

        return self._generate(talking_point, conversation, fallback)

    def _respond_with_rag_answer(
        self, required_action: str, conversation: Conversation, rag_answer: Optional[str]
    ) -> str:
        fallback = _FALLBACK_TEXT[required_action]
        if not rag_answer or not rag_answer.strip():
            return fallback
        talking_point = (
            "Convey the following answer to the customer's question in your own natural "
            f"words, without adding new facts: {rag_answer.strip()}"
        )
        return self._generate(talking_point, conversation, fallback)

    def _generate(self, talking_point: str, conversation: Conversation, fallback: str) -> str:
        if self._provider is None:
            return fallback

        language = conversation.language or "fr"
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(language=language, talking_point=talking_point)
        messages = [LLMMessage(role=LLMRole.SYSTEM, content=system_prompt)]
        try:
            response = self._provider.generate(messages, temperature=0.7, json_mode=False)
        except LLMError:
            return fallback

        text = (response.content or "").strip()
        return text or fallback

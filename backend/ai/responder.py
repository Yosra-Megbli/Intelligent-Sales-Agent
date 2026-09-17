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

import logging
from typing import Optional

from ai.prompt_loader import load_text, load_yaml
from ai.providers.interface import LLMError, LLMMessage, LLMProvider, LLMRole
from conversation_engine.compliance import verify_output_guard
from domain.enums import RejectionReason
from domain.models.conversation import Conversation
from domain.models.lead import Lead

logger = logging.getLogger(__name__)

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


def _fallback_for(required_action: str, rejection_reason: Optional[str], language: str = "fr") -> str:
    if required_action == "SEND_REJECTION":
        if rejection_reason is not None:
            return _REJECTION_FALLBACK_TEXT.get(
                RejectionReason(rejection_reason),
                _REJECTION_FALLBACK_TEXT[RejectionReason.NO_INTENT],
            )
        return _REJECTION_FALLBACK_TEXT[RejectionReason.NO_INTENT]
    lang_key = f"{required_action}_{language}"
    return _FALLBACK_TEXT.get(lang_key) or _FALLBACK_TEXT.get(required_action, "Un instant, je reviens vers vous.")


class Responder:
    """Wraps an `LLMProvider` to turn a `required_action` into a sentence.

    Usage: `Responder(provider).respond(required_action, conversation)`.
    Without a provider (or when the LLM call fails), returns a hardcoded
    fallback sentence so Sophie can always reply.
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        self._provider = provider
        self.last_guard_violation: Optional[str] = None
        self.was_rate_limited: bool = False

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
        self.last_guard_violation = None

        if required_action in _SILENT_ACTIONS:
            return None

        if required_action in ("ANSWER_FAQ", "ANSWER_OBJECTION"):
            return self._respond_with_rag_answer(required_action, conversation, rag_answer)

        talking_point = _talking_point_for(required_action, rejection_reason)
        language = conversation.language or "fr"
        fallback = _fallback_for(required_action, rejection_reason, language=language)

        if required_action == "ASK_PARTIAL_CONTACT" and lead is not None:
            missing_items = []
            if not getattr(lead, "first_name", None) or not getattr(lead, "last_name", None):
                missing_items.append("nom et prénom" if language == "fr" else ("naam en voornaam" if language == "nl" else "full name"))
            if not getattr(lead, "email", None):
                missing_items.append("adresse email" if language == "fr" else ("e-mailadres" if language == "nl" else "email address"))
            if not getattr(lead, "phone", None):
                missing_items.append("numéro de téléphone" if language == "fr" else ("telefoonnummer" if language == "nl" else "phone number"))
            if not getattr(lead, "date_of_birth", None):
                missing_items.append("date de naissance (JJ/MM/AAAA)" if language == "fr" else ("geboortedatum (DD/MM/JJJJ)" if language == "nl" else "date of birth (DD/MM/YYYY)"))

            if missing_items:
                missing_str = ", ".join(missing_items)
                talking_point = (
                    f"Acknowledge the contact information already provided, and politely ask only for "
                    f"the missing information: {missing_str}."
                )
                if language == "fr":
                    fallback = f"Merci pour ces informations. Pourriez-vous me préciser votre {missing_str} pour finaliser votre dossier ?"
                elif language == "nl":
                    fallback = f"Bedankt voor deze informatie. Kunt u nog uw {missing_str} doorgeven om uw dossier te voltooien?"
                else:
                    fallback = f"Thank you for this information. Could you please provide your {missing_str} to complete your file?"

        if talking_point is None:
            return fallback

        return self._generate(talking_point, conversation, fallback, required_action=required_action)

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
        return self._generate(talking_point, conversation, fallback, required_action=required_action)

    def _generate(
        self,
        talking_point: str,
        conversation: Conversation,
        fallback: str,
        required_action: Optional[str] = None,
    ) -> str:
        self.was_rate_limited = False
        if self._provider is None:
            return fallback

        language = conversation.language or "fr"
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(language=language, talking_point=talking_point)
        messages = [LLMMessage(role=LLMRole.SYSTEM, content=system_prompt)]
        try:
            response = self._provider.generate(messages, temperature=0.7, json_mode=False)
        except LLMError as exc:
            if type(exc).__name__ == "LLMRateLimitError" or "rate" in str(exc).lower() or "429" in str(exc):
                self.was_rate_limited = True
            return fallback

        text = (response.content or "").strip()
        if not text:
            return fallback

        # Output Guard (Layer 5): deterministic anti-hallucination and compliance linter
        is_valid, violation = verify_output_guard(text, required_action=required_action, language=language)
        if not is_valid:
            self.last_guard_violation = violation
            logger.warning(
                "Output guard triggered (%s) for action %s: '%s' -> discarded and replaced with fallback.",
                violation,
                required_action,
                text,
            )
            return fallback

        self.last_guard_violation = None
        return text


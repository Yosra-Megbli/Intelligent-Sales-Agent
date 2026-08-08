"""
Conversation State Machine.

The only module allowed to decide a ConversationState. Its job is to:

1. Run the incoming Event through the Intent Classifier (normalization seam
   for Phase 3's NLP).
2. Handle the global overrides (REQUEST_HUMAN, EXTRACTION_FAILED, QUESTION,
   OBJECTION) that can happen from almost any state.
3. For everything else, consult `rules.py` for a business Action (never
   decide field order or validation itself) and translate that Action into
   a ConversationState.
4. For resuming after a FAQ/OBJECTION detour, consult `dialogue_policy.py`
   (never decide "keep looping vs escalate" itself).

This module never touches the database and never calls an LLM - it is a
plain function of (state, event, lead, conversation) -> decision, which is
exactly what makes it easy to unit test exhaustively. Persisting the result
is `conversation_engine/engine.py`'s job, via ConversationRepository.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from conversation_engine import dialogue_policy, rules
from conversation_engine.actions import Action, ActionType
from conversation_engine.intent_classifier import IntentClassifier
from conversation_engine.transitions import Event, EventType
from domain.enums import ConversationState, RejectionReason
from domain.models.conversation import Conversation
from domain.models.lead import Lead

_intent_classifier = IntentClassifier()

# Qualification sub-states, in the fixed order defined by the rules engine.
QUALIFICATION_STATES = (
    ConversationState.COLLECT_CUSTOMER_TYPE,
    ConversationState.COLLECT_LOCATION,
    ConversationState.COLLECT_SUPPLIER,
    ConversationState.COLLECT_CONTACT,
    ConversationState.COLLECT_EAN,
)

# Declarative map: field group name -> the ConversationState whose job is to
# collect it. This is a dialogue-layer concept (which screen/state asks for
# it), which is exactly why it lives here and not in rules.py - rules.py
# only knows about "field groups", never about ConversationState.
FIELD_GROUP_TO_STATE: dict[str, ConversationState] = {
    "customer_type": ConversationState.COLLECT_CUSTOMER_TYPE,
    "location": ConversationState.COLLECT_LOCATION,
    "current_supplier": ConversationState.COLLECT_SUPPLIER,
    "contact": ConversationState.COLLECT_CONTACT,
    "ean": ConversationState.COLLECT_EAN,
}

_ASK_ACTION_BY_STATE = {
    ConversationState.COLLECT_CUSTOMER_TYPE: "ASK_CUSTOMER_TYPE",
    ConversationState.COLLECT_LOCATION: "ASK_LOCATION",
    ConversationState.COLLECT_SUPPLIER: "ASK_SUPPLIER",
    ConversationState.COLLECT_CONTACT: "ASK_CONTACT",
    ConversationState.COLLECT_EAN: "ASK_EAN",
}


@dataclass
class StateDecision:
    next_state: ConversationState
    remember_previous: bool = False
    resume_previous: bool = False
    rejection_reason: Optional[RejectionReason] = None
    required_action: Optional[str] = None  # e.g. "ASK_EAN", "ASK_CLARIFICATION"


def _resolve_qualification_action(action: Action, lead: Lead) -> StateDecision:
    """Translate an Action coming from rules.py into a ConversationState.
    This is the one and only place that mapping happens.
    """
    if action.type == ActionType.VALIDATE:
        return StateDecision(next_state=ConversationState.DATA_VALIDATION)

    if action.type == ActionType.ASK_FIELD:
        next_state = FIELD_GROUP_TO_STATE[action.field]
        required_action = _ASK_ACTION_BY_STATE[next_state]
        if action.field == "location" and getattr(lead, "region", None) and not getattr(lead, "city", None):
            required_action = "ASK_CITY_ONLY"
        return StateDecision(next_state=next_state, required_action=required_action)

    if action.type == ActionType.QUALIFY:
        return StateDecision(next_state=ConversationState.QUALIFIED, required_action="SEND_QUALIFIED_CONFIRMATION")

    if action.type == ActionType.REJECT:
        return StateDecision(
            next_state=ConversationState.REJECTED,
            rejection_reason=action.reason,
            required_action="SEND_REJECTION",
        )

    if action.type == ActionType.CORRECT_FIELD:
        back_to_state = FIELD_GROUP_TO_STATE[action.field]
        correction_action = "ASK_EAN_CORRECTION" if action.field == "ean" else "ASK_CONTACT_CORRECTION"
        return StateDecision(next_state=back_to_state, required_action=correction_action)

    raise ValueError(f"Unexpected Action from rules engine: {action}")  # pragma: no cover


def decide(
    current_state: ConversationState,
    event: Event,
    lead: Lead,
    conversation: Optional[Conversation] = None,
    intent_classifier: Optional[IntentClassifier] = None,
    is_duplicate: bool = False,
) -> StateDecision:
    """The transition table. Every branch here must be covered by a test.

    `conversation` is optional only to keep unit tests that don't care about
    detour-count policy simple; it is required in practice whenever the
    current_state is FAQ/OBJECTION/WAITING_CUSTOMER-with-real-reply so the
    Dialogue Policy has something to reason about.

    `intent_classifier` defaults to a no-provider instance (pure
    normalization, no LLM call) - callers that want the LLM-backed
    disambiguation (Phase 3C) must pass one built with a real `LLMProvider`.
    See `conversation_engine/engine.py`, which is where that classifier is
    actually constructed and threaded through.

    `is_duplicate` (F-003 fix) is a fact the caller already looked up via
    `LeadRepository.find_duplicate()` before calling this function - this
    module stays database-free (see module docstring), it only forwards the
    flag to `rules.decide_validation()` when `current_state` is
    DATA_VALIDATION. Ignored otherwise.
    """
    classifier = intent_classifier or _intent_classifier
    event = classifier.classify(event, current_state=current_state)

    # --- Global overrides: these can happen from almost any state ---
    if event.type == EventType.REQUEST_HUMAN:
        return StateDecision(next_state=ConversationState.HANDOFF, required_action="NOTIFY_HUMAN")

    if event.type == EventType.EXTRACTION_FAILED:
        # Never changes state - just ask again (see conversation_state_machine.md)
        return StateDecision(next_state=current_state, required_action="ASK_CLARIFICATION")

    if event.type == EventType.QUESTION:
        return StateDecision(
            next_state=ConversationState.FAQ, remember_previous=True, required_action="ANSWER_FAQ"
        )

    if event.type == EventType.OBJECTION:
        return StateDecision(
            next_state=ConversationState.OBJECTION,
            remember_previous=True,
            required_action="ANSWER_OBJECTION",
        )

    # --- State-specific logic ---
    if current_state == ConversationState.START:
        return StateDecision(next_state=ConversationState.GREETING, required_action="SEND_GREETING")

    if current_state == ConversationState.GREETING:
        # Bug fix: this used to unconditionally move to DISCOVERY and ask
        # the intent question, ignoring the event entirely. A customer who
        # answers the intent question in the same breath as their greeting
        # ("Bonjour, je voudrais changer de fournisseur") had that answer
        # silently discarded and got asked again - exactly the same failure
        # mode F-001 (see DISCOVERY branch below) already fixed for
        # DISCOVERY itself. Mirror that same check here - but note
        # CUSTOMER_MESSAGE is deliberately excluded, unlike in DISCOVERY:
        # existing tests (test_greeting_goes_to_discovery,
        # test_full_happy_path_reaches_handoff, the WhatsApp/Telegram
        # "resume conversation" tests) all use a generic CUSTOMER_MESSAGE
        # as the customer's opening greeting and expect it to still land on
        # DISCOVERY so Sophie asks the intent question explicitly. Only the
        # unambiguous answer types below should skip straight past it.
        if event.type in (
            EventType.PROVIDE_INFORMATION,
            EventType.CHANGE_INTENT_YES,
            EventType.CHANGE_INTENT_NO,
        ):
            return StateDecision(
                next_state=ConversationState.INTENT_CONFIRMATION,
                required_action="CONFIRM_INTENT",
            )
        return StateDecision(next_state=ConversationState.DISCOVERY, required_action="ASK_INTENT")

    if current_state == ConversationState.DISCOVERY:
        # Bug fix (F-001): this used to only recognize PROVIDE_INFORMATION.
        # DISCOVERY's open question ("do you want to switch supplier?") can
        # get answered with a direct yes/no just as easily as with free text
        # - a customer who replies "Non merci" here was previously never
        # advanced past DISCOVERY at all: CHANGE_INTENT_NO fell through to
        # the "ask again" fallback below and Sophie re-asked ASK_INTENT
        # forever. Every unambiguous answer now goes to INTENT_CONFIRMATION
        # for the formal yes/no confirmation, exactly preserving the
        # intended two-step "always explicitly confirm" design.
        #
        # CUSTOMER_MESSAGE is deliberately excluded, mirroring the GREETING
        # branch above and for the same reason: a generic CUSTOMER_MESSAGE
        # carries no actual signal about intent (F-001's own regression -
        # golden scenario conv_change_of_mind_no, turn "Je me renseigne
        # juste": a vague, non-committal reply was being forced straight to
        # the formal yes/no confirmation instead of staying in DISCOVERY and
        # re-asking, which reads as Sophie pressuring a lead who hasn't
        # actually answered anything yet). Only the unambiguous answer types
        # below - a real PROVIDE_INFORMATION or an explicit yes/no - should
        # skip straight past it.
        if event.type in (
            EventType.PROVIDE_INFORMATION,
            EventType.CHANGE_INTENT_YES,
            EventType.CHANGE_INTENT_NO,
        ):
            return StateDecision(
                next_state=ConversationState.INTENT_CONFIRMATION,
                required_action="CONFIRM_INTENT",
            )
        return StateDecision(next_state=ConversationState.DISCOVERY, required_action="ASK_INTENT")

    if current_state == ConversationState.INTENT_CONFIRMATION:
        if event.type == EventType.CHANGE_INTENT_YES:
            lead.change_intent = True
            return _resolve_qualification_action(rules.next_qualification_action(lead), lead)
        if event.type == EventType.CHANGE_INTENT_NO:
            lead.change_intent = False
            return StateDecision(
                next_state=ConversationState.REJECTED,
                rejection_reason=RejectionReason.NO_CHANGE_INTENT,
                required_action="SEND_REJECTION",
            )
        # Anything else here is a clarification issue, not a state change.
        return StateDecision(next_state=current_state, required_action="ASK_CLARIFICATION")

    if current_state in QUALIFICATION_STATES:
        return _resolve_qualification_action(rules.next_qualification_action(lead), lead)

    if current_state == ConversationState.DATA_VALIDATION:
        return _resolve_qualification_action(rules.decide_validation(lead, is_duplicate=is_duplicate), lead)

    if current_state == ConversationState.QUALIFIED:
        return StateDecision(next_state=ConversationState.HANDOFF, required_action="NOTIFY_SALES_TEAM")

    if current_state == ConversationState.HANDOFF:
        # Bug fix (F-016, BAT SC-090): this used to unconditionally close
        # the conversation - silently, with no reply at all - on ANY
        # message received while waiting for a human, including a customer
        # just checking in ("Are you still there?"). HANDOFF now stays
        # HANDOFF and reassures the customer instead. Actually closing a
        # HANDOFF conversation is a human agent's call to make (there is no
        # such mechanism in this MVP yet), not something the bot should
        # decide on its own from one more customer message.
        return StateDecision(next_state=current_state, required_action="STILL_WAITING_FOR_HUMAN")

    if current_state == ConversationState.REJECTED:
        # Bug fix: this branch was previously missing entirely, so any event
        # arriving while current_state was REJECTED hit the "no transition
        # rule defined" fallback below and crashed. REJECTED behaves like
        # HANDOFF/QUALIFIED: it's a one-turn-then-terminal state, not
        # something a customer reply should ever re-open.
        return StateDecision(next_state=ConversationState.CLOSED, required_action="NONE")

    if current_state in (ConversationState.FAQ, ConversationState.OBJECTION):
        # Not the State Machine's call alone - the Dialogue Policy decides
        # whether to resume qualification or escalate after repeated detours.
        policy_action = dialogue_policy.decide_after_detour(conversation) if conversation else Action(type=ActionType.RESUME)
        if policy_action.type == ActionType.HANDOFF:
            return StateDecision(next_state=ConversationState.HANDOFF, required_action="NOTIFY_HUMAN")
        return StateDecision(next_state=current_state, resume_previous=True, required_action="NONE")

    if current_state == ConversationState.WAITING_CUSTOMER:
        if event.type == EventType.FOLLOW_UP_DUE:
            return StateDecision(next_state=current_state, required_action="SEND_FOLLOW_UP")
        # Any real customer reply resumes qualification where it stopped.
        return _resolve_qualification_action(rules.next_qualification_action(lead), lead)

    if current_state == ConversationState.CLOSED:
        return StateDecision(next_state=ConversationState.CLOSED, required_action="NONE")

    # Should never be reached if every ConversationState is handled above.
    raise ValueError(f"No transition rule defined for state: {current_state}")

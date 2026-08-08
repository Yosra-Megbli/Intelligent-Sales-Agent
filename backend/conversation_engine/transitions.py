"""
Conversation events.

An `Event` is the structured signal the engine reacts to. In Phase 2 this is
produced synthetically (by tests, or by hand) - in Phase 3 it will be
produced by ai/extractor.py from the raw customer message. The engine itself
never parses free text; it only ever reasons about these fixed event types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    CUSTOMER_MESSAGE = "CUSTOMER_MESSAGE"     # generic reply, entities may be attached
    PROVIDE_INFORMATION = "PROVIDE_INFORMATION"  # customer gave one or more field values
    QUESTION = "QUESTION"                      # off-topic / FAQ question
    OBJECTION = "OBJECTION"                    # price/loyalty/hesitation objection
    CHANGE_INTENT_YES = "CHANGE_INTENT_YES"
    CHANGE_INTENT_NO = "CHANGE_INTENT_NO"
    REQUEST_HUMAN = "REQUEST_HUMAN"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"    # empty/unparseable message, API error
    FOLLOW_UP_DUE = "FOLLOW_UP_DUE"            # scheduler-triggered (Phase 6), not a customer turn
    CONVERSATION_STARTED = "CONVERSATION_STARTED"  # Sophie-initiated (Outbound, Phase 5), no customer text yet
    QUALIFICATION_ADVANCE = "QUALIFICATION_ADVANCE"  # F-011 fix: server-triggered second turn to
    # move QUALIFIED -> HANDOFF (NOTIFY_SALES_TEAM) within the same request that
    # reached QUALIFIED, instead of waiting for a customer message that may never
    # come. Never produced by the Extractor/IntentClassifier - only constructed
    # directly in application/conversation_service.py. state_machine.py's
    # QUALIFIED branch is unconditional on event.type, so any Event works here;
    # this dedicated type exists purely so the intent is explicit and greppable
    # in logs/tests rather than silently reusing the customer's own event.


@dataclass
class Event:
    type: EventType
    entities: dict[str, Any] = field(default_factory=dict)
    raw_answer_text: Optional[str] = None  # only used for FAQ/OBJECTION context in Phase 3


# States that are "detours": entering them always remembers where we came
# from, so the engine can resume there afterwards.
from domain.enums import ConversationState  # noqa: E402

DETOUR_STATES = {
    ConversationState.FAQ,
    ConversationState.OBJECTION,
}

# ERROR_RECOVERY is deliberately NOT a detour in the same sense: it never
# changes current_state at all (see docs/business_rules/conversation_state_machine.md).
NO_STATE_CHANGE_STATES = {
    ConversationState.ERROR_RECOVERY,
}

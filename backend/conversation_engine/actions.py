"""
Action model.

This is the fix for a real design flaw: rules.py was returning a
ConversationState directly, which silently coupled "what the business wants
to happen" to "how the dialogue layer represents it". An Action is the
channel-agnostic decision - Web, Telegram, WhatsApp or Voice all consume the
same Action and each renders it differently. Only state_machine.py is
allowed to translate an Action into a ConversationState.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from domain.enums import RejectionReason


class ActionType(str, Enum):
    ASK_FIELD = "ASK_FIELD"              # ask for one missing qualification field
    VALIDATE = "VALIDATE"                 # all required fields present, run validation
    CORRECT_FIELD = "CORRECT_FIELD"       # a field was invalid, ask again for it
    QUALIFY = "QUALIFY"                   # validation passed, lead is qualified
    REJECT = "REJECT"                     # lead is rejected, with a reason
    HANDOFF = "HANDOFF"                   # transfer to a human
    CLOSE = "CLOSE"                       # end of the conversation
    ANSWER_FAQ = "ANSWER_FAQ"
    ANSWER_OBJECTION = "ANSWER_OBJECTION"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"  # ERROR_RECOVERY - never changes state
    CONFIRM_INTENT = "CONFIRM_INTENT"
    ASK_INTENT = "ASK_INTENT"
    SEND_GREETING = "SEND_GREETING"
    RESUME = "RESUME"                     # dialogue policy: return to previous state
    SEND_FOLLOW_UP = "SEND_FOLLOW_UP"
    NONE = "NONE"


@dataclass
class Action:
    type: ActionType
    field: Optional[str] = None                       # which field group, for ASK_FIELD/CORRECT_FIELD
    reason: Optional[RejectionReason] = None           # for REJECT

    def __repr__(self) -> str:  # pragma: no cover
        parts = [self.type.value]
        if self.field:
            parts.append(f"field={self.field}")
        if self.reason:
            parts.append(f"reason={self.reason.value}")
        return f"Action({', '.join(parts)})"

"""
Dialogue Policy.

Architecture review requirement: "who decides we go back to EAN after
answering a question? Not the State Machine alone - a Policy." This module
owns that decision. It reads business_rules/dialogue_policy.yaml (declarative
config only) and the Conversation's `consecutive_detour_count` to decide
whether resuming the interrupted qualification step is still the right move,
or whether repeated detours mean it's time to hand off to a human instead.

Like rules.py, this is pure: it reads the Conversation object it's given and
returns an Action. It never persists anything itself.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from conversation_engine.actions import Action, ActionType
from domain.models.conversation import Conversation

_RULES_DIR = Path(__file__).resolve().parent.parent / "business_rules"


def _load_yaml(filename: str) -> dict:
    with open(_RULES_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


_POLICY_CONFIG = _load_yaml("dialogue_policy.yaml")
MAX_CONSECUTIVE_DETOURS: int = _POLICY_CONFIG["max_consecutive_detours"]


def decide_after_detour(conversation: Conversation) -> Action:
    """Called when a FAQ/OBJECTION detour has just been answered.

    Returns Action(RESUME) in the normal case, or Action(HANDOFF) if the
    customer has detoured too many times in a row without progressing -
    at that point, continuing to loop back into qualification is unlikely
    to work and a human should take over.
    """
    if (conversation.consecutive_detour_count or 0) >= MAX_CONSECUTIVE_DETOURS:
        return Action(type=ActionType.HANDOFF)
    return Action(type=ActionType.RESUME)

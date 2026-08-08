"""
Conversation Memory Manager.

Implements the three-layer memory design agreed in the architecture docs:

- Lead Memory        -> Lead row (PostgreSQL, permanent)
- Conversation Memory -> Conversation row + Redis cache (current state,
                         missing fields, last question - fast to read)
- Conversation History -> Message rows (PostgreSQL, append-only)

Redis is a cache only: if it is empty or flushed, everything it would have
held can be rebuilt from PostgreSQL (current_state lives on the Conversation
row already; missing fields are recomputed from the Lead's actual data via
the rules engine). This module is what makes "the customer replies three
days later and Sophie doesn't re-ask answered questions" possible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from conversation_engine import rules
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from database.redis import cache_conversation_context, get_cached_conversation_context
from domain.models.conversation import Conversation
from domain.models.lead import Lead


@dataclass
class ConversationContext:
    lead: Lead
    conversation: Conversation
    missing_field_groups: list[str]
    last_question_action: Optional[str] = None


class ConversationMemory:
    def __init__(self, db_session):
        self.lead_repo = LeadRepository(db_session)
        self.conversation_repo = ConversationRepository(db_session)

    def load(self, conversation_id: UUID) -> ConversationContext:
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise ValueError(f"No conversation found for id={conversation_id}")

        lead = self.lead_repo.get_by_id(conversation.lead_id)
        if lead is None:
            raise ValueError(f"No lead found for conversation {conversation_id}")

        missing = rules.missing_field_groups(lead)

        cached = get_cached_conversation_context(str(conversation.id)) or {}
        last_question_action = cached.get("last_question_action")

        return ConversationContext(
            lead=lead,
            conversation=conversation,
            missing_field_groups=missing,
            last_question_action=last_question_action,
        )

    def save_last_question(self, conversation_id: UUID, required_action: Optional[str]) -> None:
        """Cache the last question asked, so a resumed conversation (e.g. after
        a follow-up) can avoid immediately repeating itself if the customer's
        next message doesn't map cleanly to it. Best-effort only - this is a
        cache, never authoritative state.
        """
        context: dict[str, Any] = {"last_question_action": required_action}
        cache_conversation_context(str(conversation_id), context)

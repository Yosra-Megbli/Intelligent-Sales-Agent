import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from domain.enums import ConversationChannel, ConversationState
from domain.models.conversation import Conversation
from domain.models.lead import Lead
from domain.models.message import Message


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        lead_id: uuid.UUID,
        channel: ConversationChannel,
        language: str = "fr",
        external_id: Optional[str] = None,
    ) -> Conversation:
        conversation = Conversation(
            id=uuid.uuid4(),
            lead_id=lead_id,
            channel=channel,
            language=language,
            external_id=external_id,
            current_state=ConversationState.START,
        )
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def get_by_id(self, conversation_id: uuid.UUID) -> Optional[Conversation]:
        return self.db.get(Conversation, conversation_id)

    def get_by_external_id(
        self, channel: ConversationChannel, external_id: str
    ) -> Optional[Conversation]:
        """Find an existing conversation by the channel's own identifier
        (e.g. a Telegram chat_id), so a returning customer resumes the same
        conversation instead of a new one being created on every message.
        """
        stmt = select(Conversation).where(
            Conversation.channel == channel, Conversation.external_id == external_id
        )
        return self.db.scalars(stmt).first()

    def get_latest_for_lead(
        self, lead_id: uuid.UUID, channel: Optional[ConversationChannel] = None
    ) -> Optional[Conversation]:
        stmt = select(Conversation).where(Conversation.lead_id == lead_id)
        if channel:
            stmt = stmt.where(Conversation.channel == channel)
        stmt = stmt.order_by(Conversation.last_message_at.desc()).limit(1)
        return self.db.scalars(stmt).first()

    def list_for_lead(self, lead_id: uuid.UUID) -> list[Conversation]:
        """All conversations for a lead, most recent first - powers the
        Dashboard's lead detail view (Phase 7): a lead can have talked on
        more than one channel (Web then Telegram, say)."""
        stmt = (
            select(Conversation)
            .where(Conversation.lead_id == lead_id)
            .order_by(Conversation.last_message_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def transition_state(
        self,
        conversation: Conversation,
        new_state: ConversationState,
        remember_previous: bool = False,
    ) -> Conversation:
        """Move to a new ConversationState.

        When entering a detour (FAQ / OBJECTION / ERROR_RECOVERY), pass
        remember_previous=True so we can return to exactly where we left off.
        """
        if remember_previous:
            conversation.previous_state = conversation.current_state
        conversation.current_state = new_state
        conversation.last_message_at = datetime.utcnow()
        self.db.flush()
        return conversation

    def resume_previous_state(self, conversation: Conversation) -> Conversation:
        if conversation.previous_state is not None:
            conversation.current_state = conversation.previous_state
            conversation.previous_state = None
            self.db.flush()
        return conversation

    def increment_detour_count(self, conversation: Conversation) -> Conversation:
        conversation.consecutive_detour_count = (conversation.consecutive_detour_count or 0) + 1
        self.db.flush()
        return conversation

    def reset_detour_count(self, conversation: Conversation) -> Conversation:
        conversation.consecutive_detour_count = 0
        self.db.flush()
        return conversation

    def add_message(
        self,
        conversation: Conversation,
        role,
        content: str,
        intent_detected: Optional[str] = None,
    ) -> Message:
        next_seq = self.db.execute(select(func.coalesce(func.max(Message.seq), 0) + 1)).scalar_one()
        message = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=role,
            content=content,
            intent_detected=intent_detected,
            seq=next_seq,
        )
        self.db.add(message)
        conversation.last_message_at = datetime.utcnow()
        self.db.flush()
        return message

    def get_history(self, conversation: Conversation, limit: int = 50) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.timestamp.desc(), Message.seq.desc())
            .limit(limit)
        )
        return list(reversed(self.db.scalars(stmt).all()))

    def list_silent_since(
        self, cutoff: datetime, candidate_states: frozenset[ConversationState]
    ) -> list[Conversation]:
        """Conversations with no activity since `cutoff`, currently in one of
        `candidate_states` - used by followup/engine.py to find conversations
        that have gone silent and should move to WAITING_CUSTOMER."""
        stmt = select(Conversation).where(
            Conversation.last_message_at <= cutoff,
            Conversation.current_state.in_(candidate_states),
        )
        return list(self.db.scalars(stmt).all())

    def count_active(self) -> int:
        """Dashboard Priority 2 (Overview): conversations still "in play" -
        every ConversationState except CLOSED. CLOSED is the only true
        terminal state in transitions.py: HANDOFF stays HANDOFF until a
        human agent acts (conversation_engine/state_machine.py), and
        REJECTED is a one-turn-then-CLOSED state, not terminal itself - so
        both still count as active here, same as any other in-flight state.
        """
        stmt = select(func.count()).select_from(Conversation).where(
            Conversation.current_state != ConversationState.CLOSED
        )
        return self.db.scalar(stmt) or 0

    def count_distinct_leads_in_state(self, state: ConversationState) -> int:
        """Dashboard Priority 2 (Overview): global version of
        `count_distinct_leads_in_state_for_campaign` below, without the
        campaign scope - powers the Overview's `human_handoff` metric across
        every lead, not just one campaign's roster. Same `distinct` guard
        against double-counting a lead with more than one conversation
        currently sitting in `state`.
        """
        stmt = select(func.count(func.distinct(Conversation.lead_id))).where(
            Conversation.current_state == state
        )
        return self.db.scalar(stmt) or 0

    def list_handoff_leads(self, limit: int = 50, offset: int = 0) -> tuple[list[Conversation], int]:
        """Dashboard Priority 3 (P04 - Handoff Queue): the actual leads
        behind `count_distinct_leads_in_state(HANDOFF)` above, not just the
        number - most recently handed-off first, so the sales team sees who
        is waiting, not only how many.

        Returns Conversations (eager-loaded `.lead`) rather than Leads
        directly, since the handoff moment itself - channel, `last_message_at`
        - lives on the Conversation, not the Lead. One row per lead: a lead
        can only be sitting in ConversationState.HANDOFF on one conversation
        at a time in this MVP (HANDOFF is entered from an in-progress
        dialogue, see conversation_engine/state_machine.py), so no extra
        distinct/group-by is needed here the way the two count() methods
        above need it for their aggregate.
        """
        base = select(Conversation).where(Conversation.current_state == ConversationState.HANDOFF)

        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0

        stmt = (
            base.options(joinedload(Conversation.lead))
            .order_by(Conversation.last_message_at.desc())
            .offset(offset)
            .limit(limit)
        )
        conversations = list(self.db.scalars(stmt).all())
        return conversations, total

    def count_distinct_leads_in_state_for_campaign(
        self, campaign_id, state: ConversationState
    ) -> int:
        """Dashboard Priority 1 (Campaign Analytics): counts leads assigned
        to `campaign_id` that currently have a conversation in `state` -
        used for the campaign's `handoff` metric. HANDOFF is a
        ConversationState, not a LeadStatus (see domain/models/conversation.py),
        so this can't be derived from LeadRepository.count_by_status() the
        way pending/contacted/replied/qualified/rejected are - it needs its
        own query joining Lead for the campaign scope. `distinct` guards
        against double-counting a lead that has more than one conversation
        (e.g. Web then Telegram) currently sitting in the same state.
        """
        stmt = (
            select(func.count(func.distinct(Conversation.lead_id)))
            .join(Lead, Lead.id == Conversation.lead_id)
            .where(Lead.campaign_id == campaign_id, Conversation.current_state == state)
        )
        return self.db.scalar(stmt) or 0

    def delete_all_for_lead(self, lead_id: uuid.UUID) -> None:
        """Deletes every Message then Conversation belonging to this lead -
        used by application/lead_service.py before a hard Lead delete (see
        LeadRepository.delete's docstring on why this order matters: no
        ON DELETE CASCADE exists at the DB level). Messages first since
        Message.conversation_id has its own NOT NULL FK to conversations.id."""
        conversation_ids = list(
            self.db.scalars(select(Conversation.id).where(Conversation.lead_id == lead_id)).all()
        )
        if conversation_ids:
            self.db.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
        self.db.execute(delete(Conversation).where(Conversation.lead_id == lead_id))
        self.db.flush()

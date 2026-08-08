"""
Conversation model.

A Lead is not a Conversation: the same lead can talk to Sophie on the
website, then continue on Telegram days later. `current_state` here is the
ConversationState (dialogue behaviour), completely separate from the Lead's
`status` (CRM lifecycle).
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database.postgres import Base, GUID
from domain.enums import ConversationChannel, ConversationState


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    lead_id = Column(GUID(), ForeignKey("leads.id"), nullable=False, index=True)

    channel = Column(SAEnum(ConversationChannel, name="conversation_channel"), nullable=False)
    language = Column(String(8), nullable=False, default="fr")

    # The channel's own identifier for this conversation (e.g. a Telegram
    # chat_id, a WhatsApp phone number). NULL for Web, where the frontend
    # already round-trips `conversation.id` itself and needs nothing else.
    # This is what lets a channel find "the same conversation" for a
    # returning customer instead of creating a new one on every message -
    # see crm/conversation_repository.py:get_by_external_id.
    external_id = Column(String(255), nullable=True, index=True)

    current_state = Column(
        SAEnum(ConversationState, name="conversation_state"),
        nullable=False,
        default=ConversationState.START,
    )
    # The state Sophie was in before a detour (FAQ/OBJECTION/ERROR_RECOVERY),
    # so we always know where to return to.
    previous_state = Column(
        SAEnum(ConversationState, name="conversation_previous_state"),
        nullable=True,
    )

    # How many FAQ/OBJECTION detours have happened back-to-back without the
    # customer moving forward. Read by the Dialogue Policy (dialogue_policy.py)
    # to decide whether to keep resuming qualification or escalate to a
    # human - the State Machine itself does not make that call.
    consecutive_detour_count = Column(Integer, nullable=False, default=0)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation", order_by="Message.timestamp, Message.seq"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Conversation {self.id} lead={self.lead_id} state={self.current_state}>"

"""
Message model - stored separately from Conversation because message history
grows unbounded and should not bloat the conversation row.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.postgres import Base, GUID
from domain.enums import MessageRole


class Message(Base):
    __tablename__ = "messages"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        GUID(), ForeignKey("conversations.id"), nullable=False, index=True
    )

    role = Column(SAEnum(MessageRole, name="message_role"), nullable=False)
    content = Column(Text, nullable=False)

    # Filled in by the Message Analyzer (LLM extraction layer) - informational
    # only, never used by the Business Rules Engine to make decisions itself.
    intent_detected = Column(String(64), nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Tiebreaker for ordering: datetime.utcnow() has ~15ms resolution on
    # Windows, so back-to-back inserts can share a timestamp.
    seq = Column(Integer, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Message {self.id} role={self.role}>"

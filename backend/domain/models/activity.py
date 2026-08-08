"""
Activity model - the audit trail / event journal for a lead.

Every meaningful business event (message sent/received, status change,
follow-up sent, qualification, human handoff...) is recorded here. This is
what will power the sales dashboard later (Phase 7) and lets us reconstruct
exactly what happened and when for any lead.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from database.postgres import Base, GUID
from domain.enums import ActivityType


class Activity(Base):
    __tablename__ = "activities"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    lead_id = Column(GUID(), ForeignKey("leads.id"), nullable=False, index=True)

    type = Column(SAEnum(ActivityType, name="activity_type"), nullable=False)
    details = Column(Text, nullable=True)  # free-text / JSON-encoded context

    seq = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    lead = relationship("Lead", back_populates="activities")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Activity {self.id} type={self.type} lead={self.lead_id}>"

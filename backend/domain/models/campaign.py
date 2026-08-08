"""
Campaign model - used by the Outbound Engine (Phase 5) to decide who to
contact, when, and how many times. It never handles language/content
generation; that stays in the AI layer.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import relationship

from database.postgres import Base, GUID
from domain.enums import CampaignStatus, ConversationChannel


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(180), nullable=False)

    status = Column(
        SAEnum(CampaignStatus, name="campaign_status"),
        nullable=False,
        default=CampaignStatus.DRAFT,
    )

    # Which channel every lead in this campaign is contacted on (a campaign
    # is single-channel - see outbound/scheduler.py's OutboundScheduler,
    # which reads this to decide how to reach each lead). Defaults to
    # WhatsApp, matching this column's introduction after WhatsApp-only
    # outbound was already the only real behaviour - existing campaigns in
    # a database from before this column existed keep working unchanged.
    #
    # NOTE (schema note, same caveat as api/main.py's _create_tables_if_missing
    # docstring): this project has no Alembic migrations wired up yet -
    # `Base.metadata.create_all()` only creates missing *tables*, it will
    # NOT add this column to a `campaigns` table that already exists in a
    # deployed database. A real deployment upgrading past this change needs
    # a manual `ALTER TABLE campaigns ADD COLUMN channel VARCHAR NOT NULL
    # DEFAULT 'WHATSAPP'` (or a proper migration) before this column is
    # usable there.
    channel = Column(
        SAEnum(ConversationChannel, name="conversation_channel"),
        nullable=False,
        default=ConversationChannel.WHATSAPP,
    )

    # e.g. {"region": "Wallonie"} - kept as JSON-encoded text at MVP stage
    target_rules = Column(Text, nullable=True)

    total_leads = Column(Integer, nullable=False, default=0)
    sent = Column(Integer, nullable=False, default=0)
    replied = Column(Integer, nullable=False, default=0)
    qualified = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    leads = relationship("Lead", backref="campaign")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Campaign {self.id} name={self.name} status={self.status}>"

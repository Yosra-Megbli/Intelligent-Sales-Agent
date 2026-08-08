"""
Lead model - the CRM's source of truth for a prospect.

IMPORTANT (architecture rule): this model only stores data. It never decides
anything. All decisions (qualification, next state, rejection...) are made by
the conversation_engine / business rules layer, never here and never by the LLM.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database.postgres import Base, GUID
from domain.enums import (
    FollowUpCategory,
    LeadSource,
    LeadStatus,
    RejectionReason,
)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # --- Identity ---
    first_name = Column(String(120), nullable=True)
    last_name = Column(String(120), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(32), nullable=True, index=True)

    # --- Source ---
    source = Column(SAEnum(LeadSource, name="lead_source"), nullable=False)

    # Telegram cannot be cold-outreached by phone number - a bot may only
    # message a `chat_id` belonging to a user who has already started a
    # conversation with it (see outbound/scheduler.py's _resolve_external_id).
    # Storing the chat_id directly on the lead (populated at CSV import/
    # manual creation time, or backfilled from an inbound conversation - see
    # application/conversation_service.py's start_conversation) lets a lead
    # be targeted by an outbound Telegram campaign immediately, without
    # waiting for a Conversation row to exist first.
    telegram_chat_id = Column(String(64), nullable=True, index=True)

    # Which outbound Campaign (if any) targeted this lead - NULL for
    # inbound leads. Lets CampaignEngine avoid re-selecting a lead that's
    # already assigned to a running campaign, and lets Campaign.sent/
    # replied/qualified counters be attributed correctly (see
    # outbound/campaign_engine.py, crm/campaign_repository.py).
    campaign_id = Column(GUID(), ForeignKey("campaigns.id"), nullable=True, index=True)

    # --- Sales status (CRM lifecycle) ---
    status = Column(
        SAEnum(LeadStatus, name="lead_status"),
        nullable=False,
        default=LeadStatus.NEW,
        index=True,
    )
    rejection_reason = Column(SAEnum(RejectionReason, name="rejection_reason"), nullable=True)

    # --- Energy information ---
    # NOTE: customer_type and region are plain strings, not a DB-level Enum,
    # on purpose: the Business Rules Engine must be able to store an
    # out-of-scope value (e.g. a region we don't cover, or a customer type
    # that doesn't fit) in order to *reject* it with the right reason
    # (OUT_OF_COVERAGE / INVALID_CUSTOMER). A DB-level enum would refuse to
    # even save that data. CustomerType/Region enums remain the reference
    # vocabulary used by the rules engine's validation logic.
    customer_type = Column(String(32), nullable=True)
    region = Column(String(120), nullable=True)
    city = Column(String(120), nullable=True)
    address = Column(String(255), nullable=True)
    current_supplier = Column(String(120), nullable=True)
    ean = Column(String(18), nullable=True)
    consumption = Column(String(64), nullable=True)  # kept as free text at MVP stage

    # Required by cahier de charges §5 (qualification data) for contract
    # generation later - not currently read or validated by
    # conversation_engine/business_rules; collected and stored only.
    date_of_birth = Column(DateTime, nullable=True)

    # --- CRM import bookkeeping (added for CSV Import, Feature 1) ---
    # `provider` is who supplied/referred this lead (e.g. a marketing partner
    # or lead-gen provider) - distinct from `current_supplier`, which is the
    # customer's *own* existing energy company used by the qualification
    # flow. `notes` is free-text CRM notes, shown on the dashboard's lead
    # detail view; never read or written by conversation_engine/ai.
    provider = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)

    # --- Qualification ---
    change_intent = Column(Boolean, nullable=True)
    qualification_score = Column(Integer, nullable=True)
    qualified_at = Column(DateTime, nullable=True)

    # --- Follow-up (this is a process attached to the lead, not a CRM status) ---
    last_contact_date = Column(DateTime, nullable=True)
    next_follow_up_date = Column(DateTime, nullable=True)
    follow_up_attempts = Column(Integer, nullable=False, default=0)
    follow_up_category = Column(
        SAEnum(FollowUpCategory, name="follow_up_category"),
        nullable=True,
    )

    # --- Bookkeeping ---
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # --- Relationships ---
    conversations = relationship("Conversation", back_populates="lead")
    activities = relationship("Activity", back_populates="lead")

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return f"<Lead {self.id} status={self.status} email={self.email}>"

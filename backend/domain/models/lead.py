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
    Index,
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

    # --- Creation-time identity (P1-2: duplicate-lead protection) ---
    # Deliberately NOT the same columns as `email`/`phone` above, and
    # deliberately only ever written by LeadRepository.create() (never by
    # update_fields(), CRM edits, or conversation_engine/engine.py setting
    # entities extracted mid-conversation). Two different things both look
    # like "this lead's email" but must not share one column/constraint:
    #  1. the identity a lead was *created* with (start_conversation/CSV
    #     import) - this is what a unique constraint can safely enforce,
    #     since creating two leads for the same real prospect is always a
    #     bug, never a legitimate business outcome.
    #  2. `email`/`phone` above, which can legitimately hold a value that
    #     collides with a *different* lead while conversation_engine/
    #     rules.py's DATA_VALIDATION step is deciding whether to reject it
    #     as DUPLICATE_LEAD (F-003) - the lead being rejected must be able
    #     to durably store the colliding value it was rejected for. A
    #     table-wide unique constraint on `email`/`phone` themselves would
    #     turn that existing, intentional business flow into a hard
    #     IntegrityError instead of a graceful rejection - see
    #     tests/test_conversation_engine.py::
    #     test_duplicate_lead_rejected_at_data_validation_regression_f003.
    # find_duplicate()/get_by_email() below query these columns, not
    # `email`/`phone` - "is this the same lead" always means "same
    # creation-time identity" everywhere in the system, one definition.
    dedup_email = Column(String(255), nullable=True)
    dedup_phone = Column(String(32), nullable=True)

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

    # P1-2 (duplicate-lead protection): the application layer already checks
    # LeadRepository.find_duplicate() before creating a Lead (see
    # application/conversation_service.py's start_conversation), but that
    # check-then-insert is a classic race condition under concurrent
    # requests - two requests can both see "no match" before either has
    # committed. These partial unique indexes make PostgreSQL itself the
    # final authority on *creation-time* identity (dedup_email/dedup_phone
    # above - not email/phone, see their comment for why). NULL values are
    # excluded (many leads legitimately have no email, or no phone) so only
    # leads that actually carry the identifier are compared. dedup_email is
    # stored already-lowercased by LeadRepository.create(), so a plain
    # equality index is enough - no function-based index needed. `sqlite_
    # where` mirrors `postgresql_where` so the exact same protection is
    # exercised by the SQLite-backed test suite, not just in production; see
    # database/migrations/0002_lead_dedup_unique_indexes.sql for the manual
    # ALTER needed on any pre-existing PostgreSQL database (this project has
    # no Alembic - see that file's header for why).
    __table_args__ = (
        Index(
            "ux_leads_dedup_email",
            dedup_email,
            unique=True,
            postgresql_where=dedup_email.isnot(None),
            sqlite_where=dedup_email.isnot(None),
        ),
        Index(
            "ux_leads_dedup_phone",
            dedup_phone,
            unique=True,
            postgresql_where=dedup_phone.isnot(None),
            sqlite_where=dedup_phone.isnot(None),
        ),
    )

    # --- Relationships ---
    conversations = relationship("Conversation", back_populates="lead")
    activities = relationship("Activity", back_populates="lead")

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return f"<Lead {self.id} status={self.status} email={self.email}>"

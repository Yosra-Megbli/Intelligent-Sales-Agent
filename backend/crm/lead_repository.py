"""
Lead repository.

IMPORTANT: this layer only persists/reads data. It must never decide a
lead's status, qualification, or rejection reason - those decisions belong
to conversation_engine/rules.py (Phase 2). Keeping repositories "dumb" is
what keeps the Business Rules Engine testable in isolation.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from domain.enums import FollowUpCategory, LeadSource, LeadStatus, RejectionReason
from domain.models.lead import Lead


class LeadRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        source: LeadSource,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Lead:
        lead = Lead(
            id=uuid.uuid4(),
            source=source,
            status=LeadStatus.NEW,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
        )
        self.db.add(lead)
        self.db.flush()
        return lead

    def get_by_id(self, lead_id: uuid.UUID) -> Optional[Lead]:
        return self.db.get(Lead, lead_id)

    def get_by_email(self, email: str) -> Optional[Lead]:
        stmt = select(Lead).where(Lead.email == email)
        return self.db.scalars(stmt).first()

    def get_by_phone(self, phone: str) -> Optional[Lead]:
        stmt = select(Lead).where(Lead.phone == phone)
        return self.db.scalars(stmt).first()

    def find_duplicate(
        self, email: Optional[str], phone: Optional[str], *, exclude_lead_id: Optional[uuid.UUID] = None
    ) -> Optional[Lead]:
        """Used by the rules engine (via ConversationEngine) to detect
        DUPLICATE_LEAD before qualifying a lead.

        `exclude_lead_id` matters as soon as this is actually called from
        the live flow (F-003 fix): by the time DATA_VALIDATION runs, the
        Lead being validated already has its own email/phone saved. The
        exclusion is applied in the WHERE clause itself, not by fetching one
        row and checking its id afterwards - `get_by_email`/`get_by_phone`
        take the *first* match with no ordering guarantee, so if the lead's
        own row happened to come back first, a post-fetch check would wrongly
        conclude "no duplicate" and miss a real one instead of looking further.
        """
        if email:
            stmt = select(Lead).where(Lead.email == email)
            if exclude_lead_id is not None:
                stmt = stmt.where(Lead.id != exclude_lead_id)
            existing = self.db.scalars(stmt).first()
            if existing:
                return existing
        if phone:
            stmt = select(Lead).where(Lead.phone == phone)
            if exclude_lead_id is not None:
                stmt = stmt.where(Lead.id != exclude_lead_id)
            existing = self.db.scalars(stmt).first()
            if existing:
                return existing
        return None

    def list_new_for_campaign(self, region: Optional[str] = None, limit: int = 100) -> list[Lead]:
        stmt = select(Lead).where(Lead.status == LeadStatus.NEW, Lead.campaign_id.is_(None))
        if region:
            stmt = stmt.where(Lead.region == region)
        stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt).all())

    def assign_to_campaign(self, lead: Lead, campaign_id: uuid.UUID) -> Lead:
        lead.campaign_id = campaign_id
        self.db.flush()
        return lead

    def list_by_campaign(
        self, campaign_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[Lead], int]:
        """Leads assigned to a campaign (Dashboard's \"assigned leads\" /
        \"outbound progress\" view) - separate from `list_new_for_campaign`,
        which is `CampaignEngine`'s assignment query and only ever returns
        unassigned NEW leads, never a full campaign roster."""
        stmt = select(Lead).where(Lead.campaign_id == campaign_id)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = stmt.order_by(Lead.created_at.desc()).limit(limit).offset(offset)
        leads = list(self.db.scalars(stmt).all())
        return leads, total

    def list_pending_for_send(self, campaign_id: uuid.UUID, limit: int = 20) -> list[Lead]:
        """Leads already assigned to `campaign_id` but not yet contacted -
        what `OutboundScheduler` sends next. Natural duplicate protection:
        once `OutboundSender.send_opening_message` moves a lead to
        CONTACTED, it drops out of this query and can never be re-sent by
        the scheduler picking it up again."""
        stmt = (
            select(Lead)
            .where(Lead.campaign_id == campaign_id, Lead.status == LeadStatus.NEW)
            .order_by(Lead.created_at.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def list_due_for_follow_up(self, as_of: Optional[datetime] = None) -> list[Lead]:
        as_of = as_of or datetime.utcnow()
        stmt = select(Lead).where(
            Lead.next_follow_up_date.is_not(None),
            Lead.next_follow_up_date <= as_of,
            Lead.follow_up_category != FollowUpCategory.STOPPED,
        )
        return list(self.db.scalars(stmt).all())

    def list_leads(
        self,
        *,
        status: Optional[LeadStatus] = None,
        region: Optional[str] = None,
        source: Optional[LeadSource] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Lead], int]:
        """Read-only listing for the Dashboard (Phase 7) - filters are all
        optional and combine with AND. `search` matches first/last name,
        email or phone (simple case-insensitive substring, no full-text
        search engine at MVP scale). Returns (page, total_matching_count)
        so the caller can paginate without a second round-trip.
        """
        stmt = select(Lead)
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if region is not None:
            stmt = stmt.where(Lead.region == region)
        if source is not None:
            stmt = stmt.where(Lead.source == source)
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Lead.first_name).like(pattern),
                    func.lower(Lead.last_name).like(pattern),
                    func.lower(Lead.email).like(pattern),
                    Lead.phone.like(f"%{search}%"),
                )
            )

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        stmt = stmt.order_by(Lead.created_at.desc()).limit(limit).offset(offset)
        leads = list(self.db.scalars(stmt).all())
        return leads, total

    def count_by_status(self, campaign_id: Optional[uuid.UUID] = None) -> dict[LeadStatus, int]:
        """Powers the Dashboard's status overview (Phase 7) - one grouped
        query rather than one count() per status.

        `campaign_id` (Dashboard Priority 1, campaign analytics) scopes the
        same grouped query to a single campaign's assigned leads, so the
        Campaign Analytics view derives pending/contacted/replied/qualified/
        rejected straight from real Lead.status data instead of the
        Campaign.replied/qualified counters - which nothing in this codebase
        actually increments (see crm/campaign_repository.py; only
        increment_sent is ever called, from outbound/sender.py). Deriving
        from Lead.status avoids exposing that dead-counter gap as if it were
        real data.
        """
        stmt = select(Lead.status, func.count()).group_by(Lead.status)
        if campaign_id is not None:
            stmt = stmt.where(Lead.campaign_id == campaign_id)
        return {status: count for status, count in self.db.execute(stmt).all()}

    def update_fields(self, lead: Lead, **fields) -> Lead:
        """Generic field updater used by the Business Rules Engine after each turn."""
        for key, value in fields.items():
            if not hasattr(lead, key):
                raise AttributeError(f"Lead has no field '{key}'")
            setattr(lead, key, value)
        self.db.flush()
        return lead

    def set_status(self, lead: Lead, status: LeadStatus, rejection_reason: Optional[RejectionReason] = None) -> Lead:
        lead.status = status
        if status == LeadStatus.REJECTED:
            lead.rejection_reason = rejection_reason
        if status == LeadStatus.QUALIFIED and lead.qualified_at is None:
            lead.qualified_at = datetime.utcnow()
        self.db.flush()
        return lead

    def schedule_follow_up(self, lead: Lead, next_date: datetime, category: FollowUpCategory) -> Lead:
        """Sets the next follow-up date/category only. Bug fix (F-015, BAT
        SC-104-106): this used to also bump `follow_up_attempts` on every
        call, including the very first one - made when a conversation just
        went silent and *no follow-up message has been sent yet* (see
        `followup/engine.py`'s `mark_silent_conversations_as_waiting()`).
        That meant `max_follow_up_attempts: 3` only ever delivered 2 real
        messages: the counter was already at 1 before the first actual send.
        Counting an attempt now happens exactly once, only when a follow-up
        is actually sent - see `increment_follow_up_attempts()` below.
        """
        lead.next_follow_up_date = next_date
        lead.follow_up_category = category
        self.db.flush()
        return lead

    def increment_follow_up_attempts(self, lead: Lead) -> Lead:
        """Bumps the attempt counter - call this exactly once, only at the
        moment a follow-up message is actually sent (F-015 fix). Never call
        it just for scheduling a date/category; see `schedule_follow_up()`."""
        lead.follow_up_attempts = (lead.follow_up_attempts or 0) + 1
        self.db.flush()
        return lead

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.enums import CampaignStatus, ConversationChannel
from domain.models.campaign import Campaign


class CampaignRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        target_rules: Optional[str] = None,
        channel: ConversationChannel = ConversationChannel.WHATSAPP,
    ) -> Campaign:
        campaign = Campaign(id=uuid.uuid4(), name=name, target_rules=target_rules, channel=channel)
        self.db.add(campaign)
        self.db.flush()
        return campaign

    def get_by_id(self, campaign_id: uuid.UUID) -> Optional[Campaign]:
        return self.db.get(Campaign, campaign_id)

    def list_running(self) -> list[Campaign]:
        stmt = select(Campaign).where(Campaign.status == CampaignStatus.RUNNING)
        return list(self.db.scalars(stmt).all())

    def count_running(self) -> int:
        """Dashboard Priority 2 (Overview): how many campaigns are currently
        RUNNING - a plain count rather than `len(list_running())` so the
        Overview doesn't have to materialize every running campaign's rows
        just to size them."""
        stmt = select(func.count()).select_from(Campaign).where(Campaign.status == CampaignStatus.RUNNING)
        return self.db.scalar(stmt) or 0

    def list_all(self, *, limit: int = 50, offset: int = 0) -> tuple[list[Campaign], int]:
        """Full campaign roster for the Dashboard (`GET /api/campaigns`)."""
        stmt = select(Campaign)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = stmt.order_by(Campaign.created_at.desc()).limit(limit).offset(offset)
        campaigns = list(self.db.scalars(stmt).all())
        return campaigns, total

    def set_status(self, campaign: Campaign, status: CampaignStatus) -> Campaign:
        campaign.status = status
        self.db.flush()
        return campaign

    def add_to_total_leads(self, campaign: Campaign, count: int) -> Campaign:
        campaign.total_leads = (campaign.total_leads or 0) + count
        self.db.flush()
        return campaign

    def increment_sent(self, campaign: Campaign) -> Campaign:
        campaign.sent = (campaign.sent or 0) + 1
        self.db.flush()
        return campaign

    def increment_replied(self, campaign: Campaign) -> Campaign:
        campaign.replied = (campaign.replied or 0) + 1
        self.db.flush()
        return campaign

    def increment_qualified(self, campaign: Campaign) -> Campaign:
        campaign.qualified = (campaign.qualified or 0) + 1
        self.db.flush()
        return campaign

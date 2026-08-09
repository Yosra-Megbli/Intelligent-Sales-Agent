import uuid
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from domain.enums import ActivityType
from domain.models.activity import Activity


class ActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    def log(self, lead_id: uuid.UUID, type_: ActivityType, details: Optional[str] = None) -> Activity:
        # `seq` isn't the PK, so no DB autoincrement fills it - it's a global
        # tiebreaker for created_at ties, computed here instead.
        next_seq = self.db.execute(select(func.coalesce(func.max(Activity.seq), 0) + 1)).scalar_one()
        activity = Activity(id=uuid.uuid4(), lead_id=lead_id, type=type_, details=details, seq=next_seq)
        self.db.add(activity)
        self.db.flush()
        return activity

    def list_for_lead(self, lead_id: uuid.UUID, limit: int = 100) -> list[Activity]:
        stmt = (
            select(Activity)
            .where(Activity.lead_id == lead_id)
            .order_by(Activity.created_at.desc(), Activity.seq.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def delete_for_lead(self, lead_id: uuid.UUID) -> None:
        """Used by application/lead_service.py before a hard Lead delete -
        see LeadRepository.delete's docstring on why this has to happen
        explicitly (no ON DELETE CASCADE at the DB level)."""
        self.db.execute(delete(Activity).where(Activity.lead_id == lead_id))
        self.db.flush()

    def list_recent(self, limit: int = 50) -> list[Activity]:
        """Global activity feed (all leads combined), most recent first -
        powers the dashboard's Activity Timeline. `joinedload(Activity.lead)`
        avoids an N+1 query per row since the timeline always needs the
        lead's name alongside each event."""
        stmt = (
            select(Activity)
            .options(joinedload(Activity.lead))
            .order_by(Activity.created_at.desc(), Activity.seq.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

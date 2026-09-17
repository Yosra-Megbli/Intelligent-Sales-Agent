"""
Metrics Service (Application layer).

Single source of truth computing EVERY displayed counter and funnel metric
from canonical definitions across all screens (Overview, Leads, Funnel,
Contracts, Live Supervision).

Canonical definitions (non-negotiable):
- signed_contracts = COUNT(contracts WHERE status=SIGNED)
- qualified_leads = COUNT(leads WHERE status IN (QUALIFIED, APPOINTMENT, CONTRACT, CUSTOMER) or status.startswith('QUALIFIED'))
- engaged_conversations = COUNT(DISTINCT conversation_id FROM messages WHERE role=ASSISTANT)
- active_conversations = COUNT(conversations WHERE current_state NOT IN (CLOSED, REJECTED))
- total_leads = COUNT(leads)
- contacted_leads = COUNT(leads WHERE status != NEW)
- conversion_rate = (qualified_leads / total_leads * 100) if total_leads else 0.0 (Taux de qualification)
- ARR (estimated_ca) = signed_contracts * 60.0 (pricing truth: base fee €60/yr)
- cost_per_conversation = 0.02
- cost_per_sale = (total_conversations * 0.02) / signed_contracts if signed_contracts > 0 else 0.0

Purity & boundary discipline:
Like `application/dashboard_service.py`, this service never imports the
conversation engine or `ai/*`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.enums import ContractStatus, ConversationState, LeadStatus, MessageRole
from domain.models.contract import Contract
from domain.models.conversation import Conversation
from domain.models.lead import Lead
from domain.models.message import Message


QUALIFIED_STATUSES = {
    LeadStatus.QUALIFIED,
    LeadStatus.APPOINTMENT,
    LeadStatus.CONTRACT,
    LeadStatus.CUSTOMER,
}


@dataclass
class FunnelStage:
    stage_id: str
    label_key: str
    count: int
    pct: float
    dropoff: float
    color: str


@dataclass
class FunnelMetrics:
    total: int
    contacted: int
    qualified: int
    signed: int
    stages: list[FunnelStage]


@dataclass
class CanonicalMetrics:
    total_leads: int
    new_leads: int
    contacted_leads: int
    engaged_conversations: int
    qualified_leads: int
    signed_contracts: int
    active_conversations: int
    active_campaigns: int
    human_handoff: int
    rejected: int
    conversion_rate: float
    arr: float
    cost_per_conversation: float
    cost_per_sale: float
    funnel: FunnelMetrics
    currency: str = "EUR"

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_leads": self.total_leads,
            "new_leads": self.new_leads,
            "contacted": self.contacted_leads,
            "engaged_conversations": self.engaged_conversations,
            "qualified": self.qualified_leads,
            "signed_contracts": self.signed_contracts,
            "active_conversations": self.active_conversations,
            "active_campaigns": self.active_campaigns,
            "human_handoff": self.human_handoff,
            "rejected": self.rejected,
            "conversion_rate": self.conversion_rate,
            "arr": self.arr,
            "estimated_ca": self.arr,
            "cost_per_conversation": self.cost_per_conversation,
            "cost_per_sale": self.cost_per_sale,
            "currency": self.currency,
            "funnel": {
                "total": self.funnel.total,
                "contacted": self.funnel.contacted,
                "qualified": self.funnel.qualified,
                "signed": self.funnel.signed,
                "stages": [
                    {
                        "stage_id": s.stage_id,
                        "label_key": s.label_key,
                        "count": s.count,
                        "pct": s.pct,
                        "dropoff": s.dropoff,
                        "color": s.color,
                    }
                    for s in self.funnel.stages
                ],
            },
        }


class MetricsService:
    """Single source of truth for metrics computation."""

    def __init__(self, db: Session):
        self.db = db

    def get_canonical_metrics(self, *, active_campaigns_count: int = 0) -> CanonicalMetrics:
        # 1. Leads by status
        status_stmt = select(Lead.status, func.count()).group_by(Lead.status)
        status_counts = {st: count for st, count in self.db.execute(status_stmt).all()}

        total_leads = sum(status_counts.values())
        new_leads = status_counts.get(LeadStatus.NEW, 0)
        contacted_leads = total_leads - new_leads
        rejected = status_counts.get(LeadStatus.REJECTED, 0)

        # Qualified: strictly QUALIFIED and downstream stages (APPOINTMENT, CONTRACT, CUSTOMER)
        # or any status starting with QUALIFIED
        qualified_leads = sum(
            count for st, count in status_counts.items()
            if st in QUALIFIED_STATUSES or (hasattr(st, "value") and str(st.value).startswith("QUALIFIED"))
        )

        # 2. Signed Contracts: count contracts table where status = SIGNED
        signed_contracts_stmt = select(func.count(Contract.id)).where(Contract.status == ContractStatus.SIGNED)
        signed_contracts = self.db.scalar(signed_contracts_stmt) or 0

        # 3. Active conversations: current_state NOT IN (CLOSED, REJECTED)
        active_conv_stmt = select(func.count(Conversation.id)).where(
            Conversation.current_state.notin_([ConversationState.CLOSED, ConversationState.REJECTED])
        )
        active_conversations = self.db.scalar(active_conv_stmt) or 0

        # 4. Engaged conversations: conversations with at least one assistant message
        engaged_stmt = select(func.count(func.distinct(Message.conversation_id))).where(
            Message.role == MessageRole.ASSISTANT
        )
        engaged_conversations = self.db.scalar(engaged_stmt) or 0

        # 5. Human handoff: distinct leads currently waiting in HANDOFF
        handoff_stmt = select(func.count(func.distinct(Conversation.lead_id))).where(
            Conversation.current_state == ConversationState.HANDOFF
        )
        human_handoff = self.db.scalar(handoff_stmt) or 0

        # 6. Total conversations (for AI unit cost computation)
        total_conv_stmt = select(func.count(Conversation.id))
        total_conversations = self.db.scalar(total_conv_stmt) or 0

        # 7. Derived unit economics (Sept 2026 pricing truth: €60/yr base fixed fee)
        conversion_rate = round((qualified_leads / total_leads * 100), 1) if total_leads else 0.0
        arr = round(signed_contracts * 60.0, 2)
        cost_per_conversation = 0.02
        total_ai_cost = total_conversations * cost_per_conversation
        cost_per_sale = round(total_ai_cost / signed_contracts, 2) if signed_contracts > 0 else 0.0

        # 8. Canonical Funnel Stages
        stage_new_pct = 100.0 if total_leads > 0 else 0.0
        stage_contacted_pct = round((contacted_leads / total_leads * 100), 1) if total_leads else 0.0
        stage_qualified_pct = round((qualified_leads / total_leads * 100), 1) if total_leads else 0.0
        stage_signed_pct = round((signed_contracts / total_leads * 100), 1) if total_leads else 0.0

        dropoff_new = round(((total_leads - contacted_leads) / total_leads * 100), 1) if total_leads else 0.0
        dropoff_contacted = round(((contacted_leads - qualified_leads) / contacted_leads * 100), 1) if contacted_leads else 0.0
        dropoff_qualified = round(((qualified_leads - signed_contracts) / qualified_leads * 100), 1) if qualified_leads else 0.0

        stages = [
            FunnelStage(
                stage_id="new",
                label_key="overview.funnel.stepNew",
                count=total_leads,
                pct=stage_new_pct,
                dropoff=dropoff_new,
                color="bg-neutral-500",
            ),
            FunnelStage(
                stage_id="contacted",
                label_key="overview.funnel.stepContacted",
                count=contacted_leads,
                pct=stage_contacted_pct,
                dropoff=dropoff_contacted,
                color="bg-[var(--info-blue)]",
            ),
            FunnelStage(
                stage_id="qualified",
                label_key="overview.funnel.stepQualified",
                count=qualified_leads,
                pct=stage_qualified_pct,
                dropoff=dropoff_qualified,
                color="bg-[var(--teal-motion)]",
            ),
            FunnelStage(
                stage_id="signed",
                label_key="overview.funnel.stepSigned",
                count=signed_contracts,
                pct=stage_signed_pct,
                dropoff=0.0,
                color="bg-[var(--color-teal)]",
            ),
        ]

        funnel = FunnelMetrics(
            total=total_leads,
            contacted=contacted_leads,
            qualified=qualified_leads,
            signed=signed_contracts,
            stages=stages,
        )

        return CanonicalMetrics(
            total_leads=total_leads,
            new_leads=new_leads,
            contacted_leads=contacted_leads,
            engaged_conversations=engaged_conversations,
            qualified_leads=qualified_leads,
            signed_contracts=signed_contracts,
            active_conversations=active_conversations,
            active_campaigns=active_campaigns_count,
            human_handoff=human_handoff,
            rejected=rejected,
            conversion_rate=conversion_rate,
            arr=arr,
            cost_per_conversation=cost_per_conversation,
            cost_per_sale=cost_per_sale,
            funnel=funnel,
            currency="EUR",
        )

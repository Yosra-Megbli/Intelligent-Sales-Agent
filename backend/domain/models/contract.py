"""
Contract model — Sophie (Ecofix).

Stores generated contracts for qualified leads, tracking the contract status
through its lifecycle (DRAFT -> SENT -> SIGNED / WITHDRAWN), associated PDF
specimen, and Yousign signature request IDs.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import relationship

from database.postgres import Base, GUID
from domain.enums import ContractStatus


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    lead_id = Column(GUID(), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)

    # Product: "Flexy" (variable monthly) or "Motion" (dynamic hourly)
    product = Column(String(32), nullable=False)

    # Lifecycle status: DRAFT, SENT, SIGNED, WITHDRAWN, CANCELLED
    status = Column(
        SAEnum(ContractStatus, name="contract_status"),
        nullable=False,
        default=ContractStatus.DRAFT,
        index=True,
    )

    # Yousign metadata
    yousign_signature_request_id = Column(String(128), nullable=True, index=True)
    yousign_document_id = Column(String(128), nullable=True)

    # Local PDF specimen storage path
    pdf_path = Column(String(512), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    signed_at = Column(DateTime, nullable=True)
    withdrawn_at = Column(DateTime, nullable=True)

    # Relationships
    lead = relationship("Lead", back_populates="contracts")

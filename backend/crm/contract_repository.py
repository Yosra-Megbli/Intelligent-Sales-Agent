"""
Contract repository — Sophie (Ecofix).

Data layer persistence and querying for contracts.
Decisions on state and validation are handled by business rules / services,
keeping this repository focused exclusively on clean database access.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.enums import ContractStatus
from domain.models.contract import Contract


class ContractRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        lead_id: UUID,
        product: str,
        status: ContractStatus = ContractStatus.DRAFT,
        pdf_path: Optional[str] = None,
        yousign_signature_request_id: Optional[str] = None,
        yousign_document_id: Optional[str] = None,
    ) -> Contract:
        contract = Contract(
            id=uuid.uuid4(),
            lead_id=lead_id,
            product=product,
            status=status,
            pdf_path=pdf_path,
            yousign_signature_request_id=yousign_signature_request_id,
            yousign_document_id=yousign_document_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(contract)
        self.db.flush()
        return contract

    def get_by_id(self, contract_id: UUID | str) -> Optional[Contract]:
        cid = contract_id if isinstance(contract_id, UUID) else UUID(str(contract_id))
        stmt = select(Contract).where(Contract.id == cid)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_latest_by_lead_id(self, lead_id: UUID | str) -> Optional[Contract]:
        lid = lead_id if isinstance(lead_id, UUID) else UUID(str(lead_id))
        stmt = (
            select(Contract)
            .where(Contract.lead_id == lid)
            .order_by(Contract.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_yousign_signature_request_id(self, request_id: str) -> Optional[Contract]:
        if not request_id:
            return None
        stmt = select(Contract).where(Contract.yousign_signature_request_id == request_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def set_status(
        self,
        contract: Contract,
        status: ContractStatus,
        *,
        signed_at: Optional[datetime] = None,
        withdrawn_at: Optional[datetime] = None,
    ) -> Contract:
        contract.status = status
        contract.updated_at = datetime.utcnow()
        if signed_at is not None:
            contract.signed_at = signed_at
        elif status == ContractStatus.SIGNED and not contract.signed_at:
            contract.signed_at = datetime.utcnow()

        if withdrawn_at is not None:
            contract.withdrawn_at = withdrawn_at
        elif status == ContractStatus.WITHDRAWN and not contract.withdrawn_at:
            contract.withdrawn_at = datetime.utcnow()

        self.db.flush()
        return contract

    def update_pdf_path(self, contract: Contract, pdf_path: str) -> Contract:
        contract.pdf_path = pdf_path
        contract.updated_at = datetime.utcnow()
        self.db.flush()
        return contract

    def update_yousign_info(
        self,
        contract: Contract,
        signature_request_id: str,
        document_id: Optional[str] = None,
        status: Optional[ContractStatus] = None,
    ) -> Contract:
        contract.yousign_signature_request_id = signature_request_id
        if document_id:
            contract.yousign_document_id = document_id
        if status:
            contract.status = status
        contract.updated_at = datetime.utcnow()
        self.db.flush()
        return contract

    def list_contracts(
        self,
        lead_id: Optional[UUID | str] = None,
        status: Optional[ContractStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Contract]:
        stmt = select(Contract)
        if lead_id:
            lid = lead_id if isinstance(lead_id, UUID) else UUID(str(lead_id))
            stmt = stmt.where(Contract.lead_id == lid)
        if status:
            stmt = stmt.where(Contract.status == status)
        stmt = stmt.order_by(Contract.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.execute(stmt).scalars().all())

    def count_signed(self) -> int:
        stmt = select(func.count(Contract.id)).where(Contract.status == ContractStatus.SIGNED)
        return self.db.execute(stmt).scalar() or 0

    def count_total(self) -> int:
        stmt = select(func.count(Contract.id))
        return self.db.execute(stmt).scalar() or 0

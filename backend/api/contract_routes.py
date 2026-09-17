"""
Contract API Routes — Sophie (Ecofix).

Provides endpoints for contract lifecycle management:
- GET /api/contracts: List contracts
- POST /api/contracts: Generate contract & PDF specimen for qualified lead
- GET /api/contracts/{id}: Contract details
- GET /api/contracts/{id}/pdf: Authenticated PDF stream / download
- POST /api/contracts/webhook/yousign: HMAC-verified Yousign webhook (SENT -> SIGNED, lead -> CUSTOMER)
- POST /api/contracts/{id}/simulate-sign: Sandbox simulation trigger
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.dependencies import require_api_key
from api.routes import get_db_session
from application.contract_service import ContractService
from crm.contract_repository import ContractRepository
from domain.enums import ContractStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contracts", tags=["contracts"])



# --- Schemas ---
class CreateContractRequest(BaseModel):
    lead_id: UUID


class ContractResponse(BaseModel):
    id: str
    lead_id: str
    product: str
    status: str
    yousign_signature_request_id: Optional[str] = None
    yousign_document_id: Optional[str] = None
    pdf_url: str
    created_at: str
    updated_at: str
    signed_at: Optional[str] = None
    withdrawn_at: Optional[str] = None
    digi_subscribed: bool = False
    yousign_status: Optional[str] = None
    yousign_label: Optional[str] = None
    lead_name: Optional[str] = None
    lead_email: Optional[str] = None
    lead_phone: Optional[str] = None
    lead_region: Optional[str] = None


class ContractListResponse(BaseModel):
    items: list[ContractResponse]
    total: int


def _serialize_contract(c: Any, base_url: str = "") -> ContractResponse:
    lead = getattr(c, "lead", None)
    lead_name = None
    lead_email = None
    lead_phone = None
    lead_region = None
    if lead:
        full_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()
        lead_name = full_name if full_name else "Prospect sans nom"
        lead_email = lead.email
        lead_phone = lead.phone
        lead_region = lead.region

    return ContractResponse(
        id=str(c.id),
        lead_id=str(c.lead_id),
        product=c.product,
        digi_subscribed=bool(getattr(c, "digi_subscribed", False)),
        status=c.status.value if hasattr(c.status, "value") else str(c.status),
        yousign_signature_request_id=c.yousign_signature_request_id,
        yousign_document_id=c.yousign_document_id,
        pdf_url=f"/api/contracts/{c.id}/pdf",
        created_at=c.created_at.isoformat() if c.created_at else "",
        updated_at=c.updated_at.isoformat() if c.updated_at else "",
        signed_at=c.signed_at.isoformat() if c.signed_at else None,
        withdrawn_at=c.withdrawn_at.isoformat() if c.withdrawn_at else None,
        lead_name=lead_name,
        lead_email=lead_email,
        lead_phone=lead_phone,
        lead_region=lead_region,
    )


@router.get("", response_model=ContractListResponse, dependencies=[Depends(require_api_key)])
def list_contracts(
    lead_id: Optional[UUID] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session),
):
    repo = ContractRepository(db)
    contract_status = ContractStatus(status) if status else None
    items = repo.list_contracts(lead_id=lead_id, status=contract_status, limit=limit, offset=offset)
    total = repo.count_total()
    return ContractListResponse(
        items=[_serialize_contract(c) for c in items],
        total=total,
    )


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_contract(
    payload: CreateContractRequest,
    db: Session = Depends(get_db_session),
):
    service = ContractService(db)
    try:
        contract, pdf_bytes, yousign_res = service.create_contract_for_lead(payload.lead_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to create contract for lead %s: %s", payload.lead_id, exc)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du contrat: {str(exc)}")

    res = _serialize_contract(contract)
    res.yousign_status = yousign_res.get("status")
    res.yousign_label = yousign_res.get("label")
    return res


@router.get("/{contract_id}", response_model=ContractResponse, dependencies=[Depends(require_api_key)])
def get_contract(
    contract_id: UUID,
    db: Session = Depends(get_db_session),
):
    repo = ContractRepository(db)
    contract = repo.get_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return _serialize_contract(contract)


@router.get("/{contract_id}/pdf", dependencies=[Depends(require_api_key)])
def download_contract_pdf(
    contract_id: UUID,
    db: Session = Depends(get_db_session),
):
    service = ContractService(db)
    try:
        contract, pdf_bytes = service.get_contract_pdf(contract_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    filename = f"contrat_specimen_ecofix_{contract.product.lower()}_{str(contract.id)[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.post("/{contract_id}/simulate-sign", response_model=ContractResponse, dependencies=[Depends(require_api_key)])
def simulate_contract_signature(
    contract_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Sandbox simulation: immediately marks contract as SIGNED and lead as CUSTOMER."""
    service = ContractService(db)
    try:
        contract = service.simulate_signature(contract_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _serialize_contract(contract)


@router.post("/webhook/yousign", status_code=200)
async def yousign_webhook(
    request: Request,
    x_yousign_signature: Optional[str] = Header(None, alias="X-Yousign-Signature"),
    x_yousign_signature_256: Optional[str] = Header(None, alias="X-Yousign-Signature-256"),
    db: Session = Depends(get_db_session),
):
    """HMAC-verified webhook from Yousign v3."""
    body_bytes = await request.body()
    sig_header = x_yousign_signature or x_yousign_signature_256

    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    service = ContractService(db)
    result = service.handle_yousign_webhook(
        payload_bytes=body_bytes,
        signature_header=sig_header,
        parsed_payload=payload,
    )

    if result.get("status") == "unauthorized":
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    return result

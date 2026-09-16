"""
Knowledge entries routes (Sprint 4b - keyword-RAG v1 admin surface, "Base
de Connaissances" screen).

Same discipline as api/leads_routes.py: this module never imports a
repository or the Engine/ai directly, only KnowledgeService (enforced by
tests/test_architecture_boundaries.py). Router-level require_api_key
(same convention as leads_routes.py:42) covers every route below - never
duplicated per-route.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import require_api_key
from api.knowledge_schemas import (
    CreateKnowledgeEntryRequest,
    KnowledgeEntryListResponse,
    KnowledgeEntryResponse,
    UpdateKnowledgeEntryRequest,
)
from api.routes import get_db_session
from application.knowledge_service import KnowledgeEntryNotFoundError, KnowledgeService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=KnowledgeEntryListResponse)
def list_entries(db: Session = Depends(get_db_session)) -> KnowledgeEntryListResponse:
    entries, total = KnowledgeService(db).list_entries()
    return KnowledgeEntryListResponse(items=[KnowledgeEntryResponse.from_model(e) for e in entries], total=total)


@router.post("", response_model=KnowledgeEntryResponse, status_code=201)
def create_entry(payload: CreateKnowledgeEntryRequest, db: Session = Depends(get_db_session)) -> KnowledgeEntryResponse:
    entry = KnowledgeService(db).create_entry(**payload.model_dump())
    return KnowledgeEntryResponse.from_model(entry)


@router.get("/{entry_id}", response_model=KnowledgeEntryResponse)
def get_entry(entry_id: UUID, db: Session = Depends(get_db_session)) -> KnowledgeEntryResponse:
    entry = _require(lambda: KnowledgeService(db).get_entry(entry_id))
    return KnowledgeEntryResponse.from_model(entry)


@router.put("/{entry_id}", response_model=KnowledgeEntryResponse)
def update_entry(
    entry_id: UUID, payload: UpdateKnowledgeEntryRequest, db: Session = Depends(get_db_session)
) -> KnowledgeEntryResponse:
    entry = _require(
        lambda: KnowledgeService(db).update_entry(entry_id, **payload.model_dump(exclude_unset=True))
    )
    return KnowledgeEntryResponse.from_model(entry)


@router.post("/{entry_id}/toggle-active", response_model=KnowledgeEntryResponse)
def toggle_active(entry_id: UUID, db: Session = Depends(get_db_session)) -> KnowledgeEntryResponse:
    entry = _require(lambda: KnowledgeService(db).toggle_active(entry_id))
    return KnowledgeEntryResponse.from_model(entry)


@router.delete("/{entry_id}", status_code=204, response_model=None)
def delete_entry(entry_id: UUID, db: Session = Depends(get_db_session)) -> None:
    _require(lambda: KnowledgeService(db).delete_entry(entry_id))


def _require(action):
    try:
        return action()
    except KnowledgeEntryNotFoundError:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

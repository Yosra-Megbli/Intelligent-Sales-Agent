"""
Knowledge entries & documents routes (Sprint 4b keyword-RAG v1 & RAG v2 Phase 4).

Same discipline as api/leads_routes.py: this module never imports a
repository or the Engine/ai directly, only KnowledgeService (enforced by
tests/test_architecture_boundaries.py). Router-level require_api_key
covers every route below.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.dependencies import get_embedding_provider, require_api_key
from api.knowledge_schemas import (
    CreateKnowledgeEntryRequest,
    KnowledgeDocumentResponse,
    KnowledgeEntryListResponse,
    KnowledgeEntryResponse,
    KnowledgeStatsResponse,
    TestQueryRequest,
    TestQueryResponse,
    UpdateKnowledgeEntryRequest,
    UploadDocumentResponse,
)
from api.routes import get_db_session
from application.knowledge_service import (
    EmbeddingUnavailableError,
    InvalidPdfError,
    KnowledgeDocumentNotFoundError,
    KnowledgeEntryNotFoundError,
    KnowledgeService,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"], dependencies=[Depends(require_api_key)])


# ── RAG v2 Documents & Admin Endpoints (Phase 4) ───────────────────────────

@router.get("/documents", response_model=list[KnowledgeDocumentResponse])
def list_documents(db: Session = Depends(get_db_session)) -> list[KnowledgeDocumentResponse]:
    docs = KnowledgeService(db).list_documents()
    return [KnowledgeDocumentResponse(**doc) for doc in docs]


@router.post("/documents/upload", response_model=UploadDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    source_type: str = Form("tariff_card"),
    language: str = Form("fr"),
    review_date: Optional[str] = Form(None),
    db: Session = Depends(get_db_session),
    embedding_provider=Depends(get_embedding_provider),
) -> UploadDocumentResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_format", "message": "Only PDF files are supported"},
        )

    parsed_review_date: Optional[date] = None
    if review_date and review_date.strip():
        try:
            parsed_review_date = datetime.fromisoformat(review_date.strip()).date()
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_date", "message": "Invalid review_date format, expected YYYY-MM-DD"},
            )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=422,
            detail={"code": "empty_file", "message": "Uploaded file is empty"},
        )

    try:
        res = KnowledgeService(db).upload_document(
            file_bytes=file_bytes,
            filename=file.filename,
            title=title,
            source_type=source_type,
            language=language,
            review_date=parsed_review_date,
            embedding_provider=embedding_provider,
        )
        return UploadDocumentResponse(**res)
    except InvalidPdfError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})
    except EmbeddingUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": exc.code, "message": str(exc), "retryable": exc.retryable},
        )


@router.post("/documents/{document_id}/publish", response_model=KnowledgeDocumentResponse)
def publish_document(document_id: UUID, db: Session = Depends(get_db_session)) -> KnowledgeDocumentResponse:
    try:
        doc = KnowledgeService(db).publish_document(document_id)
        return KnowledgeDocumentResponse(**doc)
    except KnowledgeDocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Knowledge document not found")


@router.post("/documents/{document_id}/archive", response_model=KnowledgeDocumentResponse)
def archive_document(document_id: UUID, db: Session = Depends(get_db_session)) -> KnowledgeDocumentResponse:
    try:
        doc = KnowledgeService(db).archive_document(document_id)
        return KnowledgeDocumentResponse(**doc)
    except KnowledgeDocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Knowledge document not found")


@router.post("/documents/{document_id}/unpublish", response_model=KnowledgeDocumentResponse)
def unpublish_document(document_id: UUID, db: Session = Depends(get_db_session)) -> KnowledgeDocumentResponse:
    try:
        doc = KnowledgeService(db).unpublish_document(document_id)
        return KnowledgeDocumentResponse(**doc)
    except KnowledgeDocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Knowledge document not found")


@router.get("/stats", response_model=KnowledgeStatsResponse)
def get_stats(db: Session = Depends(get_db_session)) -> KnowledgeStatsResponse:
    stats = KnowledgeService(db).get_stats()
    return KnowledgeStatsResponse(**stats)


@router.post("/test", response_model=TestQueryResponse)
def test_query(
    payload: TestQueryRequest,
    db: Session = Depends(get_db_session),
    embedding_provider=Depends(get_embedding_provider),
) -> TestQueryResponse:
    res = KnowledgeService(db).test_query(
        query=payload.query,
        language=payload.language,
        embedding_provider=embedding_provider,
    )
    return TestQueryResponse(**res)


@router.get("/obsolescence")
def get_obsolescence(db: Session = Depends(get_db_session)) -> dict:
    return KnowledgeService(db).get_obsolescence_status()


# ── Keyword RAG v1 Endpoints (Sprint 4b) ───────────────────────────────────

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
    entry = _require_entry(lambda: KnowledgeService(db).get_entry(entry_id))
    return KnowledgeEntryResponse.from_model(entry)


@router.put("/{entry_id}", response_model=KnowledgeEntryResponse)
def update_entry(
    entry_id: UUID, payload: UpdateKnowledgeEntryRequest, db: Session = Depends(get_db_session)
) -> KnowledgeEntryResponse:
    entry = _require_entry(
        lambda: KnowledgeService(db).update_entry(entry_id, **payload.model_dump(exclude_unset=True))
    )
    return KnowledgeEntryResponse.from_model(entry)


@router.post("/{entry_id}/toggle-active", response_model=KnowledgeEntryResponse)
def toggle_active(entry_id: UUID, db: Session = Depends(get_db_session)) -> KnowledgeEntryResponse:
    entry = _require_entry(lambda: KnowledgeService(db).toggle_active(entry_id))
    return KnowledgeEntryResponse.from_model(entry)


@router.delete("/{entry_id}", status_code=204, response_model=None)
def delete_entry(entry_id: UUID, db: Session = Depends(get_db_session)) -> None:
    _require_entry(lambda: KnowledgeService(db).delete_entry(entry_id))


def _require_entry(action):
    try:
        return action()
    except KnowledgeEntryNotFoundError:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

"""
Request/response schemas for `api/leads_routes.py`.

Same discipline as `api/schemas.py` and `api/dashboard_schemas.py`: pure
serialization shapes, no business logic.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UpdateLeadRequest(BaseModel):
    """All fields optional and unset-by-default (not defaulted to None) so
    a PATCH only ever touches the fields the caller actually included -
    see api/leads_routes.py's use of `.model_dump(exclude_unset=True)`.
    Limited to the same CRM-only fields application/lead_service.py's
    `_EDITABLE_FIELDS` allows - anything the Business Rules Engine owns
    (status, qualification_score, campaign_id...) is deliberately absent.
    `extra="forbid"` so sending one of those gives a clear 422 instead of
    Pydantic silently dropping the field and the request no-op'ing."""

    model_config = {"extra": "forbid"}

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    current_supplier: Optional[str] = None
    provider: Optional[str] = None
    notes: Optional[str] = None


class ImportCsvRequest(BaseModel):
    """The frontend reads the uploaded file as text (FileReader.readAsText)
    and posts it as plain JSON - no multipart handling needed on either
    side, and it keeps the same JSON-only style as the rest of the API."""

    csv_text: str = Field(min_length=1)


class ImportPreviewRowResponse(BaseModel):
    row_number: int
    data: dict
    would_be_duplicate: bool
    missing_identifier: bool


class ImportPreviewResponse(BaseModel):
    headers: list[str]
    rows: list[ImportPreviewRowResponse]
    total_rows: int
    rows_missing_identifier: int


class ImportRowErrorResponse(BaseModel):
    row_number: int
    message: str


class ImportReportResponse(BaseModel):
    rows_read: int
    created: int
    updated: int
    duplicates: int
    skipped: int
    errors: int
    duration_seconds: float
    error_details: list[ImportRowErrorResponse]

"""
Request/response schemas for `api/leads_routes.py`.

Same discipline as `api/schemas.py` and `api/dashboard_schemas.py`: pure
serialization shapes, no business logic.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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

"""
Request/response schemas for api/knowledge_routes.py.

Pure serialization shapes, no business logic - same discipline as every
other api/*_schemas.py in this codebase.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from domain.models.knowledge_entry import KnowledgeEntry


class KnowledgeEntryResponse(BaseModel):
    id: UUID
    category: str
    question: str
    keywords: list[str]
    answer_fr: str
    answer_nl: Optional[str]
    answer_en: Optional[str]
    active: bool
    updated_at: datetime

    @classmethod
    def from_model(cls, entry: KnowledgeEntry) -> "KnowledgeEntryResponse":
        return cls(
            id=entry.id,
            category=entry.category,
            question=entry.question,
            keywords=entry.get_keywords(),
            answer_fr=entry.answer_fr,
            answer_nl=entry.answer_nl,
            answer_en=entry.answer_en,
            active=entry.active,
            updated_at=entry.updated_at,
        )


class KnowledgeEntryListResponse(BaseModel):
    items: list[KnowledgeEntryResponse]
    total: int


class CreateKnowledgeEntryRequest(BaseModel):
    category: str = Field(min_length=1, max_length=32)
    question: str = Field(min_length=1, max_length=255)
    keywords: list[str] = Field(min_length=1)
    answer_fr: str = Field(min_length=1)
    answer_nl: Optional[str] = None
    answer_en: Optional[str] = None
    active: bool = True


class UpdateKnowledgeEntryRequest(BaseModel):
    model_config = {"extra": "forbid"}

    category: Optional[str] = None
    question: Optional[str] = None
    keywords: Optional[list[str]] = None
    answer_fr: Optional[str] = None
    answer_nl: Optional[str] = None
    answer_en: Optional[str] = None
    active: Optional[bool] = None

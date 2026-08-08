"""
Request/response schemas for the HTTP API.

Pure serialization shapes - no business logic lives here. `SendMessageResponse.
required_action` is exposed mainly for debugging/observability (e.g. a
frontend could show a typing indicator differently for NOTIFY_HUMAN vs a
normal question); the frontend should never branch its own business logic
on it.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class StartConversationRequest(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class StartConversationResponse(BaseModel):
    conversation_id: UUID
    lead_id: UUID


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class SendMessageResponse(BaseModel):
    reply: Optional[str]
    state: str
    required_action: Optional[str]


class MessageOut(BaseModel):
    role: str
    content: str
    timestamp: str

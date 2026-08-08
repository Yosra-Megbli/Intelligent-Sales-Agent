"""
Request/response schemas for the Voice Outbound HTTP API.

Same discipline as `api/campaign_schemas.py`/`api/dashboard_schemas.py`:
pure serialization shapes, no business logic.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class InitiateOutboundCallRequest(BaseModel):
    lead_id: UUID
    campaign_id: UUID


class InitiateOutboundCallResponse(BaseModel):
    lead_id: UUID
    campaign_id: UUID
    provider_call_id: str
    status: str

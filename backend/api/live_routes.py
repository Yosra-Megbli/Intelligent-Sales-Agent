"""
Live streaming and supervision routes (Sprint 5 Live Cockpit).

Auth pattern:
1. Browser fetches short-lived HMAC token: POST /api/live/token (API-key guarded)
2. Browser connects to GET /api/live/stream?token=... (EventSource SSE)
3. Concurrency limit enforced (max 5 concurrent streams per key).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.dependencies import require_api_key
from live.auth import acquire_stream_slot, generate_live_token, release_stream_slot, verify_live_token
from live.broker import get_live_broker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["live"])


class LiveTokenResponse(BaseModel):
    token: str
    expires_in: int


class KeyHealthResponse(BaseModel):
    provider: str
    status: str
    percent_used: Optional[float] = None


@router.post("/live/token", response_model=LiveTokenResponse, dependencies=[Depends(require_api_key)])
def create_live_token(x_api_key: Optional[str] = Header(None)) -> LiveTokenResponse:
    key_id = (x_api_key or "default_key")[:16]
    token = generate_live_token(key_id, expires_in=300)
    return LiveTokenResponse(token=token, expires_in=300)


@router.get("/keys/health", response_model=KeyHealthResponse, dependencies=[Depends(require_api_key)])
def get_key_health() -> KeyHealthResponse:
    """Honest key health reporting: returns 'unknown' until a dedicated health
    probe service is introduced."""
    return KeyHealthResponse(provider="groq", status="unknown", percent_used=None)


@router.get("/live/stream")
async def live_stream(request: Request, token: str = Query(...)) -> StreamingResponse:
    key_id, is_valid = verify_live_token(token)
    if not is_valid or not key_id:
        raise HTTPException(status_code=401, detail="Invalid or expired live token")

    if not acquire_stream_slot(key_id, max_concurrent=5):
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent streams for this API key (max 5)",
        )

    broker = get_live_broker()

    async def event_generator():
        queue = await broker.subscribe()
        start_time = time.time()
        max_stream_duration = 600.0  # 10 minutes maximum stream duration
        heartbeat_interval = 25.0  # Heartbeat every 25s

        try:
            # Initial connection acknowledgement comment
            yield ": connected\n\n"

            while True:
                if await request.is_disconnected():
                    break

                elapsed = time.time() - start_time
                if elapsed >= max_stream_duration:
                    logger.debug("Closing stream after reaching 10min max duration")
                    break

                try:
                    event_payload = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                    event_type = event_payload.get("event", "message")
                    data_json = json.dumps(event_payload.get("data", {}))
                    yield f"event: {event_type}\ndata: {data_json}\n\n"
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": heartbeat\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            await broker.unsubscribe(queue)
            release_stream_slot(key_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

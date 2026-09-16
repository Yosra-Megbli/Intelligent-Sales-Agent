"""
Authentication & Concurrency limits for EventSource SSE streams (Sprint 5).

EventSource in browser standard JavaScript cannot set custom headers (e.g. X-API-Key).
Therefore, access is gated by:
1. Short-lived signed token: POST /api/live/token (API-key guarded) -> {token, expires_in: 300}
2. Token verification: GET /api/live/stream?token=...
3. Concurrency limit: max 5 concurrent streams per API key (Redis counter with in-memory fallback).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_LIVE_SECRET = "dev-live-token-secret-change-in-prod"
_in_memory_stream_counts: dict[str, int] = {}


def _get_signing_secret() -> str:
    return (
        os.getenv("LIVE_TOKEN_SECRET")
        or os.getenv("WEBHOOK_SECRET")
        or os.getenv("API_KEY")
        or DEFAULT_LIVE_SECRET
    )


def generate_live_token(key_id: str, expires_in: int = 300) -> str:
    """Generate an HMAC-signed token expiring in `expires_in` seconds."""
    expires_at = int(time.time()) + expires_in
    clean_key = key_id.replace(":", "_")
    payload = f"{clean_key}:{expires_at}"
    secret = _get_signing_secret()
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_live_token(token: str) -> tuple[Optional[str], bool]:
    """Verify an HMAC-signed token.

    Returns (key_id, True) if valid and not expired, or (None, False).
    """
    if not token or not isinstance(token, str):
        return None, False

    parts = token.strip().split(":")
    if len(parts) != 3:
        return None, False

    key_id, exp_str, sig = parts

    try:
        expires_at = int(exp_str)
    except ValueError:
        return None, False

    now = int(time.time())
    if expires_at < now:
        logger.debug("Live token expired (exp=%d, now=%d)", expires_at, now)
        return None, False

    secret = _get_signing_secret()
    payload = f"{key_id}:{expires_at}"
    expected_sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(sig, expected_sig):
        logger.debug("Live token signature mismatch")
        return None, False

    return key_id, True


def acquire_stream_slot(key_id: str, max_concurrent: int = 5) -> bool:
    """Acquire a concurrent stream slot for `key_id`.

    Enforces max concurrent streams per API key (Redis counter with fallback).
    """
    try:
        from database.redis import get_redis
        r = get_redis()
        redis_key = f"live:streams:{key_id}"
        count = r.incr(redis_key)
        if count == 1:
            r.expire(redis_key, 7200)
        if count > max_concurrent:
            r.decr(redis_key)
            logger.warning("Key %s exceeded max concurrent live streams (%d > %d)", key_id, count, max_concurrent)
            return False
        return True
    except Exception as exc:
        logger.debug("Redis unavailable for stream slots (%s), falling back to in-memory", exc)
        count = _in_memory_stream_counts.get(key_id, 0)
        if count >= max_concurrent:
            logger.warning("Key %s exceeded max concurrent live streams in-memory (%d >= %d)", key_id, count, max_concurrent)
            return False
        _in_memory_stream_counts[key_id] = count + 1
        return True


def release_stream_slot(key_id: str) -> None:
    """Release a concurrent stream slot when SSE connection closes."""
    try:
        from database.redis import get_redis
        r = get_redis()
        redis_key = f"live:streams:{key_id}"
        val = r.decr(redis_key)
        if val <= 0:
            r.delete(redis_key)
    except Exception:
        if key_id in _in_memory_stream_counts:
            _in_memory_stream_counts[key_id] = max(0, _in_memory_stream_counts[key_id] - 1)
            if _in_memory_stream_counts[key_id] == 0:
                _in_memory_stream_counts.pop(key_id, None)

"""
Redis layer.

Redis never stores business truth (that's PostgreSQL's job). It only holds:
- the active conversation context cache (fast reads while chatting)
- short-lived session data
- rate limiting counters
- temporary locks (e.g. avoid double-processing the same incoming message)

Everything here is disposable: if Redis is flushed, the system must still be
able to rebuild context from PostgreSQL (Conversation.current_state,
Conversation.messages, Lead fields).
"""

import json
import os
from typing import Any, Optional

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def _context_key(conversation_id: str) -> str:
    return f"conversation:context:{conversation_id}"


def cache_conversation_context(conversation_id: str, context: dict, ttl_seconds: int = 3600) -> None:
    get_redis().set(_context_key(conversation_id), json.dumps(context), ex=ttl_seconds)


def get_cached_conversation_context(conversation_id: str) -> Optional[dict]:
    raw = get_redis().get(_context_key(conversation_id))
    return json.loads(raw) if raw else None


def _voice_call_key(call_sid: str) -> str:
    return f"voice:call:{call_sid}"


def cache_voice_call_state(call_sid: str, state: dict, ttl_seconds: int = 1800) -> None:
    """Per-call turn-taking state for the Voice channel (see
    channels/voice/session_manager.py's module docstring: VoiceTurnState is
    deliberately not persisted to PostgreSQL). Twilio makes one HTTP request
    per turn, so this is what lets consecutive turns of the same phone call
    find each other again. 30 min TTL comfortably covers one call; if it
    expires mid-call the next turn is treated as a fresh call rather than
    erroring."""
    get_redis().set(_voice_call_key(call_sid), json.dumps(state), ex=ttl_seconds)


def get_cached_voice_call_state(call_sid: str) -> Optional[dict]:
    raw = get_redis().get(_voice_call_key(call_sid))
    return json.loads(raw) if raw else None


def clear_voice_call_state(call_sid: str) -> None:
    get_redis().delete(_voice_call_key(call_sid))


def acquire_lock(key: str, ttl_seconds: int = 10) -> bool:
    """Simple lock to avoid processing the same message twice (e.g. webhook retries)."""
    return bool(get_redis().set(f"lock:{key}", "1", nx=True, ex=ttl_seconds))


def release_lock(key: str) -> None:
    get_redis().delete(f"lock:{key}")


def rate_limit_hit(key: str, max_hits: int, window_seconds: int) -> bool:
    """Returns True if the caller is within the allowed rate, False if limited."""
    r = get_redis()
    count = r.incr(f"rate:{key}")
    if count == 1:
        r.expire(f"rate:{key}", window_seconds)
    return count <= max_hits

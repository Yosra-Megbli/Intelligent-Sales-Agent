"""
FastAPI dependencies.

`get_llm_provider` is the one place the HTTP layer decides which concrete
`LLMProvider` to use. It is built once per process (`lru_cache`) and, if no
provider can be constructed (e.g. `GROQ_API_KEY` isn't set), returns `None`
rather than raising - `channels/web.py`'s `WebChannel` already knows how to
run in a degraded, fallback-text-only mode, so a missing API key should
degrade the API, not crash it at import time.

Security hardening (Phase 7) adds `require_api_key`, `verify_telegram_secret`
and `enforce_rate_limit`. All three follow the same "degrade with a loud
warning, don't crash" philosophy as the LLM/Telegram-sender dependencies
above when their corresponding secret isn't configured - this is a
deliberately dev-friendly default, NOT a secure-by-default one. A real
deployment MUST set `API_KEY` and `TELEGRAM_WEBHOOK_SECRET`, or every
request - including the dashboard's, which returns lead PII - runs
unauthenticated. This is stated plainly rather than hidden behind a comment
precisely so it doesn't get missed at deploy time.
"""

from __future__ import annotations

import logging
import os
import secrets
from functools import lru_cache
from typing import Optional

from fastapi import Header, HTTPException, status

from ai.providers.groq import GroqProvider
from ai.providers.interface import LLMError, LLMProvider
from database.redis import rate_limit_hit

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm_provider() -> Optional[LLMProvider]:
    try:
        return GroqProvider()
    except LLMError as exc:
        logger.warning(
            "No LLM provider configured (%s) - Sophie will run in degraded, fallback-text-only mode.",
            exc,
        )
        return None


@lru_cache(maxsize=1)
def get_telegram_sender():
    """Returns a `TelegramBotAPISender.send`-compatible callable, or None if
    `TELEGRAM_BOT_TOKEN` isn't configured - the webhook still processes the
    update and returns the computed reply either way (see api/routes.py),
    it just won't be able to push it back to Telegram itself without a token.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning(
            "TELEGRAM_BOT_TOKEN not configured - Telegram replies will be computed but not sent."
        )
        return None
    from channels.telegram import TelegramBotAPISender

    return TelegramBotAPISender(token).send


@lru_cache(maxsize=1)
def get_whatsapp_sender():
    """Returns a `TwilioWhatsAppSender.send`-compatible callable, or None if
    `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_WHATSAPP_NUMBER`
    aren't all configured - same degrade-gracefully pattern as
    `get_telegram_sender`.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    if not (account_sid and auth_token and from_number):
        logger.warning(
            "TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_WHATSAPP_NUMBER not fully configured - "
            "WhatsApp replies will be computed but not sent."
        )
        return None
    from channels.whatsapp import TwilioWhatsAppSender

    return TwilioWhatsAppSender(account_sid, auth_token, from_number).send


@lru_cache(maxsize=1)
def get_telephony_provider():
    """Returns a `TelephonyProvider` (currently `TwilioTelephonyProvider`)
    for placing outbound voice calls, or None if `TWILIO_ACCOUNT_SID` /
    `TWILIO_AUTH_TOKEN` / `TWILIO_VOICE_NUMBER` aren't all configured -
    same degrade-gracefully pattern as `get_telegram_sender`/
    `get_whatsapp_sender`, except a call can't silently "compute but not
    send" the way a text reply can (there is no text yet at dial-time - see
    `outbound/voice_sender.py`'s module docstring), so
    `api/voice_routes.py` turns a None here into an explicit 503 rather
    than a no-op.

    Deliberately reuses the same `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`
    as WhatsApp (one Twilio account, multiple products - see
    `docs/architecture/voice_agent_architecture.md` §13's note that Voice
    and WhatsApp already share the same vendor/billing) - only the Voice
    number itself (`TWILIO_VOICE_NUMBER`) is channel-specific.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    voice_number = os.getenv("TWILIO_VOICE_NUMBER")
    if not (account_sid and auth_token and voice_number):
        logger.warning(
            "TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_VOICE_NUMBER not fully configured - "
            "outbound voice calls cannot be placed."
        )
        return None
    from channels.voice.providers.twilio_telephony import TwilioTelephonyProvider

    return TwilioTelephonyProvider(account_sid, auth_token, from_number=voice_number)


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Guards the conversation and dashboard routes. Compares against
    `API_KEY` using a constant-time comparison (`secrets.compare_digest`) so
    response timing can't be used to brute-force the key one character at a
    time.

    If `API_KEY` isn't configured, logs a warning and allows the request
    through unauthenticated (see module docstring) - keeps every existing
    test and a first local run working without extra setup, but it means
    auth is OFF by default, including for the dashboard's PII-bearing
    endpoints. Set `API_KEY` to turn it on.
    """
    configured_key = os.getenv("API_KEY")
    if not configured_key:
        logger.warning("API_KEY not configured - this endpoint is running WITHOUT authentication.")
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, configured_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


def verify_telegram_secret(
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
) -> None:
    """Guards the Telegram webhook using the secret token Telegram echoes
    back on every call once it's configured via `setWebhook`'s
    `secret_token` parameter (Telegram's own recommended mechanism - not the
    generic `API_KEY`, since Telegram's servers are the caller here, not our
    own frontend). Same degrade-with-a-warning default as `require_api_key`
    when `TELEGRAM_WEBHOOK_SECRET` isn't configured.
    """
    configured_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not configured_secret:
        logger.warning(
            "TELEGRAM_WEBHOOK_SECRET not configured - the Telegram webhook is running WITHOUT verifying the caller."
        )
        return
    if not x_telegram_bot_api_secret_token or not secrets.compare_digest(
        x_telegram_bot_api_secret_token, configured_secret
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret token")


def enforce_rate_limit(key: str, max_hits: int = 20, window_seconds: int = 60) -> None:
    """Wraps `database.redis.rate_limit_hit` (built in Phase 1, never
    actually called anywhere until this security pass - the same "dead
    code" pattern found with WAITING_CUSTOMER in Phase 6) into an HTTP 429.
    Callers pass a key that identifies the caller for this endpoint, e.g. an
    external chat_id or a conversation_id, not a global key - otherwise one
    busy conversation would rate-limit every other customer too.

    If Redis itself is unreachable, fails OPEN (allows the request) rather
    than taking the whole API down over a rate-limiter outage - logs a
    warning so this is visible in production, but availability wins here.
    """
    try:
        allowed = rate_limit_hit(key, max_hits=max_hits, window_seconds=window_seconds)
    except Exception as exc:  # pragma: no cover - defensive, no Redis in this sandbox
        logger.warning("Rate limiter unavailable (%s) - allowing the request through.", exc)
        return
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests - please slow down.",
        )


def _compute_twilio_signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    """Twilio's own published algorithm (used to validate `X-Twilio-Signature`):
    HMAC-SHA1 of the full request URL with every POST parameter appended,
    sorted by key, key+value concatenated with no separator - keyed with the
    Auth Token, base64-encoded. See Twilio's "Validating Signatures from
    Twilio" docs. No `twilio` SDK dependency needed for this - it's ~10
    lines of stdlib `hmac`/`hashlib`/`base64`.
    """
    import base64
    import hashlib
    import hmac as hmac_module

    data = url
    for key in sorted(params.keys()):
        data += key + params[key]
    digest = hmac_module.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def verify_twilio_signature(url: str, params: dict[str, str], signature: Optional[str]) -> None:
    """Guards the WhatsApp webhook using Twilio's request-signing mechanism
    (Twilio's own recommended mechanism, mirroring `verify_telegram_secret`
    for Telegram's secret-token mechanism - each provider signs webhooks
    differently, so each channel gets its own verifier). Called explicitly
    from `api/routes.py` (not a plain FastAPI `Depends`) because it needs
    the exact request URL and parsed form body together, which the route
    already has to read anyway to process the message.

    Same degrade-with-a-warning default as `require_api_key` and
    `verify_telegram_secret` when `TWILIO_AUTH_TOKEN` isn't configured.
    """
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if not auth_token:
        logger.warning(
            "TWILIO_AUTH_TOKEN not configured - the WhatsApp webhook is running WITHOUT verifying the caller."
        )
        return
    expected = _compute_twilio_signature(auth_token, url, params)
    if not signature or not secrets.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature")

"""
Conversation routes.

Thin HTTP wrapper around `channels/web.py`'s `WebChannel` - this module
translates HTTP request/response shapes and 404s only. It never touches
`conversation_engine/`, `ai/*`, or the repositories directly - not even for
creating a Lead/Conversation or reading history - everything goes through
`WebChannel`, which itself only delegates to `application/
conversation_service.py`'s `ConversationService`:

    FastAPI (this file) -> WebChannel -> ConversationService ->
    ConversationEngine -> Repositories

Security hardening adds `require_api_key` (every route here) and
`verify_telegram_secret` (Telegram webhook only - Telegram's own mechanism,
not the generic API key), plus per-caller rate limiting on every endpoint
that accepts inbound traffic from outside our own frontend.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.dependencies import (
    enforce_rate_limit,
    get_llm_provider,
    get_telegram_sender,
    get_whatsapp_sender,
    require_api_key,
    verify_telegram_secret,
    verify_twilio_signature,
)
from api.schemas import (
    MessageOut,
    SendMessageRequest,
    SendMessageResponse,
    StartConversationRequest,
    StartConversationResponse,
)
from channels.telegram import TelegramChannel
from channels.web import WebChannel
from channels.whatsapp import WhatsAppChannel
from database.postgres import session_scope

router = APIRouter(prefix="/api", tags=["conversations"])


def get_db_session():
    """FastAPI dependency: wraps `database.postgres.session_scope` as a
    plain generator so FastAPI manages the commit/rollback lifecycle around
    the request, same transactional behaviour as `session_scope` used
    outside of a request (scripts, scheduler jobs)."""
    with session_scope() as db:
        yield db


@router.post(
    "/conversations",
    response_model=StartConversationResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
def start_conversation(
    payload: StartConversationRequest,
    db: Session = Depends(get_db_session),
    provider=Depends(get_llm_provider),
) -> StartConversationResponse:
    channel = WebChannel(db, provider=provider)
    lead, conversation = channel.start_conversation(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
    )
    return StartConversationResponse(conversation_id=conversation.id, lead_id=lead.id)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
    dependencies=[Depends(require_api_key)],
)
def send_message(
    conversation_id: UUID,
    payload: SendMessageRequest,
    db: Session = Depends(get_db_session),
    provider=Depends(get_llm_provider),
) -> SendMessageResponse:
    channel = WebChannel(db, provider=provider)
    if channel.get_conversation(conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Keyed per-conversation so one busy customer never rate-limits another.
    enforce_rate_limit(f"web:{conversation_id}")

    reply = channel.handle_message(conversation_id, payload.text)

    return SendMessageResponse(
        reply=reply.response_text,
        state=reply.state,
        required_action=reply.required_action,
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
    dependencies=[Depends(require_api_key)],
)
def get_history(
    conversation_id: UUID,
    db: Session = Depends(get_db_session),
) -> list[MessageOut]:
    channel = WebChannel(db)
    if channel.get_conversation(conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    history = channel.get_history(conversation_id)
    return [
        MessageOut(role=message.role.value, content=message.content, timestamp=message.timestamp.isoformat())
        for message in history
    ]


@router.post("/telegram/webhook", status_code=200, dependencies=[Depends(verify_telegram_secret)])
def telegram_webhook(
    update: dict[str, Any],
    db: Session = Depends(get_db_session),
    provider=Depends(get_llm_provider),
    send_message=Depends(get_telegram_sender),
) -> dict:
    """Telegram calls this with every Update as its webhook body. Always
    returns 200 (Telegram retries aggressively on non-2xx) even for updates
    with nothing to reply to - `TelegramChannel.handle_update` returns None
    for those, and there's nothing to send back. Guarded by
    `verify_telegram_secret` (Telegram's webhook secret token mechanism, not
    the generic API key - Telegram's own servers are the caller here).
    """
    chat_id = TelegramChannel.extract_chat_id(update)
    if chat_id is not None:
        enforce_rate_limit(f"telegram:{chat_id}")

    channel = TelegramChannel(db, provider=provider, send_message=send_message)
    response = channel.handle_update(update)
    if response is None:
        return {"ok": True}
    return {"ok": True, "state": response.state, "required_action": response.required_action}


@router.post("/whatsapp/webhook", status_code=200)
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db_session),
    provider=Depends(get_llm_provider),
    send_message=Depends(get_whatsapp_sender),
) -> dict:
    """Twilio calls this with every inbound WhatsApp message as an
    `application/x-www-form-urlencoded` body (NOT JSON, unlike Telegram) -
    hence reading `request.form()` directly instead of a Pydantic body
    model. Always returns 200 (Twilio retries on non-2xx) even for
    payloads with nothing to reply to (e.g. delivery-status callbacks) -
    `WhatsAppChannel.handle_update` returns None for those.

    Guarded by `verify_twilio_signature` (Twilio's own request-signing
    mechanism - called explicitly here, not via `Depends`, because it needs
    the exact request URL together with the parsed form body, which this
    route already reads to process the message).
    """
    form = await request.form()
    payload = dict(form)

    verify_twilio_signature(
        url=str(request.url),
        params=payload,
        signature=request.headers.get("X-Twilio-Signature"),
    )

    phone = WhatsAppChannel.extract_phone(payload)
    if phone is not None:
        enforce_rate_limit(f"whatsapp:{phone}")

    channel = WhatsAppChannel(db, provider=provider, send_message=send_message)
    response = channel.handle_update(payload)
    if response is None:
        return {"ok": True}
    return {"ok": True, "state": response.state, "required_action": response.required_action}

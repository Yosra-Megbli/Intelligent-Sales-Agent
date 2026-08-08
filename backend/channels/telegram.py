"""
Telegram Channel.

Phase 4B: a thin adapter over `application/conversation_service.py`'s
`ConversationService` (Phase 4A), following the exact same shape as
`channels/web.py`. Its only two jobs, neither of which is orchestration:

1. Parse Telegram's webhook `Update` JSON into a chat_id + text.
2. Find-or-create the Conversation for that chat_id (via
   `Conversation.external_id`, added specifically so a returning Telegram
   user resumes the same conversation instead of starting a new one on
   every message - see domain/models/conversation.py).

Sending the reply back to Telegram is injected as `send_message` (a plain
callable), never called directly by this class in tests - the real
implementation (`TelegramBotAPISender`, using the Bot API's `sendMessage`)
lives at the bottom of this file and is only wired in by whatever entrypoint
actually runs the bot (outside this sandbox's network allowlist).
"""

from __future__ import annotations

from typing import Any, Callable, Optional
from uuid import UUID

from ai.providers.interface import LLMProvider
from application.conversation_service import (
    ConversationRequest,
    ConversationResponse,
    ConversationService,
)
from domain.enums import ConversationChannel


class TelegramChannel:
    """Handles one incoming Telegram update end-to-end.

    `send_message(chat_id: str, text: str) -> None` is injected so this
    class stays testable without a real Telegram bot token or network
    access - pass `TelegramBotAPISender(bot_token).send` in production, or
    leave it as None to only compute the reply without sending it (e.g. if
    the caller wants to send it itself).
    """

    def __init__(
        self,
        db_session,
        provider: Optional[LLMProvider] = None,
        send_message: Optional[Callable[[str, str], None]] = None,
    ):
        self._service = ConversationService(db_session, provider=provider)
        self._send_message = send_message

    def handle_update(self, update: dict[str, Any]) -> Optional[ConversationResponse]:
        """Process one Telegram `Update` webhook payload. Returns None for
        updates with no text message (e.g. edited messages, join events) -
        there is nothing to reply to.
        """
        parsed = self._parse_update(update)
        if parsed is None:
            return None
        chat_id, text, first_name, last_name = parsed

        conversation = self._service.get_conversation_by_external_id(
            ConversationChannel.TELEGRAM, chat_id
        )
        if conversation is None:
            _, conversation = self._service.start_conversation(
                ConversationChannel.TELEGRAM,
                first_name=first_name,
                last_name=last_name,
                external_id=chat_id,
            )

        response = self._service.handle_message(
            ConversationRequest(conversation_id=conversation.id, text=text)
        )

        if self._send_message and response.response_text:
            self._send_message(chat_id, response.response_text)

        return response

    def get_history(self, conversation_id: UUID, limit: int = 50):
        return self._service.get_history(conversation_id, limit=limit)

    @staticmethod
    def extract_chat_id(update: dict[str, Any]) -> Optional[str]:
        """Public helper for callers (api/routes.py) that need the chat_id
        before deciding to process the update at all - e.g. to rate-limit
        per-chat_id without duplicating the parsing logic."""
        parsed = TelegramChannel._parse_update(update)
        return parsed[0] if parsed else None

    @staticmethod
    def _parse_update(update: dict[str, Any]) -> Optional[tuple[str, str, Optional[str], Optional[str]]]:
        """Telegram's standard webhook shape:
        {"message": {"chat": {"id": 123}, "text": "...", "from": {"first_name": ..., "last_name": ...}}}
        Returns None if this update carries no text message.
        """
        message = update.get("message")
        if not message or "text" not in message:
            return None

        chat_id = str(message["chat"]["id"])
        text = message["text"]
        sender = message.get("from") or {}
        return chat_id, text, sender.get("first_name"), sender.get("last_name")


class TelegramBotAPISender:
    """Real `send_message` implementation using the Telegram Bot API.
    Not exercised by any test in this sandbox (no network access to
    api.telegram.org here) - wire this in only in a real deployment.
    """

    def __init__(self, bot_token: str):
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    def send(self, chat_id: str, text: str) -> None:
        import httpx  # local import: keep this dependency optional at test time

        response = httpx.post(
            f"{self._base_url}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10
        )
        response.raise_for_status()

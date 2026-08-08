"""
Web Channel.

Phase 4B: a thin adapter over `application/conversation_service.py`'s
`ConversationService` (Phase 4A). All orchestration (extractor -> engine ->
rag -> responder -> persistence) now lives in the Application layer; this
module's only job is translating the Web transport's shape (a plain
customer-id + raw text string, as the HTTP layer in `api/routes.py` already
has them) into a `ConversationRequest` and handing back a
`ConversationResponse`.

Once Telegram/WhatsApp/Voice channels exist, they will look almost
identical to this one: parse their own webhook/transcript format into a
`ConversationRequest`, call the same `ConversationService`, translate the
`ConversationResponse` back into that channel's reply format. None of them
will import `conversation_engine` or `ai/*` - only `ConversationService`
does.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from ai.providers.interface import LLMProvider
from application.conversation_service import (
    ConversationRequest,
    ConversationResponse,
    ConversationService,
)
from domain.enums import ConversationChannel


class WebChannel:
    """Handles one incoming web message end-to-end, by delegating to
    `ConversationService`. `provider` is passed straight through - see
    `ConversationService` for the degraded no-provider behaviour. (RAG has
    no channel-specific concern, so `ConversationService` picks its own
    default `Rag()` - the channel doesn't need to know it exists.)"""

    def __init__(self, db_session, provider: Optional[LLMProvider] = None):
        self._service = ConversationService(db_session, provider=provider)

    def start_conversation(
        self,
        *,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        language: str = "fr",
    ):
        return self._service.start_conversation(
            ConversationChannel.WEB,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            language=language,
        )

    def get_conversation(self, conversation_id: UUID):
        return self._service.get_conversation(conversation_id)

    def get_history(self, conversation_id: UUID, limit: int = 50):
        return self._service.get_history(conversation_id, limit=limit)

    def handle_message(self, conversation_id: UUID, raw_text: str) -> ConversationResponse:
        return self._service.handle_message(ConversationRequest(conversation_id=conversation_id, text=raw_text))

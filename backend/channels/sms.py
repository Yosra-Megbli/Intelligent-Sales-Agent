"""
SMS Channel (via Twilio).

Same thin-adapter pattern as `channels/whatsapp.py` and `channels/telegram.py`,
over the same `ConversationService`.

Invariants (AGENTS.md):
- Deterministic core: State Machine decides states; Rules Engine decides actions.
  The LLM only phrases replies.
- Compliance: AI disclosure mandatory on greeting, STOP/STOPT/ARRÊT immediate opt-out.
- No network calls in tests: `send_message` is injected.

Twilio SMS webhook parameters (application/x-www-form-urlencoded):
- From: sender's phone in E.164 (e.g. "+32488000001")
- Body: message text
- To: Twilio phone number
- MessageSid: Twilio message identifier
"""

from __future__ import annotations

from typing import Callable, Optional
from uuid import UUID

from ai.providers.interface import LLMProvider
from application.conversation_service import (
    ConversationRequest,
    ConversationResponse,
    ConversationService,
)
from domain.enums import ConversationChannel


class SmsChannel:
    """Handles one incoming Twilio SMS webhook payload end-to-end.

    `send_message(phone: str, text: str) -> None` is injected so this class
    stays testable without a real Twilio account.
    """

    def __init__(
        self,
        db_session,
        provider: Optional[LLMProvider] = None,
        send_message: Optional[Callable[[str, str], None]] = None,
    ):
        self._service = ConversationService(db_session, provider=provider)
        self._send_message = send_message

    def handle_update(self, payload: dict[str, str]) -> Optional[ConversationResponse]:
        """Process one Twilio SMS webhook payload (parsed from form-urlencoded into dict).
        Returns None if there is no message body to act on (e.g. delivery receipts).
        """
        parsed = self._parse_payload(payload)
        if parsed is None:
            return None
        phone, text = parsed

        conversation = self._service.get_conversation_by_external_id(
            ConversationChannel.SMS, phone
        )
        if conversation is None:
            _, conversation = self._service.start_conversation(
                ConversationChannel.SMS,
                phone=phone,
                external_id=phone,
            )

        response = self._service.handle_message(
            ConversationRequest(conversation_id=conversation.id, text=text)
        )

        if self._send_message and response.response_text:
            self._send_message(phone, response.response_text)

        return response

    def get_history(self, conversation_id: UUID, limit: int = 50):
        return self._service.get_history(conversation_id, limit=limit)

    @staticmethod
    def extract_phone(payload: dict[str, str]) -> Optional[str]:
        """Extract sender phone number for rate-limiting prior to full processing."""
        parsed = SmsChannel._parse_payload(payload)
        return parsed[0] if parsed else None

    @staticmethod
    def _parse_payload(payload: dict[str, str]) -> Optional[tuple[str, str]]:
        """Extract phone and message body from Twilio SMS form payload."""
        body = payload.get("Body")
        from_field = payload.get("From")
        if not body or not from_field:
            return None
        return from_field.strip(), body.strip()


class TwilioSmsSender:
    """Real `send_message` implementation using Twilio's REST Messages API."""

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number

    def send(self, phone: str, text: str) -> None:
        import httpx

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}/Messages.json"
        httpx.post(
            url,
            auth=(self._account_sid, self._auth_token),
            data={
                "From": self._from_number,
                "To": phone,
                "Body": text,
            },
            timeout=10,
        )

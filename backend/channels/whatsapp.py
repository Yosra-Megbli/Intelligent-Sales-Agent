"""
WhatsApp Channel (via Twilio).

Same thin-adapter pattern as `channels/telegram.py`, over the same
`ConversationService`. Its only two jobs, neither of which is orchestration:

1. Parse Twilio's WhatsApp webhook payload (form-encoded fields: `From`,
   `Body`, `ProfileName` - NOT JSON, unlike Telegram's webhook) into a phone
   number + text.
2. Find-or-create the Conversation for that phone number (via
   `Conversation.external_id`, the same field Telegram uses for its
   chat_id - one mechanism, two channels).

Sending the reply back to WhatsApp is injected as `send_message` (a plain
callable), never called directly by this class in tests - the real
implementation (`TwilioWhatsAppSender`, using Twilio's REST Messages API)
lives at the bottom of this file and is only wired in by whatever entrypoint
actually runs against Twilio (outside this sandbox's network allowlist, same
as Telegram's `TelegramBotAPISender`).

`external_id` is stored WITHOUT the `whatsapp:` prefix Twilio puts on every
phone number (e.g. `whatsapp:+15551234567` -> `+15551234567`), so the value
in the database reads as a plain phone number. `TwilioWhatsAppSender` adds
the prefix back on the way out.
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

_WHATSAPP_PREFIX = "whatsapp:"


class WhatsAppChannel:
    """Handles one incoming Twilio WhatsApp webhook payload end-to-end.

    `send_message(phone: str, text: str) -> None` is injected so this class
    stays testable without a real Twilio account - pass
    `TwilioWhatsAppSender(account_sid, auth_token, from_number).send` in
    production, or leave it as None to only compute the reply without
    sending it.
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
        """Process one Twilio WhatsApp webhook payload (already parsed from
        `application/x-www-form-urlencoded` into a plain dict by the
        caller - see api/routes.py). Returns None if there's no message
        body to act on (e.g. a delivery-status callback, not an inbound
        message).
        """
        parsed = self._parse_payload(payload)
        if parsed is None:
            return None
        phone, text, profile_name = parsed

        conversation = self._service.get_conversation_by_external_id(
            ConversationChannel.WHATSAPP, phone
        )
        if conversation is None:
            _, conversation = self._service.start_conversation(
                ConversationChannel.WHATSAPP,
                first_name=profile_name,
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
        """Public helper for callers (api/routes.py) that need the phone
        number before deciding to process the payload at all - e.g. to
        rate-limit per-phone-number without duplicating the parsing logic."""
        parsed = WhatsAppChannel._parse_payload(payload)
        return parsed[0] if parsed else None

    @staticmethod
    def _parse_payload(payload: dict[str, str]) -> Optional[tuple[str, str, Optional[str]]]:
        """Twilio's WhatsApp webhook shape (form-encoded, flattened here to
        a plain dict by the caller): `From=whatsapp:+1555...&Body=...&
        ProfileName=...`. Returns None if there's no `Body` to act on.
        """
        body = payload.get("Body")
        from_field = payload.get("From")
        if not body or not from_field:
            return None

        phone = from_field.removeprefix(_WHATSAPP_PREFIX)
        profile_name = payload.get("ProfileName") or None
        return phone, body, profile_name


class TwilioWhatsAppSender:
    """Real `send_message` implementation using Twilio's REST Messages API.
    Not exercised by any test in this sandbox (no network access to
    api.twilio.com here) - wire this in only in a real deployment.
    """

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self._account_sid = account_sid
        self._auth_token = auth_token
        # `from_number` is the Twilio-provisioned WhatsApp sender, plain
        # E.164 (e.g. "+14155238886") - the whatsapp: prefix is added here.
        self._from_number = from_number

    def send(self, phone: str, text: str) -> None:
        import httpx  # local import: keep this dependency optional at test time

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}/Messages.json"
        httpx.post(
            url,
            auth=(self._account_sid, self._auth_token),
            data={
                "From": f"{_WHATSAPP_PREFIX}{self._from_number}",
                "To": f"{_WHATSAPP_PREFIX}{phone}",
                "Body": text,
            },
            timeout=10,
        )

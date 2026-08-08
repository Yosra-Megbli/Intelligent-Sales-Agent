"""
Outbound channel senders (real transport wiring).

`OutboundSender`/`OutboundScheduler` compute *what* Sophie should say
(via `ConversationService.start_and_greet()`) but, on their own, never
push a word anywhere - exactly like `ConversationService.handle_message()`
never pushes an inbound reply anywhere either. Actually delivering text
over a channel's real transport (Telegram's Bot API `sendMessage`,
Twilio's WhatsApp REST API, ...) is each channel's own concern, injected
as a plain `send_message(external_id: str, text: str) -> None` callable -
same shape, same reasoning, as `channels/telegram.py`'s and
`channels/whatsapp.py`'s own injected `send_message`.

This module is the single place that builds those callables from
environment variables for the *outbound* pipeline, mirroring
`api/dependencies.py`'s `get_telegram_sender`/`get_whatsapp_sender` (which
do the exact same job for the *inbound* webhook reply path) - same env
vars, same "degrade with a loud warning, don't crash" philosophy: a
channel with missing credentials simply isn't included in the returned
dict, so `OutboundSender` computes the reply but doesn't attempt to send
it, rather than raising mid-campaign.

Kept separate from `api/dependencies.py` (rather than importing from it)
because `outbound/` is a lower layer than the HTTP layer - scripts like
`run_outbound.py` and a cron/worker tick need these senders without
pulling in FastAPI at all.
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Optional

from domain.enums import ConversationChannel

logger = logging.getLogger(__name__)


def build_telegram_sender() -> Optional[Callable[[str, str], None]]:
    """Returns a `TelegramBotAPISender.send`-compatible callable, or None
    if `TELEGRAM_BOT_TOKEN` isn't configured - the outbound send still
    happens (greeting generated, lead marked CONTACTED), it just won't
    reach a real Telegram chat without a token.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning(
            "TELEGRAM_BOT_TOKEN not configured - outbound Telegram messages "
            "will be computed but not sent."
        )
        return None
    from channels.telegram import TelegramBotAPISender

    return TelegramBotAPISender(token).send


def build_whatsapp_sender() -> Optional[Callable[[str, str], None]]:
    """Returns a `TwilioWhatsAppSender.send`-compatible callable, or None if
    `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_WHATSAPP_NUMBER` aren't
    all configured - same degrade-gracefully pattern as
    `build_telegram_sender`.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    if not (account_sid and auth_token and from_number):
        logger.warning(
            "TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_WHATSAPP_NUMBER not "
            "fully configured - outbound WhatsApp messages will be computed "
            "but not sent."
        )
        return None
    from channels.whatsapp import TwilioWhatsAppSender

    return TwilioWhatsAppSender(account_sid, auth_token, from_number).send


def build_default_senders() -> dict[ConversationChannel, Callable[[str, str], None]]:
    """Every real, currently-configured outbound sender, keyed by channel -
    the dict `OutboundSender` expects. A channel is present in the result
    only if its credentials are fully configured; an unconfigured channel
    is simply absent (never a `None` value), so callers can do a plain
    `senders.get(channel)` without a second None-check.
    """
    senders: dict[ConversationChannel, Callable[[str, str], None]] = {}

    telegram_sender = build_telegram_sender()
    if telegram_sender is not None:
        senders[ConversationChannel.TELEGRAM] = telegram_sender

    whatsapp_sender = build_whatsapp_sender()
    if whatsapp_sender is not None:
        senders[ConversationChannel.WHATSAPP] = whatsapp_sender

    return senders

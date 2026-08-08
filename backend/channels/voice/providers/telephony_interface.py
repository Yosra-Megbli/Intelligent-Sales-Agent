"""
Telephony Provider interface (Voice E, dial-out) - DESIGN + ARCHITECTURE,
no real network wiring.

Every other Voice provider abstraction in this package (`interface.py`'s
`SpeechToTextProvider`/`TextToSpeechProvider`) is about what happens
*during* an already-connected call. This one is about the piece that has
to happen *before* any of that: physically placing an outbound phone call
in the first place ("dial-out"). Unlike Telegram/WhatsApp - where the
inbound channel (webhook, `ConversationService`, a real
`TelegramBotAPISender`/`TwilioWhatsAppSender`) already exists and outbound
delivery is just "reuse that same transport to push a message" - Voice has
no outbound mechanism of any kind yet: there is no answer webhook wired
into `api/routes.py`, no `VoiceChannel` adapter tying
`channels/voice/session_manager.py`'s `VoiceSessionManager` to a live call,
and no code anywhere that has ever asked Twilio (or any provider) to ring a
number. This interface, `twilio_telephony.py`'s concrete implementation,
and `outbound/voice_sender.py` are that missing piece's architecture -
deliberately scoped to *placing the call*, not to running the conversation
once it connects (see the "Scope" note below).

Mirrors the exact discipline of `interface.py`'s STT/TTS abstractions: one
coherent capability, one abstract method, a dedicated exception hierarchy
callers catch without knowing which vendor is configured, plain-data
result types. `VoiceSessionManager`/`ConversationService` never know this
interface exists - dialing a phone is an Outbound-pipeline concern (same
layer as `outbound/sender.py`'s Telegram/WhatsApp delivery), not a
conversation-mechanics concern.

Scope (explicitly, so this isn't mistaken for more than it is): a
`TelephonyProvider.initiate_call()` call only makes the customer's phone
ring and hands the provider a `webhook_url` it should request once the
call is *answered*. What that webhook actually returns (TwiML that starts
`VoiceSessionManager.start_call()`, i.e. Sophie speaking first) is Voice
D/E's still-not-yet-built inbound-facing half - see
`docs/architecture/voice_agent_architecture.md`'s own "Voice E ... remain
design-only" note, which this module doesn't change. `outbound/
voice_sender.py` only gets the phone ringing and records the CRM
side-effect of having tried; it does not itself generate or send any
speech.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CallRequest:
    """Everything a `TelephonyProvider.initiate_call()` call needs to place
    one outbound call.

    `webhook_url` is the URL the provider should request once the call is
    answered (Twilio's `Url` parameter on `Calls.create` - the TwiML
    answer webhook). It is passed in, not decided by this layer: the
    Outbound pipeline (`outbound/voice_sender.py`) builds it from
    configuration (e.g. a `PUBLIC_BASE_URL` env var + a fixed path), since
    knowing the public URL of our own API is not a telephony-provider
    concern.
    """

    to_number: str
    webhook_url: str
    from_number: Optional[str] = None
    # A caller-supplied idempotency/correlation key (e.g. the outbound
    # attempt id) some providers accept to de-duplicate a retried request -
    # optional, never interpreted by this layer, just passed through.
    idempotency_key: Optional[str] = None


@dataclass
class CallResult:
    """The result of one `initiate_call()` call. `provider_call_id` is
    whatever id the provider assigns the call (Twilio's `CallSid`) - the
    Outbound pipeline stores it so a later status-callback webhook (not yet
    built either) could correlate back to this attempt, mirroring how
    `Conversation.external_id` correlates a Telegram/WhatsApp webhook back
    to a conversation.
    """

    provider_call_id: str
    status: str
    raw: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.raw is None:
            self.raw = {}


class TelephonyError(Exception):
    """Base class for every error this package raises for outbound
    dial-out. Callers (`outbound/voice_sender.py`) catch this - never a
    vendor-specific exception - so that layer stays decoupled from which
    telephony provider is configured, exactly like `ai/providers/
    interface.py`'s `LLMError` for the LLM layer."""


class TelephonyUnavailableError(TelephonyError):
    """The provider is unreachable or returned a server error placing the
    call. `outbound/voice_sender.py` treats this the same way
    `outbound/sender.py` treats a failed Telegram/WhatsApp send: the CRM
    bookkeeping (CONTACTED, follow_up_attempts, Campaign.sent) still
    records the attempt, logged loudly, never silently retried in a loop."""


class TelephonyAuthenticationError(TelephonyError):
    """Missing or invalid credentials. Never retried."""


class InvalidPhoneNumberError(TelephonyError):
    """`to_number` is missing, empty, or not in a shape the provider will
    accept (e.g. not E.164) - a caller/data bug (the Lead has no usable
    phone number), not a runtime provider failure."""


class TelephonyNotConfiguredError(TelephonyError):
    """Raised by a caller (not a provider itself) when no `TelephonyProvider`
    is available at all - e.g. `api/dependencies.py`'s
    `get_telephony_provider()` returned `None` because Twilio Voice
    credentials aren't set. Mirrors how `outbound/sender.py` simply omits a
    channel from `senders` rather than raising when unconfigured; this
    exception exists because, unlike a text send, an outbound call can't
    silently degrade to "compute but don't send" - there is nothing to
    compute until the call is actually placed, so the caller needs an
    explicit signal to return a clear 503 rather than pretend a call
    happened.
    """


class TelephonyProvider(ABC):
    """Every concrete provider (Twilio Voice's REST `Calls` API today;
    Vonage, Amazon Connect, or another provider later) implements this
    contract. `initiate_call` is intentionally the only method - anything
    about what happens after the call connects belongs to
    `VoiceSessionManager`/a future `VoiceProvider` (§13 of
    `voice_agent_architecture.md`), not here.
    """

    @abstractmethod
    def initiate_call(self, request: CallRequest) -> CallResult:
        """Place one outbound call per `request`. Must raise a
        `TelephonyError` subclass on an actual failure - never a vendor SDK
        exception directly, and never a fabricated/empty `CallResult` used
        to signal failure silently (same discipline as
        `SpeechToTextProvider.transcribe`/`TextToSpeechProvider.render` in
        `interface.py`).
        """
        raise NotImplementedError

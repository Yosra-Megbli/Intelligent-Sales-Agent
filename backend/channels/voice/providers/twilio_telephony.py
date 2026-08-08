"""
Twilio Voice Telephony Provider (dial-out) - concrete `TelephonyProvider`.

Same posture as `channels/telegram.py`'s `TelegramBotAPISender` and
`channels/whatsapp.py`'s `TwilioWhatsAppSender`: real, production-shaped
code against the vendor's documented REST API (Twilio's `Calls` resource,
`POST /2010-04-01/Accounts/{AccountSid}/Calls.json`), using the same
"raw HTTP over a heavy SDK" preference already established throughout this
codebase - not exercised by any test in this sandbox (no network access to
api.twilio.com here, and no real Twilio Voice number configured), wire
this in only in a real deployment.

This class's only job is placing the call - `request.webhook_url` (Twilio's
`Url` parameter) is what Twilio will request once the call is answered;
this class does not build, own, or know anything about what that URL
returns. See `telephony_interface.py`'s module docstring for the explicit
scope boundary between this (Voice E's dial-out half) and the still
not-yet-built inbound-facing TwiML answer webhook.
"""

from __future__ import annotations

from typing import Optional

from channels.voice.providers.telephony_interface import (
    CallRequest,
    CallResult,
    InvalidPhoneNumberError,
    TelephonyAuthenticationError,
    TelephonyError,
    TelephonyProvider,
    TelephonyUnavailableError,
)

_TWILIO_VOICE_CALLS_URL_TEMPLATE = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"


class TwilioTelephonyProvider(TelephonyProvider):
    """Construct one per process, same as `TwilioWhatsAppSender` - it holds
    no per-call state of its own, only the account credentials + default
    caller id needed to place any number of calls."""

    def __init__(self, account_sid: str, auth_token: str, from_number: Optional[str] = None):
        self._account_sid = account_sid
        self._auth_token = auth_token
        # The Twilio-provisioned Voice number calls are placed from by
        # default - can still be overridden per-call via
        # `CallRequest.from_number` (e.g. a campaign with multiple caller
        # ids), matching `TwilioWhatsAppSender`'s single-default-number
        # shape but without hardcoding it as the only option.
        self._default_from_number = from_number

    def initiate_call(self, request: CallRequest) -> CallResult:
        import httpx  # local import: keep this dependency optional at test time

        to_number = (request.to_number or "").strip()
        if not to_number:
            raise InvalidPhoneNumberError("CallRequest.to_number is empty - cannot place a call with no number.")

        from_number = request.from_number or self._default_from_number
        if not from_number:
            raise TelephonyError(
                "No from_number available: pass CallRequest.from_number or configure "
                "TwilioTelephonyProvider(from_number=...) with a Twilio Voice number."
            )

        url = _TWILIO_VOICE_CALLS_URL_TEMPLATE.format(account_sid=self._account_sid)
        data = {"To": to_number, "From": from_number, "Url": request.webhook_url}

        try:
            response = httpx.post(url, auth=(self._account_sid, self._auth_token), data=data, timeout=10)
        except httpx.HTTPError as exc:
            raise TelephonyUnavailableError(f"Could not reach Twilio Voice API: {exc}") from exc

        if response.status_code == 401:
            raise TelephonyAuthenticationError("Twilio rejected the account SID/auth token for this call.")
        if response.status_code >= 500:
            raise TelephonyUnavailableError(f"Twilio Voice API returned {response.status_code}: {response.text}")
        if response.status_code >= 400:
            raise TelephonyError(f"Twilio Voice API rejected the call request ({response.status_code}): {response.text}")

        payload = response.json()
        return CallResult(
            provider_call_id=payload.get("sid", ""),
            status=payload.get("status", "queued"),
            raw=payload,
        )

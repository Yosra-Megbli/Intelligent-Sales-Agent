"""
Tests for channels/voice/providers/twilio_telephony.py's
TwilioTelephonyProvider.

Same posture as its module docstring: this class makes a real network call
in production, which this sandbox can't exercise - so every test here
monkeypatches `httpx.post` to verify the request this class *builds*
(method, URL, auth, form fields) and how it maps Twilio's various
responses to `CallResult`/`TelephonyError` subclasses, without ever
touching the network.
"""

from __future__ import annotations

import httpx
import pytest

from channels.voice.providers.telephony_interface import (
    CallRequest,
    InvalidPhoneNumberError,
    TelephonyAuthenticationError,
    TelephonyError,
    TelephonyUnavailableError,
)
from channels.voice.providers.twilio_telephony import TwilioTelephonyProvider


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or str(payload)

    def json(self):
        return self._payload


def _provider() -> TwilioTelephonyProvider:
    return TwilioTelephonyProvider("AC_fake_sid", "fake_auth_token", from_number="+14155238886")


def test_initiate_call_posts_the_expected_twilio_calls_request(monkeypatch):
    captured = {}

    def fake_post(url, auth=None, data=None, timeout=None):
        captured["url"] = url
        captured["auth"] = auth
        captured["data"] = data
        return _FakeResponse(201, {"sid": "CA123", "status": "queued"})

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = _provider()
    result = provider.initiate_call(
        CallRequest(to_number="+32491234567", webhook_url="https://api.ecofix.be/api/voice/twiml")
    )

    assert captured["url"] == "https://api.twilio.com/2010-04-01/Accounts/AC_fake_sid/Calls.json"
    assert captured["auth"] == ("AC_fake_sid", "fake_auth_token")
    assert captured["data"] == {
        "To": "+32491234567",
        "From": "+14155238886",
        "Url": "https://api.ecofix.be/api/voice/twiml",
    }
    assert result.provider_call_id == "CA123"
    assert result.status == "queued"
    assert result.raw == {"sid": "CA123", "status": "queued"}


def test_per_call_from_number_overrides_the_default(monkeypatch):
    captured = {}

    def fake_post(url, auth=None, data=None, timeout=None):
        captured["data"] = data
        return _FakeResponse(201, {"sid": "CA1", "status": "queued"})

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = _provider()
    provider.initiate_call(
        CallRequest(to_number="+32491234567", webhook_url="https://x/twiml", from_number="+14155550123")
    )

    assert captured["data"]["From"] == "+14155550123"


def test_initiate_call_rejects_an_empty_to_number():
    provider = _provider()
    with pytest.raises(InvalidPhoneNumberError):
        provider.initiate_call(CallRequest(to_number="", webhook_url="https://x/twiml"))


def test_initiate_call_raises_when_no_from_number_is_available_at_all():
    provider = TwilioTelephonyProvider("AC_fake_sid", "fake_auth_token")  # no default from_number
    with pytest.raises(TelephonyError):
        provider.initiate_call(CallRequest(to_number="+32491234567", webhook_url="https://x/twiml"))


def test_a_401_response_raises_telephony_authentication_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(401, text="Authenticate"))

    provider = _provider()
    with pytest.raises(TelephonyAuthenticationError):
        provider.initiate_call(CallRequest(to_number="+32491234567", webhook_url="https://x/twiml"))


def test_a_5xx_response_raises_telephony_unavailable_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(500, text="Internal error"))

    provider = _provider()
    with pytest.raises(TelephonyUnavailableError):
        provider.initiate_call(CallRequest(to_number="+32491234567", webhook_url="https://x/twiml"))


def test_a_4xx_response_raises_the_base_telephony_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(400, text="Invalid To number"))

    provider = _provider()
    with pytest.raises(TelephonyError):
        provider.initiate_call(CallRequest(to_number="+32491234567", webhook_url="https://x/twiml"))


def test_a_network_error_raises_telephony_unavailable_error(monkeypatch):
    def raise_network_error(*args, **kwargs):
        raise httpx.ConnectError("simulated network outage")

    monkeypatch.setattr(httpx, "post", raise_network_error)

    provider = _provider()
    with pytest.raises(TelephonyUnavailableError):
        provider.initiate_call(CallRequest(to_number="+32491234567", webhook_url="https://x/twiml"))

import pytest
from fastapi import HTTPException

from api.dependencies import (
    _compute_twilio_signature,
    enforce_rate_limit,
    require_api_key,
    verify_telegram_secret,
    verify_twilio_signature,
)


def test_require_api_key_allows_through_when_not_configured(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    require_api_key(x_api_key=None)  # should not raise


def test_require_api_key_accepts_the_correct_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")
    require_api_key(x_api_key="s3cret")  # should not raise


def test_require_api_key_rejects_a_missing_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key=None)
    assert exc_info.value.status_code == 401


def test_require_api_key_rejects_a_wrong_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key="wrong")
    assert exc_info.value.status_code == 401


def test_verify_telegram_secret_allows_through_when_not_configured(monkeypatch):
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    verify_telegram_secret(x_telegram_bot_api_secret_token=None)  # should not raise


def test_verify_telegram_secret_accepts_the_correct_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "tg-secret")
    verify_telegram_secret(x_telegram_bot_api_secret_token="tg-secret")  # should not raise


def test_verify_telegram_secret_rejects_a_wrong_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "tg-secret")
    with pytest.raises(HTTPException) as exc_info:
        verify_telegram_secret(x_telegram_bot_api_secret_token="wrong")
    assert exc_info.value.status_code == 403


def test_enforce_rate_limit_fails_open_when_redis_is_unavailable():
    """No Redis server exists in this sandbox - enforce_rate_limit must not
    take the whole API down over a rate-limiter outage."""
    enforce_rate_limit("some-key")  # should not raise, even without Redis


def test_enforce_rate_limit_blocks_once_the_limit_is_exceeded(monkeypatch):
    calls = {"count": 0}

    def fake_rate_limit_hit(key, max_hits, window_seconds):
        calls["count"] += 1
        return calls["count"] <= max_hits

    monkeypatch.setattr("api.dependencies.rate_limit_hit", fake_rate_limit_hit)

    for _ in range(3):
        enforce_rate_limit("test-caller", max_hits=3)

    with pytest.raises(HTTPException) as exc_info:
        enforce_rate_limit("test-caller", max_hits=3)
    assert exc_info.value.status_code == 429


def test_verify_twilio_signature_allows_through_when_not_configured(monkeypatch):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    verify_twilio_signature(url="https://example.com/webhook", params={}, signature=None)  # no raise


def test_verify_twilio_signature_accepts_a_correctly_computed_signature(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-secret")
    url = "https://example.com/api/whatsapp/webhook"
    params = {"From": "whatsapp:+15551234567", "Body": "Bonjour"}
    signature = _compute_twilio_signature("twilio-secret", url, params)

    verify_twilio_signature(url=url, params=params, signature=signature)  # should not raise


def test_verify_twilio_signature_rejects_a_wrong_signature(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-secret")
    with pytest.raises(HTTPException) as exc_info:
        verify_twilio_signature(
            url="https://example.com/api/whatsapp/webhook",
            params={"From": "whatsapp:+15551234567", "Body": "Bonjour"},
            signature="wrong-signature",
        )
    assert exc_info.value.status_code == 403


def test_verify_twilio_signature_rejects_a_tampered_param(monkeypatch):
    """The signature is computed over the URL + params - changing a param
    after the fact (e.g. a MITM altering the message body) must invalidate
    a signature that was valid for the original params."""
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-secret")
    url = "https://example.com/api/whatsapp/webhook"
    original_params = {"From": "whatsapp:+15551234567", "Body": "Bonjour"}
    signature = _compute_twilio_signature("twilio-secret", url, original_params)

    tampered_params = {"From": "whatsapp:+15551234567", "Body": "Something else entirely"}
    with pytest.raises(HTTPException) as exc_info:
        verify_twilio_signature(url=url, params=tampered_params, signature=signature)
    assert exc_info.value.status_code == 403

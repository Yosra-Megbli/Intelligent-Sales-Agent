"""
Tests for outbound/senders.py - the env-based factory that builds real
outbound delivery callables for OutboundSender/OutboundScheduler.
"""

from domain.enums import ConversationChannel
from outbound.senders import build_default_senders, build_telegram_sender, build_whatsapp_sender


def test_build_telegram_sender_returns_none_when_token_not_configured(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert build_telegram_sender() is None


def test_build_telegram_sender_returns_a_callable_when_token_configured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    sender = build_telegram_sender()
    assert callable(sender)


def test_build_whatsapp_sender_returns_none_when_partially_configured(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_NUMBER", raising=False)
    assert build_whatsapp_sender() is None


def test_build_whatsapp_sender_returns_a_callable_when_fully_configured(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("TWILIO_WHATSAPP_NUMBER", "+14155238886")
    sender = build_whatsapp_sender()
    assert callable(sender)


def test_build_default_senders_omits_unconfigured_channels(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_NUMBER", raising=False)

    senders = build_default_senders()

    assert senders == {}


def test_build_default_senders_includes_only_configured_channels(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_NUMBER", raising=False)

    senders = build_default_senders()

    assert set(senders.keys()) == {ConversationChannel.TELEGRAM}
    assert callable(senders[ConversationChannel.TELEGRAM])

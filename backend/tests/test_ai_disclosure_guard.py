"""
Guard tests: every first outbound/inbound message MUST contain the AI
disclosure string mandated by AGENTS.md.

These tests use the no-LLM (fallback text) path so they need no network
access or provider credentials. They cover all three language paths
(FR / NL / EN) and all live channels (Web, Telegram, WhatsApp, Voice/outbound).

A failure here means a regression in compliance -- STOP and fix immediately.
"""

import pytest

from channels.telegram import TelegramChannel
from channels.web import WebChannel
from channels.whatsapp import WhatsAppChannel
from conversation_engine.compliance import AI_DISCLOSURE, disclosure_for
from crm.conversation_repository import ConversationRepository
from domain.enums import ConversationChannel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _disclosure_present(text: str, language: str) -> bool:
    """Check that the canonical disclosure key-phrase is present in `text`.

    We do a case-insensitive substring check on a key discriminator from
    each disclosure string rather than an exact-match so minor whitespace
    normalisation in the fallback YAML does not break the test.
    """
    discriminators = {
        "fr": "assistante virtuelle (intelligence artificielle)",
        "nl": "virtuele assistent (AI) van Ecofix",
        "en": "virtual assistant (AI) for Ecofix",
    }
    phrase = discriminators.get(language, discriminators["fr"])
    return phrase.lower() in (text or "").lower()


def _telegram_update(chat_id: int, text: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
            "from": {"id": chat_id, "first_name": "Test"},
        },
    }


# ---------------------------------------------------------------------------
# Item 1a -- compliance.py unit checks
# ---------------------------------------------------------------------------

def test_disclosure_for_fr_returns_fr_string():
    text = disclosure_for("fr")
    assert "assistante virtuelle (intelligence artificielle)" in text


def test_disclosure_for_nl_returns_nl_string():
    text = disclosure_for("nl")
    assert "virtuele assistent (AI) van Ecofix" in text


def test_disclosure_for_en_returns_en_string():
    text = disclosure_for("en")
    assert "virtual assistant (AI) for Ecofix" in text


def test_disclosure_for_unknown_language_falls_back_to_fr():
    text = disclosure_for("es")
    assert "assistante virtuelle (intelligence artificielle)" in text


# ---------------------------------------------------------------------------
# Item 1b -- channel guard tests (FR, the default language)
# ---------------------------------------------------------------------------

def test_inbound_web_first_response_contains_disclosure_fr(db_session):
    """WebChannel first message (FR, no LLM) must contain the FR disclosure."""
    channel = WebChannel(db_session, provider=None)
    _, conversation = channel.start_conversation(language="fr")
    response = channel.handle_message(conversation.id, "Bonjour")
    # The GREETING state fires SEND_GREETING whose fallback must include disclosure.
    assert _disclosure_present(response.response_text, "fr"), (
        f"FR disclosure missing from web first response.\nGot: {response.response_text!r}"
    )


def test_inbound_web_first_response_contains_disclosure_nl(db_session):
    """WebChannel first message (NL, no LLM) must contain the NL disclosure."""
    channel = WebChannel(db_session, provider=None)
    _, conversation = channel.start_conversation(language="nl")
    response = channel.handle_message(conversation.id, "Hallo")
    assert _disclosure_present(response.response_text, "nl"), (
        f"NL disclosure missing from web first response.\nGot: {response.response_text!r}"
    )


def test_inbound_web_first_response_contains_disclosure_en(db_session):
    """WebChannel first message (EN, no LLM) must contain the EN disclosure."""
    channel = WebChannel(db_session, provider=None)
    _, conversation = channel.start_conversation(language="en")
    response = channel.handle_message(conversation.id, "Hello")
    assert _disclosure_present(response.response_text, "en"), (
        f"EN disclosure missing from web first response.\nGot: {response.response_text!r}"
    )


def test_inbound_telegram_first_response_contains_disclosure(db_session):
    """Telegram first message (FR default) must contain the FR disclosure."""
    channel = TelegramChannel(db_session, provider=None)
    response = channel.handle_update(_telegram_update(chat_id=9001, text="Bonjour"))
    assert _disclosure_present(response.response_text, "fr"), (
        f"FR disclosure missing from Telegram first response.\nGot: {response.response_text!r}"
    )


def test_inbound_whatsapp_first_response_contains_disclosure(db_session):
    """WhatsApp first message (FR default) must contain the FR disclosure."""
    channel = WhatsAppChannel(db_session, provider=None)
    response = channel.handle_update({
        "From": "whatsapp:+32488000001",
        "Body": "Bonjour",
        "ProfileName": "Test User",
    })
    assert _disclosure_present(response.response_text, "fr"), (
        f"FR disclosure missing from WhatsApp first response.\nGot: {response.response_text!r}"
    )


def test_outbound_start_and_greet_contains_disclosure(db_session):
    """Outbound start_and_greet (FR) must contain the FR disclosure."""
    from application.conversation_service import ConversationService
    from domain.enums import ConversationChannel

    service = ConversationService(db_session, provider=None)
    _lead, _conv, response = service.start_and_greet(
        ConversationChannel.WEB, language="fr"
    )
    assert _disclosure_present(response.response_text, "fr"), (
        f"FR disclosure missing from outbound start_and_greet.\nGot: {response.response_text!r}"
    )

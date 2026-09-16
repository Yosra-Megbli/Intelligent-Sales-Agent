"""
Tests for Language Detection and Persistence on Lead (Sprint 2).

Invariants (AGENTS.md):
- Deterministic language detection between 'fr', 'nl', 'en'
- Falls back to 'fr'
- Preserves / updates language directly on Lead entity
"""

import uuid
import pytest

from conversation_engine.language_detector import detect_language
from application.conversation_service import ConversationRequest, ConversationService
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel, LeadSource


def test_detect_language_french_samples():
    assert detect_language("Bonjour, je souhaite changer de fournisseur d'électricité.") == "fr"
    assert detect_language("Merci beaucoup, nous habitons en Wallonie à Liège.") == "fr"
    assert detect_language("Salut Sophie, quel est votre tarif ?") == "fr"


def test_detect_language_dutch_samples():
    assert detect_language("Hallo, ik wil graag overstappen naar een andere leverancier.") == "nl"
    assert detect_language("Goedendag, wij wonen in Vlaanderen te Gent.") == "nl"
    assert detect_language("Bedankt voor de hulp, mijn contract loopt af.") == "nl"


def test_detect_language_english_samples():
    assert detect_language("Hello, I want to switch my energy supplier please.") == "en"
    assert detect_language("Hi Sophie, can you give me more details about electricity prices?") == "en"
    assert detect_language("Thanks a lot, I live in Flanders.") == "en"


def test_detect_language_empty_and_unknown_falls_back():
    assert detect_language("") == "fr"
    assert detect_language(None) == "fr"
    assert detect_language("12345", fallback="nl") == "nl"
    assert detect_language("???", fallback="fr") == "fr"


def test_start_conversation_sets_lead_language(db_session):
    service = ConversationService(db_session, provider=None)
    lead, conv = service.start_conversation(
        ConversationChannel.WEB,
        language="nl",
        email="jan@test.be",
    )

    assert lead.language == "nl"
    assert conv.language == "nl"


def test_handle_message_updates_lead_language_on_dutch_input(db_session):
    service = ConversationService(db_session, provider=None)
    lead, conv = service.start_conversation(
        ConversationChannel.WEB,
        language="fr",
        email="prospect@test.be",
    )
    assert lead.language == "fr"

    # Customer speaks Dutch
    service.handle_message(
        ConversationRequest(
            conversation_id=conv.id,
            text="Hallo, ik wil graag overstappen van leverancier in Antwerpen.",
        )
    )

    refreshed_lead = LeadRepository(db_session).get_by_id(lead.id)
    refreshed_conv = ConversationRepository(db_session).get_by_id(conv.id)
    assert refreshed_lead.language == "nl"
    assert refreshed_conv.language == "nl"

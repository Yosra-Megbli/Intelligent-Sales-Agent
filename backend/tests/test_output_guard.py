"""
Output Guard Tests (Deterministic Anti-Hallucination & Compliance Linter).

Layer 5 of the 5-layer guarantee:
1. Regex linter inspects assistant output before sending.
2. If forbidden patterns (stats invention like '20%', 'gratuit', 'jamais', 'toujours',
   'le marché va baisser', 'garanti') match, discard LLM text and use deterministic fallback.
3. If SEND_GREETING lacks mandatory AI disclosure, discard and use fallback.
4. ActivityType.GUARD_TRIGGERED is logged on the lead with violation details.
5. Clean phrasing passes through untouched.
"""

from __future__ import annotations

import json
import uuid
import pytest

from ai.providers.interface import LLMMessage, LLMProvider, LLMResponse
from ai.responder import Responder
from application.conversation_service import ConversationRequest, ConversationService
from conversation_engine.compliance import (
    find_forbidden_claim,
    is_disclosure_present,
    verify_output_guard,
)
from crm.activity_repository import ActivityRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ActivityType, ConversationChannel, ConversationState, LeadSource
from domain.models.conversation import Conversation
from domain.models.lead import Lead


class FakeProvider(LLMProvider):
    def __init__(self, content: str, json_content: Optional[str] = None):
        self.content = content
        self.json_content = json_content or json.dumps({
            "intent": "provide_supplier",
            "entities": {"supplier": "Engie"}
        })
        self.calls: list[dict] = []

    def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.calls.append({"messages": messages, "kwargs": kwargs})
        content = self.json_content if kwargs.get("json_mode") else self.content
        return LLMResponse(content=content, model="fake-model")


def _make_conversation(language: str = "fr") -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        lead_id=uuid.uuid4(),
        channel=ConversationChannel.WEB,
        current_state=ConversationState.COLLECT_SUPPLIER,
        language=language,
    )


# ---------------------------------------------------------------------------
# Unit tests: compliance linter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden_text,expected_pattern",
    [
        ("Vous pouvez économiser jusqu'à 20% sur votre facture.", "percentage_statistic"),
        ("Avec nous, c'est 15 % d'économies garanties.", "percentage_statistic"),
        ("Le changement de fournisseur est 100% sans frais.", "percentage_statistic"),
        ("Profitez de notre offre avec un mois gratuit.", "free_promise"),
        ("Het contract is volledig gratis.", "free_promise"),
        ("This energy switch is completely free.", "free_promise"),
        ("Vous ne paierez jamais trop cher votre électricité.", "absolute_never"),
        ("Bij ons betaalt u nooit te veel.", "absolute_never"),
        ("You will never overpay with Ecofix.", "absolute_never"),
        ("Nous avons toujours les meilleurs tarifs de Belgique.", "absolute_always"),
        ("Onze prijzen zijn altijd het laagst.", "absolute_always"),
        ("Our prices are always lower than competitors.", "absolute_always"),
        ("Le marché va baisser dans les prochains mois, c'est le moment.", "market_prediction"),
        ("De markt daalt momenteel sterk.", "market_prediction"),
        ("The market will drop very soon.", "market_prediction"),
        ("Nous vous offrons un tarif garanti toute l'année.", "guaranteed_promise"),
        ("Een gegarandeerd tarief voor uw elektriciteit.", "guaranteed_promise"),
        ("We offer a guaranteed fixed-like stability.", "guaranteed_promise"),
    ],
)
def test_find_forbidden_claim_detects_prohibited_patterns(forbidden_text, expected_pattern):
    result = find_forbidden_claim(forbidden_text)
    assert result is not None, f"Expected forbidden claim in: {forbidden_text!r}"
    pattern_name, matched_text = result
    assert pattern_name == expected_pattern


def test_clean_text_has_no_forbidden_claims():
    clean_texts = [
        "Quel est votre fournisseur d'énergie actuel ?",
        "Dans quelle région habitez-vous et dans quelle ville ?",
        "Pourriez-vous me préciser votre nom et prénom ?",
        "Ecofix propose les contrats Flexy (variable mensuel) et Motion (dynamique).",
        "En Belgique, vous êtes libre de résilier sans frais de rupture.",
    ]
    for text in clean_texts:
        assert find_forbidden_claim(text) is None, f"False positive on: {text!r}"


def test_is_disclosure_present_helper():
    greeting_no_disclosure = "Bonjour ! Je suis Sophie d'Ecofix. Comment puis-je vous aider ?"
    assert not is_disclosure_present(greeting_no_disclosure, "fr")

    greeting_with_disclosure = (
        "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle) d'Ecofix -- "
        "un conseiller humain reste disponible à tout moment. Comment puis-je vous aider ?"
    )
    assert is_disclosure_present(greeting_with_disclosure, "fr")
    assert not is_disclosure_present(greeting_with_disclosure, "nl")


# ---------------------------------------------------------------------------
# Responder pipeline tests: replacement with fallback & violation flagging
# ---------------------------------------------------------------------------


def test_responder_discards_forbidden_claim_and_substitutes_fallback():
    # Phrasing model hallucinates a forbidden stat "20%"
    bad_llm_text = "Avec Ecofix, vous économisez jusqu'à 20% par an ! Quel est votre fournisseur actuel ?"
    provider = FakeProvider(content=bad_llm_text)
    responder = Responder(provider)
    conv = _make_conversation()

    result = responder.respond("ASK_SUPPLIER", conversation=conv)

    # Must NOT contain the bad LLM phrasing or the 20% claim
    assert "20%" not in result
    # Must be the deterministic fallback for ASK_SUPPLIER
    assert result == "Quel est votre fournisseur d'energie actuel ?"
    # Guard violation must be recorded
    assert responder.last_guard_violation is not None
    assert "percentage_statistic" in responder.last_guard_violation


def test_responder_discards_greeting_without_disclosure_and_substitutes_fallback():
    # Phrasing model hallucinates a greeting without AI disclosure
    bad_greeting = "Bonjour ! Je suis Sophie d'Ecofix. Comment puis-je vous aider aujourd'hui ?"
    provider = FakeProvider(content=bad_greeting)
    responder = Responder(provider)
    conv = _make_conversation("fr")

    result = responder.respond("SEND_GREETING", conversation=conv)

    # Must be replaced with the deterministic fallback containing the disclosure
    assert "assistante virtuelle (intelligence artificielle)" in result
    assert responder.last_guard_violation == "missing_ai_disclosure"


def test_responder_allows_clean_llm_phrasing_to_pass_through():
    clean_llm_text = "Pourriez-vous m'indiquer chez quel fournisseur d'énergie vous êtes actuellement ?"
    provider = FakeProvider(content=clean_llm_text)
    responder = Responder(provider)
    conv = _make_conversation()

    result = responder.respond("ASK_SUPPLIER", conversation=conv)

    assert result == clean_llm_text
    assert responder.last_guard_violation is None


# ---------------------------------------------------------------------------
# End-to-end integration test: ConversationService logs GUARD_TRIGGERED activity
# ---------------------------------------------------------------------------


def test_conversation_service_logs_guard_triggered_activity(db_session):
    """When the output guard triggers, ConversationService sends fallback text
    and records an Activity with ActivityType.GUARD_TRIGGERED on the lead."""
    # Setup lead and conversation
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE)
    conv = ConversationRepository(db_session).create(lead_id=lead.id, channel=ConversationChannel.WEB)
    ConversationRepository(db_session).transition_state(conv, ConversationState.COLLECT_SUPPLIER)
    db_session.commit()

    # Provider returns forbidden claim: "garanti" and "20%"
    provider = FakeProvider(content="Notre offre a 20% de remise garantie. Quel est votre fournisseur ?")
    service = ConversationService(db_session, provider=provider)

    # Process message in COLLECT_SUPPLIER
    response = service.handle_message(
        ConversationRequest(conversation_id=conv.id, text="J'habite à Namur en Wallonie")
    )

    # 1. Response must NOT contain forbidden text
    assert "20%" not in response.response_text
    assert "garantie" not in response.response_text

    # 2. Activity log must contain GUARD_TRIGGERED
    activities = ActivityRepository(db_session).list_for_lead(lead.id)
    guard_activities = [a for a in activities if a.type == ActivityType.GUARD_TRIGGERED]
    assert len(guard_activities) >= 1
    assert "forbidden_claim" in (guard_activities[0].details or "")

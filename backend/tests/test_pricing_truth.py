"""
Tests for pricing truth:
Verified against official Ecofix tariff card (EL_Ecofix_Flexy_FR.pdf, Sept 2026):
1. Frais fixes (obligatoire): 60,00 €/an (part of 'Prix de l'énergie').
2. Ecofix Digi: 5,99 €/mois — OPTIONAL digital app add-on (consumption tracking, smart control).
   NEVER present it as the base subscription or an obligatory fee.
3. Friends with Benefits: referral program (5 €/month discount per referral, no cap) — not a subscription.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from ai.extractor import Extractor
from ai.providers.interface import LLMProvider, LLMResponse
from ai.rag import Rag
from ai.responder import Responder
from application.conversation_service import ConversationRequest, ConversationService
from conversation_engine.engine import ConversationEngine
from conversation_engine.transitions import Event, EventType
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel, ConversationState, LeadSource
from domain.models.conversation import Conversation


class ScriptedExtractionProvider(LLMProvider):
    def __init__(self, extraction_payload: dict):
        self.extraction_payload = extraction_payload
        self.calls: list[dict] = []

    def generate(self, messages, *, temperature=0.0, max_tokens=1024, json_mode=False):
        self.calls.append({"messages": messages, "json_mode": json_mode})
        if json_mode:
            return LLMResponse(content=json.dumps(self.extraction_payload), model="fake-model")
        # For non-json phrasing, mirror the prompt facts or return default
        return LLMResponse(
            content="Des frais fixes de 60 €/an et l'appli Ecofix Digi en option à 5,99 €/mois.",
            model="fake-model",
        )


@pytest.fixture(autouse=True)
def fake_redis_cache(monkeypatch):
    store: dict[str, dict] = {}

    def fake_cache(conversation_id, context, ttl_seconds=3600):
        store[conversation_id] = context

    def fake_get(conversation_id):
        return store.get(conversation_id)

    monkeypatch.setattr("conversation_engine.memory.cache_conversation_context", fake_cache)
    monkeypatch.setattr("conversation_engine.memory.get_cached_conversation_context", fake_get)
    yield store


def test_rag_answers_pricing_truth_for_fees_inquiry():
    rag = Rag()
    answer = rag.answer("Quels sont vos frais ?", category="faq")
    assert answer is not None, "RAG should return an answer for 'Quels sont vos frais ?'"

    # Must cite 60 €/an fixed fee
    assert "60" in answer
    assert "an" in answer

    # Must cite Digi 5,99 €/mois as optional
    assert "5,99" in answer
    assert "Digi" in answer
    assert "option" in answer.lower()

    # Must mention free switching and no cancellation fees
    assert "gratuit" in answer.lower() or "sans frais" in answer.lower()

    # ASSERTION: Must NOT claim 5,99 €/mois is the base fee or obligatory
    lower_answer = answer.lower()
    assert "frais fixes de 5,99" not in lower_answer
    assert "redevance de 5,99" not in lower_answer
    assert "abonnement de 5,99" not in lower_answer
    assert "base de 5,99" not in lower_answer


def test_responder_formats_pricing_truth_answer():
    rag = Rag()
    rag_answer = rag.answer("Quels sont vos frais ?", category="faq")
    clean_phrasing = "Des frais fixes de 60 €/an et l'appli Ecofix Digi en option à 5,99 €/mois. Le changement est sans frais cachés ni résiliation."
    provider = ScriptedExtractionProvider(extraction_payload={})
    provider.generate = lambda messages, **kwargs: LLMResponse(content=clean_phrasing, model="fake-model")
    responder = Responder(provider=provider)
    conv = Conversation(channel=ConversationChannel.WEB, language="fr")

    reply = responder.respond("ANSWER_FAQ", conversation=conv, rag_answer=rag_answer)
    assert reply is not None

    # Must cite 60 €/an and optional Digi 5,99 €/mois
    assert "60" in reply
    assert "Digi" in reply
    assert "5,99" in reply
    assert "option" in reply.lower()

    # Must NOT claim 5,99 €/mo is the base fee
    lower_reply = reply.lower()
    assert "frais fixes de 5,99" not in lower_reply
    assert "redevance de 5,99" not in lower_reply
    assert "base de 5,99" not in lower_reply


def test_conversation_service_handles_fees_question_with_pricing_truth(db_session):
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE)
    conversation = ConversationRepository(db_session).create(
        lead_id=lead.id, channel=ConversationChannel.WEB, language="fr"
    )
    # Transition past START to GREETING
    ConversationRepository(db_session).transition_state(conversation, ConversationState.GREETING)
    db_session.commit()

    clean_phrasing = "Des frais fixes transparents de 60 €/an, et l'appli Ecofix Digi en option à 5,99 €/mois pour le suivi intelligent. Sans frais cachés."

    class FakeServiceLLM(LLMProvider):
        def generate(self, messages, *, temperature=0.0, max_tokens=1024, json_mode=False):
            if json_mode:
                return LLMResponse(content=json.dumps({"event_type": "QUESTION", "entities": {}}), model="fake")
            return LLMResponse(content=clean_phrasing, model="fake")

    service = ConversationService(db_session, provider=FakeServiceLLM())

    req = ConversationRequest(
        conversation_id=conversation.id,
        text="Quels sont vos frais ?",
    )
    response = service.handle_message(req)

    assert response.state == "FAQ"
    assert response.required_action == "ANSWER_FAQ"
    assert response.response_text is not None

    reply = response.response_text
    assert "60" in reply
    assert "Digi" in reply
    assert "5,99" in reply
    assert "option" in reply.lower()

    # Negative check: 5,99 is NOT claimed as base or obligatory fee
    lower_reply = reply.lower()
    assert "frais fixes de 5,99" not in lower_reply
    assert "redevance de 5,99" not in lower_reply
    assert "base de 5,99" not in lower_reply


def test_trilingual_fee_fallbacks_adhere_to_pricing_truth():
    fallback_file = Path(__file__).resolve().parent.parent / "prompts" / "responder" / "fallback_text.yaml"
    with open(fallback_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # FR
    fr_text = data.get("ANSWER_FEES_fr", "")
    assert "60 €/an" in fr_text or "60" in fr_text
    assert "Digi" in fr_text
    assert "option" in fr_text.lower()
    assert "5,99 €/mois" in fr_text
    assert "frais fixes de 5,99" not in fr_text.lower()

    # NL (u-form)
    nl_text = data.get("ANSWER_FEES_nl", "")
    assert "60 €/jaar" in nl_text or "60" in nl_text
    assert "Digi" in nl_text
    assert "optionele" in nl_text.lower()
    assert "5,99 €/maand" in nl_text
    assert "u" in nl_text.lower()  # u-form required
    assert "vaste kosten van 5,99" not in nl_text.lower()

    # EN
    en_text = data.get("ANSWER_FEES_en", "")
    assert "€60/year" in en_text or "60" in en_text
    assert "Digi" in en_text
    assert "optional" in en_text.lower()
    assert "€5.99/month" in en_text or "5.99" in en_text

"""
Deterministic refusal messages for RAG v2 (ZEN Knowledge pattern).

When retrieval finds no published chunk clearing RAG_MIN_SIMILARITY
and keyword RAG v1 also finds no match, Sophie returns this deterministic
legal refusal WITHOUT making any LLM call. This completely prevents
hallucinations on out-of-corpus questions.
"""

from __future__ import annotations

from typing import Optional

REFUSAL_MESSAGES: dict[str, str] = {
    "fr": (
        "Je n'ai pas d'information suffisante dans ma base documentaire pour "
        "répondre précisément à cette question — un conseiller humain vous répondra très prochainement."
    ),
    "nl": (
        "Ik heb niet voldoende informatie in mijn documentenbasis om deze vraag "
        "nauwkeurig te beantwoorden — een menselijke adviseur zal u zeer binnenkort antwoorden."
    ),
    "en": (
        "I don't have sufficient information in my document base to answer this "
        "question precisely — a human advisor will get back to you very soon."
    ),
}

DEFAULT_REFUSAL = REFUSAL_MESSAGES["fr"]


def get_refusal_message(language: Optional[str] = None) -> str:
    lang = (language or "fr").lower()
    return REFUSAL_MESSAGES.get(lang, DEFAULT_REFUSAL)

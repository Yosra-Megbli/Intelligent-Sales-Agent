"""
AI Compliance Strings -- Sophie (Ecofix).

Single source of truth for the mandatory AI-disclosure sentence that MUST
appear in every first outbound message and every voice-call opening,
as required by AGENTS.md (Golden rules, compliance -- mandatory in all
copy/prompts).

Usage:
    from conversation_engine.compliance import disclosure_for
    text = disclosure_for("fr")   # -> FR disclosure string

Nothing in this module depends on any database, LLM, or channel -- it is
safe to import from anywhere (prompts, responder, guard tests, voice layer).
"""

from __future__ import annotations

import re
from typing import Optional

# The exact strings from AGENTS.md -- never rephrase, never abbreviate.
AI_DISCLOSURE: dict[str, str] = {
    "fr": (
        "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle) "
        "d'Ecofix -- un conseiller humain reste disponible a tout moment."
    ),
    "nl": (
        "Dag, hier is Sophie, de virtuele assistent (AI) van Ecofix -- een "
        "menselijke adviseur neemt op elk moment over als u dat liever heeft."
    ),
    "en": (
        "Hi, this is Sophie, a virtual assistant (AI) for Ecofix -- a human "
        "advisor is available at any time."
    ),
}

# Fallback to FR when language is unknown/unsupported.
_DEFAULT_LANGUAGE = "fr"


def disclosure_for(language: str) -> str:
    """Return the mandatory AI-disclosure sentence for `language`.

    Falls back to French if `language` is not one of the three supported
    values (fr / nl / en) -- French is the primary operating language of
    this deployment.
    """
    return AI_DISCLOSURE.get(language.lower(), AI_DISCLOSURE[_DEFAULT_LANGUAGE])


# Canonical AI disclosure key phrases (case-insensitive substring discriminator per language)
DISCLOSURE_DISCRIMINATORS: dict[str, str] = {
    "fr": "assistante virtuelle (intelligence artificielle)",
    "nl": "virtuele assistent (ai)",
    "en": "virtual assistant (ai)",
}

# Forbidden claims: patterns violating AGENTS.md compliance invariants
# (stats invention, absolute promises, market predictions)
FORBIDDEN_CLAIM_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Percentage statistics (e.g. "jusqu'à 20%", "15 %")
    ("percentage_statistic", re.compile(r"\d+\s*%", re.IGNORECASE)),
    # Free/gratuit claims (e.g. "c'est gratuit", "gratis", "free")
    ("free_promise", re.compile(r"\b(?:gratuit(?:e|es|s)?|gratis|free)\b", re.IGNORECASE)),
    # Absolute negation promises (e.g. "jamais trop payer", "nooit te veel", "never overpay")
    ("absolute_never", re.compile(r"\b(?:jamais|nooit|never)\b", re.IGNORECASE)),
    # Absolute assurance promises (e.g. "toujours les meilleurs prix", "altijd goedkoper", "always cheaper")
    ("absolute_always", re.compile(r"\b(?:toujours|altijd|always)\b", re.IGNORECASE)),
    # Guaranteed promises (e.g. "garanti", "garantie", "gegarandeerd", "guaranteed")
    ("guaranteed_promise", re.compile(r"\b(?:garanti(?:e|es|s)?|gegarandeerd(?:e)?|guaranteed?)\b", re.IGNORECASE)),
    # Market predictions (e.g. "le marché va baisser", "le marché monte", "de markt zal", "the market will")
    ("market_prediction", re.compile(r"(?:le\s+marché\s+(?:va|va\s+baisser|monte|évolue|augmentera|baissera)|de\s+markt\s+(?:zal|daalt|stijgt)|the\s+market\s+will)", re.IGNORECASE)),
]


def is_disclosure_present(text: str, language: str = "fr") -> bool:
    """Check that the canonical AI disclosure key-phrase is present in `text`."""
    if not text:
        return False
    discriminator = DISCLOSURE_DISCRIMINATORS.get(language.lower(), DISCLOSURE_DISCRIMINATORS["fr"])
    return discriminator in text.lower()


def find_forbidden_claim(text: str) -> Optional[tuple[str, str]]:
    """Inspect text for forbidden claims patterns.
    Returns (pattern_name, matched_text) if found, otherwise None.
    """
    if not text:
        return None
    for name, pattern in FORBIDDEN_CLAIM_PATTERNS:
        match = pattern.search(text)
        if match:
            return (name, match.group(0))
    return None


def verify_output_guard(
    text: str,
    required_action: Optional[str] = None,
    language: str = "fr",
) -> tuple[bool, Optional[str]]:
    """Output Guard: deterministic anti-hallucination and compliance linter.

    Layer 5 of the 5-layer guarantee: runs AFTER the LLM phrases and BEFORE sending.
    Returns (is_valid, violation_detail).
    If invalid:
      - caller MUST discard the LLM output
      - substitute the deterministic fallback text for `required_action`
      - log a GUARD_TRIGGERED activity
    """
    if not text or not text.strip():
        return False, "empty_response"

    # Check for mandatory AI disclosure on greetings
    if required_action == "SEND_GREETING" and not is_disclosure_present(text, language=language):
        return False, "missing_ai_disclosure"

    # Check for forbidden claims (stats, absolute promises, market predictions)
    forbidden = find_forbidden_claim(text)
    if forbidden:
        pattern_name, matched_string = forbidden
        return False, f"forbidden_claim:{pattern_name}:{matched_string}"

    return True, None

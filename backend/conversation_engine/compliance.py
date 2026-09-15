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

"""
Language Detector -- Sophie (Ecofix).

Deterministic language classifier for incoming customer messages.
Detects between French ('fr', default), Dutch ('nl'), and English ('en')
based on vocabulary discriminators, common greetings, and regional terms.

Invariants (AGENTS.md):
- Deterministic core (no LLM dependency for language routing)
- Falls back to 'fr' (Ecofix primary market)
"""

from __future__ import annotations

import re
from typing import Optional

_NL_KEYWORDS = re.compile(
    r"\b(?:hallo|goedendag|dag|goeiedag|goede\s+morgen|goedenavond|"
    r"ik|ben|mijn|het|een|voor|niet|graag|bedankt|dank\s+u|alsjeblieft|"
    r"contract|stroom|gas|leverancier|energie|vlaanderen|overstappen|"
    r"antwerpen|gent|brugge|leuven|hasselt|aalst|mechelen|kortrijk)\b",
    re.IGNORECASE,
)

_EN_KEYWORDS = re.compile(
    r"\b(?:hello|hi|good\s+morning|good\s+evening|greetings|"
    r"my|the|is|are|please|thanks|thank\s+you|switch|supplier|"
    r"energy|electricity|flanders|wallonia|brussels)\b",
    re.IGNORECASE,
)

_FR_KEYWORDS = re.compile(
    r"\b(?:bonjour|salut|bonsoir|coucou|"
    r"je|mon|ma|mes|le|la|les|un|une|des|pour|pas|merci|s'il\s+vous\s+pla[îi]t|"
    r"contrat|fournisseur|énergie|électricité|wallonie|flandre|bruxelles|"
    r"liège|namur|charleroi|mons|tournai|wavre|arlon)\b",
    re.IGNORECASE,
)


def detect_language(text: Optional[str], fallback: str = "fr") -> str:
    """Detect language from text content.

    Returns:
        'fr', 'nl', or 'en'
    """
    if not text or not text.strip():
        return fallback.lower() if fallback in ("fr", "nl", "en") else "fr"

    clean_text = text.lower()

    # Count discriminator matches
    nl_matches = len(_NL_KEYWORDS.findall(clean_text))
    en_matches = len(_EN_KEYWORDS.findall(clean_text))
    fr_matches = len(_FR_KEYWORDS.findall(clean_text))

    if nl_matches > fr_matches and nl_matches > en_matches:
        return "nl"
    if en_matches > fr_matches and en_matches > nl_matches:
        return "en"
    if fr_matches > 0:
        return "fr"

    return fallback.lower() if fallback in ("fr", "nl", "en") else "fr"

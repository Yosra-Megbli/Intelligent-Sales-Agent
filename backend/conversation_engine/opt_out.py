"""
Opt-out detection -- Sophie (Ecofix).

AGENTS.md (golden rules): STOP/STOPT/ARRET = immediate opt-out.
This module owns ONLY the detection logic. Side-effects (PII purge, campaign
removal, timestamp, activity log) are in application/conversation_service.py
so they stay within the transaction managed there.

Pure function -- no DB, no imports from the rest of the codebase.
"""

from __future__ import annotations

import unicodedata


# Canonical opt-out keywords (case-insensitive, accent-insensitive).
# Single-word exact match only -- "stop" inside a sentence does NOT trigger
# opt-out (e.g. "Je dois m''arreter un moment" is NOT an opt-out request).
_OPT_OUT_KEYWORDS: frozenset[str] = frozenset({"stop", "stopt", "arret"})


def _normalize(text: str) -> str:
    """Strip accents, lowercase, strip whitespace."""
    nfd = unicodedata.normalize("NFD", text)
    ascii_only = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return ascii_only.lower().strip()


def is_opt_out(text: str) -> bool:
    """Return True if `text` is an opt-out request (STOP / STOPT / ARRET).

    The check is:
    - accent-insensitive  (ARRET == ARRET with circumflex)
    - case-insensitive    (STOP == stop)
    - leading/trailing whitespace ignored
    - EXACT WORD MATCH only -- the keyword must be the entire message,
      not embedded in a longer sentence.
    """
    return _normalize(text) in _OPT_OUT_KEYWORDS

"""
RAG (FAQ / Objection answering).

Phase 3E: the customer's raw message (via `Event.raw_answer_text`, once the
State Machine has already decided `event.type` is QUESTION or OBJECTION -
see state_machine.py's global overrides) is matched against a small,
declarative knowledge base (`knowledge_base.yaml`) to find the single fact
Sophie is allowed to state. This module never invents an answer: if nothing
matches well enough, it returns `None` and the caller (ultimately
`ai/responder.py`) falls back to its own generic "handing this to a
colleague" message rather than let the LLM improvise.

"RAG answers product questions only. It never changes CRM state."
(docs/09_RAG_ARCHITECTURE.md): this module has no concept of a Lead's
status, a Conversation's state, or a database. It is a pure function of
(text, category) -> Optional[str].

PURITY GUARANTEE (same discipline as ai/extractor.py and ai/responder.py):
never imports a repository, never calls `.flush()`/`.commit()`, and never
decides a Lead's status, qualification score, or Conversation's
current_state.

Retrieval here is deliberately simple keyword overlap, not embeddings: the
knowledge base is small and hand-curated, and a transparent, dependency-free
match is easier to test and reason about than a vector index for this
volume of content. Swapping in a real vector store later only needs a new
implementation behind the same `Rag.answer()` contract.

Rule 3 ("prompts never contain business logic") applies to
`knowledge_base.yaml` in a narrower sense than the other YAML files: the
*facts* Sophie may state (fees, contract terms, coverage regulator names...)
necessarily live here, since answering questions is this module's entire
job - but *how a message maps to a fact* (the matching logic below) and
*how that fact gets phrased* (ai/responder.py) both stay in code, not YAML.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

_KNOWLEDGE_BASE_PATH = Path(__file__).resolve().parent / "knowledge_base.yaml"

# Minimum number of matching keywords for an entry to be considered a real
# match. Below this, silence (None) is safer than a confidently wrong answer.
_MIN_MATCH_SCORE = 1

_WORD_PATTERN = re.compile(r"[a-zà-ÿ]+", re.IGNORECASE)


@dataclass(frozen=True)
class KnowledgeEntry:
    id: str
    category: str  # "faq" or "objection"
    keywords: tuple[str, ...]
    answer: str


def _load_entries() -> tuple[KnowledgeEntry, ...]:
    with open(_KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return tuple(
        KnowledgeEntry(
            id=item["id"],
            category=item["category"],
            keywords=tuple(item["keywords"]),
            answer=item["answer"].strip(),
        )
        for item in raw["entries"]
    )


_ENTRIES: tuple[KnowledgeEntry, ...] = _load_entries()


def _tokenize(text: str) -> set[str]:
    return {match.group(0).lower() for match in _WORD_PATTERN.finditer(text)}


def _normalize(text: str) -> str:
    """Lowercase, accent-agnostic-ish word sequence, order preserved - used
    for multi-word keyword phrase matching (order matters for a phrase;
    a bag of words does not)."""
    return " ".join(match.group(0).lower() for match in _WORD_PATTERN.finditer(text))


def _score(entry: KnowledgeEntry, message_tokens: set[str], normalized_message: str) -> int:
    score = 0
    for keyword in entry.keywords:
        keyword_tokens = _tokenize(keyword)
        if len(keyword_tokens) > 1:
            # Multi-word keyword (e.g. "contrat actuel"): require the exact
            # phrase in order, not just each word appearing unrelated to
            # each other somewhere in the message.
            if _normalize(keyword) in normalized_message:
                score += 1
            continue
        if keyword_tokens & message_tokens:
            score += 1
    return score


class Rag:
    """Matches a customer message against the knowledge base for a given
    category ("faq" or "objection") and returns the best-matching fact, or
    None if nothing matches well enough.

    Usage: `Rag().answer(event.raw_answer_text, category="faq")`.
    """

    def __init__(self, entries: tuple[KnowledgeEntry, ...] = _ENTRIES):
        self._entries = entries

    def _best_match(self, raw_text: Optional[str], category: str) -> Optional[KnowledgeEntry]:
        if not raw_text or not raw_text.strip():
            return None

        message_tokens = _tokenize(raw_text)
        if not message_tokens:
            return None
        normalized_message = _normalize(raw_text)

        candidates = [entry for entry in self._entries if entry.category == category]
        best_entry: Optional[KnowledgeEntry] = None
        best_score = 0
        for entry in candidates:
            score = _score(entry, message_tokens, normalized_message)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry is None or best_score < _MIN_MATCH_SCORE:
            return None
        return best_entry

    def answer(self, raw_text: Optional[str], *, category: str) -> Optional[str]:
        entry = self._best_match(raw_text, category)
        return entry.answer if entry else None

    def match_id(self, raw_text: Optional[str], *, category: str) -> Optional[str]:
        """Same matching as `answer`, but returns the entry id instead of the
        fact text - useful for logging/analytics without exposing the answer
        content itself."""
        entry = self._best_match(raw_text, category)
        return entry.id if entry else None

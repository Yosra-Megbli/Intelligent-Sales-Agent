"""
Citation validator for RAG v2.

Parses `[SOURCE n]` mentions in generated text. Any `[SOURCE n]` whose index `n`
is not among the valid injected context indices is stripped.
Returns the sanitized text and the list of stripped indices for auditing.
"""

from __future__ import annotations

import re

_CITATION_PATTERN = re.compile(r"\[SOURCE\s+(\d+)\]", re.IGNORECASE)


def validate_citations(text: str, valid_source_indices: set[int]) -> tuple[str, list[int]]:
    """Validates citations in generated response.
    
    Any [SOURCE n] where n not in valid_source_indices is stripped.
    Returns (cleaned_text, stripped_indices).
    """
    if not text:
        return text, []

    stripped_indices: list[int] = []

    def _replace(match: re.Match) -> str:
        try:
            source_num = int(match.group(1))
        except (ValueError, TypeError):
            return ""

        if source_num in valid_source_indices:
            return match.group(0)

        stripped_indices.append(source_num)
        return ""

    cleaned = _CITATION_PATTERN.sub(_replace, text)
    # Clean up any leftover double spaces
    cleaned = re.sub(r"  +", " ", cleaned).strip()
    return cleaned, stripped_indices

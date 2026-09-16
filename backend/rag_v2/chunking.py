"""
Deterministic chunking - RAG v2 Phase 1 (docs/RAG_BACKLOG.md).

Pure function, no I/O, no network, no LLM: the same input text always
produces the same chunks in the same order. A sliding window over words
(not paragraphs): an earlier paragraph-aware version could lose the tail
of any paragraph much longer than the target size when it flushed and
reset to only the overlap tail, silently dropping content. A plain word
window has no such failure mode - every word in the input appears in at
least one output chunk, always.

No tokenizer dependency: "tokens" here are approximated as
words / 0.75 (roughly matching GPT/Gemini-family tokenization, where one
token is typically ~0.75 English words) rather than pulling in tiktoken
for an MVP where exact token counts don't change correctness - only how
many words end up per chunk. If a future accuracy need justifies it,
swapping in a real tokenizer only changes _approx_words_for_tokens below;
the windowing algorithm itself is tokenizer-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass

_WORDS_PER_TOKEN = 0.75


def _approx_words_for_tokens(tokens: int) -> int:
    return max(1, int(tokens * _WORDS_PER_TOKEN))


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str


def chunk_text(text: str, *, target_tokens: int = 500, overlap_tokens: int = 50) -> list[Chunk]:
    """Split `text` into deterministic, overlapping word-window chunks.

    Each chunk holds up to `target_tokens` (approximated from word count -
    see module docstring); consecutive chunks share `overlap_tokens` of
    trailing/leading words, so a fact split across a chunk boundary is
    still findable from either neighboring chunk. Every word of `text`
    appears in at least one chunk - a chunk boundary can land mid-sentence
    (this is a word window, not a paragraph splitter), which is the
    accepted tradeoff for guaranteeing no content is ever silently
    dropped.
    """
    words = text.split()
    if not words:
        return []

    target_words = _approx_words_for_tokens(target_tokens)
    overlap_words = min(_approx_words_for_tokens(overlap_tokens), target_words - 1)
    step = target_words - overlap_words

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + target_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step

    return [Chunk(index=i, text=c) for i, c in enumerate(chunks)]

"""
Embedding Provider interface - RAG v2 (docs/RAG_BACKLOG.md).

Same abstraction pattern as `ai/providers/interface.py`'s `LLMProvider`:
`rag_v2/ingestion.py` and Phase 2's retrieval talk only to an
`EmbeddingProvider`, never to a vendor SDK directly. Settled decision
(docs/RAG_BACKLOG.md): embeddings via API only - Google AI's
text-embedding-004 by default, Mistral's mistral-embed as the documented
fallback - never a local model (Render free tier is 512MB RAM).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingError(Exception):
    """Base class for every error this package raises. Callers catch this -
    never a vendor-specific exception - so the rest of the system stays
    decoupled from which embedding provider is configured."""


class EmbeddingRateLimitError(EmbeddingError):
    """The provider rejected the call for rate-limit reasons, including
    after retries. Ingestion is expected to back off and retry on this -
    see rag_v2/ingestion.py."""


class EmbeddingAuthenticationError(EmbeddingError):
    """Missing or invalid API key. Never retried."""


class EmbeddingProvider(ABC):
    """Every concrete provider (Google AI, Mistral, ...) implements this
    contract. `embed` is intentionally the only method and always takes a
    batch - even a single text is a one-element list - so a provider
    implementation owns its own batching/rate-limit strategy instead of
    every call site reinventing one."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Output vector width for this provider's model - must match
        domain/models/knowledge_chunk.py's EMBEDDING_DIMENSIONS for
        whichever provider is actually configured."""
        raise NotImplementedError

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, same order as
        `texts`. Must raise an `EmbeddingError` subclass on failure, never
        a vendor SDK exception directly.
        """
        raise NotImplementedError

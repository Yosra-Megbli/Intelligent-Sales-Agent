"""
Google AI embedding provider - RAG v2.

Concrete `EmbeddingProvider` backed by Google AI's text-embedding-004
model (free tier, 768 dimensions - docs/RAG_BACKLOG.md's settled choice).
Same retry-by-exception-name convention as `ai/providers/groq.py`, and the
same optional-dependency pattern: importing this module never fails even
if `google-generativeai` isn't installed, so `pytest tests/` still works
without it - only instantiating `GoogleEmbeddingProvider` (or injecting a
fake `client=`) requires it.

KNOWN FOLLOW-UP, not done here: `google-generativeai` (the package this
module imports) emits a FutureWarning on import as of the version pinned
in requirements.txt - Google has end-of-lifed it in favor of a new unified
`google-genai` package. It still installs and functions today, and every
test in this file runs against a fake client (no network), so nothing here
is blocked by the deprecation. But this module's exact API surface
(`embed_content(model=, content=, task_type=)`) was written against
`google-generativeai`'s documented shape, NOT verified against a live call
in this environment (no network access here, no real API key was ever
pasted into this session - see AGENTS.md/project memory on why that's
deliberate). Before relying on real ingestion in production: run
`python -m rag_v2.ingest` once against a real PDF with a real
GOOGLE_AI_API_KEY and confirm it actually returns 768-dim vectors: if
Google has changed or removed this method, only this file needs to change
- the EmbeddingProvider interface and every caller stay the same. Migrating
to `google-genai` outright is the more future-proof fix and is a small,
isolated change scoped to this one file when someone verifies its API.
"""

from __future__ import annotations

import inspect
import os
import time
from typing import Any, Optional

from ai.providers.embeddings.interface import (
    EmbeddingAuthenticationError,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingRateLimitError,
)

_genai_import_error: Optional[str] = None
try:
    import google.generativeai as genai
except Exception as _exc:  # pragma: no cover - exercised via injected `client=` in tests
    genai = None  # type: ignore[assignment]
    _genai_import_error = f"{type(_exc).__name__}: {_exc}"

DEFAULT_MODEL = "models/gemini-embedding-001"
DIMENSIONS = 768

# Matched by name (not isinstance), same reasoning as groq.py: works
# whether or not the real google-generativeai package is installed, and a
# fake client in tests can raise plain exceptions with these names to get
# the same retry behaviour production would see on a real 429.
_RETRYABLE_ERROR_NAMES = {"ResourceExhausted", "TooManyRequests", "DeadlineExceeded", "ServiceUnavailable"}
_AUTH_ERROR_NAMES = {"PermissionDenied", "Unauthenticated"}

# Google AI's embed_content batch limit as of the free tier - ingestion
# (rag_v2/ingestion.py) chunks its own batches to this size before calling
# embed(), so a single document's chunks never exceed it silently.
MAX_BATCH_SIZE = 100


class GoogleEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        client: Optional[Any] = None,
    ):
        self.model = model or os.getenv("RAG_EMBEDDING_MODEL", DEFAULT_MODEL)
        self.max_retries = max_retries

        if client is not None:
            self._client = client
            return

        api_key = api_key or os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            raise EmbeddingAuthenticationError("GOOGLE_AI_API_KEY is not set")
        if genai is None:
            details = f" ({_genai_import_error})" if _genai_import_error else ""
            raise EmbeddingError(
                f"the 'google-generativeai' package is not installed{details} - run: pip install google-generativeai"
            )
        genai.configure(api_key=api_key)
        self._client = genai

    @property
    def dimensions(self) -> int:
        return DIMENSIONS

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if len(texts) > MAX_BATCH_SIZE:
            raise EmbeddingError(
                f"embed() received {len(texts)} texts, over the {MAX_BATCH_SIZE}-text batch limit - "
                "the caller must chunk its own batches (see rag_v2/ingestion.py)."
            )

        kwargs: dict[str, Any] = {
            "model": self.model,
            "content": texts,
            "task_type": "retrieval_document",
        }
        try:
            sig = inspect.signature(self._client.embed_content)
            if "output_dimensionality" in sig.parameters or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                kwargs["output_dimensionality"] = self.dimensions
        except (ValueError, TypeError):
            pass

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                result = self._client.embed_content(**kwargs)
                return list(result["embedding"])
            except Exception as exc:  # noqa: BLE001 - classified by name below
                error_name = type(exc).__name__

                if error_name in _AUTH_ERROR_NAMES:
                    raise EmbeddingAuthenticationError(str(exc)) from exc

                if error_name in _RETRYABLE_ERROR_NAMES:
                    last_error = exc
                    if attempt < self.max_retries - 1:
                        self._sleep_backoff(attempt)
                    continue

                raise EmbeddingError(str(exc)) from exc

        if isinstance(last_error, Exception) and type(last_error).__name__ in ("ResourceExhausted", "TooManyRequests"):
            raise EmbeddingRateLimitError(str(last_error)) from last_error
        raise EmbeddingError(str(last_error)) from last_error

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(min(2**attempt * 0.5, 8))

"""
Tests for the RAG v2 Google AI embedding adapter.

Uses a fake client (duck-typed: `.embed_content(model=, content=, task_type=)`)
instead of the real `google-generativeai` SDK, so these tests run without
network access and without the package installed - only
`GoogleEmbeddingProvider(client=fake)` needs it, never the module import.
"""

import pytest

from ai.providers.embeddings.google import DIMENSIONS, MAX_BATCH_SIZE, GoogleEmbeddingProvider
from ai.providers.embeddings.interface import (
    EmbeddingAuthenticationError,
    EmbeddingError,
    EmbeddingRateLimitError,
)


class ResourceExhausted(Exception):
    pass


class PermissionDenied(Exception):
    pass


class BadRequest(Exception):
    pass


class FakeClient:
    def __init__(self, *, fail_times=0, error_cls=ResourceExhausted, vectors=None):
        self.calls: list[dict] = []
        self._fail_times = fail_times
        self._error_cls = error_cls
        self._vectors = vectors

    def embed_content(self, *, model, content, task_type):
        self.calls.append({"model": model, "content": content, "task_type": task_type})
        if self._fail_times > 0:
            self._fail_times -= 1
            raise self._error_cls("simulated failure")
        vectors = self._vectors or [[0.1, 0.2, 0.3] for _ in content]
        return {"embedding": vectors}


def test_embed_returns_one_vector_per_text():
    client = FakeClient()
    provider = GoogleEmbeddingProvider(client=client)

    result = provider.embed(["hello", "world"])

    assert len(result) == 2
    assert client.calls[0]["content"] == ["hello", "world"]
    assert client.calls[0]["task_type"] == "retrieval_document"


def test_embed_empty_list_makes_no_call():
    client = FakeClient()
    provider = GoogleEmbeddingProvider(client=client)

    assert provider.embed([]) == []
    assert client.calls == []


def test_dimensions_matches_the_model():
    provider = GoogleEmbeddingProvider(client=FakeClient())
    assert provider.dimensions == DIMENSIONS == 768


def test_embed_retries_transient_error_then_succeeds():
    client = FakeClient(fail_times=1, error_cls=ResourceExhausted)
    provider = GoogleEmbeddingProvider(client=client, max_retries=3)

    result = provider.embed(["hello"])

    assert len(result) == 1
    assert len(client.calls) == 2


def test_embed_raises_rate_limit_error_after_exhausting_retries():
    client = FakeClient(fail_times=10, error_cls=ResourceExhausted)
    provider = GoogleEmbeddingProvider(client=client, max_retries=2)

    with pytest.raises(EmbeddingRateLimitError):
        provider.embed(["hello"])


def test_embed_raises_authentication_error_without_retrying():
    client = FakeClient(fail_times=10, error_cls=PermissionDenied)
    provider = GoogleEmbeddingProvider(client=client, max_retries=3)

    with pytest.raises(EmbeddingAuthenticationError):
        provider.embed(["hello"])

    assert len(client.calls) == 1  # never retried


def test_embed_raises_plain_error_for_non_retryable_failures():
    client = FakeClient(fail_times=10, error_cls=BadRequest)
    provider = GoogleEmbeddingProvider(client=client, max_retries=3)

    with pytest.raises(EmbeddingError):
        provider.embed(["hello"])

    assert len(client.calls) == 1  # not retried, not a known transient error


def test_embed_rejects_a_batch_over_the_limit():
    provider = GoogleEmbeddingProvider(client=FakeClient())

    with pytest.raises(EmbeddingError):
        provider.embed(["x"] * (MAX_BATCH_SIZE + 1))


def test_missing_api_key_raises_authentication_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    with pytest.raises(EmbeddingAuthenticationError):
        GoogleEmbeddingProvider()

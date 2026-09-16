"""
Tests for rag_v2/retrieval.py - Phase 2.

A fake EmbeddingProvider stands in for the real Google/Mistral one - no
network call happens in this file, ever, same discipline as every other
RAG v2 test file. Embeddings here are simple, hand-picked vectors chosen
so cosine similarity is easy to reason about by eye (parallel vectors =
1.0, orthogonal = 0.0, opposite = -1.0), not realistic semantic embeddings.
"""

import uuid

import pytest

from ai.providers.embeddings.interface import EmbeddingProvider
from domain.enums import KnowledgeDocumentStatus
from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument
from rag_v2.retrieval import retrieve


class FakeEmbeddingProvider(EmbeddingProvider):
    """Returns a fixed vector regardless of input text - the test controls
    similarity entirely through the chunk embeddings it seeds, not through
    any real semantic behavior."""

    def __init__(self, query_vector):
        self._query_vector = query_vector
        self.calls: list[str] = []

    @property
    def dimensions(self) -> int:
        return len(self._query_vector)

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.extend(texts)
        return [self._query_vector for _ in texts]


def _make_document(db_session, *, status=KnowledgeDocumentStatus.PUBLISHED, language="fr"):
    document = KnowledgeDocument(
        id=uuid.uuid4(),
        title="Carte tarifaire Flexy",
        source_type="tariff_card",
        filename="flexy.pdf",
        language=language,
        status=status,
        version=1,
    )
    db_session.add(document)
    db_session.flush()
    return document


def _make_chunk(db_session, document, *, content: str, embedding):
    chunk = KnowledgeChunk(
        id=uuid.uuid4(),
        document_id=document.id,
        chunk_index=0,
        content=content,
        embedding=embedding,
    )
    db_session.add(chunk)
    db_session.flush()
    return chunk


def test_empty_query_returns_no_matches(db_session):
    provider = FakeEmbeddingProvider([1.0, 0.0])
    assert retrieve(db_session, "", embedding_provider=provider) == []
    assert retrieve(db_session, None, embedding_provider=provider) == []
    assert provider.calls == []  # never even called embed() for empty input


def test_no_published_documents_returns_no_matches(db_session):
    provider = FakeEmbeddingProvider([1.0, 0.0])
    assert retrieve(db_session, "une question", embedding_provider=provider) == []


def test_parallel_vector_is_a_near_perfect_match(db_session):
    document = _make_document(db_session)
    _make_chunk(db_session, document, content="Les frais fixes sont de 60 euros par an.", embedding=[1.0, 0.0])
    provider = FakeEmbeddingProvider([1.0, 0.0])

    matches = retrieve(db_session, "combien coutent les frais fixes ?", embedding_provider=provider)

    assert len(matches) == 1
    assert matches[0].chunk.content == "Les frais fixes sont de 60 euros par an."
    assert matches[0].similarity == pytest.approx(1.0)


def test_orthogonal_vector_is_excluded_by_the_default_threshold(db_session):
    document = _make_document(db_session)
    _make_chunk(db_session, document, content="Contenu sans rapport.", embedding=[0.0, 1.0])
    provider = FakeEmbeddingProvider([1.0, 0.0])  # orthogonal -> similarity 0.0

    matches = retrieve(db_session, "une question", embedding_provider=provider)

    assert matches == []


def test_min_similarity_can_be_overridden_explicitly(db_session):
    document = _make_document(db_session)
    _make_chunk(db_session, document, content="Contenu partiellement lie.", embedding=[0.6, 0.8])
    provider = FakeEmbeddingProvider([1.0, 0.0])  # similarity = 0.6

    assert retrieve(db_session, "q", embedding_provider=provider, min_similarity=0.9) == []
    matches = retrieve(db_session, "q", embedding_provider=provider, min_similarity=0.5)
    assert len(matches) == 1
    assert matches[0].similarity == pytest.approx(0.6)


def test_draft_documents_chunks_are_never_matched(db_session):
    """Publish-explicit applies to Phase 2 retrieval exactly as it does to
    Phase 1's list_published_chunks - a DRAFT document's chunk must never
    be returned, no matter how similar."""
    draft_document = _make_document(db_session, status=KnowledgeDocumentStatus.DRAFT)
    _make_chunk(db_session, draft_document, content="Reponse en brouillon.", embedding=[1.0, 0.0])
    provider = FakeEmbeddingProvider([1.0, 0.0])

    assert retrieve(db_session, "une question", embedding_provider=provider) == []


def test_archived_documents_chunks_are_never_matched(db_session):
    archived_document = _make_document(db_session, status=KnowledgeDocumentStatus.ARCHIVED)
    _make_chunk(db_session, archived_document, content="Reponse archivee.", embedding=[1.0, 0.0])
    provider = FakeEmbeddingProvider([1.0, 0.0])

    assert retrieve(db_session, "une question", embedding_provider=provider) == []


def test_language_filter_excludes_other_languages(db_session):
    fr_document = _make_document(db_session, language="fr")
    nl_document = _make_document(db_session, language="nl")
    _make_chunk(db_session, fr_document, content="Reponse FR.", embedding=[1.0, 0.0])
    _make_chunk(db_session, nl_document, content="NL antwoord.", embedding=[1.0, 0.0])
    provider = FakeEmbeddingProvider([1.0, 0.0])

    matches = retrieve(db_session, "vraag", embedding_provider=provider, language="nl")

    assert len(matches) == 1
    assert matches[0].chunk.content == "NL antwoord."


def test_results_are_sorted_best_first_and_capped_at_top_k(db_session):
    document = _make_document(db_session)
    _make_chunk(db_session, document, content="Moins pertinent.", embedding=[0.8, 0.6])  # sim 0.8
    _make_chunk(db_session, document, content="Le plus pertinent.", embedding=[1.0, 0.0])  # sim 1.0
    _make_chunk(db_session, document, content="Encore moins.", embedding=[0.6, 0.8])  # sim 0.6
    provider = FakeEmbeddingProvider([1.0, 0.0])

    matches = retrieve(db_session, "q", embedding_provider=provider, top_k=2, min_similarity=0.0)

    assert len(matches) == 2
    assert matches[0].chunk.content == "Le plus pertinent."
    assert matches[1].chunk.content == "Moins pertinent."
    assert matches[0].similarity >= matches[1].similarity


def test_chunks_without_an_embedding_are_skipped_not_crashed_on(db_session):
    document = _make_document(db_session)
    _make_chunk(db_session, document, content="Jamais embedde.", embedding=None)
    _make_chunk(db_session, document, content="Bien embedde.", embedding=[1.0, 0.0])
    provider = FakeEmbeddingProvider([1.0, 0.0])

    matches = retrieve(db_session, "q", embedding_provider=provider)

    assert len(matches) == 1
    assert matches[0].chunk.content == "Bien embedde."


def test_valid_until_filter_excludes_expired_chunks(db_session):
    document = _make_document(db_session)
    # Expired chunk (yesterday)
    _make_chunk(
        db_session,
        document,
        content="Tarif expire hier.",
        embedding=[1.0, 0.0],
    )
    chunk_exp = KnowledgeChunk(
        id=uuid.uuid4(),
        document_id=document.id,
        chunk_index=1,
        content="Autre tarif expire.",
        embedding=[1.0, 0.0],
    )
    chunk_exp.set_metadata({"valid_until": "2020-01-01"})

    chunk_valid = KnowledgeChunk(
        id=uuid.uuid4(),
        document_id=document.id,
        chunk_index=2,
        content="Tarif en vigueur.",
        embedding=[1.0, 0.0],
    )
    chunk_valid.set_metadata({"valid_until": "2099-12-31"})

    db_session.add(chunk_exp)
    db_session.add(chunk_valid)
    db_session.flush()

    provider = FakeEmbeddingProvider([1.0, 0.0])
    matches = retrieve(db_session, "tarifs", embedding_provider=provider)

    contents = [m.chunk.content for m in matches]
    assert "Tarif en vigueur." in contents
    assert "Autre tarif expire." not in contents


def test_citation_validator_strips_fabricated_sources():
    from rag_v2.citations import validate_citations

    text = "Selon [SOURCE 1], les frais sont nuls. En revanche [SOURCE 99] invente des choses."
    cleaned, stripped = validate_citations(text, valid_source_indices={1})

    assert "[SOURCE 1]" in cleaned
    assert "[SOURCE 99]" not in cleaned
    assert stripped == [99]


def test_refusal_messages_match_exact_strings():
    from rag_v2.refusal import get_refusal_message

    fr_refusal = get_refusal_message("fr")
    assert "Je n'ai pas d'information suffisante" in fr_refusal
    assert "un conseiller humain vous répondra très prochainement" in fr_refusal

    nl_refusal = get_refusal_message("nl")
    assert "Ik heb niet voldoende informatie" in nl_refusal
    assert "een menselijke adviseur" in nl_refusal

    en_refusal = get_refusal_message("en")
    assert "I don't have sufficient information" in en_refusal
    assert "a human advisor will get back to you very soon" in en_refusal

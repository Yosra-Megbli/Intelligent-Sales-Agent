"""
Tests for rag_v2/ingestion.py.

A fake EmbeddingProvider stands in for the real Google/Mistral one - no
network call happens in this file, ever, same discipline as
tests/test_llm_provider.py and tests/test_google_embedding_provider.py.
extract_pdf_text is monkeypatched too, so these tests don't depend on a
real PDF fixture or pypdf's exact extraction output - rag_v2/chunking.py
already has its own dedicated, pure tests.
"""

import pytest

from ai.providers.embeddings.interface import EmbeddingProvider
from domain.enums import KnowledgeDocumentStatus
from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument
from rag_v2 import ingestion
from rag_v2.ingestion import IngestionError, ingest_document


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dim: int = 8):
        self._dim = dim
        self.calls: list[list[str]] = []

    @property
    def dimensions(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(len(t))] * self._dim for t in texts]


SAMPLE_TEXT = (
    "Ecofix Flexy est une offre a tarification variable mensuelle.\n\n"
    "Les frais fixes obligatoires sont de 60,00 EUR par an.\n\n"
    "Ecofix Digi est un service optionnel a 5,99 EUR par mois."
)


@pytest.fixture(autouse=True)
def fake_pdf_extraction(monkeypatch):
    monkeypatch.setattr(ingestion, "extract_pdf_text", lambda file_path: SAMPLE_TEXT)
    yield


def test_ingest_document_creates_a_draft_document(db_session):
    provider = FakeEmbeddingProvider()

    result = ingest_document(
        db_session,
        file_path="fake.pdf",
        title="Ecofix Flexy - tarif",
        source_type="tariff_card",
        language="fr",
        embedding_provider=provider,
    )

    assert result.document.status == KnowledgeDocumentStatus.DRAFT
    assert result.document.published_at is None
    assert result.document.filename == "fake.pdf"
    assert result.document.version == 1


def test_ingest_document_creates_one_chunk_row_per_chunk(db_session):
    provider = FakeEmbeddingProvider()

    result = ingest_document(
        db_session,
        file_path="fake.pdf",
        title="Ecofix Flexy - tarif",
        source_type="tariff_card",
        language="fr",
        embedding_provider=provider,
    )

    rows = db_session.query(KnowledgeChunk).filter_by(document_id=result.document.id).all()
    assert len(rows) == result.chunks_created > 0
    assert {r.chunk_index for r in rows} == set(range(result.chunks_created))


def test_ingest_document_stores_the_embedding_and_metadata(db_session):
    provider = FakeEmbeddingProvider(dim=8)

    result = ingest_document(
        db_session,
        file_path="fake.pdf",
        title="Ecofix Flexy - tarif",
        source_type="tariff_card",
        language="nl",
        embedding_provider=provider,
    )

    row = db_session.query(KnowledgeChunk).filter_by(document_id=result.document.id).first()
    assert row.embedding is not None
    assert len(row.embedding) == 8
    assert row.get_metadata() == {"source_type": "tariff_card", "language": "nl"}


def test_ingest_document_batches_embed_calls(db_session, monkeypatch):
    """chunk_text with a tiny target forces many chunks - embed() must be
    called in batches capped at EMBED_BATCH_SIZE, never with everything at
    once."""
    monkeypatch.setattr(ingestion, "EMBED_BATCH_SIZE", 2)
    # chunk_text's default target is ~500 tokens (~375 words) - this needs
    # to comfortably exceed that several times over to force multiple
    # chunks, since ingest_document calls chunk_text with its defaults.
    long_text = "\n\n".join(f"Paragraphe numero {i} avec beaucoup de mots de contenu ici." for i in range(200))
    monkeypatch.setattr(ingestion, "extract_pdf_text", lambda file_path: long_text)
    provider = FakeEmbeddingProvider()

    result = ingest_document(
        db_session,
        file_path="fake.pdf",
        title="Multi-chunk doc",
        source_type="faq",
        language="fr",
        embedding_provider=provider,
        # small target_tokens isn't a parameter of ingest_document itself -
        # chunk_text's defaults (~500 tokens) already split long_text into
        # a handful of chunks; what matters here is that no single embed()
        # call received more than 2 texts.
    )

    assert result.chunks_created > 2
    assert all(len(batch) <= 2 for batch in provider.calls)


def test_ingest_document_raises_when_pdf_extraction_fails(db_session, monkeypatch):
    def boom(file_path):
        raise IngestionError(f"{file_path}: no extractable text (empty PDF or no text layer)")

    monkeypatch.setattr(ingestion, "extract_pdf_text", boom)

    with pytest.raises(IngestionError):
        ingest_document(
            db_session,
            file_path="corrupt.pdf",
            title="x",
            source_type="tariff_card",
            language="fr",
            embedding_provider=FakeEmbeddingProvider(),
        )


def test_clean_text_collapses_whitespace_without_eating_paragraph_breaks():
    dirty = "Ligne  un   avec   espaces.\n\n\n\n\nLigne deux apres trop de sauts."
    cleaned = ingestion.clean_text(dirty)
    assert "  " not in cleaned
    assert "\n\n\n" not in cleaned
    assert "Ligne un avec espaces." in cleaned
    assert "Ligne deux apres trop de sauts." in cleaned

"""
Ingestion pipeline core - RAG v2 Phase 1 (docs/RAG_BACKLOG.md).

extract (PDF via pypdf) -> clean -> chunk (rag_v2.chunking) -> embed (via
an injected EmbeddingProvider, batched to the provider's own limit) ->
persist as one KnowledgeDocument + its KnowledgeChunk rows, always
status=DRAFT (publish-explicit - see KnowledgeDocumentStatus's docstring:
ingesting never publishes; rag_v2/documents.py's publish_document is a
separate, explicit action).

This is the reusable, testable core - rag_v2/ingest.py wraps it in a CLI.
No network call happens unless the caller injects a real
EmbeddingProvider; tests inject a fake one, same discipline as
channels/sms.py's injected send_message.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from ai.providers.embeddings.interface import EmbeddingProvider
from domain.enums import KnowledgeDocumentStatus
from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument
from rag_v2.chunking import chunk_text

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - exercised via extract_pdf_text's own guard
    PdfReader = None  # type: ignore[assignment,misc]

# How many texts get embedded per EmbeddingProvider.embed() call. Kept
# here (not read off the provider) so ingestion works the same way
# regardless of which provider is injected - a provider that needs a
# smaller batch enforces that itself (see GoogleEmbeddingProvider.embed's
# own MAX_BATCH_SIZE guard).
EMBED_BATCH_SIZE = 100


class IngestionError(Exception):
    pass


def extract_pdf_text(file_path: str) -> str:
    if PdfReader is None:
        raise IngestionError("the 'pypdf' package is not installed - run: pip install pypdf")
    reader = PdfReader(file_path)
    pages_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages_text)
    if not text.strip():
        raise IngestionError(f"{file_path}: no extractable text (empty PDF or no text layer)")
    return text


def clean_text(text: str) -> str:
    """Normalize PDF-extraction whitespace artifacts without touching real
    paragraph breaks (double newlines) - repeated spaces/tabs collapse to
    one, three-or-more consecutive newlines collapse to a paragraph break."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@dataclass
class IngestionResult:
    document: KnowledgeDocument
    chunks_created: int


def ingest_document(
    db_session,
    *,
    file_path: str,
    title: str,
    source_type: str,
    language: str,
    embedding_provider: EmbeddingProvider,
    review_date: Optional[date] = None,
) -> IngestionResult:
    """Extract, chunk, embed, and persist one PDF as a DRAFT
    KnowledgeDocument + its KnowledgeChunk rows."""
    raw_text = extract_pdf_text(file_path)
    cleaned = clean_text(raw_text)
    chunks = chunk_text(cleaned)
    if not chunks:
        raise IngestionError(f"{file_path}: produced zero chunks after cleaning")

    document = KnowledgeDocument(
        id=uuid.uuid4(),
        title=title,
        source_type=source_type,
        filename=Path(file_path).name,
        language=language,
        status=KnowledgeDocumentStatus.DRAFT,
        version=1,
        review_date=review_date,
    )
    db_session.add(document)
    db_session.flush()

    chunk_texts = [c.text for c in chunks]
    embeddings: list[list[float]] = []
    for start in range(0, len(chunk_texts), EMBED_BATCH_SIZE):
        batch = chunk_texts[start : start + EMBED_BATCH_SIZE]
        embeddings.extend(embedding_provider.embed(batch))

    metadata = {"source_type": source_type, "language": language}
    for chunk, embedding in zip(chunks, embeddings):
        row = KnowledgeChunk(
            id=uuid.uuid4(),
            document_id=document.id,
            chunk_index=chunk.index,
            content=chunk.text,
            embedding=embedding,
        )
        row.set_metadata(metadata)
        db_session.add(row)

    db_session.commit()
    return IngestionResult(document=document, chunks_created=len(chunks))

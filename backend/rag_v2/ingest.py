#!/usr/bin/env python
"""
RAG v2 ingestion CLI - Phase 1 (docs/RAG_BACKLOG.md).

Thin argument-parsing wrapper around rag_v2/ingestion.py's
ingest_document(): this script owns the DB session, the real
GoogleEmbeddingProvider, and argv - nothing here is unit-tested directly
(see tests/test_rag_v2_ingestion.py instead, which calls ingest_document()
with a fake provider and no network).

A freshly ingested document is always DRAFT (publish-explicit - see
domain/enums.py's KnowledgeDocumentStatus). This script never publishes;
use rag_v2/documents.py's publish_document() as a separate, explicit step.

Usage:
    export GOOGLE_AI_API_KEY=...
    python -m rag_v2.ingest --file knowledge_corpus/tariffs/2026-09/EL_Flexy_2026-09.pdf \\
        --title "Ecofix Flexy - tarif electricite" --source-type tariff_card \\
        --language fr --review-date 2026-10-31
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(backend_dir / ".env")
load_dotenv(backend_dir.parent / ".env")

from ai.providers.embeddings.google import GoogleEmbeddingProvider  # noqa: E402
from database.postgres import SessionLocal  # noqa: E402
from rag_v2.ingestion import IngestionError, ingest_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", required=True, help="Path to the source PDF")
    parser.add_argument("--title", required=True)
    parser.add_argument("--source-type", required=True, help="e.g. tariff_card, terms, faq, regulatory")
    parser.add_argument("--language", required=True, help="2-letter code: fr, nl, en")
    parser.add_argument("--review-date", help="YYYY-MM-DD - when this document should next be reviewed")
    args = parser.parse_args()

    review_date = date.fromisoformat(args.review_date) if args.review_date else None

    db = SessionLocal()
    try:
        provider = GoogleEmbeddingProvider()
        result = ingest_document(
            db,
            file_path=args.file,
            title=args.title,
            source_type=args.source_type,
            language=args.language,
            embedding_provider=provider,
            review_date=review_date,
        )
        doc_filename = result.document.filename
        doc_id = result.document.id
        chunks_created = result.chunks_created
    except IngestionError as exc:
        print(f"::error:: {exc}", file=sys.stderr)
        db.rollback()
        return 1
    finally:
        db.close()

    print(
        f"Ingested {doc_filename} -> document {doc_id} "
        f"({chunks_created} chunks, status=DRAFT). "
        f"Publish it explicitly with rag_v2.documents.publish_document() when reviewed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

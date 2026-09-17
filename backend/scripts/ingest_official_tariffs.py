"""
Batch ingestion and publishing script for all 12 official Sept 2026 Ecofix tariff cards.
Uses real GoogleEmbeddingProvider (gemini-embedding-001 with output_dimensionality=768)
and publishes them to Neon pgvector PostgreSQL database.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

load_dotenv(backend_dir / ".env")
load_dotenv(backend_dir.parent / ".env")

from ai.providers.embeddings.google import GoogleEmbeddingProvider
from database.postgres import SessionLocal
from domain.enums import KnowledgeDocumentStatus
from domain.models.knowledge_document import KnowledgeDocument
from rag_v2.documents import publish_document
from rag_v2.ingestion import ingest_document

TARIFFS_DIR = backend_dir.parent / "knowledge_corpus" / "tariffs" / "2026-09"

TARIFF_DOCUMENTS = [
    {
        "filename": "EL_Ecofix_Flexy_FR.pdf",
        "title": "Ecofix Flexy Électricité (FR)",
        "source_type": "tariff_card",
        "language": "fr",
        "review_date": date(2026, 10, 31),
    },
    {
        "filename": "EL_Ecofix_Flexy_NL.pdf",
        "title": "Ecofix Flexy Elektriciteit (NL)",
        "source_type": "tariff_card",
        "language": "nl",
        "review_date": date(2026, 10, 31),
    },
    {
        "filename": "EL_Ecofix_Flexy_Online_FR.pdf",
        "title": "Ecofix Flexy Online Électricité (FR)",
        "source_type": "tariff_card",
        "language": "fr",
        "review_date": date(2026, 10, 31),
    },
    {
        "filename": "EL_Ecofix_Flexy_Online_NL.pdf",
        "title": "Ecofix Flexy Online Elektriciteit (NL)",
        "source_type": "tariff_card",
        "language": "nl",
        "review_date": date(2026, 10, 31),
    },
    {
        "filename": "EL_Ecofix_Motion_FR.pdf",
        "title": "Ecofix Motion Électricité Dynamique (FR)",
        "source_type": "tariff_card",
        "language": "fr",
        "review_date": date(2026, 10, 31),
    },
    {
        "filename": "EL_Ecofix_Motion_NL.pdf",
        "title": "Ecofix Motion Elektriciteit Dynamisch (NL)",
        "source_type": "tariff_card",
        "language": "nl",
        "review_date": date(2026, 10, 31),
    },
    {
        "filename": "EL_Ecofix_Motion_Online_FR.pdf",
        "title": "Ecofix Motion Online Électricité (FR)",
        "source_type": "tariff_card",
        "language": "fr",
        "review_date": date(2026, 10, 31),
    },
    {
        "filename": "EL_Ecofix_Motion_Online_NL.pdf",
        "title": "Ecofix Motion Online Elektriciteit (NL)",
        "source_type": "tariff_card",
        "language": "nl",
        "review_date": date(2026, 10, 31),
    },
    {
        "filename": "GAS_Ecofix_Flexy_FR.pdf",
        "title": "Ecofix Flexy Gaz (FR)",
        "source_type": "tariff_card",
        "language": "fr",
        "review_date": date(2026, 10, 31),
    },
    {
        "filename": "GAS_Ecofix_Flexy_NL.pdf",
        "title": "Ecofix Flexy Gas (NL)",
        "source_type": "tariff_card",
        "language": "nl",
        "review_date": date(2026, 10, 31),
    },
    {
        "filename": "GAS_Ecofix_Flexy_Online_FR.pdf",
        "title": "Ecofix Flexy Online Gaz (FR)",
        "source_type": "tariff_card",
        "language": "fr",
        "review_date": date(2026, 10, 31),
    },
    {
        "filename": "GAS_Ecofix_Flexy_Online_NL.pdf",
        "title": "Ecofix Flexy Online Gas (NL)",
        "source_type": "tariff_card",
        "language": "nl",
        "review_date": date(2026, 10, 31),
    },
]


def run_ingestion() -> None:
    db = SessionLocal()
    try:
        provider = GoogleEmbeddingProvider()
        print("Starting batch ingestion of official Ecofix tariffs...")

        for item in TARIFF_DOCUMENTS:
            pdf_path = TARIFFS_DIR / item["filename"]
            if not pdf_path.exists():
                print(f"[WARN] File not found: {pdf_path}")
                continue

            existing = (
                db.query(KnowledgeDocument)
                .filter(KnowledgeDocument.filename == item["filename"])
                .first()
            )

            if existing:
                print(f"[EXISTS] {item['filename']} (ID: {existing.id}, Status: {existing.status.value})")
                doc = existing
            else:
                print(f"[INGESTING] {item['filename']}...")
                result = ingest_document(
                    db,
                    file_path=str(pdf_path),
                    title=item["title"],
                    source_type=item["source_type"],
                    language=item["language"],
                    embedding_provider=provider,
                    review_date=item["review_date"],
                )
                doc = result.document
                print(f"   -> Chunks: {result.chunks_created}")

            if doc.status != KnowledgeDocumentStatus.PUBLISHED:
                publish_document(db, doc.id)
                print(f"[PUBLISHED] {item['filename']} -> PUBLISHED")
            else:
                print(f"[OK] Already PUBLISHED: {item['filename']}")

        print("\nAll official tariffs processed successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    run_ingestion()

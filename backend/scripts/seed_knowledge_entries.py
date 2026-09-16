#!/usr/bin/env python
"""
One-time, idempotent seed: backend/ai/knowledge_base.yaml -> knowledge_entries
table (Sprint 4b). Running this twice must never create duplicate rows.

Usage (PowerShell, from backend/, venv activated):
    python scripts\\seed_knowledge_entries.py

Idempotency: each YAML entry's own string `id` (e.g. "switching_fees") is
turned into a DETERMINISTIC UUID via uuid.uuid5() - the same YAML id always
produces the same primary key, so re-running is a plain "insert if this id
doesn't exist yet" per row, never a duplicate.

This script does NOT run automatically at boot (unlike
database/migration_runner.py's SQL migrations) - it's a one-time data
migration, not schema. Run it once after applying migration 0012.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

import yaml  # noqa: E402

from database.postgres import SessionLocal  # noqa: E402
from crm.knowledge_repository import KnowledgeRepository  # noqa: E402
from domain.models.knowledge_entry import KnowledgeEntry  # noqa: E402

_SEED_NAMESPACE = uuid.UUID("6f6a1e3a-2b8b-4b0e-9f0d-8f7a6c5d4e3b")
_KNOWLEDGE_BASE_PATH = backend_dir / "ai" / "knowledge_base.yaml"


def deterministic_id(yaml_entry_id: str) -> uuid.UUID:
    return uuid.uuid5(_SEED_NAMESPACE, f"knowledge_base_yaml:{yaml_entry_id}")


def seed(db_session) -> tuple[int, int]:
    """Returns (created, skipped). Builds each KnowledgeEntry row directly
    with its deterministic id (rather than KnowledgeRepository.create(),
    which always assigns a fresh uuid4()) - mutating .id on an
    already-flushed row to "fix up" the primary key afterwards would be a
    fragile UPDATE-the-PK operation, not a clean insert."""
    with open(_KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    repo = KnowledgeRepository(db_session)
    created = 0
    skipped = 0
    for item in raw["entries"]:
        entry_id = deterministic_id(item["id"])
        if repo.get_by_id(entry_id) is not None:
            skipped += 1
            continue
        entry = KnowledgeEntry(
            id=entry_id,
            category=item["category"],
            question=item["id"].replace("_", " ").capitalize(),
            answer_fr=item["answer"].strip(),
            active=True,
        )
        entry.set_keywords(list(item["keywords"]))
        db_session.add(entry)
        db_session.flush()
        created += 1

    db_session.commit()
    return created, skipped


def main() -> int:
    db = SessionLocal()
    try:
        created, skipped = seed(db)
    finally:
        db.close()
    print(f"Seeded knowledge_entries: {created} created, {skipped} already present (skipped).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

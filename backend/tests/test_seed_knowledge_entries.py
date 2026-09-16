"""
Tests for scripts/seed_knowledge_entries.py - must be idempotent (running
twice creates zero duplicates).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from crm.knowledge_repository import KnowledgeRepository
from seed_knowledge_entries import seed


def test_seed_creates_one_row_per_yaml_entry(db_session):
    created, skipped = seed(db_session)

    assert created == 12  # backend/ai/knowledge_base.yaml currently has 12 entries
    assert skipped == 0
    assert KnowledgeRepository(db_session).count() == 12


def test_seed_is_idempotent(db_session):
    seed(db_session)
    created_second_run, skipped_second_run = seed(db_session)

    assert created_second_run == 0
    assert skipped_second_run == 12
    assert KnowledgeRepository(db_session).count() == 12


def test_seeded_entries_have_the_same_keywords_as_the_yaml(db_session):
    seed(db_session)

    entries, _ = KnowledgeRepository(db_session).list_all()
    switching_fees = next(e for e in entries if "gratuit" in e.get_keywords())
    assert "frais" in switching_fees.get_keywords()
    assert switching_fees.category == "faq"
    assert switching_fees.active is True

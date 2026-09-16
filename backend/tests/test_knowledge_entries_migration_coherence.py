"""
Migration/model coherence check for 0012_knowledge_entries.sql - same
pattern as tests/test_rag_v2_migration_coherence.py, same reason:
Base.metadata.create_all() on SQLite is what tests actually run against,
migration_runner.py skips SQL on any non-postgresql dialect, and nothing
else in this repo verifies the ORM model and the .sql file agree.
"""

from pathlib import Path

from domain.models.knowledge_entry import KnowledgeEntry

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "database" / "migrations" / "0012_knowledge_entries.sql"


def _migration_sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8").lower()


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file(), f"expected {MIGRATION_PATH} to exist"


def test_every_column_appears_in_the_migration():
    sql = _migration_sql()
    for column in KnowledgeEntry.__table__.columns:
        assert column.name.lower() in sql, (
            f"KnowledgeEntry.{column.name} is not mentioned in {MIGRATION_PATH.name} - "
            "model and migration have drifted."
        )


def test_migration_creates_the_table():
    assert "create table if not exists knowledge_entries" in _migration_sql()


def test_migration_number_does_not_collide_with_rag_v2():
    """0011 is already used by RAG v2's
    0011_knowledge_documents_and_chunks.sql (merged first) - this table
    must be 0012, not a second 0011."""
    migrations_dir = MIGRATION_PATH.parent
    zero_zero_one_ones = list(migrations_dir.glob("0011_*.sql"))
    assert len(zero_zero_one_ones) == 1, f"expected exactly one 0011_*.sql, found: {zero_zero_one_ones}"
    assert MIGRATION_PATH.name.startswith("0012_")

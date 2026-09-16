"""
Migration/model coherence check for 0011_knowledge_documents_and_chunks.sql
- the trap AGENTS.md documents: tests build the schema with
Base.metadata.create_all() on SQLite, migration_runner.py skips SQL
entirely on any non-postgresql dialect, and nothing else in this repo
verifies the SQLAlchemy model and the .sql migration actually agree. A
full read-back against a live PostgreSQL+pgvector instance isn't possible
in this test environment (no Postgres service here, unlike Redis) - this
is the next best thing: every column the ORM model declares must appear,
by name, in the migration file that is what production actually runs.

Not a substitute for actually running the migration against a real Neon
database once - this only catches "renamed a column in one place and
forgot the other," not e.g. a wrong SQL type or index definition.
"""

from pathlib import Path

from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1] / "database" / "migrations" / "0011_knowledge_documents_and_chunks.sql"
)


def _migration_sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8").lower()


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file(), f"expected {MIGRATION_PATH} to exist"


def test_every_knowledge_document_column_appears_in_the_migration():
    sql = _migration_sql()
    for column in KnowledgeDocument.__table__.columns:
        assert column.name.lower() in sql, (
            f"KnowledgeDocument.{column.name} is not mentioned in {MIGRATION_PATH.name} - "
            "model and migration have drifted."
        )


def test_every_knowledge_chunk_column_appears_in_the_migration():
    sql = _migration_sql()
    for column in KnowledgeChunk.__table__.columns:
        assert column.name.lower() in sql, (
            f"KnowledgeChunk.{column.name} is not mentioned in {MIGRATION_PATH.name} - "
            "model and migration have drifted."
        )


def test_migration_creates_both_tables():
    sql = _migration_sql()
    assert "create table if not exists knowledge_documents" in sql
    assert "create table if not exists knowledge_chunks" in sql


def test_migration_enables_the_pgvector_extension():
    assert "create extension if not exists vector" in _migration_sql()


def test_migration_creates_an_hnsw_index_on_the_embedding_column():
    sql = _migration_sql()
    assert "using hnsw" in sql
    assert "vector_cosine_ops" in sql


def test_embedding_column_width_matches_the_model_constant():
    """domain/models/knowledge_chunk.py's EMBEDDING_DIMENSIONS (768,
    text-embedding-004's output width) must match the migration's
    `vector(768)` column width - these are two independent hardcoded
    numbers with nothing to keep them in sync automatically."""
    from domain.models.knowledge_chunk import EMBEDDING_DIMENSIONS

    assert f"vector({EMBEDDING_DIMENSIONS})" in _migration_sql()

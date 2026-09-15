from pathlib import Path
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from database.migration_runner import (
    MIGRATIONS_DIR,
    run_migrations,
    ensure_migrations_table,
    get_applied_migrations,
)
from database.postgres import normalize_database_url


def test_normalize_database_url():
    # Neon/Render style postgres://
    assert normalize_database_url("postgres://user:pass@ep-xyz.neon.tech/db") == (
        "postgresql+psycopg2://user:pass@ep-xyz.neon.tech/db"
    )
    # Generic postgresql://
    assert normalize_database_url("postgresql://user:pass@ep-xyz.neon.tech/db?sslmode=require") == (
        "postgresql+psycopg2://user:pass@ep-xyz.neon.tech/db?sslmode=require"
    )
    # Already explicit psycopg2
    assert normalize_database_url("postgresql+psycopg2://user:pass@localhost:5432/db") == (
        "postgresql+psycopg2://user:pass@localhost:5432/db"
    )
    # Non-postgres urls unchanged
    assert normalize_database_url("sqlite:///:memory:") == "sqlite:///:memory:"


def test_migration_runner_skips_non_postgresql():
    sqlite_engine = create_engine("sqlite:///:memory:")
    result = run_migrations(sqlite_engine)
    assert result == []
    sqlite_engine.dispose()


def test_migration_files_exist_and_sorted():
    assert MIGRATIONS_DIR.is_dir()
    files = sorted([f.name for f in MIGRATIONS_DIR.glob("*.sql")])
    assert len(files) >= 4
    assert files[0].startswith("0001_")
    assert files[1].startswith("0002_")
    assert files[2].startswith("0003_")
    assert files[3].startswith("0004_")


def test_migration_runner_executes_unapplied_idempotently(monkeypatch):
    applied_in_db = set()
    executed_sqls = []

    mock_cursor = MagicMock()

    def fake_execute(sql, params=None):
        if "INSERT INTO schema_migrations" in sql:
            applied_in_db.add(params[0])
        else:
            executed_sqls.append(sql)

    mock_cursor.execute = fake_execute

    mock_raw_conn = MagicMock()
    mock_raw_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    mock_engine.raw_connection.return_value = mock_raw_conn

    # Mock ensure_migrations_table and get_applied_migrations
    monkeypatch.setattr("database.migration_runner.ensure_migrations_table", lambda eng: None)
    monkeypatch.setattr("database.migration_runner.get_applied_migrations", lambda eng: set(applied_in_db))

    # First run: should apply all files
    applied_first_run = run_migrations(mock_engine)
    assert len(applied_first_run) == len(list(MIGRATIONS_DIR.glob("*.sql")))
    assert "0001_add_telegram_chat_id.sql" in applied_first_run
    assert "0004_date_of_birth_as_string.sql" in applied_first_run
    assert len(applied_in_db) == len(applied_first_run)

    # Second run: should be completely idempotent (0 applied)
    applied_second_run = run_migrations(mock_engine)
    assert applied_second_run == []

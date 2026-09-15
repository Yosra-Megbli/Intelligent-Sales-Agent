"""
Idempotent Database Migration Runner.

Automatically discovers and executes all SQL migration files in
`backend/database/migrations/` in alphabetical order on application boot.

Tracks applied migrations in a `schema_migrations` table so that each
migration is executed exactly once, replacing manual psql commands.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def ensure_migrations_table(engine: Engine) -> None:
    """Create the schema_migrations tracking table if it does not exist."""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(255) PRIMARY KEY,
        applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
    with engine.begin() as conn:
        conn.execute(text(create_table_sql))


def get_applied_migrations(engine: Engine) -> set[str]:
    """Retrieve the set of already applied migration filenames."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version FROM schema_migrations;"))
        return {row[0] for row in result}


def run_migrations(engine: Optional[Engine] = None) -> List[str]:
    """Discover and execute all unapplied SQL migrations in alphabetical order.

    Returns the list of migration filenames applied during this invocation.
    Safe to call multiple times (strictly idempotent).
    """
    if engine is None:
        from database.postgres import engine as default_engine
        engine = default_engine

    # SQLite (used in memory for unit tests) does not support Postgres-specific
    # dialect syntax (such as DO $$ ... $$, VARCHAR casts, or PostgreSQL functions).
    # Unit tests rely on Base.metadata.create_all() which already creates the full schema.
    if engine.dialect.name != "postgresql":
        logger.info("Skipping SQL migrations runner: dialect is '%s' (not postgresql).", engine.dialect.name)
        return []

    if not MIGRATIONS_DIR.is_dir():
        logger.warning("Migrations directory '%s' not found.", MIGRATIONS_DIR)
        return []

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        logger.info("No migration files found in '%s'.", MIGRATIONS_DIR)
        return []

    ensure_migrations_table(engine)
    applied = get_applied_migrations(engine)

    newly_applied: List[str] = []

    # Use raw_connection to execute complete SQL scripts (including PL/pgSQL DO blocks) safely
    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cursor:
            for sql_file in migration_files:
                filename = sql_file.name
                if filename in applied:
                    continue

                logger.info("Applying database migration: %s", filename)
                sql_content = sql_file.read_text(encoding="utf-8")
                
                cursor.execute(sql_content)
                cursor.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s);",
                    (filename,),
                )
                raw_conn.commit()
                newly_applied.append(filename)
                logger.info("Successfully applied database migration: %s", filename)
    except Exception as exc:
        raw_conn.rollback()
        logger.exception("Migration failed on file '%s': %s", filename, exc)
        raise
    finally:
        raw_conn.close()

    return newly_applied


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    from database.postgres import engine
    print(f"Connecting to database to check and run migrations...")
    try:
        applied = run_migrations(engine)
        if applied:
            print(f"Successfully applied {len(applied)} migration(s): {', '.join(applied)}")
        else:
            print("Database is up to date. No pending migrations.")
    except Exception as e:
        print(f"Error running migrations: {e}")
        raise SystemExit(1)

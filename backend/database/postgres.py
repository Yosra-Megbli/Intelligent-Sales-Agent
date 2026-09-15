"""
PostgreSQL connection layer.

PostgreSQL is used from day one (not SQLite) because the project needs
relational queries and reporting across Leads, Conversations, Messages,
Activities and Campaigns from the start.
"""

import os
import uuid
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import CHAR, create_engine
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

load_dotenv()


def normalize_database_url(url: str) -> str:
    """Normalize DATABASE_URL for SQLAlchemy and psycopg2.

    Safely strips any leading/trailing spaces or quotes that operators might paste,
    and ensures 'postgresql+psycopg2://' is used so SQLAlchemy loads the psycopg2 driver.
    """
    if not url:
        return url
    url = url.strip().strip('"').strip("'")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


DATABASE_URL = normalize_database_url(
    os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://ecofix:ecofix@localhost:5432/ecofix_sophie",
    )
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


class GUID(TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's native UUID type in production, and a CHAR(36) column
    everywhere else (e.g. SQLite in unit tests), so the exact same models can
    be exercised in fast in-memory tests without needing a real Postgres
    instance for every test run.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a request-scoped SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for use outside of FastAPI (scripts, scheduler jobs, tests)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. In production this is supplemented by migration_runner."""
    from domain import models  # noqa: F401  (ensures models are registered on Base)

    Base.metadata.create_all(bind=engine)

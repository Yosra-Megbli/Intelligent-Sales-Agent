"""
Document obsolescence management - RAG v2 Phase 3 (ZEN W3 pattern).

In a regulated energy market, tariffs and contract terms expire on fixed schedules
(e.g. monthly tariff cards, annual regulatory reviews). Unchecked obsolescence leads
to hallucinated prices.

This module provides:
1. `review_due_documents`: flags published documents coming up for review (within N days, default 7).
2. `auto_archive_expired`: auto-archives published documents past their grace period
   (review_date < today - grace_days, default 30 days via RAG_GRACE_PERIOD_DAYS).
   Withdrawing from retrieval is immediate and idempotent.
3. `detect_version_conflict`: warns when multiple published documents share the same
   (source_type, language, product). Archiving remains manual.
4. CLI: `python -m rag_v2.obsolescence --run` suitable for cron jobs.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
import os
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select

from domain.enums import KnowledgeDocumentStatus
from domain.models.knowledge_chunk import KnowledgeChunk
from domain.models.knowledge_document import KnowledgeDocument
from rag_v2.documents import archive_document

logger = logging.getLogger(__name__)

RAG_GRACE_PERIOD_DAYS_DEFAULT = 30


def _grace_period_days() -> int:
    return int(os.getenv("RAG_GRACE_PERIOD_DAYS", RAG_GRACE_PERIOD_DAYS_DEFAULT))


def review_due_documents(
    db_session, *, within_days: int = 7, reference_date: Optional[date] = None
) -> list[KnowledgeDocument]:
    """Returns published documents whose review_date is due on or before
    reference_date + within_days (default: today + 7 days)."""
    today = reference_date or date.today()
    cutoff = today + timedelta(days=within_days)

    stmt = (
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.status == KnowledgeDocumentStatus.PUBLISHED,
            KnowledgeDocument.review_date.isnot(None),
            KnowledgeDocument.review_date <= cutoff,
        )
        .order_by(KnowledgeDocument.review_date.asc())
    )
    return list(db_session.scalars(stmt).all())


def auto_archive_expired(
    db_session, *, grace_days: Optional[int] = None, reference_date: Optional[date] = None
) -> list[KnowledgeDocument]:
    """Auto-archives published documents past their review_date + grace_period.
    
    Idempotent: once ARCHIVED, they are excluded from this query and from retrieval.
    """
    days = grace_days if grace_days is not None else _grace_period_days()
    today = reference_date or date.today()
    cutoff = today - timedelta(days=days)

    stmt = select(KnowledgeDocument).where(
        KnowledgeDocument.status == KnowledgeDocumentStatus.PUBLISHED,
        KnowledgeDocument.review_date.isnot(None),
        KnowledgeDocument.review_date < cutoff,
    )
    expired_docs = list(db_session.scalars(stmt).all())

    archived: list[KnowledgeDocument] = []
    for doc in expired_docs:
        logger.info(
            "Auto-archiving expired document %s (%s, review_date=%s, grace_days=%d)",
            doc.id,
            doc.title,
            doc.review_date,
            days,
        )
        archive_document(db_session, doc.id)
        archived.append(doc)

    return archived


def detect_version_conflict(db_session, *, product_key: str) -> list[dict[str, Any]]:
    """Detects version conflicts among published documents for a given product key.
    
    A conflict occurs when more than one PUBLISHED document shares the same
    (source_type, language) and contains chunks associated with `product_key`.
    Returns list of conflict warning dicts. Archiving remains manual.
    """
    stmt = (
        select(KnowledgeDocument, KnowledgeChunk)
        .join(KnowledgeChunk, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(KnowledgeDocument.status == KnowledgeDocumentStatus.PUBLISHED)
    )
    rows = db_session.execute(stmt).all()

    matching_docs: dict[UUID, KnowledgeDocument] = {}
    for doc, chunk in rows:
        meta = chunk.get_metadata()
        if meta.get("product") == product_key:
            matching_docs[doc.id] = doc

    if len(matching_docs) <= 1:
        return []

    # Group by (source_type, language)
    groups: dict[tuple[str, str], list[KnowledgeDocument]] = {}
    for doc in matching_docs.values():
        key = (doc.source_type, doc.language)
        groups.setdefault(key, []).append(doc)

    conflicts: list[dict[str, Any]] = []
    for (source_type, lang), docs in groups.items():
        if len(docs) > 1:
            conflicts.append({
                "product": product_key,
                "source_type": source_type,
                "language": lang,
                "conflicting_documents": [
                    {
                        "id": str(d.id),
                        "title": d.title,
                        "version": d.version,
                        "review_date": d.review_date.isoformat() if d.review_date else None,
                        "published_at": d.published_at.isoformat() if d.published_at else None,
                    }
                    for d in docs
                ],
                "message": (
                    f"Multiple published versions exist for product '{product_key}' "
                    f"({source_type}, {lang}). Review and archive older versions."
                ),
            })
    return conflicts


def get_obsolescence_status(db_session, *, reference_date: Optional[date] = None) -> dict[str, Any]:
    """Feeds the admin alert card with due soon, overdue, and conflict info."""
    today = reference_date or date.today()

    stmt_all_published = select(KnowledgeDocument).where(
        KnowledgeDocument.status == KnowledgeDocumentStatus.PUBLISHED,
        KnowledgeDocument.review_date.isnot(None),
    )
    published_with_review = list(db_session.scalars(stmt_all_published).all())

    due_soon = []
    overdue = []

    for doc in published_with_review:
        rev: date = doc.review_date
        diff = (rev - today).days
        doc_dict = {
            "id": str(doc.id),
            "title": doc.title,
            "version": doc.version,
            "language": doc.language,
            "source_type": doc.source_type,
            "review_date": rev.isoformat(),
        }
        if diff < 0:
            doc_dict["days_overdue"] = abs(diff)
            overdue.append(doc_dict)
        elif diff <= 7:
            doc_dict["days_until_due"] = diff
            due_soon.append(doc_dict)

    # Count archived docs (past review or archived)
    stmt_archived = select(KnowledgeDocument).where(
        KnowledgeDocument.status == KnowledgeDocumentStatus.ARCHIVED
    )
    archived_count = len(list(db_session.scalars(stmt_archived).all()))

    return {
        "due_soon": due_soon,
        "overdue": overdue,
        "archived_count": archived_count,
    }


def run_obsolescence_cycle(
    db_session, *, grace_days: Optional[int] = None, reference_date: Optional[date] = None
) -> dict[str, Any]:
    """Runs a complete obsolescence cycle: auto-archives expired documents and returns summary."""
    archived = auto_archive_expired(db_session, grace_days=grace_days, reference_date=reference_date)
    status = get_obsolescence_status(db_session, reference_date=reference_date)
    return {
        "archived_now_count": len(archived),
        "archived_now_ids": [str(d.id) for d in archived],
        "due_soon_count": len(status["due_soon"]),
        "overdue_count": len(status["overdue"]),
    }


if __name__ == "__main__":
    import argparse
    from database.postgres import session_scope

    parser = argparse.ArgumentParser(description="Run RAG v2 obsolescence cycle")
    parser.add_argument("--run", action="store_true", help="Execute auto-archive for expired documents")
    parser.add_argument("--grace-days", type=int, default=None, help="Override grace period in days")
    args = parser.parse_args()

    if args.run:
        with session_scope() as db:
            result = run_obsolescence_cycle(db, grace_days=args.grace_days)
            print(
                f"RAG v2 Obsolescence cycle complete: "
                f"{result['archived_now_count']} documents auto-archived, "
                f"{result['overdue_count']} overdue, "
                f"{result['due_soon_count']} review due soon."
            )

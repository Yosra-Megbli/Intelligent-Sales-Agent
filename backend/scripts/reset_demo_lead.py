"""
DEV/DEMO ONLY — never part of production workflows.

Reset & inspection utility for testing/demos of the Sophie sales agent.
Given a phone, email, or chat_id (or in --list mode), this script can:
  1. Inspect all leads and their Telegram chat_ids / statuses (--list).
  2. Clear:
     - opt_out_at (removes opt-out block)
     - rejection_reason (clears REQUEST_HUMAN_ONLY or other rejection)
     - dedup keys (dedup_email, dedup_phone) so re-qualification / duplicate checks pass
     - chat-level suppression (resets conversation.current_state from CLOSED to START,
       clears previous_state, detour counts, and extraction failure counts)
     - Redis cached conversation context (if Redis is accessible)
  3. Set lead status = LeadStatus.NEW.

Usage:
  # List all leads and their Telegram chat IDs (read-only):
  python scripts/reset_demo_lead.py --list

  # Reset by Telegram chat ID:
  python scripts/reset_demo_lead.py --chat-id 123456789

  # Reset by email or phone (searches lead PII, dedup keys, and message history):
  python scripts/reset_demo_lead.py --email prospect@example.com
  python scripts/reset_demo_lead.py --phone 0477123456

  # Target remote Neon database explicitly:
  python scripts/reset_demo_lead.py --list --db-url "postgresql+psycopg2://..."
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from domain.enums import ConversationState, LeadStatus
from domain.models.conversation import Conversation
from domain.models.lead import Lead
from domain.models.message import Message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reset_demo_lead")


def list_demo_leads(db: Session) -> list[dict[str, Any]]:
    """List all leads and their linked conversations for inspection.

    DEV/DEMO ONLY — read-only.
    """
    leads = db.query(Lead).order_by(Lead.created_at.desc()).all()
    records = []
    for l in leads:
        conv_info = []
        for c in l.conversations:
            conv_info.append({
                "conversation_id": str(c.id),
                "channel": c.channel.value if hasattr(c.channel, "value") else str(c.channel),
                "external_id": c.external_id,
                "current_state": c.current_state.value if hasattr(c.current_state, "value") else str(c.current_state),
                "message_count": len(c.messages),
                "last_message_at": str(c.last_message_at) if c.last_message_at else None,
            })
        records.append({
            "lead_id": str(l.id),
            "source": l.source.value if hasattr(l.source, "value") else str(l.source),
            "status": l.status.value if hasattr(l.status, "value") else str(l.status),
            "rejection_reason": l.rejection_reason.value if hasattr(l.rejection_reason, "value") and l.rejection_reason else None,
            "opt_out_at": str(l.opt_out_at) if l.opt_out_at else None,
            "email": l.email,
            "phone": l.phone,
            "dedup_email": l.dedup_email,
            "dedup_phone": l.dedup_phone,
            "telegram_chat_id": l.telegram_chat_id,
            "first_name": l.first_name,
            "last_name": l.last_name,
            "created_at": str(l.created_at) if l.created_at else None,
            "conversations": conv_info,
        })
    return records


def reset_demo_lead(
    db: Session,
    *,
    chat_id: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    redis_client: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """Reset one or more matching demo leads and their conversations back to NEW/START.

    DEV/DEMO ONLY — never part of production workflows.

    Tables and columns touched:
      - leads:
          status -> LeadStatus.NEW
          opt_out_at -> None
          rejection_reason -> None
          dedup_email -> None
          dedup_phone -> None
          change_intent -> None
          qualification_score -> None
          qualified_at -> None
          next_follow_up_date -> None
          follow_up_attempts -> 0
          follow_up_category -> None
      - conversations:
          current_state -> ConversationState.START
          previous_state -> None
          consecutive_detour_count -> 0
          consecutive_extraction_failures -> 0
      - Redis cache:
          deletes key 'conversation:context:{conversation_id}'

    Returns a list of summary dicts for each lead reset.
    Raises ValueError if no matching lead is found.
    """
    if not chat_id and not email and not phone:
        raise ValueError("At least one of chat_id, email, or phone must be provided.")

    matching_leads: list[Lead] = []

    # 1. Search by chat_id (checks Lead.telegram_chat_id and Conversation.external_id)
    if chat_id:
        cid_str = str(chat_id).strip()
        leads_by_chat = db.query(Lead).filter(Lead.telegram_chat_id == cid_str).all()
        for l in leads_by_chat:
            if l not in matching_leads:
                matching_leads.append(l)

        convs_by_ext = db.query(Conversation).filter(Conversation.external_id == cid_str).all()
        for c in convs_by_ext:
            if c.lead and c.lead not in matching_leads:
                matching_leads.append(c.lead)

    # 2. Search by email (checks Lead.email and Lead.dedup_email)
    if email:
        raw_email = email.strip()
        norm_email = raw_email.lower()
        leads_by_email = (
            db.query(Lead)
            .filter((Lead.email == raw_email) | (Lead.dedup_email == norm_email))
            .all()
        )
        for l in leads_by_email:
            if l not in matching_leads:
                matching_leads.append(l)

        # Fallback for GDPR-purged leads: search messages exchanged for this email
        if not matching_leads:
            messages_with_email = (
                db.query(Message)
                .filter(Message.content.ilike(f"%{raw_email}%"))
                .all()
            )
            for m in messages_with_email:
                if m.conversation and m.conversation.lead and m.conversation.lead not in matching_leads:
                    matching_leads.append(m.conversation.lead)

    # 3. Search by phone (checks Lead.phone and Lead.dedup_phone)
    if phone:
        raw_phone = phone.strip()
        leads_by_phone = (
            db.query(Lead)
            .filter((Lead.phone == raw_phone) | (Lead.dedup_phone == raw_phone))
            .all()
        )
        for l in leads_by_phone:
            if l not in matching_leads:
                matching_leads.append(l)

        # Fallback for GDPR-purged leads: search messages exchanged for this phone
        if not matching_leads:
            messages_with_phone = (
                db.query(Message)
                .filter(Message.content.ilike(f"%{raw_phone}%"))
                .all()
            )
            for m in messages_with_phone:
                if m.conversation and m.conversation.lead and m.conversation.lead not in matching_leads:
                    matching_leads.append(m.conversation.lead)

    if not matching_leads:
        ident = chat_id or email or phone
        raise ValueError(
            f"No lead found matching identifier: {ident!r}.\n"
            f"NOTE: When STOP is sent on Telegram, GDPR purges email/phone from the lead row.\n"
            f"Use 'python scripts/reset_demo_lead.py --list' to find the exact Telegram chat_id,\n"
            f"then run 'python scripts/reset_demo_lead.py --chat-id <CHAT_ID>'."
        )

    # Initialize Redis client if not supplied
    if redis_client is None:
        try:
            from database.redis import get_redis
            redis_client = get_redis()
        except Exception as err:
            logger.warning("Redis client unavailable; cache purge will be skipped (%s)", err)
            redis_client = None

    results = []

    for lead in matching_leads:
        old_status = lead.status
        old_opt_out = lead.opt_out_at
        old_rejection = lead.rejection_reason
        old_dedup_email = lead.dedup_email
        old_dedup_phone = lead.dedup_phone

        # Reset lead lifecycle and GDPR suppression
        lead.status = LeadStatus.NEW
        lead.opt_out_at = None
        lead.rejection_reason = None
        lead.dedup_email = None
        lead.dedup_phone = None

        # Reset qualification and follow-up data
        lead.change_intent = None
        lead.qualification_score = None
        lead.qualified_at = None
        lead.next_follow_up_date = None
        lead.follow_up_attempts = 0
        lead.follow_up_category = None

        # Reset conversations linked to this lead
        conv_ids_reset: list[str] = []
        redis_purged = 0

        # Query all conversations for this lead
        convs = db.query(Conversation).filter(Conversation.lead_id == lead.id).all()
        for conv in convs:
            conv.current_state = ConversationState.START
            conv.previous_state = None
            conv.consecutive_detour_count = 0
            conv.consecutive_extraction_failures = 0
            conv_ids_reset.append(str(conv.id))

            # Evict conversation context from Redis cache
            if redis_client:
                try:
                    cache_key = f"conversation:context:{conv.id}"
                    redis_client.delete(cache_key)
                    redis_purged += 1
                except Exception as ex:
                    logger.warning("Failed to delete Redis key for conv %s: %s", conv.id, ex)

        db.flush()

        results.append({
            "lead_id": str(lead.id),
            "old_status": old_status.value if hasattr(old_status, "value") else str(old_status),
            "new_status": lead.status.value,
            "old_opt_out_at": str(old_opt_out) if old_opt_out else None,
            "new_opt_out_at": None,
            "old_rejection_reason": old_rejection.value if hasattr(old_rejection, "value") and old_rejection else None,
            "new_rejection_reason": None,
            "old_dedup_email": old_dedup_email,
            "old_dedup_phone": old_dedup_phone,
            "conversations_reset": conv_ids_reset,
            "redis_purged_count": redis_purged,
        })

    db.commit()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DEV/DEMO ONLY: Reset or inspect opted-out / suppressed leads and conversations."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List all leads and their chat IDs (read-only inspection)")
    group.add_argument("--chat-id", help="Telegram chat ID / external ID to reset")
    group.add_argument("--email", help="Prospect email address to reset")
    group.add_argument("--phone", help="Prospect phone number to reset")

    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL"),
        help="Custom PostgreSQL DATABASE_URL (defaults to DATABASE_URL env var)",
    )

    args = parser.parse_args()

    db_url = args.db_url
    if not db_url:
        sys.exit("ERROR: DATABASE_URL is not set. Provide --db-url or set DATABASE_URL in .env.")

    from database.postgres import normalize_database_url
    norm_url = normalize_database_url(db_url)
    engine = create_engine(norm_url, pool_pre_ping=True)
    SessionMaker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionMaker()

    try:
        if args.list:
            leads = list_demo_leads(session)
            print("=" * 80)
            print(f"DEV/DEMO ONLY: All Leads in Database ({len(leads)} lead(s) found)")
            print("=" * 80)
            for idx, l in enumerate(leads, 1):
                print(f"Lead #{idx}: {l['lead_id']}")
                print(f"  Source            : {l['source']}")
                print(f"  Status            : {l['status']}")
                print(f"  Opt-out at        : {l['opt_out_at'] or 'None'}")
                print(f"  Rejection reason  : {l['rejection_reason'] or 'None'}")
                print(f"  Name (PII)        : {l['first_name'] or 'None'} {l['last_name'] or 'None'}")
                print(f"  Email (PII)       : {l['email'] or 'None'}")
                print(f"  Phone (PII)       : {l['phone'] or 'None'}")
                print(f"  Dedup Email       : {l['dedup_email'] or 'None'}")
                print(f"  Dedup Phone       : {l['dedup_phone'] or 'None'}")
                print(f"  Telegram Chat ID  : {l['telegram_chat_id'] or 'None'}")
                print(f"  Created at        : {l['created_at']}")
                print(f"  Conversations ({len(l['conversations'])}):")
                for c in l['conversations']:
                    print(f"    - [{c['channel']}] id={c['conversation_id']} | chat_id/external_id={c['external_id']!r} | state={c['current_state']} | msgs={c['message_count']}")
                print("-" * 80)
            print("\n[INFO] RESET GUIDE:")
            print("   When STOP is sent, GDPR purges email/phone from the lead row.")
            print("   To reset a lead so you can re-test /start on Telegram, run:")
            print("   python scripts/reset_demo_lead.py --chat-id <CHAT_ID>")
            print("=" * 80)
            return

        results = reset_demo_lead(
            session,
            chat_id=args.chat_id,
            email=args.email,
            phone=args.phone,
        )
        print("=" * 60)
        print("DEV/DEMO ONLY: Lead Reset Summary")
        print("=" * 60)
        for r in results:
            print(f"Lead ID              : {r['lead_id']}")
            print(f"Status               : {r['old_status']} -> {r['new_status']}")
            print(f"opt_out_at           : {r['old_opt_out_at']} -> {r['new_opt_out_at']}")
            print(f"rejection_reason     : {r['old_rejection_reason']} -> {r['new_rejection_reason']}")
            print(f"dedup keys cleared   : dedup_email={r['old_dedup_email']!r}, dedup_phone={r['old_dedup_phone']!r}")
            print(f"Conversations reset  : {len(r['conversations_reset'])} conversation(s) -> START")
            for cid in r['conversations_reset']:
                print(f"  - Conversation ID  : {cid}")
            print(f"Redis cache keys purged : {r['redis_purged_count']}")
        print("=" * 60)
        print("SUCCESS: Reset complete. You can now send /start on Telegram!")
    except Exception as err:
        logger.error("Operation failed: %s", err)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()

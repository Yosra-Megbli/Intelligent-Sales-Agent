"""
Follow-up Scheduler.

The entrypoint a real scheduler (cron, Celery beat, APScheduler - whichever
the deployment picks; this module deliberately doesn't depend on any of
them) calls periodically, e.g. every hour. It runs one full cycle:

1. Mark conversations that have gone silent as WAITING_CUSTOMER
   (FollowUpEngine.mark_silent_conversations_as_waiting).
2. Send every follow-up that's now due
   (FollowUpEngine.send_due_follow_ups), delivering each one through
   `deliver` - a plain callable keyed by the conversation, so this module
   doesn't need to know about Telegram/Web/WhatsApp specifics (same
   separation as outbound/sender.py not knowing how TelegramBotAPISender
   works).

Not wired into an actual cron/Celery schedule here - that's a deployment
decision, not something this sandbox can exercise (no persistent process to
schedule against). Call `run_followup_cycle(db_session, ...)` from whatever
mechanism the deployment picks.
"""

from __future__ import annotations

from typing import Callable, Optional

from application.conversation_service import ConversationService
from domain.models.conversation import Conversation
from followup.engine import FollowUpEngine, FollowUpResult


def run_followup_cycle(
    db_session,
    provider=None,
    deliver: Optional[Callable[[Conversation, str], None]] = None,
) -> list[FollowUpResult]:
    """Runs one silence-detection + due-follow-up cycle. Returns the list of
    `FollowUpResult`s so a caller that doesn't pass `deliver` can inspect or
    dispatch them itself (e.g. for a dry-run / preview mode).
    """
    service = ConversationService(db_session, provider=provider)
    engine = FollowUpEngine(db_session, service=service)

    engine.mark_silent_conversations_as_waiting()
    results = engine.send_due_follow_ups()

    if deliver:
        for result in results:
            if result.response_text:
                deliver(result.conversation, result.response_text)

    return results

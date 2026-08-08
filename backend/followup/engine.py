"""
Follow-up Engine.

Two jobs, both pure decision-making (never sends anything itself - that's
`followup/scheduler.py` + a channel's send function, mirroring the
Campaign Engine / Outbound Sender split from Phase 5):

1. `mark_silent_conversations_as_waiting()` - find conversations with no
   reply for longer than `silence_threshold_hours` that aren't already
   finished, move them to `ConversationState.WAITING_CUSTOMER` (remembering
   what they were doing so they can resume exactly there), and schedule the
   Lead's `next_follow_up_date`.
2. `send_due_follow_ups()` - for every Lead whose `next_follow_up_date` has
   passed (`LeadRepository.list_due_for_follow_up`, built in Phase 1), either
   send a follow-up (via `ConversationService.send_follow_up`, which runs the
   normal engine/responder pipeline) and reschedule the next attempt, or -
   past `max_follow_up_attempts` - give up: close the conversation and stop.

Reads `business_rules/followup_rules.yaml` (declarative only, same
discipline as every other business_rules file).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml

from application.conversation_service import ConversationService
from crm.activity_repository import ActivityRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ActivityType, ConversationState, FollowUpCategory, LeadStatus
from domain.models.conversation import Conversation
from domain.models.lead import Lead

_RULES_DIR = Path(__file__).resolve().parent.parent / "business_rules"


def _load_yaml(filename: str) -> dict:
    with open(_RULES_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


_FOLLOWUP_CONFIG = _load_yaml("followup_rules.yaml")
SILENCE_THRESHOLD_HOURS: int = _FOLLOWUP_CONFIG["silence_threshold_hours"]
FOLLOW_UP_DELAY_DAYS: int = _FOLLOWUP_CONFIG["follow_up_delay_days"]
MAX_FOLLOW_UP_ATTEMPTS: int = _FOLLOWUP_CONFIG["max_follow_up_attempts"]

# States a conversation can be silently sitting in and still be a candidate
# for follow-up. Anything not listed here is either already WAITING_CUSTOMER
# (nothing to do) or terminal (QUALIFIED/HANDOFF/REJECTED/CLOSED all resolve
# to CLOSED on their very next turn regardless of event - see
# state_machine.py - so following up on them would be meaningless).
_SILENCE_CANDIDATE_STATES = frozenset(
    {
        ConversationState.GREETING,
        ConversationState.DISCOVERY,
        ConversationState.INTENT_CONFIRMATION,
        ConversationState.COLLECT_CUSTOMER_TYPE,
        ConversationState.COLLECT_LOCATION,
        ConversationState.COLLECT_SUPPLIER,
        ConversationState.COLLECT_CONTACT,
        ConversationState.COLLECT_EAN,
        ConversationState.DATA_VALIDATION,
        ConversationState.FAQ,
        ConversationState.OBJECTION,
    }
)


def _category_for_attempt(attempt_number: int) -> FollowUpCategory:
    """First follow-up = HOT (still fresh), then WARM, then COLD for any
    further attempts - purely a labeling convention for the sales team's
    dashboard, not something the engine itself acts on differently."""
    if attempt_number <= 0:
        return FollowUpCategory.HOT
    if attempt_number == 1:
        return FollowUpCategory.WARM
    return FollowUpCategory.COLD


@dataclass
class FollowUpResult:
    lead: Lead
    conversation: Conversation
    response_text: Optional[str]
    gave_up: bool = False


class FollowUpEngine:
    def __init__(self, db_session, service: Optional[ConversationService] = None):
        self.db = db_session
        self.service = service if service is not None else ConversationService(db_session)
        self.lead_repo = LeadRepository(db_session)
        self.conversation_repo = ConversationRepository(db_session)
        self.activity_repo = ActivityRepository(db_session)

    def mark_silent_conversations_as_waiting(self, as_of: Optional[datetime] = None) -> list[Conversation]:
        as_of = as_of or datetime.utcnow()
        cutoff = as_of - timedelta(hours=SILENCE_THRESHOLD_HOURS)

        silent = self.conversation_repo.list_silent_since(cutoff, _SILENCE_CANDIDATE_STATES)
        marked: list[Conversation] = []
        for conversation in silent:
            lead = self.lead_repo.get_by_id(conversation.lead_id)
            if lead is None:
                continue

            previous_state = conversation.current_state
            self.conversation_repo.transition_state(
                conversation, ConversationState.WAITING_CUSTOMER, remember_previous=True
            )
            self.lead_repo.schedule_follow_up(
                lead,
                as_of + timedelta(days=FOLLOW_UP_DELAY_DAYS),
                _category_for_attempt(lead.follow_up_attempts or 0),
            )
            self.activity_repo.log(
                lead.id,
                ActivityType.STATE_CHANGED,
                details=f"{previous_state.value} -> WAITING_CUSTOMER (silence)",
            )
            marked.append(conversation)
        return marked

    def send_due_follow_ups(self, as_of: Optional[datetime] = None) -> list[FollowUpResult]:
        as_of = as_of or datetime.utcnow()
        due_leads = self.lead_repo.list_due_for_follow_up(as_of=as_of)

        results: list[FollowUpResult] = []
        for lead in due_leads:
            conversation = self.conversation_repo.get_latest_for_lead(lead.id)
            if conversation is None or conversation.current_state != ConversationState.WAITING_CUSTOMER:
                # Nothing to follow up on - e.g. the customer already replied
                # through another path and the conversation moved on.
                continue

            if (lead.follow_up_attempts or 0) >= MAX_FOLLOW_UP_ATTEMPTS:
                results.append(self._give_up(lead, conversation))
                continue

            response = self.service.send_follow_up(conversation.id)
            # F-015 fix: count the attempt only now, right when a message
            # actually goes out - not when merely scheduling a date (see
            # LeadRepository.schedule_follow_up's docstring). The category
            # below intentionally uses the *post*-increment count: it labels
            # the *next* attempt that this scheduling is setting up, exactly
            # like mark_silent_conversations_as_waiting() does for the very
            # first one (category_for_attempt(0) before anything is sent).
            self.lead_repo.increment_follow_up_attempts(lead)
            self.lead_repo.schedule_follow_up(
                lead,
                as_of + timedelta(days=FOLLOW_UP_DELAY_DAYS),
                _category_for_attempt(lead.follow_up_attempts),
            )
            self.activity_repo.log(lead.id, ActivityType.FOLLOW_UP_SENT)
            results.append(
                FollowUpResult(lead=lead, conversation=conversation, response_text=response.response_text)
            )
        return results

    def _give_up(self, lead: Lead, conversation: Conversation) -> FollowUpResult:
        self.conversation_repo.transition_state(conversation, ConversationState.CLOSED)
        self.lead_repo.update_fields(lead, next_follow_up_date=None, follow_up_category=FollowUpCategory.STOPPED)
        self.lead_repo.set_status(lead, LeadStatus.CLOSED)
        self.activity_repo.log(lead.id, ActivityType.STATUS_CHANGED, details="Gave up after max follow-up attempts")
        return FollowUpResult(lead=lead, conversation=conversation, response_text=None, gave_up=True)

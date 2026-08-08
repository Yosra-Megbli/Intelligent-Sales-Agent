"""
Conversation Engine.

This is the orchestrator described in the architecture docs:

    Memory Loader -> Business Rules / State Machine -> CRM update -> (Phase 3: Response Generator)

It ties together `memory.py` (context loading), `state_machine.py` (pure
decision), the repositories (persistence) and `ActivityRepository` (audit
trail). It never imports an LLM client and never generates natural language
- `process_turn()` returns a structured `EngineResult` that Phase 3's
`ai/responder.py` will turn into an actual sentence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from conversation_engine import state_machine
from conversation_engine.intent_classifier import IntentClassifier
from conversation_engine.memory import ConversationMemory
from conversation_engine.transitions import DETOUR_STATES, Event, NO_STATE_CHANGE_STATES
from crm.activity_repository import ActivityRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ActivityType, ConversationState, LeadStatus


@dataclass
class EngineResult:
    previous_state: ConversationState
    next_state: ConversationState
    required_action: Optional[str]
    rejection_reason: Optional[str] = None


# ConversationState values that also drive a LeadStatus update, since reaching
# them means something happened in the sales journey, not just the dialogue.
_CONVERSATION_STATE_TO_LEAD_STATUS = {
    ConversationState.QUALIFIED: LeadStatus.QUALIFIED,
    ConversationState.REJECTED: LeadStatus.REJECTED,
    ConversationState.HANDOFF: LeadStatus.APPOINTMENT,
    ConversationState.CLOSED: LeadStatus.CLOSED,
}


class ConversationEngine:
    def __init__(self, db_session, provider=None):
        self.db = db_session
        self.memory = ConversationMemory(db_session)
        self.lead_repo = LeadRepository(db_session)
        self.conversation_repo = ConversationRepository(db_session)
        self.activity_repo = ActivityRepository(db_session)
        # Phase 3C's LLM-backed disambiguation only ever fires if this
        # classifier actually has a provider - without one it behaves
        # exactly like the Phase 2 passthrough (see intent_classifier.py).
        self.intent_classifier = IntentClassifier(provider)

    def process_turn(self, conversation_id: UUID, event: Event) -> EngineResult:
        context = self.memory.load(conversation_id)
        lead = context.lead
        conversation = context.conversation
        current_state = conversation.current_state

        # Apply any entities the (future) extractor attached to this event
        # directly onto the lead. This is data assignment, not a decision:
        # the state machine / rules engine still decides what happens next.
        for field_name, value in event.entities.items():
            if hasattr(lead, field_name):
                setattr(lead, field_name, value)
        if event.entities:
            self.db.flush()

        # F-003 fix: LeadRepository.find_duplicate() existed but was never
        # called anywhere in the live flow, so a lead could always be
        # qualified twice under the same email/phone. Only looked up right
        # when it's about to matter (DATA_VALIDATION) - every other turn
        # skips the query entirely. exclude_lead_id is required here: by
        # this point the lead being validated already has its own
        # email/phone saved, so without excluding its own id it would
        # "match" itself and get rejected as a duplicate of itself.
        is_duplicate = False
        if current_state == ConversationState.DATA_VALIDATION:
            is_duplicate = (
                self.lead_repo.find_duplicate(lead.email, lead.phone, exclude_lead_id=lead.id) is not None
            )

        decision = state_machine.decide(
            current_state,
            event,
            lead,
            conversation,
            intent_classifier=self.intent_classifier,
            is_duplicate=is_duplicate,
        )

        if decision.resume_previous:
            self.conversation_repo.resume_previous_state(conversation)
            next_state = conversation.current_state
        else:
            self.conversation_repo.transition_state(
                conversation,
                decision.next_state,
                remember_previous=decision.remember_previous,
            )
            next_state = decision.next_state

        # Dialogue Policy bookkeeping: entering a detour counts towards the
        # "consecutive detours" threshold; any other real transition resets
        # it (resuming alone does not - only genuine forward progress does).
        if decision.remember_previous:
            self.conversation_repo.increment_detour_count(conversation)
        elif not decision.resume_previous:
            self.conversation_repo.reset_detour_count(conversation)

        self._sync_lead_status(lead, next_state, decision.rejection_reason)
        self._log_activity(lead, current_state, next_state)
        self.memory.save_last_question(conversation.id, decision.required_action)

        return EngineResult(
            previous_state=current_state,
            next_state=next_state,
            required_action=decision.required_action,
            rejection_reason=decision.rejection_reason.value if decision.rejection_reason else None,
        )

    def _sync_lead_status(self, lead, next_state, rejection_reason) -> None:
        new_status = _CONVERSATION_STATE_TO_LEAD_STATUS.get(next_state)
        if new_status is None:
            # Still inside qualification -> reflect that on the CRM lifecycle too.
            if next_state in state_machine.QUALIFICATION_STATES + (ConversationState.DATA_VALIDATION,):
                new_status = LeadStatus.QUALIFICATION
            elif next_state == ConversationState.INTENT_CONFIRMATION:
                new_status = LeadStatus.ENGAGED
        if new_status is not None and lead.status != new_status:
            self.lead_repo.set_status(lead, new_status, rejection_reason=rejection_reason)

    def _log_activity(self, lead, previous_state, next_state) -> None:
        if previous_state == next_state:
            return
        self.activity_repo.log(
            lead.id,
            ActivityType.STATE_CHANGED,
            details=f"{previous_state.value} -> {next_state.value}",
        )
        if next_state == ConversationState.QUALIFIED:
            self.activity_repo.log(lead.id, ActivityType.QUALIFIED)
        if next_state == ConversationState.REJECTED:
            self.activity_repo.log(lead.id, ActivityType.REJECTED)
        if next_state == ConversationState.HANDOFF:
            self.activity_repo.log(lead.id, ActivityType.HUMAN_HANDOFF)

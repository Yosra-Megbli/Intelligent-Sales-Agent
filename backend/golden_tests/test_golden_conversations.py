"""
Golden dataset - full multi-turn conversation wiring tests.

Replays each scenario in golden_tests/scenarios/conversations.yaml through
the real ConversationEngine (state_machine + rules + dialogue_policy +
repositories), turn by turn, with a ScriptedProvider standing in for the
LLM (see harness.py - always returns the scenario's own `expected` label,
so this suite tests engine/business-logic wiring given correct extraction,
never the LLM's actual judgement on the French text).

Every turn's resulting ConversationState (and, where specified,
required_action) is asserted - not just the final state - so a bug that
corrupts an intermediate step (wrong field re-asked, a detour that resumes
to the wrong place, a rejection that doesn't stick) fails at the turn where
it actually happens, with that turn's `notes` visible in the failure.
"""

from __future__ import annotations

import pytest

from conversation_engine.engine import ConversationEngine
from conversation_engine.transitions import Event, EventType
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel, ConversationState, LeadSource

from golden_tests.harness import (
    ScriptedProvider,
    load_conversation_scenarios,
    scripted_payload_for_turn,
)

_SCENARIOS = load_conversation_scenarios()


def _new_conversation(db_session):
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE)
    conversation = ConversationRepository(db_session).create(lead_id=lead.id, channel=ConversationChannel.WEB)
    db_session.commit()
    return lead, conversation


def _apply_setup(db_session, setup: dict):
    if "existing_lead" in setup:
        existing = setup["existing_lead"]
        LeadRepository(db_session).create(source=LeadSource.WEBSITE, email=existing["email"], phone=existing["phone"])
        db_session.commit()


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=[s.id for s in _SCENARIOS])
def test_full_conversation(db_session, scenario):
    _apply_setup(db_session, scenario.setup)
    lead, conversation = _new_conversation(db_session)

    # One scripted payload per turn that actually goes through extraction;
    # system_event turns construct their Event directly and never touch
    # the provider, so they contribute no payload here.
    payloads = [scripted_payload_for_turn(turn) for turn in scenario.turns if turn.input is not None]
    provider = ScriptedProvider(payloads)
    # No provider passed to the engine itself: IntentClassifier(None) is a
    # pure passthrough (see intent_classifier.py), so a scenario's scripted
    # extraction is never second-guessed. That's intentional here - this
    # suite assumes correct extraction and tests what happens downstream of
    # it; LLM-backed disambiguation of an *ambiguous* real message is
    # exactly the real-LLM-eval concern, exercised separately via
    # harness.evaluate_message_scenarios_with_provider (run_real_llm_eval.py).
    engine = ConversationEngine(db_session)

    for i, turn in enumerate(scenario.turns):
        if turn.system_event is not None:
            event = Event(type=EventType(turn.system_event))
        else:
            # Mirrors application/conversation_service.py's
            # _extract_event(): run the (scripted) Extractor, exactly as
            # production does, so IntentClassifier's normalization is
            # exercised the same way in both real and test code paths.
            from ai.extractor import Extractor

            event = Extractor(provider).extract(turn.input)

        result = engine.process_turn(conversation.id, event)

        context = f"{scenario.id} turn {i} ({turn.input or turn.system_event}): {turn.notes}"
        assert result.next_state == ConversationState(turn.expected_state_after), context
        if turn.expected_action_after is not None:
            assert result.required_action == turn.expected_action_after, context

"""
Golden dataset - message-level wiring tests.

Runs entirely with a ScriptedProvider (no network, no real LLM): what's
under test here is that (a) the golden dataset itself is well-formed, and
(b) Extractor's own parsing/normalization (ai/extractor.py) doesn't drop or
mangle entities a *correct* LLM output would contain (regression-proofs the
JSON parsing / entity whitelist / customer_type lowercasing / EAN-phone
space-stripping logic against real-shaped scenario data, instead of only
the handful of synthetic payloads in tests/test_extractor.py).

This suite can NEVER catch the LLM misclassifying "combien coûte ?" as an
OBJECTION - by construction, the provider is told the right answer. That
question belongs to run_real_llm_eval.py.
"""

from __future__ import annotations

import pytest

from ai.extractor import Extractor
from domain.enums import ConversationState

from golden_tests.harness import (
    ScriptedProvider,
    load_message_scenarios,
    scripted_payload_for_message,
)

_SCENARIOS = load_message_scenarios()
_VALID_EVENT_TYPES = {
    "PROVIDE_INFORMATION",
    "QUESTION",
    "OBJECTION",
    "CHANGE_INTENT_YES",
    "CHANGE_INTENT_NO",
    "REQUEST_HUMAN",
    "CUSTOMER_MESSAGE",
}
_VALID_ENTITY_KEYS = {
    "customer_type",
    "region",
    "city",
    "current_supplier",
    "first_name",
    "last_name",
    "email",
    "phone",
    "ean",
}


def test_dataset_has_meaningful_coverage():
    assert len(_SCENARIOS) >= 30, "Golden dataset should have at least 30 scenarios (per audit recommendation)."
    ids = [s.id for s in _SCENARIOS]
    assert len(ids) == len(set(ids)), "Scenario ids must be unique."
    categories = {s.category for s in _SCENARIOS}
    assert len(categories) >= 8, "Scenarios should span many risk categories, not cluster in one."


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=[s.id for s in _SCENARIOS])
def test_scenario_is_well_formed(scenario):
    assert scenario.expected_event_type in _VALID_EVENT_TYPES, scenario.id
    assert set(scenario.expected_entities) <= _VALID_ENTITY_KEYS, scenario.id
    if scenario.current_state:
        # Raises ValueError if not a real ConversationState - fails loudly.
        ConversationState(scenario.current_state)


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=[s.id for s in _SCENARIOS])
def test_extractor_preserves_a_correct_llm_output(scenario):
    """If the LLM had produced exactly the golden label, does Extractor's
    own parsing hand it through unchanged? Catches normalization bugs
    (e.g. a future change to _ENTITY_KEYS or customer_type lowercasing that
    would silently start dropping real fields)."""
    payload = scripted_payload_for_message(scenario)
    provider = ScriptedProvider([payload])
    extractor = Extractor(provider)

    event = extractor.extract(scenario.input, expected_field=scenario.expected_field)

    assert event.type.value == scenario.expected_event_type, scenario.id
    assert event.entities == scenario.expected_entities, scenario.id
    assert event.raw_answer_text == scenario.input, scenario.id

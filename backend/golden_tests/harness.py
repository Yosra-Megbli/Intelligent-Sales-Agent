"""
Golden Dataset harness.

Loads golden_tests/scenarios/*.yaml and provides two independent ways to run
them, matching the audit's recommendation to keep deterministic regression
tests and real-LLM evaluation completely separate:

  - ScriptedProvider + build_message_scenarios/build_conversation_scenarios:
    used by test_golden_messages.py / test_golden_conversations.py (pytest,
    always runs, no network). The provider is scripted to return each
    scenario's `expected` output verbatim, so what's actually under test is
    the deterministic pipeline downstream of extraction (entity
    normalization, IntentClassifier passthrough, State Machine, Rules
    Engine, Dialogue Policy) - never the LLM's judgement.

  - evaluate_message_scenarios_with_provider: used by run_real_llm_eval.py
    (a standalone script, never collected by pytest) to send the real
    customer text to a real LLMProvider and diff its actual output against
    `expected`. THIS is the layer that can tell you whether the LLM
    actually understands a French customer - a golden dataset run against
    a ScriptedProvider never can, by construction.

Nothing in this module talks to a database - conversation-level engine
wiring lives in test_golden_conversations.py, which is the one place that
needs `db_session` (reuses the same sqlite-in-memory pattern as
tests/test_conversation_engine.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from ai.providers.interface import LLMProvider, LLMResponse

_SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass
class MessageScenario:
    id: str
    category: str
    input: str
    expected_field: Optional[str]
    expected_event_type: str
    expected_entities: dict[str, Any]
    current_state: Optional[str] = None
    notes: str = ""


@dataclass
class ConversationTurn:
    expected_event_type: str
    expected_entities: dict[str, Any]
    expected_state_after: str
    input: Optional[str] = None
    system_event: Optional[str] = None
    expected_action_after: Optional[str] = None
    notes: str = ""

    def __post_init__(self):
        if (self.input is None) == (self.system_event is None):
            raise ValueError("A turn needs exactly one of `input` or `system_event`")


@dataclass
class ConversationScenario:
    id: str
    category: str
    description: str
    turns: list[ConversationTurn]
    setup: dict[str, Any] = field(default_factory=dict)


def _load_yaml(name: str) -> dict:
    with open(_SCENARIOS_DIR / name, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_message_scenarios() -> list[MessageScenario]:
    raw = _load_yaml("messages.yaml")
    scenarios = []
    for item in raw["scenarios"]:
        expected = item["expected"]
        scenarios.append(
            MessageScenario(
                id=item["id"],
                category=item["category"],
                input=item["input"],
                expected_field=item.get("expected_field"),
                expected_event_type=expected["event_type"],
                expected_entities=expected.get("entities", {}) or {},
                current_state=item.get("current_state"),
                notes=item.get("notes", ""),
            )
        )
    return scenarios


def load_conversation_scenarios() -> list[ConversationScenario]:
    raw = _load_yaml("conversations.yaml")
    scenarios = []
    for item in raw["scenarios"]:
        turns = [
            ConversationTurn(
                input=turn.get("input"),
                system_event=turn.get("system_event"),
                expected_event_type=turn["expected_event_type"],
                expected_entities=turn.get("expected_entities", {}) or {},
                expected_state_after=turn["expected_state_after"],
                expected_action_after=turn.get("expected_action_after"),
                notes=turn.get("notes", ""),
            )
            for turn in item["turns"]
        ]
        scenarios.append(
            ConversationScenario(
                id=item["id"],
                category=item["category"],
                description=item.get("description", ""),
                turns=turns,
                setup=item.get("setup", {}) or {},
            )
        )
    return scenarios


# --------------------------------------------------------------------------
# Fake-mode: scripted provider (wiring regression, no network, no LLM judgement)
# --------------------------------------------------------------------------


class ScriptedProvider(LLMProvider):
    """Returns a fixed sequence of pre-baked JSON responses, one per call -
    exactly what a golden scenario's `expected` says the LLM *should* have
    returned. Used to test everything downstream of extraction, never the
    extraction/classification judgement itself.
    """

    def __init__(self, payloads: list[dict]):
        self._payloads = list(payloads)
        self._index = 0
        self.calls: list[dict] = []

    def generate(self, messages, *, temperature=0.0, max_tokens=1024, json_mode=False):
        self.calls.append({"messages": messages, "json_mode": json_mode})
        if self._index >= len(self._payloads):
            raise AssertionError(
                f"ScriptedProvider exhausted after {len(self._payloads)} calls - "
                "scenario made an unexpected extra LLM call."
            )
        payload = self._payloads[self._index]
        self._index += 1
        return LLMResponse(content=json.dumps(payload), model="scripted")


def scripted_payload_for_message(scenario: MessageScenario) -> dict:
    return {"event_type": scenario.expected_event_type, "entities": scenario.expected_entities}


def scripted_payload_for_turn(turn: ConversationTurn) -> dict:
    return {"event_type": turn.expected_event_type, "entities": turn.expected_entities}


# --------------------------------------------------------------------------
# Real-LLM mode: diff actual extraction against the golden label
# --------------------------------------------------------------------------


@dataclass
class MessageEvalResult:
    scenario: MessageScenario
    actual_event_type: str
    actual_entities: dict[str, Any]
    event_type_correct: bool
    entities_correct: bool

    @property
    def passed(self) -> bool:
        return self.event_type_correct and self.entities_correct


def evaluate_message_scenarios_with_provider(
    scenarios: list[MessageScenario], provider: LLMProvider
) -> list[MessageEvalResult]:
    """Runs each scenario's real customer text through the real Extractor
    (+ IntentClassifier, for scenarios that set `current_state` to exercise
    the disambiguation second pass) and diffs against the golden label.
    """
    # Local imports: this module is imported by conftest-free scripts too,
    # and importing ai/conversation_engine eagerly at module load time would
    # make golden_tests fail to import in contexts that only need the YAML
    # (e.g. a schema-only smoke test) without the rest of the backend on
    # the path yet.
    from ai.extractor import Extractor
    from conversation_engine.intent_classifier import IntentClassifier
    from domain.enums import ConversationState

    extractor = Extractor(provider)
    classifier = IntentClassifier(provider)

    results = []
    for scenario in scenarios:
        event = extractor.extract(scenario.input, expected_field=scenario.expected_field)
        if scenario.current_state:
            event = classifier.classify(event, current_state=ConversationState(scenario.current_state))

        event_type_correct = event.type.value == scenario.expected_event_type
        entities_correct = event.entities == scenario.expected_entities
        results.append(
            MessageEvalResult(
                scenario=scenario,
                actual_event_type=event.type.value,
                actual_entities=event.entities,
                event_type_correct=event_type_correct,
                entities_correct=entities_correct,
            )
        )
    return results


def summarize(results: list[MessageEvalResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        bucket = by_category.setdefault(r.scenario.category, {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += int(r.passed)
    return {
        "total": total,
        "passed": passed,
        "accuracy": (passed / total) if total else 0.0,
        "by_category": by_category,
    }

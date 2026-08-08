"""
Extractor.

Phase 3B: turns one raw customer message into a Phase 2 `Event` (see
conversation_engine/transitions.py) by asking an `LLMProvider` for
structured JSON. This is the only place in the system where free text is
read - everything downstream (IntentClassifier, StateMachine, Rules Engine)
only ever sees the fixed `EventType` vocabulary and a plain entities dict.

PURITY GUARANTEE (same discipline as conversation_engine/rules.py): this
module never imports a repository, never calls `.flush()`/`.commit()`, and
never decides a Lead's status, qualification score, or Conversation's
current_state. It extracts *signals from text* and hands them to the
engine as an `Event` - what happens with that Event is entirely the
Business Rules Engine / State Machine's call.

"Prompts never contain business logic" (MASTER_ARCHITECTURE.md, rule 3): the
prompt (loaded from prompts/extractor/system.md via ai/prompt_loader.py -
never hardcoded in this file) only ever states the fixed EventType/entity
*vocabulary* (domain/enums.py) - never coverage regions, validation
formats, field collection order, or rejection reasons. Those live
exclusively in business_rules/*.yaml and conversation_engine/rules.py. If
the model invents a value outside that vocabulary, it is discarded here,
never trusted.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from ai.prompt_loader import load_text
from ai.providers.interface import LLMError, LLMMessage, LLMProvider, LLMRole
from conversation_engine.transitions import Event, EventType

# EventTypes a customer message can plausibly produce. EXTRACTION_FAILED is
# this module's own fallback (never asked of the model) and FOLLOW_UP_DUE is
# scheduler-triggered (Phase 6) - neither is something free text maps to.
_CLASSIFIABLE_EVENT_TYPES = [
    EventType.PROVIDE_INFORMATION,
    EventType.QUESTION,
    EventType.OBJECTION,
    EventType.CHANGE_INTENT_YES,
    EventType.CHANGE_INTENT_NO,
    EventType.REQUEST_HUMAN,
    EventType.CUSTOMER_MESSAGE,
]
_CLASSIFIABLE_EVENT_TYPE_VALUES = {e.value for e in _CLASSIFIABLE_EVENT_TYPES}

# Entity keys this extractor will ever populate, and the fixed vocabulary for
# the two enum-shaped ones. This mirrors FIELD_GROUP_TO_LEAD_ATTRS in
# rules.py (Lead attribute names) but intentionally doesn't import it - the
# extractor doesn't know that these are "qualification fields" or what order
# they're collected in, only that these are the entities it may recognize.
_ENTITY_KEYS = (
    "customer_type",
    "region",
    "city",
    "current_supplier",
    "first_name",
    "last_name",
    "email",
    "phone",
    "ean",
)
_CUSTOMER_TYPE_VALUES = {"particulier", "professionnel"}
# Bug fix (F-002, BAT SC-013): "region" used to be restricted to this exact
# set, same as customer_type. That was wrong in a way customer_type isn't:
# particulier/professionnel is a genuine closed classification, but this
# set was standing in for "which regions Ecofix currently covers" - a
# business/coverage decision. Restricting extraction to it meant any
# customer outside the three covered regions had their region silently
# dropped here, so `rules.decide_validation()` (which already has its own,
# correct `is_region_covered()` check against business_rules/
# qualification_rules.yaml) never even saw a region to reject - the lead
# just sat stuck being asked for "location" forever instead of ever being
# told Ecofix doesn't serve their area. Region is now free text, exactly
# like city/current_supplier below: this module's only job is to capture
# what the customer said, never to pre-judge whether it's servable.

_SYSTEM_PROMPT = load_text("extractor/system.md")


def _build_messages(raw_text: str, expected_field: Optional[str]) -> list[LLMMessage]:
    context = ""
    if expected_field:
        context = f"\n\nContext: Sophie's last question was about: {expected_field}."
    return [
        LLMMessage(role=LLMRole.SYSTEM, content=_SYSTEM_PROMPT + context),
        LLMMessage(role=LLMRole.USER, content=raw_text),
    ]


def _normalize_entities(raw_entities: Any) -> dict[str, Any]:
    """Keep only known keys with non-null, non-empty values; validate
    customer_type against its fixed vocabulary (a genuine closed
    classification, unlike region - see the F-002 note above `_SYSTEM_PROMPT`).
    Never raises - anything unexpected is simply dropped, since a
    hallucinated/malformed entity is a missing entity, not a crash.
    """
    if not isinstance(raw_entities, dict):
        return {}

    entities: dict[str, Any] = {}
    for key in _ENTITY_KEYS:
        value = raw_entities.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip()

        if key == "customer_type" and value.lower() not in _CUSTOMER_TYPE_VALUES:
            continue
        if key == "customer_type":
            value = value.lower()
        if key in ("ean", "phone"):
            value = value.replace(" ", "")

        entities[key] = value

    return entities


def _parse_response(content: str, raw_text: str) -> Event:
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError):
        return Event(type=EventType.EXTRACTION_FAILED, raw_answer_text=raw_text)

    if not isinstance(parsed, dict):
        return Event(type=EventType.EXTRACTION_FAILED, raw_answer_text=raw_text)

    event_type_value = parsed.get("event_type")
    if event_type_value not in _CLASSIFIABLE_EVENT_TYPE_VALUES:
        return Event(type=EventType.EXTRACTION_FAILED, raw_answer_text=raw_text)

    entities = _normalize_entities(parsed.get("entities"))
    return Event(type=EventType(event_type_value), entities=entities, raw_answer_text=raw_text)


class Extractor:
    """Wraps an `LLMProvider` to turn raw text into a Phase 2 `Event`.

    Usage: `Extractor(provider).extract(raw_text, expected_field="ean")`.
    `expected_field` is optional context (which field group Sophie just
    asked for) that helps disambiguate short answers - it is passed to the
    model as context only, never used to force a particular entity.
    """

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    def extract(self, raw_text: Optional[str], *, expected_field: Optional[str] = None) -> Event:
        if not raw_text or not raw_text.strip():
            return Event(type=EventType.EXTRACTION_FAILED, raw_answer_text=raw_text)

        messages = _build_messages(raw_text, expected_field)
        try:
            response = self._provider.generate(messages, temperature=0.0, json_mode=True)
        except LLMError:
            return Event(type=EventType.EXTRACTION_FAILED, raw_answer_text=raw_text)

        return _parse_response(response.content, raw_text)

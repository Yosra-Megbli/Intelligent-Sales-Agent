"""
Qualification Rules Engine.

This is "the real brain" the design docs kept referring to: it reads the
current Lead data and decides what's missing, whether data is valid, and
whether the lead should be rejected - using plain Python and the YAML config
in business_rules/, never an LLM call and never a hardcoded prompt.

PURITY GUARANTEE (architecture review, Phase 2 follow-up): this module never
imports a repository, never calls `.flush()`/`.commit()`, and never writes
to the database. It only reads the Lead object it's given and returns an
Action describing what should happen next. Persisting anything - including
the very fields being validated - is the caller's job (conversation_engine/
engine.py + crm/ repositories), never this file's.

It also never returns a ConversationState directly. It returns an Action
(see actions.py) - a channel-agnostic decision. Only state_machine.py is
allowed to translate an Action into a ConversationState.

The LLM (Phase 3) only ever provides *entities* as input to this engine and
turns this engine's *decision* (via the Action) into language. It never
calls anything here itself, and nothing here imports an LLM client.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

from conversation_engine.actions import Action, ActionType
from domain.enums import RejectionReason
from domain.models.lead import Lead

_RULES_DIR = Path(__file__).resolve().parent.parent / "business_rules"


def _load_yaml(filename: str) -> dict:
    with open(_RULES_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


_QUALIFICATION_CONFIG = _load_yaml("qualification_rules.yaml")
_VALIDATION_CONFIG = _load_yaml("validation_rules.yaml")

# Maps a logical "field group" name (from qualification_rules.yaml) to the
# Lead attributes that must be present for that group to be considered
# complete. Purely declarative data read from this module's own constants -
# NOT from YAML, because this mapping is Python-attribute-shaped, not a
# business rule Ecofix would ever want to change independently.
FIELD_GROUP_TO_LEAD_ATTRS: dict[str, tuple[str, ...]] = {
    "customer_type": ("customer_type",),
    # Only `city` gates progression here - `region` is deliberately not
    # required for this group to be "complete". A customer can name a city
    # Ecofix doesn't recognize as belonging to any covered region (e.g.
    # "Lille") without ever stating a region word at all; that's not a
    # missing-field situation, it's a coverage decision, and
    # decide_validation()/is_region_covered() (below) already handles a
    # null region exactly like an uncovered one - it rejects at
    # DATA_VALIDATION, it doesn't get stuck re-asking COLLECT_LOCATION
    # forever waiting for a region value that was never coming.
    "location": ("city",),
    "current_supplier": ("current_supplier",),
    "contact": ("first_name", "last_name", "email", "phone"),
    "ean": ("ean",),
}

REQUIRED_FIELD_ORDER: list[str] = _QUALIFICATION_CONFIG["required_fields_order"]
ALLOWED_REGIONS: list[str] = _QUALIFICATION_CONFIG["coverage"]["allowed_regions"]

_EAN_LENGTH: int = _VALIDATION_CONFIG["ean"]["length"]
_EAN_NUMERIC_ONLY: bool = _VALIDATION_CONFIG["ean"]["numeric_only"]
_EMAIL_MUST_CONTAIN: str = _VALIDATION_CONFIG["email"]["must_contain"]
_PHONE_PATTERN: str = _VALIDATION_CONFIG["phone"]["pattern"]


def is_field_group_complete(lead: Lead, field_group: str) -> bool:
    attrs = FIELD_GROUP_TO_LEAD_ATTRS[field_group]
    return all(getattr(lead, attr) not in (None, "") for attr in attrs)


def missing_field_groups(lead: Lead) -> list[str]:
    """Return required field groups still missing, in the fixed collection order."""
    return [group for group in REQUIRED_FIELD_ORDER if not is_field_group_complete(lead, group)]


def next_qualification_action(lead: Lead) -> Action:
    """What to ask next, as an Action. Returns Action(VALIDATE) once nothing
    is missing - state_machine.py decides that this means moving to
    DATA_VALIDATION; this function doesn't know that state exists.
    """
    missing = missing_field_groups(lead)
    if not missing:
        return Action(type=ActionType.VALIDATE)
    return Action(type=ActionType.ASK_FIELD, field=missing[0])


def validate_ean(ean: Optional[str]) -> bool:
    if not ean:
        return False
    if _EAN_NUMERIC_ONLY and not ean.isdigit():
        return False
    return len(ean) == _EAN_LENGTH


def validate_email(email: Optional[str]) -> bool:
    return bool(email) and _EMAIL_MUST_CONTAIN in email


def validate_phone(phone: Optional[str]) -> bool:
    return bool(phone) and re.match(_PHONE_PATTERN, phone) is not None


def is_region_covered(region: Optional[str]) -> bool:
    return region in ALLOWED_REGIONS


def decide_validation(lead: Lead, *, is_duplicate: bool = False) -> Action:
    """Run all DATA_VALIDATION checks and return the resulting Action.

    Order matters: coverage is checked first because it's a hard rejection,
    then duplicate detection (F-003 fix - also a hard rejection: if this
    contact already exists as a Lead, there is no field left to "correct",
    they simply shouldn't be qualified a second time), then per-field
    corrections that route back to collection instead.

    `is_duplicate` is a fact the caller (conversation_engine/engine.py)
    computes via `LeadRepository.find_duplicate()` and passes in - this
    function stays pure (see module docstring) and never queries the
    database itself.
    """
    region_value = lead.region.value if hasattr(lead.region, "value") else lead.region
    if not is_region_covered(region_value):
        return Action(type=ActionType.REJECT, reason=RejectionReason.OUT_OF_COVERAGE)

    if is_duplicate:
        return Action(type=ActionType.REJECT, reason=RejectionReason.DUPLICATE_LEAD)

    if not validate_email(lead.email):
        return Action(type=ActionType.CORRECT_FIELD, field="contact")

    if not validate_phone(lead.phone):
        return Action(type=ActionType.CORRECT_FIELD, field="contact")

    if not validate_ean(lead.ean):
        return Action(type=ActionType.CORRECT_FIELD, field="ean")

    return Action(type=ActionType.QUALIFY)


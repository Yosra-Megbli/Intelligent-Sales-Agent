"""
Pure field validators, declarative-config-backed - business_rules/.

Extracted from conversation_engine/rules.py (which re-exports everything
here unchanged, so nothing that already imports from there breaks) because
`conversation_engine.rules` is on the forbidden-import list for every
Application-layer service (tests/test_architecture_boundaries.py -
`_ENGINE_AND_AI_MODULES`), including application/lead_service.py, which
needs these exact same checks for POST /api/leads (manual creation) to
honor "reuse validation_rules.yaml, never a second copy of the rules" per
AGENTS.md. This module has zero DB/LLM dependency (same purity class as
conversation_engine/compliance.py) and is not on that forbidden list, so
it's safe to import from anywhere - Engine, Application layer, or a route.

PURITY GUARANTEE: no repository import, no `.flush()`/`.commit()`, no
database access at all. Every function here is a pure function of its
arguments (plus the YAML config loaded once at import time).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import yaml

_RULES_DIR = Path(__file__).resolve().parent


def _load_yaml(filename: str) -> dict:
    with open(_RULES_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


_QUALIFICATION_CONFIG = _load_yaml("qualification_rules.yaml")
_VALIDATION_CONFIG = _load_yaml("validation_rules.yaml")

_EAN_LENGTH: int = _VALIDATION_CONFIG["ean"]["length"]
_EAN_NUMERIC_ONLY: bool = _VALIDATION_CONFIG["ean"]["numeric_only"]
_EMAIL_MUST_CONTAIN: str = _VALIDATION_CONFIG["email"]["must_contain"]
_PHONE_PATTERN: str = _VALIDATION_CONFIG["phone"]["pattern"]

_DOB_CONFIG = _QUALIFICATION_CONFIG.get("date_of_birth") or _VALIDATION_CONFIG.get("date_of_birth", {})
_DOB_MIN_AGE: int = int(_DOB_CONFIG.get("min_age", 18))

ALLOWED_REGIONS: list[str] = _QUALIFICATION_CONFIG["coverage"]["allowed_regions"]


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


def parse_date_of_birth(dob: Optional[str | datetime | date]) -> Optional[date]:
    """Parse date of birth strictly in DD/MM/YYYY format."""
    if not dob:
        return None
    if isinstance(dob, datetime):
        return dob.date()
    if isinstance(dob, date):
        return dob
    if not isinstance(dob, str):
        return None
    dob = dob.strip()
    if not re.match(r"^\d{2}/\d{2}/\d{4}$", dob):
        return None
    try:
        return datetime.strptime(dob, "%d/%m/%Y").date()
    except ValueError:
        return None


def validate_date_of_birth(dob: Optional[str | datetime | date]) -> bool:
    """Validate format strictly as DD/MM/YYYY."""
    return parse_date_of_birth(dob) is not None


def is_adult(
    dob: Optional[str | datetime | date],
    min_age: int = _DOB_MIN_AGE,
    *,
    reference_date: Optional[date] = None,
) -> bool:
    """True if age is at least min_age years old."""
    parsed = parse_date_of_birth(dob)
    if not parsed:
        return False
    today = reference_date or date.today()
    age = today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))
    return age >= min_age


def is_region_covered(region: Optional[str]) -> bool:
    return region in ALLOWED_REGIONS


# --- Rijksregisternummer (Belgian national register number) detection ------
#
# AGENTS.md golden rule: "Never ask Rijksregisternummer." The live
# conversation flow enforces this by simply never asking for one - there was
# never a stored value to validate against. Manual lead creation (a human
# typing into a form) is a new risk this project didn't have before: a sales
# rep could paste one into a free-text field without Sophie ever having
# asked. This is a new, conservative detector, not a relaxation of an
# existing rule - it checks the standard mod-97 check-digit structure
# (YYMMDD-NNN-CC, born-after-2000 offset per the official algorithm) so it
# flags an actual well-formed RRN, not just any 11-digit string a real
# phone/reference number might coincidentally look like.
_RRN_DIGITS_PATTERN = re.compile(r"^\d{11}$")


def looks_like_rijksregisternummer(value: Optional[str]) -> bool:
    if not value:
        return False
    digits = re.sub(r"[.\-\s]", "", value)
    if not _RRN_DIGITS_PATTERN.match(digits):
        return False

    number_part = int(digits[:9])
    check_digits = int(digits[9:])

    # Mod-97 check digit; people born 2000+ use (2000000000 + number_part).
    if (97 - (number_part % 97)) == check_digits:
        return True
    if (97 - ((2_000_000_000 + number_part) % 97)) == check_digits:
        return True
    return False

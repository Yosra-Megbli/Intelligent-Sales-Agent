"""
Coherence check for ActivityType enum values in PostgreSQL migrations.
Prevents the trap where an enum value is added in Python but missing in PostgreSQL migrations.
"""

from pathlib import Path
from domain.enums import ActivityType

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "database" / "migrations"


def test_all_activity_types_accounted_for_in_migrations():
    all_migration_sql = " ".join(
        f.read_text(encoding="utf-8") for f in MIGRATIONS_DIR.glob("*.sql")
    )

    # Initial enum values from base schema setup:
    base_values = {
        "MESSAGE_SENT",
        "MESSAGE_RECEIVED",
        "STATUS_CHANGED",
        "STATE_CHANGED",
        "FOLLOW_UP_SENT",
        "QUALIFIED",
        "REJECTED",
        "HUMAN_HANDOFF",
        "LEAD_IMPORTED",
        "OPT_OUT",
    }

    for activity_type in ActivityType:
        val = activity_type.value
        if val in base_values:
            continue
        assert val in all_migration_sql, (
            f"ActivityType.{val} is missing from PostgreSQL migration scripts (*.sql) in {MIGRATIONS_DIR}."
        )

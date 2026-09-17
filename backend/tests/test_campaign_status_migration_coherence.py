"""
Coherence check for CampaignStatus enum values in PostgreSQL migrations.
Prevents the migration trap where an enum value is added in Python but missing in PostgreSQL migrations.
"""

from pathlib import Path
from domain.enums import CampaignStatus

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "database" / "migrations"


def test_all_campaign_statuses_accounted_for_in_migrations():
    all_migration_sql = " ".join(
        f.read_text(encoding="utf-8") for f in MIGRATIONS_DIR.glob("*.sql")
    )

    # Initial enum values from base schema setup:
    base_values = {
        "DRAFT",
        "RUNNING",
        "PAUSED",
        "COMPLETED",
    }

    for status in CampaignStatus:
        val = status.value
        if val in base_values:
            continue
        assert val in all_migration_sql, (
            f"CampaignStatus.{val} is missing from PostgreSQL migration scripts (*.sql) in {MIGRATIONS_DIR}."
        )

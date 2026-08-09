-- P1-2: real PostgreSQL-level duplicate-lead protection (see
-- domain/models/lead.py's Lead.dedup_email/dedup_phone and __table_args__,
-- which are the source of truth this file mirrors). This project has no
-- Alembic - database/postgres.py only calls Base.metadata.create_all(),
-- which creates missing tables/columns/indexes but never alters an existing
-- table - so a manual migration is required on any database that already
-- has a `leads` table.
--
-- Fresh/disposable dev databases don't need this file at all: just recreate
-- the database (e.g. `docker compose down -v && docker compose up -d`) and
-- these columns/indexes will already be there the next time create_all()
-- runs.
--
-- WHY dedup_email/dedup_phone, not a unique index straight on email/phone:
-- conversation_engine's existing DUPLICATE_LEAD flow (F-003) intentionally
-- lets a second, about-to-be-rejected Lead hold the same email/phone as an
-- existing one, for exactly as long as it takes to detect and reject it -
-- a plain unique index on email/phone would turn that into a hard DB error
-- instead of the graceful rejection the product already relies on. These
-- two columns instead capture only *creation-time* identity (set once, by
-- LeadRepository.create(), never touched afterwards), which is what's safe
-- to make unique: creating two Leads for the same real prospect is always a
-- bug, never a legitimate business outcome. See
-- tests/test_conversation_engine.py::
-- test_duplicate_lead_rejected_at_data_validation_regression_f003 for the
-- regression this distinction protects.
--
-- BEFORE applying this on a database with real data: check for existing
-- creation-time duplicates first, or the final CREATE UNIQUE INDEX
-- statements will fail with a clear "could not create unique index" error
-- rather than silently skipping the offending rows.
--
--   SELECT lower(email), count(*) FROM leads WHERE email IS NOT NULL
--     GROUP BY lower(email) HAVING count(*) > 1;
--   SELECT phone, count(*) FROM leads WHERE phone IS NOT NULL
--     GROUP BY phone HAVING count(*) > 1;
--
-- If either query returns rows, resolve/merge those leads manually before
-- applying this migration (out of scope for this change - do not delete
-- data automatically). This project's dev database had 0 rows in either
-- query as of this migration being written (6 leads total), so the
-- backfill below is a straight copy for it, but re-run the check above on
-- any other database before applying.
--
-- Apply once, in order, on any database created before this migration was
-- added:
--   psql "$DATABASE_URL" -f database/migrations/0002_lead_dedup_unique_indexes.sql

-- If an earlier draft of this migration was applied (a unique index
-- directly on lower(email)/phone), drop it - it is incompatible with F-003
-- (see above) and is superseded by the dedup_email/dedup_phone columns.
DROP INDEX IF EXISTS ux_leads_email_ci;
DROP INDEX IF EXISTS ux_leads_phone;

ALTER TABLE leads ADD COLUMN IF NOT EXISTS dedup_email VARCHAR(255);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS dedup_phone VARCHAR(32);

-- Backfill: a lead's creation-time identity is, for all pre-existing rows,
-- simply whatever email/phone it currently holds (there is no way to
-- recover "what it was at creation" more precisely than that).
UPDATE leads SET dedup_email = lower(email) WHERE email IS NOT NULL AND dedup_email IS NULL;
UPDATE leads SET dedup_phone = phone WHERE phone IS NOT NULL AND dedup_phone IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_leads_dedup_email ON leads (dedup_email) WHERE dedup_email IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_leads_dedup_phone ON leads (dedup_phone) WHERE dedup_phone IS NOT NULL;

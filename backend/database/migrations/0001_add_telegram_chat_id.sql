-- Adds Lead.telegram_chat_id (see domain/models/lead.py for why this field
-- exists). This project has no Alembic - database/postgres.py only calls
-- Base.metadata.create_all(), which creates missing tables but never alters
-- an existing one - so a manual ALTER TABLE is required on any database
-- that already has a `leads` table.
--
-- Fresh/disposable dev databases don't need this file at all: just recreate
-- the database (e.g. `docker compose down -v && docker compose up -d`) and
-- the column will already be there the next time create_all() runs.
--
-- Apply once, in order, on any database created before this migration was
-- added:
--   psql "$DATABASE_URL" -f database/migrations/0001_add_telegram_chat_id.sql

ALTER TABLE leads ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(64);
CREATE INDEX IF NOT EXISTS ix_leads_telegram_chat_id ON leads (telegram_chat_id);

-- Migration 0008: add language column to leads table
--
-- Tracks customer preferred/detected language ('fr', 'nl', 'en') on the Lead entity.
-- Defaults to 'fr' (Ecofix primary market).
--
-- Idempotent: safe to run more than once.
-- Run on target DB:
--   psql $DATABASE_URL -f backend/database/migrations/0008_add_language_to_leads.sql

ALTER TABLE leads ADD COLUMN IF NOT EXISTS language VARCHAR(8) DEFAULT 'fr';
CREATE INDEX IF NOT EXISTS ix_leads_language ON leads (language);

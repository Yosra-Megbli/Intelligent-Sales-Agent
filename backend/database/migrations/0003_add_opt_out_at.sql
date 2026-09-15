-- Migration 0003: add opt_out_at column to leads table
--
-- Records the UTC timestamp at which a lead sent a STOP/STOPT/ARRET message.
-- Non-null means the lead has opted out -- the follow-up scheduler and any
-- outbound engine MUST check this column before contacting the lead.
--
-- Idempotent: safe to run more than once (IF NOT EXISTS).
-- Manual execution required (no Alembic in this project -- see 0001 header).
--
-- Run on the target DB:
--   psql $DATABASE_URL -f backend/database/migrations/0003_add_opt_out_at.sql

ALTER TABLE leads ADD COLUMN IF NOT EXISTS opt_out_at TIMESTAMP;

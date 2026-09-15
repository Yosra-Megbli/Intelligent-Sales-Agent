-- Migration 0006: add consecutive_same_state_ask column to conversations table
--
-- Tracks consecutive same-state re-ask attempts during qualification states
-- to trigger deterministic escalation (single-field asks like ASK_CITY_ONLY / ASK_REGION_ONLY).
--
-- Idempotent: safe to run more than once (IF NOT EXISTS).
-- Manual execution required (no Alembic in this project -- see 0001 header).
--
-- Run on the target DB:
--   psql $DATABASE_URL -f backend/database/migrations/0006_add_consecutive_same_state_ask.sql

ALTER TABLE conversations ADD COLUMN IF NOT EXISTS consecutive_same_state_ask INTEGER DEFAULT 0 NOT NULL;

-- Migration 0005: add consecutive_extraction_failures column to conversations table
--
-- Tracks consecutive extraction failure attempts (0-extraction turns) during
-- qualification states to trigger progressive fallback (single-field asks / error recovery).
--
-- Idempotent: safe to run more than once (IF NOT EXISTS).
-- Manual execution required (no Alembic in this project -- see 0001 header).
--
-- Run on the target DB:
--   psql $DATABASE_URL -f backend/database/migrations/0005_add_consecutive_extraction_failures.sql

ALTER TABLE conversations ADD COLUMN IF NOT EXISTS consecutive_extraction_failures INTEGER DEFAULT 0 NOT NULL;

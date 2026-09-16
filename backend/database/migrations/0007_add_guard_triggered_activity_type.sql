-- Migration 0007: add GUARD_TRIGGERED to activity_type enum
--
-- Tracks output guard activations (anti-hallucination / compliance violations
-- caught and replaced by deterministic fallbacks).
--
-- Idempotent: safe to run more than once (IF NOT EXISTS).
-- Manual execution required (no Alembic in this project -- see 0001 header).
--
-- Run on the target DB:
--   psql $DATABASE_URL -f backend/database/migrations/0007_add_guard_triggered_activity_type.sql

ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'GUARD_TRIGGERED';

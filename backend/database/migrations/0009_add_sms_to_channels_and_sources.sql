-- Migration 0009: add SMS to conversation_channel and lead_source enums
--
-- Enables Twilio SMS channel (Sprint 2).
--
-- Idempotent: safe to run more than once.
-- Run on target DB:
--   psql $DATABASE_URL -f backend/database/migrations/0009_add_sms_to_channels_and_sources.sql

ALTER TYPE conversation_channel ADD VALUE IF NOT EXISTS 'SMS';
ALTER TYPE lead_source ADD VALUE IF NOT EXISTS 'SMS';

-- Migration 0015: Add CANCELLED value to campaign_status enum
-- Allows definitive cancellation of campaigns in production

ALTER TYPE campaign_status ADD VALUE IF NOT EXISTS 'CANCELLED';

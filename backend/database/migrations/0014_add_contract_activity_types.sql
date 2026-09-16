-- Migration 0014: Add contract activity types and lead_created to activity_type enum
-- Fixes contract generation in production (CONTRACT_DRAFTED, CONTRACT_SENT, etc.)

ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'CONTRACT_DRAFTED';
ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'CONTRACT_SENT';
ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'CONTRACT_SIGNED';
ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'CONTRACT_WITHDRAWN';
ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'LEAD_CREATED';

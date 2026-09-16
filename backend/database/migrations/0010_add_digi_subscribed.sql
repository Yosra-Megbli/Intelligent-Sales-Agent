-- Migration 0010: Add digi_subscribed to contracts and leads table
-- Ecofix Digi is an OPTIONAL digital app add-on at 5,99 €/month (never base fee)

ALTER TABLE contracts ADD COLUMN IF NOT EXISTS digi_subscribed BOOLEAN DEFAULT FALSE;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS digi_subscribed BOOLEAN DEFAULT FALSE;

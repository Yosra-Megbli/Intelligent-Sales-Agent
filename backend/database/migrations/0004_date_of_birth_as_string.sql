-- Migration 0004: alter date_of_birth column type from TIMESTAMP to VARCHAR(64)
--
-- Ecofix qualification rules validate date_of_birth strictly in DD/MM/YYYY
-- format. Storing as VARCHAR(64) preserves raw prospect input across extraction
-- and enables deterministic rules engine format/age validation without database
-- timestamp conversion errors.
--
-- Handles existing data safely via TO_CHAR with NULL safety.
-- Idempotent: checks current column data type before altering.
-- Manual execution required (no Alembic in this project -- run before deploy).
--
-- Run on the target DB:
--   psql $DATABASE_URL -f backend/database/migrations/0004_date_of_birth_as_string.sql

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'leads' 
          AND column_name = 'date_of_birth' 
          AND data_type LIKE '%timestamp%'
    ) THEN
        ALTER TABLE leads 
        ALTER COLUMN date_of_birth TYPE VARCHAR(64) 
        USING CASE 
            WHEN date_of_birth IS NOT NULL THEN TO_CHAR(date_of_birth, 'DD/MM/YYYY') 
            ELSE NULL 
        END;
    END IF;
END $$;

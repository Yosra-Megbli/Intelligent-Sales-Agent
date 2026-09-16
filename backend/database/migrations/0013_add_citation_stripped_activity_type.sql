-- Migration 0013: add CITATION_STRIPPED to activity_type enum
--
-- Tracks RAG v2 citation validator actions when invalid/hallucinated
-- [SOURCE n] citations are stripped from generated answers.
--
-- Idempotent: safe to run more than once (IF NOT EXISTS).

ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'CITATION_STRIPPED';

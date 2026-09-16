-- 0012_knowledge_entries.sql (Sprint 4b - keyword-RAG v1 admin surface)
-- NOT RAG v2 (see 0011_knowledge_documents_and_chunks.sql for that) - this
-- table backs the EXISTING keyword-matching ai/rag.py, giving it a
-- DB-editable source of entries alongside backend/ai/knowledge_base.yaml.
--
-- Keep in sync BY HAND with domain/models/knowledge_entry.py - tests build
-- the schema from that model via Base.metadata.create_all() on SQLite,
-- this file is what production actually runs (migration_runner.py skips
-- SQL entirely on any non-postgresql dialect), and nothing but
-- tests/test_knowledge_entries_migration_coherence.py verifies the two
-- agree. See AGENTS.md's "Migration trap".
--
-- Manual application:
--   psql $DATABASE_URL -f backend/database/migrations/0012_knowledge_entries.sql

CREATE TABLE IF NOT EXISTS knowledge_entries (
    id UUID PRIMARY KEY,
    category VARCHAR(32) NOT NULL,
    question VARCHAR(255) NOT NULL,
    keywords_json TEXT NOT NULL,
    answer_fr TEXT NOT NULL,
    answer_nl TEXT NULL,
    answer_en TEXT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_entries_category ON knowledge_entries(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_entries_active ON knowledge_entries(active);

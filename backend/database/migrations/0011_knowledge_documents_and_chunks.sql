-- 0011_knowledge_documents_and_chunks.sql (RAG v2 Phase 1)
-- Vector-backed knowledge base: documents + chunks, publish-explicit.
-- Keep this in sync BY HAND with domain/models/knowledge_document.py and
-- domain/models/knowledge_chunk.py - tests build the schema from those
-- models via Base.metadata.create_all() on SQLite, this file is what
-- production actually runs (database/migration_runner.py skips SQL
-- entirely on any non-postgresql dialect), and nothing in this repo
-- verifies the two agree. See AGENTS.md's "Migration trap".
--
-- Manual application:
--   psql $DATABASE_URL -f backend/database/migrations/0011_knowledge_documents_and_chunks.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    source_type VARCHAR(64) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    language VARCHAR(2) NOT NULL DEFAULT 'fr',
    status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
    version INTEGER NOT NULL DEFAULT 1,
    review_date DATE NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    published_at TIMESTAMP WITHOUT TIME ZONE NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_source_type ON knowledge_documents(source_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_documents_status ON knowledge_documents(status);
CREATE INDEX IF NOT EXISTS idx_knowledge_documents_review_date ON knowledge_documents(review_date);

-- 768 = text-embedding-004 (Google AI) output dimensionality. Matches
-- domain/models/knowledge_chunk.py's EMBEDDING_DIMENSIONS constant -
-- changing the embedding provider to a different dimensionality needs a
-- new migration, not an edit to this one (existing embeddings can't be
-- resized in place; they would all need re-ingesting).
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768) NULL,
    metadata_json TEXT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document_id ON knowledge_chunks(document_id);

-- HNSW: approximate nearest-neighbour index for cosine similarity, used by
-- Phase 2's retrieval (not built yet - this migration only prepares the
-- schema). vector_cosine_ops matches the cosine-distance query Phase 2 is
-- specified to use (docs/RAG_BACKLOG.md).
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding_hnsw
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

-- 0007_contracts.sql (Sprint 3 / Package C)
-- Contract data layer: contracts table and energy assets on leads
--
-- Manual application:
--   psql $DATABASE_URL -f backend/database/migrations/0007_contracts.sql

-- Add energy assets to leads if not present
ALTER TABLE leads ADD COLUMN IF NOT EXISTS has_ev BOOLEAN DEFAULT FALSE;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS has_heat_pump BOOLEAN DEFAULT FALSE;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS has_battery BOOLEAN DEFAULT FALSE;

-- Contracts table for Sophie energy contracts (Flexy & Motion)
CREATE TABLE IF NOT EXISTS contracts (
    id UUID PRIMARY KEY,
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    product VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    yousign_signature_request_id VARCHAR(128) NULL,
    yousign_document_id VARCHAR(128) NULL,
    pdf_path VARCHAR(512) NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    signed_at TIMESTAMP WITHOUT TIME ZONE NULL,
    withdrawn_at TIMESTAMP WITHOUT TIME ZONE NULL
);

CREATE INDEX IF NOT EXISTS idx_contracts_lead_id ON contracts(lead_id);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contracts_yousign_sig_req ON contracts(yousign_signature_request_id);

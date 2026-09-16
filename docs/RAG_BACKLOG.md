# RAG v2 Implementation Backlog & Architecture Specification

> **Status**: **DEFERRED**  
> **Prerequisites before execution**: Vercel frontend deployment completed + production secrets rotation completed.  
> **Governance rule**: An exhaustive technical specification document (`RAG_Implementation_Spec_v2.md`) must be reviewed and approved by the owner before any implementation code or schema migrations are committed.

---

## 1. Context & Purpose

This document serves as the single source of truth for the future **Retrieval-Augmented Generation (RAG v2)** upgrade for Sophie, the AI energy sales agent for Ecofix Gas & Power.

The current system relies on a curated declarative keyword-matching engine (`backend/ai/knowledge_base.yaml` + `backend/ai/rag.py`) which ensures 100% deterministic, hallucination-free answers for core FAQs and objections. RAG v2 will enhance this with vector semantic search over official source documents while preserving all compliance invariants.

---

## 2. Corpus Inventory (`knowledge_corpus/`)

Raw source material is staged in `knowledge_corpus/`. Ingestion into the active runtime is deferred.

```
knowledge_corpus/
├── README.md                                    # Corpus catalog and trust hierarchy rules
├── tariffs/
│   └── 2026-09/                                # 12 Official Sept 2026 Tariff Card PDFs (FR + NL)
│       ├── EL_Ecofix_Flexy_FR.pdf              # Electricity Flexy (Variable monthly) - FR
│       ├── EL_Ecofix_Flexy_NL.pdf              # Electricity Flexy (Variable monthly) - NL
│       ├── GAS_Ecofix_Flexy_FR.pdf             # Gas Flexy (Variable monthly) - FR
│       ├── GAS_Ecofix_Flexy_NL.pdf             # Gas Flexy (Variable monthly) - NL
│       ├── EL_Ecofix_Motion_FR.pdf             # Electricity Motion (Dynamic hourly) - FR
│       ├── EL_Ecofix_Motion_NL.pdf             # Electricity Motion (Dynamic hourly) - NL
│       ├── EL_Ecofix_Flexy_Online_FR.pdf       # Electricity Flexy Online - FR
│       ├── EL_Ecofix_Flexy_Online_NL.pdf       # Electricity Flexy Online - NL
│       ├── GAS_Ecofix_Flexy_Online_FR.pdf      # Gas Flexy Online - FR
│       ├── GAS_Ecofix_Flexy_Online_NL.pdf      # Gas Flexy Online - NL
│       ├── EL_Ecofix_Motion_Online_FR.pdf      # Electricity Motion Online - FR
│       └── EL_Ecofix_Motion_Online_NL.pdf      # Electricity Motion Online - NL
├── contracts/
│   └── conditions_generales.md                 # General supply conditions note (URL & summary)
├── faq/
│   ├── helpdesk_klant_worden.md                # Helpdesk: onboarding, EAN 18-digit requirement
│   ├── helpdesk_tarieven_producten.md          # Helpdesk: rates, products, and fees explanation
│   ├── helpdesk_facturen_betalen.md            # Helpdesk: invoices, advance payments, settlements
│   ├── helpdesk_wijzigingen_contracten.md      # Helpdesk: contract changes, moving, termination
│   └── overstappen.md                          # Guide: switching suppliers in Belgium without fees
├── marketing/
│   ├── friends_with_benefits.md                # Referral program (€5/mo discount, no cap)
│   └── ecofix_digi_app.md                      # Ecofix Digi optional add-on (€5.99/mo, smart control)
└── regulatory/
    ├── cwape_wallonia_license.md               # CWaPE Wallonia license (2025-04-03) & ORES/RESA
    ├── creg_market_report.md                   # CREG federal market monitoring & transparency rules
    └── brugel_regulatory_overview.md           # BRUGEL: Brussels regional market & out-of-coverage
```

### Trust Hierarchy

When two source documents contain conflicting information, the retrieval pipeline and arbitration layer must strictly observe the following order of precedence:

$$\text{Tariff Card} > \text{Conditions Générales} > \text{Helpdesk} > \text{Regulator} > \text{Marketing}$$

1. **Tariff Card (`tariff_card`)** [Highest Authority]: Authoritative for fixed subscription fees (€60,00/an), kWh rate formulas, indexation parameters, and optional Digi app pricing.
2. **Conditions Générales (`conditions`)**: Authoritative for contractual terms, 14-day statutory right of withdrawal, legal notice periods (3–4 weeks), and termination procedures.
3. **Helpdesk (`helpdesk`)**: Practical explanations of customer journeys (moving, onboarding, bill cycles, meter readings).
4. **Regulator (`regulator`)**: CWaPE Wallonia license (2025-04-03), CREG federal pricing rules, VREG Flemish comparison tools (`v-test.vreg.be`), and BRUGEL territory boundaries.
5. **Marketing (`marketing`)** [Lowest Authority]: Campaign brochures, Friends with Benefits referral explanations, and feature highlights. Never overrides contractual or tariff facts.

---

## 3. Chunk Metadata Schema

Every chunk ingested into the vector database must carry the following structured metadata fields to enable pre-filtering before semantic vector distance calculation:

```typescript
interface KnowledgeChunkMetadata {
  chunk_id: string;             // UUID primary key
  document_id: string;          // Source document identifier
  source_type: 'tariff_card' | 'conditions' | 'helpdesk' | 'regulator' | 'marketing';
  product: 'flexy' | 'motion' | 'flexy_online' | 'motion_online' | 'all' | 'none';
  energy_type: 'electricity' | 'gas' | 'dual_fuel' | 'general';
  region: 'flanders' | 'wallonia' | 'all' | 'out_of_coverage';
  language: 'fr' | 'nl' | 'en';
  valid_from: string;           // ISO 8601 Date (e.g. "2026-09-01")
  valid_until: string | null;   // ISO 8601 Date or null for open-ended
  status: 'active' | 'archived' | 'draft';
  trust_weight: number;         // 100 (tariff_card) down to 20 (marketing)
}
```

---

## 4. Architectural & Implementation Decisions

### 1. Vector Store: `pgvector` on Neon PostgreSQL
- Uses PostgreSQL with the `pgvector` extension hosted on the existing Neon serverless cluster.
- Eliminates the operational complexity, cost, and latency of managing a dedicated third-party vector database (Pinecone, Weaviate, etc.).
- Keeps transactional CRM data (Leads, Conversations, Contracts) and knowledge embeddings in the same ACID-compliant database.

### 2. Embeddings: Cloud API-Based Multilingual Embeddings (NOT Local Models)
- **Constraint**: The backend container runs on Render's free tier with a strict **512 MB RAM limit**.
- Local embedding models (e.g., HuggingFace `sentence-transformers`, `FastEmbed`, PyTorch) require >1 GB RAM and will instantly trigger an out-of-memory (OOM) kernel termination (`Exit status 137`).
- **Decision**: Use a lightweight, API-based multilingual embedding service (e.g., Voyage AI `voyage-multilingual-2`, Cohere `embed-multilingual-v3.0`, OpenAI `text-embedding-3-small`, or Mistral embeddings) accessed over HTTPS via `httpx`.

### 3. Relevance Gate & Hard Refusal Without LLM Call
- Deterministic similarity threshold (e.g., cosine similarity $\ge 0.78$).
- If top-ranked chunk similarity falls below the cutoff, the system triggers a **hard refusal without calling the LLM**:
  - Automatically falls back to the deterministic safety response (`_FALLBACK_TEXT["ANSWER_FAQ"]` / `_FALLBACK_TEXT["ANSWER_OBJECTION"]`).
  - Completely prevents hallucinations when customers ask out-of-scope, off-topic, or unanswerable questions.

### 4. Zero-Downtime Safe Migration Strategy
- The legacy keyword RAG engine (`backend/ai/knowledge_base.yaml` + `backend/ai/rag.py`) remains fully operational.
- During migration, the retrieval pipeline will query the vector index and fall back to `knowledge_base.yaml` if the vector query is unavailable or times out.
- Extensively regression-tested using the existing 103+ golden scenarios and the dedicated pricing truth test suite (`test_pricing_truth.py`).

---

## 5. Execution Roadmap

1. **Gate 1 (Completed)**: Raw official sources gathered in `knowledge_corpus/` (12 tariff PDFs Sept 2026, web notes, regulatory citations).
2. **Gate 2 (Current)**: Vercel frontend deployment and production environment secrets rotation.
3. **Gate 3 (Future)**: Draft, review, and approve `RAG_Implementation_Spec_v2.md`.
4. **Gate 4 (Future)**: Database migration adding `pgvector` extension and `knowledge_embeddings` table.
5. **Gate 5 (Future)**: Ingestion script with automated chunking, metadata extraction, and embedding generation.
6. **Gate 6 (Future)**: End-to-end evaluation against golden conversation tests.

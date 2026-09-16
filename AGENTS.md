# AGENTS.md — Intelligent Sales Agent "Sophie"

## Context

AI sales agent ("Sophie") selling Belgian energy contracts (Ecofix Gas & Power context). Production-grade demo/portfolio, deployed live. ALL demo prospect data is FICTIONAL — files must carry "SPÉCIMEN / DEMO — DONNÉES FICTIVES".

Product data, by contrast, is REAL and verified against Ecofix's official sources.

## Architecture invariants (NEVER break)

**Deterministic core.** The State Machine decides states; the YAML Rules Engine decides qualification & product pitch. The LLM (Groq) extracts entities (constrained JSON) and phrases sentences — it NEVER decides a state, a qualification, or a business action.

**Five anti-hallucination layers.** (1) deterministic decision, (2) constrained extraction + strict validation, (3) controlled phrasing via `talking_points.yaml`, (4) deterministic per-action fallback via `fallback_text.yaml`, (5) output-guard — a regex linter forbidding invented stats, absolute promises and market predictions, which replaces the reply with the fallback and logs `GUARD_TRIGGERED`.

**Purity and boundary tests are load-bearing — never weaken them to make a build green.** `ai/extractor.py`, `ai/responder.py` and `ai/rag.py` are AST-tested to prove they never import a repository and never touch the DB (`tests/test_rag.py::test_rag_module_never_touches_the_database_or_crm`). `tests/test_architecture_boundaries.py` proves Channels and `api/routes.py` reach the Engine only through `application/conversation_service.py`. If a task seems to require breaking one of these, the design is wrong — stop and ask. To give `Rag` a new data source, inject the entries from the Application layer; do not let `ai/rag.py` read a database.

**Channels:** Telegram (live), Web (live), SMS (complete — `channels/sms.py`, signed `X-Twilio-Signature` webhook, short ≤320-char trilingual disclosure, STOP handling), WhatsApp + Voice/Twilio (built end-to-end, NOT activated — API keys missing).

**CRM:** PostgreSQL + Redis, `find_duplicate()`, campaigns, follow-ups.

## Golden rules (compliance — mandatory in all copy/prompts)

Every FIRST outbound message and every call opening MUST contain an explicit AI disclosure + human-handover offer + opt-out hint:

- **FR:** "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle) d'Ecofix — un conseiller humain reste disponible à tout moment."
- **NL:** "Dag, hier is Sophie, de virtuele assistent (AI) van Ecofix — een menselijke adviseur neemt op elk moment over als u dat liever heeft."
- **EN:** "Hi, this is Sophie, a virtual assistant (AI) for Ecofix — a human advisor is available at any time."

STOP / STOPT / ARRÊT = immediate opt-out: leave campaign, purge PII, keep only a suppression key, log it.

NEVER invent stats ("jusqu'à 20%"), absolute promises ("jamais trop payer", "nooit te veel"), or market predictions. Sell FREEDOM (no exit fees, transparent monthly revision).

Always vouvoiement (FR) / u-form (NL). FIXED_SEEKER: max 1 reframe → polite refusal, save status, `do_not_pitch_variable=true`.

Never ask for a Rijksregisternummer. EAN = 18 digits starting with 5414.

## Domain facts

**Grid operators:** Flanders = Fluvius, Wallonia = ORES/RESA. Never mixed. No Brussels (supplier absent there → `OUT_OF_COVERAGE` rejection).

**Regulatory:** CWaPE granted Ecofix general electricity & gas supply licenses for Wallonia on 2025-04-03. Flanders regulator: VREG (v-test.vreg.be official comparison). Brussels: BRUGEL zone — not served.

**Products:** NO fixed contracts (deliberate). Flexy (variable monthly), Motion (dynamic hourly — pitch if `has_ev` / `has_heat_pump` / `has_battery`), Flexy Online, Motion Online (Online variants ~10 €/yr fixed fee, app-managed). Smart Control & Smart Integration available since T2 2026 per tariff card margin notes.

**Pricing truth** — guarded by `tests/test_pricing_truth.py`:
- Frais fixes (obligatoire) = 60,00 €/an, part of the Prix de l'énergie.
- Ecofix Digi = 5,99 €/mois, **OPTIONAL** digital app add-on (consumption tracking, smart control). NEVER present it as a base or obligatory fee.
- Friends with Benefits = referral program, 5 €/mo discount per active referral, no cap.
- No residential cancellation fees in BE. Switch 3–4 weeks. 14-day withdrawal.

Verified against the Sept 2026 tariff card on 2026-09-16. **Tariff cards change monthly** — re-verify any figure against `portal.ecofixgp.be/docs/prices/current/` before writing commercial copy. A 5,99 €/60 € mix-up was already caught this way.

## Tests & CI

752 tests green (`tests/` + `golden_tests/`, including `scenarios/conversations.yaml`). Separate real-LLM eval against Groq (`golden_tests/run_real_llm_eval.py`) — never collected by pytest, never gating.

CI: `.github/workflows/ci.yml` runs the suite on a Python 3.11/3.12 matrix plus the frontend build on every push/PR to main. The real-LLM eval is `workflow_dispatch` opt-in.

**Migration trap:** tests build the schema with `Base.metadata.create_all()` on SQLite in-memory, and `migration_runner.py` skips SQL migrations on any non-postgresql dialect. A broken `.sql` migration therefore passes CI green and fails at boot on Render. Any new table needs BOTH a SQLAlchemy model AND a SQL migration, kept consistent by hand — a static coherence test (column names cross-checked between the model and the `.sql` file) is the pattern to reuse; see `tests/test_rag_v2_migration_coherence.py`. Next migration number is **0013** (`0011` and `0012` are both now used - RAG v2's `knowledge_documents`/`knowledge_chunks` and Sprint 4b's `knowledge_entries` respectively; note two files also already share the `0007` prefix).

## Status

**Live in production**, all free tiers: backend on Render (Docker, `python:3.12-slim`, migrations auto-run at boot), PostgreSQL on Neon, Redis on Upstash, frontend on Vercel, Groq `openai/gpt-oss-120b`, Telegram bot `@EcofixSalesBot`. Health endpoint `/health` checks DB + Redis.

### Done

- **Sprint 1 (compliance):** trilingual AI disclosure in all channels + guard tests; full STOP handler with PII purge + suppression list; `date_of_birth` in `qualification_rules.yaml` (strict DD/MM/YYYY, 18+, 31/02 rejected) + golden tests; GDPR section in README. A real-LLM test caught a production bug — multi-field extraction failed because the extractor schema lacked `date_of_birth` → fixed with few-shots, partial acknowledgement (`ASK_PARTIAL_CONTACT`) and progressive field-by-field fallback (`consecutive_extraction_failures`).
- **Deployment:** root Dockerfile, `render.yaml`, auto-migrations at boot, `/health`, webhook CLI (`scripts/setup_telegram_webhook.py`), documented secret rotation.
- **Sprint 2:** deterministic language detection stored on the lead (fr default); real dashboard metrics (cost/conversation ≈ 0,02 €, cost/sale, estimated revenue — 60 €/yr base, optional Digi counted separately); complete Twilio SMS channel.
- **Sprint 3 (contract lifecycle):** `contracts` table, states `CONTRACT_DRAFT → SENT → SIGNED/WITHDRAWN`, `CONTRACT_MODE=full|handoff` env switch, ReportLab PDF (`contracts/pdf_generator.py` — preamble quotes the AI Act disclosure verbatim, withdrawal annex, CRM data only), Yousign sandbox v3 integration (`integrations/yousign.py`, HMAC webhook, graceful degradation without a key, `POST /api/contracts/{id}/simulate-sign`), frontend wired (contract card in drawer, SIGNED chip, "Contrats signés" KPI).
- **Engine fix:** `ASK_LOCATION` loop resolved (flandre → `ASK_CITY_ONLY`, generalized `consecutive_same_state_ask ≥ 2` guard → field-by-field collection). Verified live in the Simulator.
- **Frontend Phase 1 + login redesign:** navy/teal/lavender (oklch), full fr/nl/en i18n, dark mode.

### Known gaps (never claim "done")

- WhatsApp and Voice are built but NOT activated (API keys missing).
- Yousign is sandbox-only; no real e-signature key.
- Campaigns admin screen is real (list, create, two-step launch, pause/resume) but scoped down from the original vision: no lead multi-select/CSV-import wizard, no SSE live cockpit, no cancel. See "Sprint 4c / Campaigns are real" below.
- No manual lead creation endpoint (`POST /api/leads`) — only CSV import; `PATCH` and `DELETE` already exist.
- RAG v2 retrieval is wired into the chat as first tier (`rag_v2/retrieval.py` + `application/conversation_service.py` + all channels: Web, Telegram, WhatsApp, SMS); degrades cleanly to keyword RAG if no `GOOGLE_AI_API_KEY` or no chunk clears similarity threshold.
- NL copy has never been field-tested.
- README content has stale sections (it still claims contract generation is unimplemented) and carries a UTF-8 double-encoding corruption in its prose.

## Knowledge & RAG

`knowledge_corpus/` holds the official raw material (12 Sept-2026 tariff card PDFs FR+NL, terms, FAQ, regulators) — see `knowledge_corpus/README.md`.

**Keyword RAG v1 admin (Sprint 4b) is done**, migration `0012` (RAG v2's Phase 1 already claimed `0011` - see below): `knowledge_entries` table (`domain/models/knowledge_entry.py`), CRUD at `GET/POST/PUT/DELETE /api/knowledge` + `POST /api/knowledge/{id}/toggle-active`, and a "Base de Connaissances" sidebar screen. `ai/rag.py` is untouched — it already accepted `entries=` as a constructor parameter before this work started, so `application/conversation_service.py`'s new `_build_rag(language)` just uses that existing injection point: it re-queries `knowledge_entries` on every call (never cached), converts active rows to `ai.rag.KnowledgeEntry` tuples using the answer matching the conversation's language, and falls back to the original YAML-backed `Rag()` when the table is empty. Seed script `scripts/seed_knowledge_entries.py` migrates `ai/knowledge_base.yaml` into the table (idempotent, deterministic UUIDs via `uuid.uuid5` — not run automatically, run it once after applying migration `0012`).

**RAG v2** — vision: port the ZEN Knowledge patterns (publish-explicit, W3 obsolescence, citations validator, refusal-before-LLM) to FastAPI/Python. Backlog and decisions: `docs/RAG_BACKLOG.md`. Settled decisions: pgvector on Neon; embeddings via API (Google AI `text-embedding-004`, 768-dim, free tier — Mistral documented as a fallback), no local models (Render free = 512 MB); source-of-truth hierarchy tariff card > terms > helpdesk > regulator > marketing; legacy keyword RAG kept during migration.

**Phase 1 (schema + ingestion) is done, migration `0011`:**
- `domain/models/knowledge_document.py` / `knowledge_chunk.py`, migration `database/migrations/0011_knowledge_documents_and_chunks.sql` (pgvector extension, `vector(768)` column, HNSW cosine index).
- Cross-dialect vector column: `database/vector_types.py`'s `EmbeddingVector` — real pgvector type on PostgreSQL, JSON-in-Text fallback on SQLite (same pattern as `GUID`), so the model works in both the SQLite test suite and production.
- `ai/providers/embeddings/` — `EmbeddingProvider` interface + `GoogleEmbeddingProvider`. **Known follow-up:** built against `google-generativeai`, which Google end-of-lifed in favor of `google-genai` during this same work — it still installs and functions, every test uses a fake client (no network, no real key ever used), but the real API call shape is unverified against a live call. Verify with one real `rag_v2.ingest` run before depending on it; see the file's docstring for the exact migration path if it needs fixing.
- `rag_v2/chunking.py` — deterministic word-window chunking (~500 tokens/50 overlap, no tokenizer dependency), pure function, no I/O.
- `rag_v2/ingestion.py` (core, testable) + `rag_v2/ingest.py` (CLI: `python -m rag_v2.ingest --file ... --title ... --source-type ... --language ...`) — extract (pypdf) → clean → chunk → embed (batched) → persist, always `status=DRAFT`.
- `rag_v2/documents.py` — publish-explicit: `publish_document()`/`archive_document()`/`list_published_chunks()`. Ingesting never publishes; nothing is retrievable until this is called.
- 37 new tests, all offline (fake `EmbeddingProvider`, monkeypatched PDF extraction, no network) — chunking correctness incl. a no-content-loss regression, ingestion, publish-explicit gating, and a static model/migration column-coherence check (`tests/test_rag_v2_migration_coherence.py`).

**Phase 2 (similarity-search retrieval + relevance gate + grounded generation + citations) is done:**
- `rag_v2/search.py` — `VectorSearch` interface with `PgVectorSearch` (pgvector `<=>` cosine distance on PostgreSQL) and `InMemoryCosineSearch` (pure Python cosine on published chunks for SQLite/tests).
- `rag_v2/retrieval.py` — threshold `RAG_MIN_SIMILARITY` (0.30 default), `RAG_TOP_K` (20 default), `valid_until` filtering, `ScoredChunk` dataclass.
- `rag_v2/refusal.py` — deterministic legal trilingual refusal without LLM call if below threshold or no source.
- `rag_v2/citations.py` — post-generation citation validation; invalid `[SOURCE n]` mentions stripped, `CITATION_STRIPPED` activity logged.
- `application/conversation_service.py` — RAG v2 vector search attempted first before keyword RAG, safe fallback, grounded prompt formatting `[SOURCE n]`, citation validation, output guard layer 5.
- Channels & API: `channels/web.py`, `channels/telegram.py`, `channels/whatsapp.py`, `channels/sms.py`, and `api/routes.py` with `get_embedding_provider()` dependency.

**Phase 3 (obsolescence - ZEN W3 pattern) is done:**
- `rag_v2/obsolescence.py` — `review_due_documents` (7d default), `auto_archive_expired` (grace period 30d default, idempotent archive), `detect_version_conflict` (warnings on duplicate product keys), CLI `python -m rag_v2.obsolescence --run`.
- API: `GET /api/knowledge/obsolescence` (due_soon, overdue, archived_today_count) routed through `KnowledgeService`.
- Tests: 7 new tests covering auto-archive, grace periods, idempotency, version conflict detection, API endpoint.

## Priority order

1. **Sprint 4:** make the remaining admin surfaces real — manual Leads CRUD (`POST /api/leads`; campaign channel-activation guard + launch preview already done, see Sprint 5 note below), Knowledge management (`knowledge_base.yaml` → `knowledge_entries` table + CRUD + active toggle — this is the *keyword* RAG's admin surface, separate from RAG v2). Remove stubs that become real; keep honest stubs for WhatsApp/Voice, real Yousign, and RAG v2's retrieval/admin UI.
2. **RAG v2:** Phase 1 (schema + ingestion), Phase 2 (retrieval + gate + citations), Phase 3 (obsolescence) done. Phase 4 (admin API + UI: documents table, upload PDF, stats, QA test box) next.
3. Optional: real WhatsApp/Voice, EU hosting region instead of US.

**Sprint 4c / Campaigns are real** (Sprint 5's own Phase 1 backend + a scoped-down frontend, done together): channel-activation guard (`WHATSAPP`/`VOICE` → 422 `channel_not_activated`, `SMS` allowed), `POST /api/campaigns/{id}/preview` (dry-run launch count + disclosure preview), and the Campagnes screen itself — list with real data, create (name + channel + optional region target_rules), two-step launch (preview modal → start), pause/resume. **Fixed while wiring this up**: the previous CampaignsPage.tsx rendered fabricated numbers (hardcoded `34.2%` response rate, `1.8%` opt-out rate, `14 protégés`, `c.leads_count || 120`) instead of real API data — a compliance-adjacent honesty bug (AGENTS.md's own "no invented stats" rule), not just a stub; the frontend `CampaignSummary` type also didn't match the real backend schema at all (`status: "ACTIVE"` isn't a real value — it's `RUNNING`). Both fixed. **Not built**: the 3-step wizard (multi-select leads / CSV import with row-level validation), SSE live-supervisor layer, "Annuler" (no `CANCELLED` `CampaignStatus` value exists), a `campaign_member` mapping table (deliberately not added — `get_campaign_analytics` already derives sent/responded/qualified/opted-out live from `Lead.status`, a mapping table would just re-shadow that). Creation targets one optional region instead of a lead multi-select/CSV wizard — documented tradeoff, not an oversight.

## Workflow

Run the full test suite BEFORE and AFTER every change — keep it green. Small commits, one concern per branch. Update golden conversations when copy changes. Ask before architectural changes.

**AGENTS.md must be updated in the SAME commit as any sprint merge — doc drift is a defect, not an afterthought.** This file previously claimed SMS was unbuilt and Sprint 3 unstarted while both were live.

Never do line-surgery on Python files from PowerShell (regex/line-by-line shell edits) — it has caused bugs here. Rewrite the whole file instead.

All customer-facing text is trilingual fr/nl/en, with the compliance rules above.

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

**Migration trap:** tests build the schema with `Base.metadata.create_all()` on SQLite in-memory, and `migration_runner.py` skips SQL migrations on any non-postgresql dialect. A broken `.sql` migration therefore passes CI green and fails at boot on Render. Any new table needs BOTH a SQLAlchemy model AND a SQL migration, kept consistent by hand. Next migration number is **0011** (note: two files already share the `0007` prefix).

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
- Campaigns and Knowledge admin screens are still honest "Phase 2" stubs (Sprint 4 target).
- No manual lead creation endpoint (`POST /api/leads`) — only CSV import; `PATCH` and `DELETE` already exist.
- RAG is keyword-only. RAG v2 (vector) deferred — see below.
- NL copy has never been field-tested.
- README content has stale sections (it still claims contract generation is unimplemented) and carries a UTF-8 double-encoding corruption in its prose.

## Knowledge & RAG

`knowledge_corpus/` holds the official raw material (12 Sept-2026 tariff card PDFs FR+NL, terms, FAQ, regulators) — see `knowledge_corpus/README.md`.

**RAG v2 is DEFERRED and the spec must be written BEFORE any code.** Backlog and decisions: `docs/RAG_BACKLOG.md`. Vision: port the ZEN Knowledge patterns (publish-explicit, W3 obsolescence, citations validator, refusal-before-LLM) to FastAPI/Python. Settled decisions: pgvector on Neon; embeddings via API (Gemini/Mistral), no local models (Render free = 512 MB) except a measured `fastembed` prototype; source-of-truth hierarchy tariff card > terms > helpdesk > regulator > marketing; legacy keyword RAG kept during migration.

## Priority order

1. **Sprint 4:** make the three admin surfaces real — manual Leads CRUD, real Campaigns (wire the existing engine), Knowledge management (`knowledge_base.yaml` → `knowledge_entries` table + CRUD + active toggle). Remove stubs that become real; keep honest stubs for WhatsApp/Voice, real Yousign, and RAG v2.
2. **RAG v2:** spec first, then code.
3. Optional: real WhatsApp/Voice, EU hosting region instead of US.

## Workflow

Run the full test suite BEFORE and AFTER every change — keep it green. Small commits, one concern per branch. Update golden conversations when copy changes. Ask before architectural changes.

**AGENTS.md must be updated in the SAME commit as any sprint merge — doc drift is a defect, not an afterthought.** This file previously claimed SMS was unbuilt and Sprint 3 unstarted while both were live.

Never do line-surgery on Python files from PowerShell (regex/line-by-line shell edits) — it has caused bugs here. Rewrite the whole file instead.

All customer-facing text is trilingual fr/nl/en, with the compliance rules above.

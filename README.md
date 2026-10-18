# Sophie: Deterministic AI Sales Agent

![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088FF) ![Python](https://img.shields.io/badge/Python-3.12-3776AB) ![FastAPI](https://img.shields.io/badge/FastAPI-009688) ![React](https://img.shields.io/badge/React-18-61DAFB) ![License](https://img.shields.io/badge/License-MIT-green)

A conversational AI sales agent that qualifies leads for electricity and gas contracts. It engages prospects, handles objections, collects and validates required information, generates the contract, sends it for e-signature, and hands qualified leads to the human sales team.

**Author and architect:** Yosra Megbli ([github.com/Yosra-Megbli](https://github.com/Yosra-Megbli)): design, architecture, code and deployment. The repository is hosted under a family account.

## The key idea

Sophie is not a chatbot demo. A **deterministic state machine plus a declarative YAML rules engine** makes every dialogue and qualification decision. The LLM only phrases replies in natural language and **never decides a state transition or a qualification**. This makes the agent auditable, testable and predictable.

## Live demo

| Resource | Link |
|---|---|
| Ops dashboard | https://intelligent-sales-agent.onrender.com/dashboard/ (access key on request) |
| API health check | https://intelligent-sales-agent.onrender.com/health |
| Telegram bot | https://t.me/EcofixSalesBot |

Hosted on Render's free tier: the first load after inactivity can take 30 to 60 seconds.

## Features

- **Conversation engine:** pure state machine, YAML business rules, intent classifier, dialogue policy
- **Multi-channel:** Telegram and Web widget live; SMS operational; WhatsApp and outbound Voice (Twilio) fully wired, pending account activation
- **Outbound campaign engine** with mandatory preview and AI-disclosure message, pause/resume/cancel, live progress
- **Contract lifecycle:** PDF generation (ReportLab) and e-signature via Yousign (HMAC-secured webhooks, graceful degradation when not configured)
- **RAG v2:** pgvector semantic search, relevance threshold, citation validator, explicit publish step, obsolescence management
- **Ops dashboard (React):** KPIs, CRM, contracts, conversation replay, simulator, campaigns, compliance, knowledge base, live supervision (SSE)
- **Automated follow-ups:** silence detection and reminders
- **GDPR by design:** instant deterministic opt-out, data purge, retention rules

## Architecture

```
backend/
├── domain/                 Business models (Lead, Conversation, Campaign, ...)
├── conversation_engine/    Pure state machine, rules engine, intent classifier, dialogue policy
├── business_rules/         Declarative YAML rules (qualification, validation, follow-up)
├── ai/                     LLM abstraction (Groq), extraction, reply generation, embeddings
├── rag_v2/                 pgvector retrieval, citation validation, obsolescence
├── prompts/                Prompts as Markdown/YAML, never hard-coded
├── channels/               Per-channel adapters (Web, Telegram, SMS, WhatsApp, Voice)
├── outbound/               Campaign engine
├── followup/               Silence detection and automatic reminders
├── contracts/              PDF contract generation
├── integrations/           Yousign e-signature
├── live/                   Real-time supervision cockpit (SSE)
├── api/                    FastAPI routes, security, rate limiting, CORS
├── application/            Application services
└── tests/, golden_tests/   Unit, integration and end-to-end conversation scenarios

frontend/                   React 18 + Vite + TypeScript + TanStack Query + Tailwind
```

### Anti-hallucination layers

The simulator lets you exercise five protection layers against hallucination, including a final regex guard that rejects invented statistics and absolute promises.

## RAG v2

1. **Explicit publish:** every ingested document starts as `DRAFT` and stays invisible to the agent until manually published (`DRAFT → PUBLISHED → ARCHIVED`).
2. **Relevance gate:** cosine similarity search with a configurable threshold (`RAG_MIN_SIMILARITY`) and bounded retrieval (`RAG_TOP_K`). If nothing passes, the system falls back to keyword RAG, then to a deterministic trilingual (FR/NL/EN) refusal **without any LLM call**.
3. **Grounded generation:** context blocks are labeled `[SOURCE n]` with title, version and review date. The citation validator strips any reference not present in the context and logs it for audit.
4. **Obsolescence:** review dates are monitored, documents due within 7 days are flagged, and documents past the grace period are archived automatically, which removes their chunks from search immediately.
5. **Calibration:** a QA tester in the dashboard shows real similarity scores without calling the LLM, to tune the threshold.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy |
| Database | PostgreSQL + pgvector (Neon), HNSW cosine index |
| Cache / pub-sub | Redis (Upstash) |
| LLM | Groq (`openai/gpt-oss-120b` / Llama 3.3) behind a replaceable `LLMProvider` |
| Embeddings | Google `gemini-embedding-001` (768 dimensions) behind a replaceable `EmbeddingProvider` |
| Frontend | React 18, Vite, TypeScript, Tailwind, TanStack Query |
| Hosting | Render (Docker), Neon, Upstash |
| Tests | Pytest, 898 unit/integration tests plus golden conversation scenarios |

## Channels

| Channel | Status |
|---|---|
| Telegram | Live (secured webhook) |
| Web widget | Live |
| SMS | Operational (Twilio HMAC signature, STOP handling) |
| WhatsApp Business | Wired, inactive (awaiting Twilio keys) |
| Voice | Wired, inactive (full STT/TTS pipeline, awaiting number) |

## Security

- Sensitive routes protected by an `X-API-Key` header (constant-time comparison)
- Telegram, Twilio and Yousign webhooks verified by signature or shared secret (HMAC)
- CORS disabled by default; rate limiting per conversation and IP
- With `ENVIRONMENT=production`, the API refuses to start if `API_KEY` or `TELEGRAM_WEBHOOK_SECRET` is missing
- Secrets are never committed; client delivery archives are built with `git archive`

## GDPR

- **Legal basis:** consent and pre-contractual steps for inbound leads; legitimate interest for outbound campaigns, with immediate AI disclosure and an unconditional right to object
- **Retention:** 12 months maximum for non-converted prospects, then irreversible purge or anonymization
- **Opt-out:** `STOP`, `STOPT` or `ARRÊT` (case and accent insensitive) triggers an immediate, LLM-free process: removal from campaigns, cancelled reminders, PII purge, hashed suppression key to prevent re-import, audit log entry, single confirmation message
- **Minimization:** only the text strictly needed for qualification reaches the inference API; rule evaluation, age checks, duplicate detection and the suppression list run locally

## Getting started

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # set GROQ_API_KEY, DATABASE_URL, ...
uvicorn api.main:app --host 127.0.0.1 --port 8001
```

API docs: http://127.0.0.1:8001/docs · Health: http://127.0.0.1:8001/health

### Dashboard

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173, proxies /api to :8001
```

### Tests

```bash
cd backend
pytest tests/ golden_tests/ -v
```

A local Redis server is required: several tests use the real cache instead of a mock.

## Known limitations

- WhatsApp and Voice are architected, wired and tested but not activated until Twilio accounts are provisioned.
- French is the main language tested under pilot conditions; Dutch and English are covered by the engine (RAG v2, disclosure, opt-out).
- The embeddings provider runs on a free tier and should be monitored if volume grows.
- Cost and conversion figures in the project documentation are pilot estimates, not measured production results.

## Status

Deployed as a live pilot and demo, without real production load.

## License

MIT

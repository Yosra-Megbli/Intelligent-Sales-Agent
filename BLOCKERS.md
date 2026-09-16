# BLOCKERS.md — autonomous session, 2026-09-16

Per the mission's autonomy protocol: items skipped or scoped down during
the T0→T1→T2→T3→SWEEP autonomous run, and why. None of these are stop
conditions in the mission's own sense (no purity/architecture test was
touched, no irreversible data destruction, no missing credential blocked
anything) — they are scope/time judgment calls, recorded here as the
protocol also asks for.

## T3 — Campaigns

- **No 3-step wizard** (multi-select leads table / CSV import with
  row-level validation preview). Campaign creation targets one optional
  region (`target_rules: {"region": ...}`) instead. The backend already
  supports arbitrary `target_rules`; only the richer frontend selection UI
  is missing.
## Known pre-existing gaps, remaining after this session

Carried over from AGENTS.md, unchanged by this session:
- WhatsApp and Voice built but not activated (no Twilio credentials in Render).
- Yousign sandbox only (no real production e-signature key configured).
- Real-corpus ingestion pending `GOOGLE_AI_API_KEY` configuration in Render.
- `RAG_MIN_SIMILARITY` calibration on real prospect queries (default 0.30).
- NL copy never field-tested.
- Campaigns admin screen is real (list, create, two-step launch, pause/resume) but scoped down from original vision (no 3-step lead multi-select/CSV import wizard, no cancel).
- Manual lead creation endpoint (`POST /api/leads`) remaining (CSV import exists).

*Note: RAG v2 (Phases 2, 3, 4) and Sprint 5 (C1 SSE Live Backend + C2 Cockpit Frontend) are now fully completed and operational.*

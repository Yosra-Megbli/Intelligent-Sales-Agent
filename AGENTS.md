AGENTS.md — Intelligent Sales Agent "Sophie"
Context
AI sales agent ("Sophie") selling Belgian energy contracts (Ecofix context).Production-grade demo/portfolio. ALL demo prospect data is FICTIONAL — filesmust carry "SPÉCIMEN / DEMO — DONNÉES FICTIVES".

Architecture invariants (NEVER break)
Deterministic core: State Machine decides states; YAML Rules Engine decidesqualification & product pitch. The LLM (Groq) ONLY phrases sentences — itNEVER decides a state, qualification, or business action.
Channels: Telegram (live), Web (live), WhatsApp + Voice/Twilio (built, notactivated), SMS (not built).
CRM: PostgreSQL + Redis, find_duplicate(), campaigns, follow-ups.
Tests: ~583 + golden conversations + separate real-LLM eval (not in CI).
Golden rules (compliance — mandatory in all copy/prompts)
Every FIRST outbound message & every call opening MUST contain explicit AIdisclosure + human-handover offer + opt-out hint:FR: "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle)d'Ecofix — un conseiller humain reste disponible à tout moment."NL: "Dag, hier is Sophie, de virtuele assistent (AI) van Ecofix — eenmenselijke adviseur neemt op elk moment over als u dat liever heeft."EN: "Hi, this is Sophie, a virtual assistant (AI) for Ecofix — a humanadvisor is available at any time."
STOP/STOPT/ARRÊT = immediate opt-out: leave campaign, purge PII, keep onlya suppression key.
NEVER invent stats ("jusqu'à 20%"), absolute promises ("jamais trop payer","nooit te veel"), or market predictions. Sell FREEDOM (no exit fees,transparent monthly revision).
Grid operators: Flanders=Fluvius, Wallonia=ORES/RESA. Never mixed. NoBrussels (supplier absent there).
Product facts: NO fixed contracts (deliberate). Flexy=variable monthly,Motion=dynamic hourly (pitch if has_ev/has_heat_pump/has_battery). Platformfee €5.99/mo. Friends with Benefits: €5/mo per active referral. Noresidential cancellation fees in BE. Switch 3–4 weeks. 14-day withdrawal.
Always vouvoiement (FR) / u-form (NL). FIXED_SEEKER: max 1 reframe → politerefusal, save status, do_not_pitch_variable=true.
Never ask Rijksregisternummer. EAN = 18 digits starting with 5414.
Known gaps (never claim "done")
Contract generation/signature (states CONTRACT/CUSTOMER empty); date_of_birthin DB but NOT in qualification_rules.yaml; no SMS; AI-disclosure not yet inprompts; no GDPR docs; dashboard lacks cost-per-sale & CA; NL not field-tested.

Priority order
Sprint 1 (compliance): disclosure strings in all channels + guard tests;STOP handler + purge + suppression list + tests; date_of_birth intoqualification_rules.yaml + golden tests; GDPR section in README.
Sprint 2: SMS (Twilio); dashboard cost-per-conversation/sale + estimated CA;language detection stored on lead.
Sprint 3: contract PDF (SPÉCIMEN) + e-signature sandbox → fillCONTRACT/CUSTOMER states.
Frontend direction (Vision UI)
Full professional UI allowed, including not-yet-implemented features — but anynon-implemented control must be an honest stub: badge "Phase 2", click →elegant toast ("Disponible en Phase 2"), never a dead silent button.Tokens: green oklch(60% .14 160) on oklch(97.5% .004 250), radius .75rem,Inter + JetBrains Mono (EAN), tabular-nums, i18n fr(default)/nl/en scaffoldfrom day 1. No violet AI gradients, no emojis in UI, skeletons not spinners.

Workflow
Run full test suite before AND after every change — keep it green. Smallcommits, one concern per branch. Update golden conversations when copychanges. Ask before architectural changes.
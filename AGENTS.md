AGENTS.md — Intelligent Sales Agent "Sophie"
Context
AI sales agent ("Sophie") selling Belgian energy contracts (Ecofix context).Production-grade demo/portfolio. ALL demo prospect data is FICTIONAL — filesmust carry "SPÉCIMEN / DEMO — DONNÉES FICTIVES".

Architecture invariants (NEVER break)
Deterministic core: State Machine decides states; YAML Rules Engine decidesqualification & product pitch. The LLM (Groq) ONLY phrases sentences — itNEVER decides a state, qualification, or business action.
Channels: Telegram (live), Web (live), WhatsApp + Voice/Twilio (built, notactivated), SMS (not built).
CRM: PostgreSQL + Redis, find_duplicate(), campaigns, follow-ups.
Tests: 752 passed + golden conversations + separate real-LLM eval (not in CI).
Golden rules (compliance — mandatory in all copy/prompts)
Every FIRST outbound message & every call opening MUST contain explicit AIdisclosure + human-handover offer + opt-out hint:FR: "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle)d'Ecofix — un conseiller humain reste disponible à tout moment."NL: "Dag, hier is Sophie, de virtuele assistent (AI) van Ecofix — eenmenselijke adviseur neemt op elk moment over als u dat liever heeft."EN: "Hi, this is Sophie, a virtual assistant (AI) for Ecofix — a humanadvisor is available at any time."
STOP/STOPT/ARRÊT = immediate opt-out: leave campaign, purge PII, keep onlya suppression key.
NEVER invent stats ("jusqu'à 20%"), absolute promises ("jamais trop payer","nooit te veel"), or market predictions. Sell FREEDOM (no exit fees,transparent monthly revision).
Grid operators: Flanders=Fluvius, Wallonia=ORES/RESA. Never mixed. NoBrussels (supplier absent there).
Regulatory: CWaPE granted Ecofix general electricity & gas supply licenses for Wallonia on 2025-04-03. Flanders regulator: VREG (v-test.vreg.be official comparison). Brussels: BRUGEL zone — not served by Ecofix.
Product facts: NO fixed contracts (deliberate). Products: Flexy (variable monthly), Motion (dynamic hourly — pitch if has_ev/has_heat_pump/has_battery), Flexy Online, Motion Online (Online variants ~10€/yr fixed fee, app-managed). Features: Smart Control & Smart Integration available since T2 2026 per tariff card margin notes. Pricing truth: Frais fixes (obligatoire) = 60,00 €/an (part of Prix de l'énergie); Ecofix Digi = 5,99 €/mois (OPTIONNEL digital app add-on for consumption tracking and smart control, NEVER base fee or obligatory); Friends with Benefits = referral program (€5/mo discount per active referral, no cap). No residential cancellation fees in BE. Switch 3–4 weeks. 14-day withdrawal. Pricing truth verified against Sept 2026 tariff card on 2026-09-16.
Engine fixes: Location loop fixed (flandre → ASK_CITY_ONLY with generalized consecutive_same_ask guard).
Knowledge & RAG: knowledge_corpus/ folder documented. RAG v2 DEFERRED — vision: port ZEN Knowledge patterns (reference: user's zen-knowledge project — publish-explicit, W3 obsolescence, citations validator, refusal-before-LLM) phased, spec first.
Always vouvoiement (FR) / u-form (NL). FIXED_SEEKER: max 1 reframe → politerefusal, save status, do_not_pitch_variable=true.
Never ask Rijksregisternummer. EAN = 18 digits starting with 5414.
Known gaps (never claim "done")
Contract generation/signature (states CONTRACT/CUSTOMER empty); no SMS; dashboard lacks cost-per-sale & CA; NL not field-tested.

Priority order
Sprint 1 (compliance): disclosure strings in all channels + guard tests;STOP handler + purge + suppression list + tests; date_of_birth intoqualification_rules.yaml + golden tests; GDPR section in README.
Sprint 2: SMS (Twilio); dashboard cost-per-conversation/sale + estimated CA;language detection stored on lead.
Sprint 3: contract PDF (SPÉCIMEN) + e-signature sandbox → fillCONTRACT/CUSTOMER states.
Frontend direction (Vision UI)
Full professional UI allowed, including not-yet-implemented features — but anynon-implemented control must be an honest stub: badge "Phase 2", click →elegant toast ("Disponible en Phase 2"), never a dead silent button.Tokens: green oklch(60% .14 160) on oklch(97.5% .004 250), radius .75rem,Inter + JetBrains Mono (EAN), tabular-nums, i18n fr(default)/nl/en scaffoldfrom day 1. No violet AI gradients, no emojis in UI, skeletons not spinners.

Workflow
Run full test suite before AND after every change — keep it green. Smallcommits, one concern per branch. Update golden conversations when copychanges. Ask before architectural changes.
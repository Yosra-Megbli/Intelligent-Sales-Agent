# Knowledge Corpus — Ecofix Gas & Power

Raw source material for future RAG v2 ingestion — **DEFERRED work**.

Documents in this corpus are public official Ecofix and regulator documents collected for reference, contract verification, and future automated ingestion into an expanded retrieval-augmented generation pipeline.

> [!IMPORTANT]
> **DO NOT ingest anything into the active RAG engine from this directory.**
> The active sales engine operates on deterministic state machine rules and the curated declarative knowledge base at `backend/ai/knowledge_base.yaml`. This repository serves solely as raw source material storage.

---

## Trust Hierarchy

When resolving conflicts between documents during future RAG v2 design and ingestion, adhere strictly to the following trust hierarchy (highest authority first):

```
Tariff Card  >  Conditions Générales  >  Helpdesk  >  Regulator  >  Marketing
 (Highest)                                                         (Lowest)
```

1. **Tariff Card (`tariffs/`)** (Highest Authority):
   - Official monthly tariff cards published on `portal.ecofixgp.be/docs/prices/current/`.
   - Authoritative for exact pricing components: fixed subscription fees (frais fixes obligatoires : 60,00 €/an), indexation formulas, kWh rates, margin parameters, and optional Digi app pricing.
2. **Conditions Générales (`contracts/`)**:
   - Official general supply terms (*Algemene Voorwaarden*).
   - Authoritative for contractual rights, 14-day legal withdrawal rules, payment terms, and legal termination procedures.
3. **Helpdesk / FAQ (`faq/`)**:
   - Practical operational explanations of onboarding, moving, meter readings, and billing cycles.
4. **Regulator (`regulatory/`)**:
   - CWaPE (Wallonia license dated 2025-04-03, ORES/RESA grid rules), CREG (federal market oversight and price structure guidelines), BRUGEL (Brussels absence / coverage boundary confirmation).
5. **Marketing (`marketing/`)** (Lowest Authority):
   - Product feature brochures, Friends with Benefits referral details, and app descriptions. Subordinate to tariff cards and contractual terms.

---

## Directory Structure & Catalog

```
knowledge_corpus/
├── README.md
├── tariffs/
│   └── 2026-09/                                # Official Sept 2026 tariff cards (PDFs)
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
│   ├── helpdesk_klant_worden.md                # Helpdesk: becoming a customer & onboarding
│   ├── helpdesk_tarieven_producten.md          # Helpdesk: rates, products, and fees explanation
│   ├── helpdesk_facturen_betalen.md            # Helpdesk: invoices, advance payments, settlements
│   ├── helpdesk_wijzigingen_contracten.md      # Helpdesk: contract changes, moving, termination
│   └── overstappen.md                          # Guide: switching suppliers in Belgium without fees
├── marketing/
│   ├── friends_with_benefits.md                # Referral program (€5/mo discount, no cap)
│   └── ecofix_digi_app.md                      # Ecofix Digi optional add-on (€5.99/mo, smart control)
└── regulatory/
    ├── cwape_wallonia_license.md               # CWaPE license (2025-04-03) & Wallonia grid operators
    ├── creg_market_report.md                   # CREG federal market monitoring & transparency rules
    └── brugel_regulatory_overview.md           # BRUGEL: Brussels regional market & out-of-coverage
```

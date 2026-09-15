# Sophie â€” Agent IA de vente Ecofix

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Vite%20%2B%20TS-61DAFB?logo=react&logoColor=black)
![Tests](https://img.shields.io/badge/tests-655%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

Sophie est un agent conversationnel IA qui qualifie des prospects pour des contrats d'أ©lectricitأ© et de gaz Ecofix : elle engage la conversation, rأ©pond aux objections, collecte et valide les informations nأ©cessaires, puis transmet les leads qualifiأ©s أ  l'أ©quipe commerciale humaine.

## In short (EN)

A production-shaped AI sales agent, not a chatbot demo: a deterministic state machine + declarative YAML rules engine owns every dialogue/qualification decision â€” the LLM (Groq/Llama) only phrases replies in natural language, it never decides a state transition. Multi-channel (Telegram + Web live; WhatsApp and outbound Voice fully wired end-to-end via Twilio, pending activation), with an outbound campaign engine, a React ops dashboard, API-key/webhook-signature security, and **655 automated tests** including end-to-end golden conversation scenarios. See below (French) for full docs â€” this project is built for a real French-speaking client.

## Statut du projet

**Sophie qualifie des leads et les transmet أ  un commercial humain. Elle ne gأ©nأ¨re pas encore de contrat signأ©.**

Le cycle de vie d'un lead (`domain/enums.py::LeadStatus`) prأ©voit des statuts `CONTRACT` et `CUSTOMER` pour une vente entiأ¨rement conclue, mais rien dans le code actuel ne les atteint. Le parcours rأ©ellement implأ©mentأ© est :

```
QUALIFIED â†’ (transfert humain dأ©clenchأ©) â†’ APPOINTMENT
```

Gأ©nأ©ration de contrat, signature أ©lectronique et envoi de confirmation **ne sont pas implأ©mentأ©s** dans cette version. Toute mأ©trique du dashboard intitulأ©e "conversion" ou "vente" reflأ¨te une qualification, pas une vente conclue â€” voir `application/dashboard_service.py`.

## Architecture

```
backend/                      API Python/FastAPI
â”œâ”€â”€ domain/                   Modأ¨les mأ©tier (Lead, Conversation, Message, Campaign, Activity) + enums
â”œâ”€â”€ conversation_engine/      State machine pure + Rules Engine (YAML) + Intent Classifier + Dialogue Policy
â”œâ”€â”€ business_rules/           Rأ¨gles dأ©claratives en YAML (qualification, validation, follow-up...)
â”œâ”€â”€ ai/                       Abstraction LLM (Groq), extraction, gأ©nأ©ration de rأ©ponse, RAG
â”œâ”€â”€ prompts/                  Prompts en Markdown/YAML (jamais codأ©s en dur en Python)
â”œâ”€â”€ crm/                      Repositories (leads, conversations, activitأ©s, campagnes)
â”œâ”€â”€ channels/                 Adaptateurs par canal (Web, Telegram ; WhatsApp/Voice prأھts, non activأ©s)
â”œâ”€â”€ outbound/                 Moteur de campagnes sortantes
â”œâ”€â”€ followup/                 Dأ©tection de silence + relances automatiques
â”œâ”€â”€ api/                      Routes FastAPI, sأ©curitأ© (clأ© API, rate limiting, CORS)
â”œâ”€â”€ application/              Services applicatifs (orchestrent domain + conversation_engine + crm)
â”œâ”€â”€ dashboard/                Build compilأ© du dashboard React, servi en statique par FastAPI
â”œâ”€â”€ docs/                     Documentation d'architecture (state machine, decisions techniques)
â””â”€â”€ tests/ + golden_tests/    Suite de tests unitaires/intأ©gration + scأ©narios de conversation bout-en-bout

frontend/
â”œâ”€â”€ artifacts/sophie-dashboard/   Dashboard React (Vite + Tailwind + shadcn/ui + TanStack Query)
â”œâ”€â”€ artifacts/api-server/         Proxy Node/Express (prod) : masque la clأ© API au navigateur
â””â”€â”€ lib/                          Client API gأ©nأ©rأ© depuis lib/api-spec/openapi.yaml
```

**Principe central** : le moteur mأ©tier (state machine + rأ¨gles YAML) dأ©cide seul de l'أ©tat de la conversation et du statut du lead. Le LLM ne fait que formuler les rأ©ponses en langage naturel â€” il ne dأ©cide jamais d'une transition d'أ©tat ni d'une qualification.

## Stack technique

- Backend : Python 3.12+, FastAPI, SQLAlchemy, PostgreSQL (SQLite pour les tests), Redis
- IA : Groq (`openai/gpt-oss-120b` par dأ©faut), abstraction `LLMProvider` remplaأ§able
- Frontend : React, Vite, TypeScript, Tailwind v4, shadcn/ui, TanStack Query
- Tests : Pytest (655 tests unitaires/intأ©gration + scأ©narios golden)

## Dأ©marrage rapide â€” backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # puis renseigner GROQ_API_KEY, DATABASE_URL, etc.
uvicorn api.main:app --host 127.0.0.1 --port 8001
```

Le port `8001` n'est pas arbitraire : c'est celui que le dashboard React attend
(`frontend/artifacts/sophie-dashboard/vite.config.ts` proxy `/api` dessus en dev).

- Documentation API interactive : http://127.0.0.1:8001/docs
- Healthcheck : http://127.0.0.1:8001/health

## Dأ©marrage rapide â€” dashboard React

```bash
cd frontend
pnpm install
pnpm --filter sophie-dashboard dev   # http://localhost:5173, proxy /api -> localhost:8001
```

En production, le dashboard passe par `frontend/artifacts/api-server` (proxy Node/Express) qui injecte la clأ© API cأ´tأ© serveur, pour ne jamais l'exposer au navigateur.

## Migrations DB

Ce projet n'a pas d'Alembic : `database/postgres.py` appelle uniquement
`Base.metadata.create_all()` au dأ©marrage, qui crأ©e les tables manquantes
mais ne modifie jamais une table existante. Un changement de schأ©ma sur une
table dأ©jأ  crأ©أ©e (nouvelle colonne, nouvel index...) nأ©cessite donc un
`ALTER TABLE` manuel, en plus du changement dans `domain/models/`.

Les scripts SQL correspondants vivent dans `backend/database/migrations/`,
numأ©rotأ©s dans l'ordre oأ¹ ils doivent أھtre appliquأ©s :

```bash
psql "$DATABASE_URL" -f backend/database/migrations/0001_add_telegram_chat_id.sql
```

Sur une base de dev jetable (recrأ©أ©e أ  chaque fois), ce n'est pas
nأ©cessaire : `docker compose down -v && docker compose up -d` puis un
redأ©marrage du backend suffit, `create_all()` crأ©e alors le schأ©ma أ  jour
directement.

## Tests

```bash
cd backend
pytest tests/ golden_tests/ -v
```

## Canaux

| Canal | Statut |
|---|---|
| Telegram | Actif et testأ© â€” canal du pilote |
| Web (widget) | Actif et testأ© |
| WhatsApp Business | Architecturأ© et testأ© (`channels/whatsapp.py`, signature Twilio), non activأ© pour le pilote actuel |
| Appel vocal | Pipeline complet cأ¢blأ© (`application/voice_inbound_service.py` + `channels/voice/session_manager.py`, STT/TTS Twilio) ; il ne manque qu'un compte Twilio Voice rأ©el (`TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_VOICE_NUMBER`/`PUBLIC_BASE_URL`) pour un appel en conditions rأ©elles â€” voir `docs/architecture/voice_agent_architecture.md` |
| SMS, Messenger, Instagram | Non implأ©mentأ©s â€” roadmap |

## Sأ©curitأ©

- Toutes les routes API sensibles (conversations, dashboard, campagnes) protأ©gأ©es par une clأ© `X-API-Key` (comparaison أ  temps constant)
- Webhook Telegram vأ©rifiأ© par secret partagأ©
- CORS dأ©sactivأ© par dأ©faut (safe-by-default), أ  configurer explicitement via `CORS_ALLOWED_ORIGINS`
- Rate limiting appliquأ© par conversation/IP
- âڑ ï¸ڈ Par dأ©faut (dأ©veloppement), si `API_KEY` n'est pas configurأ©e, l'authentification est dأ©sactivأ©e avec un avertissement en log
- âœ… En dأ©finissant `ENVIRONMENT=production` (voir `backend/.env.example`), l'API **refuse de dأ©marrer** si `API_KEY` ou `TELEGRAM_WEBHOOK_SECRET` ne sont pas configurأ©es, au lieu de tourner sans authentification (`api/main.py:_fail_fast_if_misconfigured_for_production`)
- `backend/.env` (secrets rأ©els) est exclu de git via `.gitignore` et n'a jamais أ©tأ© commit â€” pour livrer une archive au client, utiliser `scripts/package_client_delivery.ps1` (basأ© sur `git archive`, ne peut physiquement pas inclure un fichier non commit comme `.env`) plutأ´t qu'une compression manuelle du dossier

## Conformitأ© RGPD / GDPR Compliance

Sophie intأ¨gre les principes du Rأ¨glement Gأ©nأ©ral sur la Protection des Donnأ©es (RGPD / GDPR) dأ¨s la conception (*privacy by design*) :

### 1. Bases lأ©gales de traitement (Art. 6 RGPD)
- **Leads entrants (Inbound)** : Consentement explicite et exأ©cution de mesures prأ©contractuelles أ  la demande du prospect (Art. 6(1)(a) & (b) RGPD) lors de l'initiation d'un أ©change pour أ©tudier ou souscrire une offre d'أ©nergie Ecofix.
- **Campagnes sortantes (Outbound)** : Intأ©rأھt lأ©gitime (Art. 6(1)(f) RGPD) pour la prospection commerciale B2B / prospects qualifiأ©s, assorti d'une **transparence obligatoire et immأ©diate** (mention explicite de l'agent virtuel IA dأ¨s le premier message sur tous les canaux) et du droit inconditionnel d'opposition (Art. 21 RGPD).

### 2. Durأ©e de conservation (Rأ¨gle des 12 mois)
- Les donnأ©es أ  caractأ¨re personnel des prospects non convertis sont conservأ©es pendant une durأ©e maximale de **12 mois** أ  compter du dernier contact ou de la clأ´ture de la qualification.
- أ€ l'issue de cette pأ©riode de 12 mois, les donnأ©es d'identification (`first_name`, `last_name`, `email`, `phone`, `notes`, `date_of_birth`) sont purgأ©es ou anonymisأ©es de maniأ¨re irrأ©versible, sauf en cas de conversion effective en contrat client actif (soumis aux dأ©lais lأ©gaux de conservation contractuelle et comptable).

### 3. Procأ©dure d'opt-out / droit d'opposition (STOP / STOPT / ARRأٹT)
- Le prospect peut أ  tout moment exercer son droit d'opposition par simple envoi d'un mot-clأ© d'arrأھt standardisأ© : **`STOP`**, **`STOPT`** ou **`ARRأٹT`** (insensible أ  la casse et aux accents, supportأ© en franأ§ais, nأ©erlandais et anglais).
- Le traitement d'opt-out est **immأ©diat et dأ©terministe** (gأ©rأ© au niveau applicatif par le Rules Engine / ConversationService, sans dأ©pendance LLM) :
  1. **Retrait immأ©diat des campagnes** : le lead est retirأ© de toute campagne sortante active ou future (`campaign_id = NULL`).
  2. **Annulation des relances programmأ©es** : tout follow-up programmأ© est annulأ© ; le planificateur de relances (`FollowUpEngine`) ignore systأ©matiquement tout prospect ayant manifestأ© son opposition (`opt_out_at IS NOT NULL`).
  3. **Purge des donnأ©es PII** : suppression immأ©diate des donnأ©es identifiantes directes (`first_name`, `last_name`, `email`, `notes`, `date_of_birth`).
  4. **Clأ© de suppression (Suppression Key)** : conservation d'une clأ© technique de suppression / empreinte hashأ©e afin d'empأھcher toute rأ©importation ou rأ©envoi ultأ©rieur non sollicitأ©.
  5. **Horodatage et audit trail** : enregistrement de l'horodatage UTC (`opt_out_at`), mise أ  jour du statut en `REJECTED` et inscription d'un أ©vأ©nement `OPT_OUT` dans le journal d'activitأ© d'audit (`activities`).
  6. **Confirmation de dأ©sabonnement** : envoi d'un message unique de confirmation attestant la prise en compte de la demande et garantissant qu'aucune communication ultأ©rieure ne sera أ©mise.

### 4. Transfert de donnأ©es & DPA Groq (Sous-traitance IA)
- Les requأھtes d'extraction d'entitأ©s et de formulation de rأ©ponses s'appuient sur l'API Groq Cloud.
- **Accord de traitement des donnأ©es (DPA)** : l'exploitation en production nأ©cessite la souscription du Data Processing Agreement (DPA) avec Groq Inc., incorporant les Clauses Contractuelles Types (CCT / SCCs) approuvأ©es par la Commission Europأ©enne pour rأ©gir les transferts de donnأ©es hors Union Europأ©enne.
- **Minimisation des donnأ©es (Art. 5(1)(c) RGPD)** : seuls les fragments textuels strictement nأ©cessaires أ  la qualification conversationnelle transitent par l'API d'infأ©rence. L'أ©valuation des rأ¨gles mأ©tier, la validation de la majoritأ©, la dأ©tection des doublons et la liste d'exclusion (suppression list) s'exأ©cutent entiأ¨rement en local dans l'application.

## Limites connues du MVP actuel

- Pas de gأ©nأ©ration/signature de contrat automatique (roadmap)
- Pas de canal SMS, Messenger, Instagram, Meta Ads (roadmap)
- WhatsApp et Voice sont architecturأ©s mais non activأ©s dans le pilote (voir tableau des canaux)
- Nأ©erlandais/Anglais : أ  confirmer/أ©tendre selon les besoins du pilote (le franأ§ais est le canal principal actuellement testأ©)


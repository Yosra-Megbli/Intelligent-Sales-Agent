# Sophie — Agent IA de vente Ecofix

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Vite%20%2B%20TS-61DAFB?logo=react&logoColor=black)
![Tests](https://img.shields.io/badge/tests-653%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

Sophie est un agent conversationnel IA qui qualifie des prospects pour des contrats d'électricité et de gaz Ecofix : elle engage la conversation, répond aux objections, collecte et valide les informations nécessaires, puis transmet les leads qualifiés à l'équipe commerciale humaine.

## In short (EN)

A production-shaped AI sales agent, not a chatbot demo: a deterministic state machine + declarative YAML rules engine owns every dialogue/qualification decision — the LLM (Groq/Llama) only phrases replies in natural language, it never decides a state transition. Multi-channel (Telegram + Web live; WhatsApp and outbound Voice fully wired end-to-end via Twilio, pending activation), with an outbound campaign engine, a React ops dashboard, API-key/webhook-signature security, and **653 automated tests** including end-to-end golden conversation scenarios. See below (French) for full docs — this project is built for a real French-speaking client.

## Statut du projet

**Sophie qualifie des leads et les transmet à un commercial humain. Elle ne génère pas encore de contrat signé.**

Le cycle de vie d'un lead (`domain/enums.py::LeadStatus`) prévoit des statuts `CONTRACT` et `CUSTOMER` pour une vente entièrement conclue, mais rien dans le code actuel ne les atteint. Le parcours réellement implémenté est :

```
QUALIFIED → (transfert humain déclenché) → APPOINTMENT
```

Génération de contrat, signature électronique et envoi de confirmation **ne sont pas implémentés** dans cette version. Toute métrique du dashboard intitulée "conversion" ou "vente" reflète une qualification, pas une vente conclue — voir `application/dashboard_service.py`.

## Architecture

```
backend/                      API Python/FastAPI
├── domain/                   Modèles métier (Lead, Conversation, Message, Campaign, Activity) + enums
├── conversation_engine/      State machine pure + Rules Engine (YAML) + Intent Classifier + Dialogue Policy
├── business_rules/           Règles déclaratives en YAML (qualification, validation, follow-up...)
├── ai/                       Abstraction LLM (Groq), extraction, génération de réponse, RAG
├── prompts/                  Prompts en Markdown/YAML (jamais codés en dur en Python)
├── crm/                      Repositories (leads, conversations, activités, campagnes)
├── channels/                 Adaptateurs par canal (Web, Telegram ; WhatsApp/Voice prêts, non activés)
├── outbound/                 Moteur de campagnes sortantes
├── followup/                 Détection de silence + relances automatiques
├── api/                      Routes FastAPI, sécurité (clé API, rate limiting, CORS)
├── application/              Services applicatifs (orchestrent domain + conversation_engine + crm)
├── dashboard/                Build compilé du dashboard React, servi en statique par FastAPI
├── docs/                     Documentation d'architecture (state machine, decisions techniques)
└── tests/ + golden_tests/    Suite de tests unitaires/intégration + scénarios de conversation bout-en-bout

frontend/
├── artifacts/sophie-dashboard/   Dashboard React (Vite + Tailwind + shadcn/ui + TanStack Query)
├── artifacts/api-server/         Proxy Node/Express (prod) : masque la clé API au navigateur
└── lib/                          Client API généré depuis lib/api-spec/openapi.yaml
```

**Principe central** : le moteur métier (state machine + règles YAML) décide seul de l'état de la conversation et du statut du lead. Le LLM ne fait que formuler les réponses en langage naturel — il ne décide jamais d'une transition d'état ni d'une qualification.

## Stack technique

- Backend : Python 3.12+, FastAPI, SQLAlchemy, PostgreSQL (SQLite pour les tests), Redis
- IA : Groq (`openai/gpt-oss-120b` par défaut), abstraction `LLMProvider` remplaçable
- Frontend : React, Vite, TypeScript, Tailwind v4, shadcn/ui, TanStack Query
- Tests : Pytest (653 tests unitaires/intégration + scénarios golden)

## Démarrage rapide — backend

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

## Démarrage rapide — dashboard React

```bash
cd frontend
pnpm install
pnpm --filter sophie-dashboard dev   # http://localhost:5173, proxy /api -> localhost:8001
```

En production, le dashboard passe par `frontend/artifacts/api-server` (proxy Node/Express) qui injecte la clé API côté serveur, pour ne jamais l'exposer au navigateur.

## Migrations DB

Ce projet n'a pas d'Alembic : `database/postgres.py` appelle uniquement
`Base.metadata.create_all()` au démarrage, qui crée les tables manquantes
mais ne modifie jamais une table existante. Un changement de schéma sur une
table déjà créée (nouvelle colonne, nouvel index...) nécessite donc un
`ALTER TABLE` manuel, en plus du changement dans `domain/models/`.

Les scripts SQL correspondants vivent dans `backend/database/migrations/`,
numérotés dans l'ordre où ils doivent être appliqués :

```bash
psql "$DATABASE_URL" -f backend/database/migrations/0001_add_telegram_chat_id.sql
```

Sur une base de dev jetable (recréée à chaque fois), ce n'est pas
nécessaire : `docker compose down -v && docker compose up -d` puis un
redémarrage du backend suffit, `create_all()` crée alors le schéma à jour
directement.

## Tests

```bash
cd backend
pytest tests/ golden_tests/ -v
```

## Canaux

| Canal | Statut |
|---|---|
| Telegram | Actif et testé — canal du pilote |
| Web (widget) | Actif et testé |
| WhatsApp Business | Architecturé et testé (`channels/whatsapp.py`, signature Twilio), non activé pour le pilote actuel |
| Appel vocal | Pipeline complet câblé (`application/voice_inbound_service.py` + `channels/voice/session_manager.py`, STT/TTS Twilio) ; il ne manque qu'un compte Twilio Voice réel (`TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_VOICE_NUMBER`/`PUBLIC_BASE_URL`) pour un appel en conditions réelles — voir `docs/architecture/voice_agent_architecture.md` |
| SMS, Messenger, Instagram | Non implémentés — roadmap |

## Sécurité

- Toutes les routes API sensibles (conversations, dashboard, campagnes) protégées par une clé `X-API-Key` (comparaison à temps constant)
- Webhook Telegram vérifié par secret partagé
- CORS désactivé par défaut (safe-by-default), à configurer explicitement via `CORS_ALLOWED_ORIGINS`
- Rate limiting appliqué par conversation/IP
- ⚠️ Par défaut (développement), si `API_KEY` n'est pas configurée, l'authentification est désactivée avec un avertissement en log
- ✅ En définissant `ENVIRONMENT=production` (voir `backend/.env.example`), l'API **refuse de démarrer** si `API_KEY` ou `TELEGRAM_WEBHOOK_SECRET` ne sont pas configurées, au lieu de tourner sans authentification (`api/main.py:_fail_fast_if_misconfigured_for_production`)
- `backend/.env` (secrets réels) est exclu de git via `.gitignore` et n'a jamais été commit — pour livrer une archive au client, utiliser `scripts/package_client_delivery.ps1` (basé sur `git archive`, ne peut physiquement pas inclure un fichier non commit comme `.env`) plutôt qu'une compression manuelle du dossier

## Conformité RGPD / GDPR Compliance

Sophie intègre les principes du Règlement Général sur la Protection des Données (RGPD / GDPR) dès la conception (*privacy by design*) :

### 1. Bases légales de traitement (Art. 6 RGPD)
- **Leads entrants (Inbound)** : Consentement explicite et exécution de mesures précontractuelles à la demande du prospect (Art. 6(1)(a) & (b) RGPD) lors de l'initiation d'un échange pour étudier ou souscrire une offre d'énergie Ecofix.
- **Campagnes sortantes (Outbound)** : Intérêt légitime (Art. 6(1)(f) RGPD) pour la prospection commerciale B2B / prospects qualifiés, assorti d'une **transparence obligatoire et immédiate** (mention explicite de l'agent virtuel IA dès le premier message sur tous les canaux) et du droit inconditionnel d'opposition (Art. 21 RGPD).

### 2. Durée de conservation (Règle des 12 mois)
- Les données à caractère personnel des prospects non convertis sont conservées pendant une durée maximale de **12 mois** à compter du dernier contact ou de la clôture de la qualification.
- À l'issue de cette période de 12 mois, les données d'identification (`first_name`, `last_name`, `email`, `phone`, `notes`, `date_of_birth`) sont purgées ou anonymisées de manière irréversible, sauf en cas de conversion effective en contrat client actif (soumis aux délais légaux de conservation contractuelle et comptable).

### 3. Procédure d'opt-out / droit d'opposition (STOP / STOPT / ARRÊT)
- Le prospect peut à tout moment exercer son droit d'opposition par simple envoi d'un mot-clé d'arrêt standardisé : **`STOP`**, **`STOPT`** ou **`ARRÊT`** (insensible à la casse et aux accents, supporté en français, néerlandais et anglais).
- Le traitement d'opt-out est **immédiat et déterministe** (géré au niveau applicatif par le Rules Engine / ConversationService, sans dépendance LLM) :
  1. **Retrait immédiat des campagnes** : le lead est retiré de toute campagne sortante active ou future (`campaign_id = NULL`).
  2. **Annulation des relances programmées** : tout follow-up programmé est annulé ; le planificateur de relances (`FollowUpEngine`) ignore systématiquement tout prospect ayant manifesté son opposition (`opt_out_at IS NOT NULL`).
  3. **Purge des données PII** : suppression immédiate des données identifiantes directes (`first_name`, `last_name`, `email`, `notes`, `date_of_birth`).
  4. **Clé de suppression (Suppression Key)** : conservation d'une clé technique de suppression / empreinte hashée afin d'empêcher toute réimportation ou réenvoi ultérieur non sollicité.
  5. **Horodatage et audit trail** : enregistrement de l'horodatage UTC (`opt_out_at`), mise à jour du statut en `REJECTED` et inscription d'un événement `OPT_OUT` dans le journal d'activité d'audit (`activities`).
  6. **Confirmation de désabonnement** : envoi d'un message unique de confirmation attestant la prise en compte de la demande et garantissant qu'aucune communication ultérieure ne sera émise.

### 4. Transfert de données & DPA Groq (Sous-traitance IA)
- Les requêtes d'extraction d'entités et de formulation de réponses s'appuient sur l'API Groq Cloud.
- **Accord de traitement des données (DPA)** : l'exploitation en production nécessite la souscription du Data Processing Agreement (DPA) avec Groq Inc., incorporant les Clauses Contractuelles Types (CCT / SCCs) approuvées par la Commission Européenne pour régir les transferts de données hors Union Européenne.
- **Minimisation des données (Art. 5(1)(c) RGPD)** : seuls les fragments textuels strictement nécessaires à la qualification conversationnelle transitent par l'API d'inférence. L'évaluation des règles métier, la validation de la majorité, la détection des doublons et la liste d'exclusion (suppression list) s'exécutent entièrement en local dans l'application.

## Limites connues du MVP actuel

- Pas de génération/signature de contrat automatique (roadmap)
- Pas de canal SMS, Messenger, Instagram, Meta Ads (roadmap)
- WhatsApp et Voice sont architecturés mais non activés dans le pilote (voir tableau des canaux)
- Néerlandais/Anglais : à confirmer/étendre selon les besoins du pilote (le français est le canal principal actuellement testé)

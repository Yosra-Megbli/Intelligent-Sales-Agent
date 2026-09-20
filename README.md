# Sophie — Agent IA de vente Ecofix

[![CI](https://github.com/Yosra-Megbli/Intelligent-Sales-Agent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Yosra-Megbli/Intelligent-Sales-Agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Vite%20%2B%20TS-61DAFB?logo=react&logoColor=black)
![Tests](https://img.shields.io/badge/tests-898%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

Sophie est un agent conversationnel IA qui qualifie des prospects pour des contrats d'électricité et de gaz Ecofix : elle engage la conversation, répond aux objections, collecte et valide les informations nécessaires, génère le contrat et le fait signer électroniquement, puis transmet les leads qualifiés à l'équipe commerciale humaine.

## In short (EN)

A production-shaped AI sales agent, not a chatbot demo: a deterministic state machine + declarative YAML rules engine owns every dialogue/qualification decision — the LLM (Groq/Llama) only phrases replies in natural language, it never decides a state transition. Multi-channel (Telegram + Web live, SMS ready; WhatsApp and outbound Voice fully wired end-to-end via Twilio, pending activation), with an outbound campaign engine, PDF contract generation, Yousign e-signature integration, a React ops dashboard, a RAG v2 knowledge base with citation validation, API-key/webhook-signature security, and **898 automated tests** including end-to-end golden conversation scenarios. See below (French) for full docs — this project is built for a real French-speaking client.

## Démo en ligne

| Ressource | Lien |
|---|---|
| **Dashboard (démo live)** | https://intelligent-sales-agent.onrender.com/dashboard/ |
| **Healthcheck de l'API** | https://intelligent-sales-agent.onrender.com/health |
| **Bot Telegram** | https://t.me/EcofixSalesBot |

> L'hébergement Render est en offre gratuite : après une période d'inactivité, le premier chargement peut prendre 30 à 60 secondes.

## Statut du projet & déploiement en production

Le projet est **déployé en production** sur une infrastructure cloud moderne, sécurisée et optimisée (100 % free tier pour le pilote).

### Infrastructure de production live

| Composant | Fournisseur / Technologie | Statut / URL |
|---|---|---|
| **Backend API** | Render (Docker `python:3.12-slim`, auto-migrations) | `https://intelligent-sales-agent.onrender.com` |
| **Healthcheck** | Endpoint public DB + Redis | [`/health`](https://intelligent-sales-agent.onrender.com/health) (`{"status":"ok"}`) |
| **Base de données** | Neon (PostgreSQL managé + extension pgvector) | Actif, index HNSW cosinus 768d |
| **Cache & Pub/Sub** | Upstash (Redis serverless) | Actif pour le rate limiting et le streaming SSE |
| **Frontend (Dashboard)** | Render (intégré / SPA React 18 + Vite) | [`/dashboard/`](https://intelligent-sales-agent.onrender.com/dashboard/) |
| **Inférence IA** | Groq Cloud (`openai/gpt-oss-120b` / Llama 3.3) | ~300 ms de latence moyenne |
| **Embeddings RAG** | Google AI (`models/gemini-embedding-001`, 768 dimensions) | Actif, 12 grilles tarifaires officielles publiées |
| **Bot Telegram** | Pilote inbound multi-canal | [`@EcofixSalesBot`](https://t.me/EcofixSalesBot) (actif en direct) |

### Cycle de vie et signature contractuelle

Sophie qualifie les prospects de bout en bout et pilote le cycle contractuel complet :

```
NOUVEAU LEAD → QUALIFIÉ → CONTRAT GÉNÉRÉ (PDF) → ENVOI YOUSIGN → SIGNÉ / CLIENT ACTIF
```

- **Génération de contrat PDF** : module ReportLab (`contracts/pdf_generator.py`) incluant les mentions légales obligatoires (loi IA européenne, droit de rétractation de 14 jours, grille tarifaire officielle).
- **Signature électronique** : intégration Yousign Sandbox v3 (`integrations/yousign.py`) avec webhooks HMAC sécurisés et simulation de signature instantanée (`POST /api/contracts/{id}/simulate-sign`). Dégradation propre si `YOUSIGN_API_KEY` n'est pas configurée : le flux s'arrête proprement à l'étape PDF sans planter.

## Modèle économique (estimations du pilote)

Les chiffres ci-dessous sont des **estimations et hypothèses** du pilote, pas des résultats mesurés en production. Ils servent de base de discussion et sont à valider avec des données réelles :

### 1. Structure de coûts de fonctionnement
- **Coût d'inférence par conversation qualifiée** : ~0,02 € (architecture hybride : moteur déterministe YAML + extraction Groq ultra-rapide).
- **Coût d'infrastructure d'hébergement** : 0,00 € / mois en phase pilote grâce aux niveaux gratuits de Render, Neon et Upstash.
- **Économie estimée** : de l'ordre de 99 % par rapport à un centre d'appels classique (hypothèse interne : 8 à 15 € par lead qualifié par un opérateur humain, à sourcer).

### 2. Hypothèses tarifaires Ecofix (septembre 2026, à confirmer avec le client)
- **Frais fixes de base (obligatoires)** : 60,00 € / an par contrat d'énergie (électricité ou gaz).
- **Option Ecofix Digi (strictement optionnelle)** : 5,99 € / mois pour le suivi temps réel et le pilotage intelligent via l'application mobile — jamais présentée comme une redevance de base.
- **Programme de parrainage « Friends with Benefits »** : remise permanente de 5,00 € / mois par filleul actif, sans plafond de cumul.
- **Frais de sortie résidentielle en Belgique** : 0,00 € (résiliation libre à tout moment, bascule standard sous 3 à 4 semaines).

### 3. Projection financière du pilote (hypothèses)
Pour 1 000 conversations menées par Sophie, avec les hypothèses de conversion suivantes :
- Coût total d'inférence IA : 20,00 €
- Leads hautement qualifiés (~30 %) : 300 prospects
- Contrats conclus estimés (~10 %) : 100 souscriptions
- Chiffre d'affaires brut généré (frais fixes seuls) : 6 000 € / an (hors consommation volumétrique et abonnements Digi)

## Captures d'écran

Captures de l'application déployée ([dashboard en ligne](https://intelligent-sales-agent.onrender.com/dashboard/)).

### Tableau de bord
![Tableau de bord](docs/images/01-dashboard.png)

### Prospects (CRM) et tiroir de détail 360°
![Prospects](docs/images/02-leads.png)

### Simulateur de conversation
![Simulateur](docs/images/03-simulateur.png)

### Supervision live (flux SSE) et replay
![Supervision live](docs/images/04-live.png)

### Base de connaissances (RAG v2)
![Base de connaissances](docs/images/05-knowledge.png)

## Architecture

```
backend/                      API Python/FastAPI
├── domain/                   Modèles métier (Lead, Conversation, Message, Campaign, Activity, KnowledgeDocument, KnowledgeChunk) + enums
├── conversation_engine/      State machine pure + Rules Engine (YAML) + Intent Classifier + Dialogue Policy
├── business_rules/           Règles déclaratives en YAML (qualification, validation, follow-up...)
├── ai/                       Abstraction LLM (Groq), extraction, génération de réponse, RAG v1 par mots-clés, embeddings
├── rag_v2/                   RAG sémantique vectoriel pgvector, retrieval cosinus, obsolescence W3
├── prompts/                  Prompts en Markdown/YAML (jamais codés en dur en Python)
├── crm/                      Repositories (leads, conversations, activités, campagnes)
├── channels/                 Adaptateurs par canal (Web, Telegram, SMS ; WhatsApp/Voice prêts, non activés)
├── outbound/                 Moteur de campagnes sortantes
├── followup/                 Détection de silence + relances automatiques
├── contracts/                Génération de contrat PDF (specimen certifié, mentions légales)
├── integrations/             Yousign (signature électronique)
├── live/                     Cockpit de supervision temps réel (SSE)
├── api/                      Routes FastAPI, sécurité (clé API, rate limiting, CORS)
├── application/              Services applicatifs (orchestrent domain + conversation_engine + crm)
├── dashboard/                Build compilé du dashboard React, servi en statique par FastAPI
├── docs/                     Documentation d'architecture (state machine, décisions techniques)
└── tests/ + golden_tests/    Suite de tests unitaires/intégration + scénarios de conversation bout en bout

frontend/
├── src/                      Dashboard React (Vite + TypeScript + TanStack Query + Tailwind)
├── src/pages/                Tableau de bord, Prospects, Conversations, Live Cockpit, Campagnes, RAG, etc.
└── src/components/           Composants UI, modals CSV & prospects, drawer 360°, sparklines
```

**Principe central** : le moteur métier (state machine + règles YAML) décide seul de l'état de la conversation et du statut du lead. Le LLM ne fait que formuler les réponses en langage naturel — il ne décide jamais d'une transition d'état ni d'une qualification.

## Stack technique

- **Backend** : Python 3.12+, FastAPI, SQLAlchemy, PostgreSQL (Neon pgvector), Redis (Upstash)
- **IA Conversationnelle** : Groq (`openai/gpt-oss-120b` / Llama 3.3), abstraction `LLMProvider` remplaçable
- **Embeddings RAG** : Google AI (`models/gemini-embedding-001`, 768 dimensions), abstraction `EmbeddingProvider`
- **Frontend** : React 18, Vite, TypeScript, Tailwind, TanStack Query
- **Tests** : Pytest (898 tests unitaires/intégration + scénarios golden)

## Démarrage rapide — backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env           # puis renseigner GROQ_API_KEY, DATABASE_URL, etc.
uvicorn api.main:app --host 127.0.0.1 --port 8001
```

Le port `8001` n'est pas arbitraire : c'est celui que le dashboard React attend en dev.

- Documentation API interactive : http://127.0.0.1:8001/docs
- Healthcheck : http://127.0.0.1:8001/health

## Démarrage rapide — dashboard React

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxy /api -> localhost:8001
```

## Migrations DB

Ce projet gère ses migrations via des scripts SQL exécutés automatiquement au démarrage ou via `backend/database/migration_runner.py`. Les scripts SQL correspondants vivent dans `backend/database/migrations/`, numérotés dans l'ordre où ils doivent être appliqués :

```bash
psql "$DATABASE_URL" -f backend/database/migrations/0014_add_contract_activity_types.sql
```

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ golden_tests/ -v
```

> Redis doit être démarré localement (`redis-server`) pour que la suite complète passe : plusieurs tests (opt-out, disclosure guard, live cockpit, RAG v2) passent par le cache Redis réel plutôt qu'un mock.

## Écrans du dashboard React

Le dashboard d'administration et de supervision comporte 10 écrans complets :

- **Tableau de bord** (`/`) : indicateurs clés (taux de qualification, coût moyen par conversation ~0,02 €, coût d'acquisition, revenus annuels estimés avec distinction frais fixes 60 €/an et add-on Digi optionnel 5,99 €/mois) — tous calculés par `application/metrics_service.py`, source unique de vérité partagée avec les autres écrans.
- **Prospects & Leads** (`/leads`) : tableau CRM en temps réel, filtres multi-critères, modal d'import CSV avec prévisualisation et titres en gras, bouton d'ajout unitaire de prospect, tiroir de détail 360° du lead (données CRM, timeline d'activités, génération et signature du contrat SPÉCIMEN).
- **Contrats & Ventes** (`/contracts`) : 5 KPIs commerciaux (Total, Signés, En attente, Taux de signature, ARR), recherche et filtres par statut, téléchargement PDF, et signature simulée avec tampon eIDAS certifié (hash SHA-256 + horodatage UTC) via le studio de signature interactif (`frontend/src/components/contracts/ContractVisualViewerModal.tsx`).
- **Conversations & Replay** (`/conversations`) : historique trilingue des dialogues par canal, drawer de relecture pas à pas avec trace d'audit.
- **Simulateur** (`/chat`) : bac à sable interactif connecté en direct au moteur de vente (state machine + rules engine), permettant d'éprouver les 5 couches anti-hallucination et les règles d'admissibilité en conditions réelles.
- **Campagnes sortantes** (`/campaigns`) : assistant de création en 3 étapes (info & canal, ciblage géographique/CRM/CSV, récapitulatif avec aperçu de divulgation IA légale), prévisualisation obligatoire avant lancement, pause/reprise/annulation et métriques de progression en direct.
- **Conformité** (`/compliance`) : synthèse RGPD (mécanisme STOP et purge des données) et cadre réglementaire du marché belge de l'énergie (gestionnaires de réseau par région, zéro frais de résiliation).
- **Base de connaissances** (`/knowledge`) : gestionnaire RAG v2 avec table des documents sources PDF, statut de cycle de vie (Brouillon / Publié / Archivé), zone de téléversement avec vérification de la couche texte, testeur QA de transparence avec curseur de sensibilité `RAG_MIN_SIMILARITY` (inspection des segments extraits et score sans appel LLM), alertes d'obsolescence (cycle W3) et table de repli RAG v1 par mots-clés.
- **Supervision Live** (`/live`) : cockpit temps réel alimenté par flux SSE (Server-Sent Events) via jeton HMAC signé, cartes de conversation actives dynamiques, compteurs in/out par minute, tiroir replay intégré et repli automatique sur polling 30 s si la liaison est interrompue plus de 60 s.
- **Paramètres** (`/settings`) : gestion sécurisée des clés API, secrets de webhooks, simulation Yousign Sandbox pour validation du cycle de vie contractuel et statut de santé des intégrations.

## Architecture RAG v2

Le système RAG v2 implémente les patrons ZEN Knowledge adaptés à FastAPI et pgvector :

### 1. Ingestion explicite et cycle de vie (Publish-Explicit)
- Découpage par fenêtres de mots de ~500 tokens (50 tokens de recouvrement) sans perte d'information.
- Tout document ingéré est créé au statut `DRAFT` : ses segments vectoriels restent strictement invisibles pour l'agent Sophie jusqu'à sa publication manuelle et explicite.
- Le cycle de vie complet (`DRAFT -> PUBLISHED -> ARCHIVED`) garantit une maîtrise absolue des sources citées.
- Les 12 grilles tarifaires officielles de Septembre 2026 sont entièrement préparées et ingérables via `backend/scripts/ingest_official_tariffs.py`.

### 2. Double moteur de recherche et seuil de pertinence (Relevance Gate)
- Recherche vectorielle cross-dialecte : `PgVectorSearch` (distance cosinus `<=>` PostgreSQL) en production, `InMemoryCosineSearch` (calcul cosinus Python pur) sur SQLite et en environnement de test.
- Seuil de similarité `RAG_MIN_SIMILARITY` (défaut `0.30`) et extraction bornée `RAG_TOP_K` (défaut `20`).
- Chaîne de repli à double niveau :
  1. Si aucun segment n'atteint le seuil minimal, repli transparent vers le RAG v1 par mots-clés.
  2. Si aucune entrée mot-clé ne correspond, émission d'un **refus déterministe trilingue sans aucun appel LLM** :
     - FR : *"Je n'ai pas d'information suffisante dans ma base documentaire pour répondre précisément à cette question — un conseiller humain vous répondra très prochainement."*
     - NL : *"Ik heb niet voldoende informatie in mijn documentenbasis om deze vraag nauwkeurig te beantwoorden — een menselijke adviseur zal u zeer binnenkort antwoorden."*
     - EN : *"I don't have sufficient information in my document base to answer this question precisely - a human advisor will get back to you very soon."*

### 3. Génération ancrée et validateur de citations
- Les segments valides sont injectés sous la forme de blocs contextualisés `[SOURCE n]` avec titre, version et date de revue.
- Le validateur de citations (`rag_v2/citations.py`) analyse la réponse générée : toute référence `[SOURCE n]` non présente dans le contexte fourni est automatiquement retirée et tracée dans le journal d'audit (`CITATION_STRIPPED`).
- La couche de garde regex (Layer 5) valide la réponse finale contre toute statistique inventée ou promesse absolue.

### 4. Gestion de l'obsolescence (Patron ZEN W3)
- Contrôle continu des dates de revue documentaire (`review_date`).
- Les documents à échéance dans les 7 jours sont signalés à l'administrateur (`due_soon`).
- Les documents dépassant la période de grâce (`RAG_GRACE_PERIOD_DAYS`, défaut 30 jours) sont automatiquement archivés (`auto_archive_expired`), retirant instantanément leurs segments du périmètre de recherche.
- Détection proactive des conflits de versions sur les mêmes types de produits.

### 5. Calibration, fournisseurs d'embeddings et coûts
- **Calibration** : ajuster `RAG_MIN_SIMILARITY` en observant les scores réels retournés par le testeur QA (`POST /api/knowledge/test`).
- **Fournisseur d'embeddings** : abstraction `EmbeddingProvider` (`ai/providers/embeddings/`) ; implémentation actuelle Google AI (`models/gemini-embedding-001`, 768 dimensions), interchangeable sans modifier l'application.
- **Estimation des coûts** : `/api/knowledge/stats` (nombre de segments actifs × 500 tokens × coût unitaire du fournisseur).
- **Guide d'ingestion** : `docs/RAG_V2_INGESTION_GUIDE.md` (commandes CLI pour les 12 grilles tarifaires de référence).

## Canaux de Communication

| Canal | Statut | Détails |
|---|---|---|
| **Telegram** | Actif | `@EcofixSalesBot` — canal du pilote live avec webhook sécurisé |
| **Web (widget)** | Actif | Intégré sur le dashboard et simulateur interactif |
| **SMS** | Opérationnel | `channels/sms.py` avec signature HMAC Twilio et traitement STOP |
| **WhatsApp Business** | Câblé (Inactif) | `channels/whatsapp.py` complet, en attente de clés Twilio WhatsApp |
| **Appel vocal** | Câblé (Inactif) | Pipeline STT/TTS complet, en attente de numéro Twilio Voice dédié |
| **Messenger, Instagram, Meta Ads** | Roadmap | Non implémentés dans le pilote initial |

## Sécurité

- Toutes les routes API sensibles (conversations, dashboard, campagnes) protégées par une clé `X-API-Key` (comparaison à temps constant).
- Webhooks Telegram, WhatsApp/SMS (Twilio) et Yousign vérifiés par signature/secret partagé (HMAC).
- CORS désactivé par défaut (safe-by-default), à configurer explicitement via `CORS_ALLOWED_ORIGINS`.
- Rate limiting appliqué par conversation/IP.
- ⚠️ Par défaut (développement), si `API_KEY` n'est pas configurée, l'authentification est désactivée avec un avertissement en log.
- ✅ En définissant `ENVIRONMENT=production` (voir `backend/.env.example`), l'API **refuse de démarrer** si `API_KEY` ou `TELEGRAM_WEBHOOK_SECRET` ne sont pas configurées, au lieu de tourner sans authentification (`api/main.py:_fail_fast_if_misconfigured_for_production`).
- `backend/.env` (secrets réels) est exclu de git via `.gitignore` et n'a jamais été commit — pour livrer une archive au client, utiliser `scripts/package_client_delivery.ps1` (basé sur `git archive`, ne peut physiquement pas inclure un fichier non commit comme `.env`) plutôt qu'une compression manuelle du dossier.

## Conformité RGPD

Sophie intègre les principes du RGPD dès la conception (*privacy by design*) :

### 1. Bases légales de traitement (Art. 6 RGPD)
- **Leads entrants (inbound)** : consentement explicite et exécution de mesures précontractuelles à la demande du prospect (Art. 6(1)(a) et (b)) lors de l'initiation d'un échange pour étudier ou souscrire une offre d'énergie Ecofix.
- **Campagnes sortantes (outbound)** : intérêt légitime (Art. 6(1)(f)) pour la prospection commerciale sur prospects qualifiés, assorti d'une transparence obligatoire et immédiate (mention explicite de l'agent virtuel IA dès le premier message sur tous les canaux) et du droit inconditionnel d'opposition (Art. 21).

### 2. Durée de conservation (règle des 12 mois)
- Les données personnelles des prospects non convertis sont conservées 12 mois maximum à compter du dernier contact ou de la clôture de la qualification.
- À l'issue de cette période, les données d'identification (`first_name`, `last_name`, `email`, `phone`, `notes`, `date_of_birth`) sont purgées ou anonymisées de manière irréversible, sauf conversion effective en contrat client actif (soumise aux délais légaux de conservation contractuelle et comptable).

### 3. Procédure d'opt-out / droit d'opposition (STOP / STOPT / ARRÊT)
Le prospect peut à tout moment exercer son droit d'opposition en envoyant un mot-clé standardisé (`STOP`, `STOPT` ou `ARRÊT`, insensible à la casse et aux accents, en français/néerlandais/anglais). Le traitement est immédiat et déterministe, géré par le Rules Engine / `ConversationService`, sans dépendance LLM :
1. Retrait immédiat de toute campagne sortante active ou future (`campaign_id = NULL`).
2. Annulation des relances programmées ; `FollowUpEngine` ignore systématiquement tout prospect en opposition (`opt_out_at IS NOT NULL`).
3. Purge des données PII directes (`first_name`, `last_name`, `email`, `notes`, `date_of_birth`).
4. Conservation d'une clé de suppression hashée pour empêcher toute réimportation ultérieure non sollicitée.
5. Horodatage UTC (`opt_out_at`), statut mis à `REJECTED`, événement `OPT_OUT` inscrit dans le journal d'audit (`activities`).
6. Envoi d'un message unique de confirmation de désabonnement.

### 4. Transfert de données & sous-traitance IA (Groq)
- Les requêtes d'extraction d'entités et de formulation de réponses s'appuient sur l'API Groq Cloud.
- La production nécessite la souscription d'un Data Processing Agreement (DPA) avec Groq Inc., incorporant les Clauses Contractuelles Types approuvées par la Commission européenne pour les transferts hors UE.
- Minimisation des données (Art. 5(1)(c)) : seuls les fragments textuels strictement nécessaires à la qualification transitent par l'API d'inférence ; l'évaluation des règles métier, la validation de majorité, la détection des doublons et la liste de suppression s'exécutent entièrement en local.

## Limites connues du pilote actuel

- WhatsApp et Voice sont entièrement architecturés, câblés et testés, mais non activés en production tant que les comptes Twilio correspondants ne sont pas provisionnés (voir tableau des canaux).
- Néerlandais/anglais : couverts par le moteur (RAG v2, disclosure, opt-out), mais le français reste la langue principale réellement testée en conditions pilote.
- Fournisseur d'embeddings RAG v2 actuel (Google `gemini-embedding-001`) sur niveau gratuit — à surveiller en cas de montée en volume.

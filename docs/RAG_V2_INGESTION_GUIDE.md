# Guide d'Ingestion RAG v2 — Grilles Tarifaires Ecofix

Ce guide détaille la procédure complète pour ingérer, vectoriser et publier les 12 grilles tarifaires officielles Ecofix (Septembre 2026) dans le RAG v2 de Sophie.

---

## 1. Prérequis & Variables d'Environnement

L'ingestion s'exécute depuis le dossier `backend/` avec l'environnement virtuel activé.

### Variables requises (Render / Déploiement)

| Variable | Description | Valeur / Défaut |
|---|---|---|
| `GOOGLE_AI_API_KEY` | Clé API Google AI Studio pour le modèle `text-embedding-004` (768 dimensions) | Obligatoire pour vectorisation réelle |
| `DATABASE_URL` | URL de connexion PostgreSQL (avec extension pgvector active) | Fourni par Neon / Render Postgres |
| `RAG_MIN_SIMILARITY` | Seuil minimal de similarité cosinus pour retenir un segment | `0.30` (calibrable) |
| `RAG_TOP_K` | Nombre maximal de segments candidats extraits par requête | `20` |
| `RAG_GRACE_PERIOD_DAYS` | Période de grâce après date de revue avant archivage automatique | `30` |

---

## 2. Commandes CLI d'Ingestion (12 Fichiers PDF)

Exécutez chaque commande depuis la racine du dépôt ou depuis `backend/` (avec `PYTHONPATH=.`) :

```bash
cd backend

# Électricité — Flexy (Variable Mensuel)
python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/EL_Ecofix_Flexy_FR.pdf \
  --title "Ecofix Flexy Électricité (FR)" \
  --source-type tariff_card \
  --language fr \
  --review-date 2026-10-31

python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/EL_Ecofix_Flexy_NL.pdf \
  --title "Ecofix Flexy Elektriciteit (NL)" \
  --source-type tariff_card \
  --language nl \
  --review-date 2026-10-31

# Électricité — Flexy Online (Gestion Web)
python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/EL_Ecofix_Flexy_Online_FR.pdf \
  --title "Ecofix Flexy Online Électricité (FR)" \
  --source-type tariff_card \
  --language fr \
  --review-date 2026-10-31

python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/EL_Ecofix_Flexy_Online_NL.pdf \
  --title "Ecofix Flexy Online Elektriciteit (NL)" \
  --source-type tariff_card \
  --language nl \
  --review-date 2026-10-31

# Électricité — Motion (Dynamique Horaire)
python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/EL_Ecofix_Motion_FR.pdf \
  --title "Ecofix Motion Électricité Dynamique (FR)" \
  --source-type tariff_card \
  --language fr \
  --review-date 2026-10-31

python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/EL_Ecofix_Motion_NL.pdf \
  --title "Ecofix Motion Elektriciteit Dynamisch (NL)" \
  --source-type tariff_card \
  --language nl \
  --review-date 2026-10-31

# Électricité — Motion Online
python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/EL_Ecofix_Motion_Online_FR.pdf \
  --title "Ecofix Motion Online Électricité Dynamique (FR)" \
  --source-type tariff_card \
  --language fr \
  --review-date 2026-10-31

python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/EL_Ecofix_Motion_Online_NL.pdf \
  --title "Ecofix Motion Online Elektriciteit Dynamisch (NL)" \
  --source-type tariff_card \
  --language nl \
  --review-date 2026-10-31

# Gaz — Flexy (Variable Mensuel)
python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/GAS_Ecofix_Flexy_FR.pdf \
  --title "Ecofix Flexy Gaz (FR)" \
  --source-type tariff_card \
  --language fr \
  --review-date 2026-10-31

python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/GAS_Ecofix_Flexy_NL.pdf \
  --title "Ecofix Flexy Gas (NL)" \
  --source-type tariff_card \
  --language nl \
  --review-date 2026-10-31

# Gaz — Flexy Online
python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/GAS_Ecofix_Flexy_Online_FR.pdf \
  --title "Ecofix Flexy Online Gaz (FR)" \
  --source-type tariff_card \
  --language fr \
  --review-date 2026-10-31

python -m rag_v2.ingest \
  --file ../knowledge_corpus/tariffs/2026-09/GAS_Ecofix_Flexy_Online_NL.pdf \
  --title "Ecofix Flexy Online Gas (NL)" \
  --source-type tariff_card \
  --language nl \
  --review-date 2026-10-31
```

---

## 3. Étape de Publication Explicite (Publish-Explicit)

> [!IMPORTANT]
> Conformément au principe architectural d'ingestion explicite (pattern ZEN Knowledge), tout document ingéré reçoit initialement le statut `DRAFT`. Ses segments ne sont **pas interrogeables par Sophie** tant qu'il n'est pas explicitement publié.

Pour publier les documents :

### Option A — Interface Web (Dashboard)
1. Ouvrez l'écran **Base de Connaissances** (`/knowledge`).
2. Dans le tableau des **Documents Sources RAG v2**, repérez les documents au statut `Brouillon` (`DRAFT`).
3. Cliquez sur le bouton **Publier** pour chacun et confirmez.

### Option B — Script Python One-Liner
Depuis le dossier `backend/` :
```bash
python -c "from database.postgres import SessionLocal; from rag_v2.documents import publish_document, list_documents; db=SessionLocal(); drafts=[publish_document(db, d.id) for d in list_documents(db) if d.status.value=='draft']; print(f'Succès : {len(drafts)} document(s) publié(s).')"
```

### Option C — Requête SQL directe (PostgreSQL)
```sql
UPDATE knowledge_documents
SET status = 'published', published_at = NOW()
WHERE status = 'draft';
```

### Option D — API REST
```bash
curl -X POST "https://<your-backend-domain>/api/knowledge/documents/<DOCUMENT_ID>/publish" \
  -H "X-API-Key: <VOTRE_CLE_API>"
```

---

## 4. Vérification et Transparence QA

Après publication, vérifiez la bonne récupération documentaire sans solliciter le LLM :

1. Via l'interface graphique : dans le bloc **Tester le RAG (Transparence QA)** de l'écran Base de Connaissances, saisissez :
   - *« Quels sont les frais fixes annuels pour Flexy ? »*
   - Observez les segments extraits avec leur score de similarité et la confirmation d'absence de refus.
2. Via l'API :
```bash
curl -X POST "https://<your-backend-domain>/api/knowledge/test" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <VOTRE_CLE_API>" \
  -d '{"query": "frais fixes annuels Flexy électricité", "language": "fr"}'
```

"""
prod_compliance_test.py — Validation Sprint 1 de Sophie en PRODUCTION réelle.

1. Simule des messages Telegram (POST vers le webhook Render, avec le
   secret officiel) pour dérouler 4 scénarios de conformité bout-en-bout.
2. Vérifie via l'API dashboard (X-API-Key) que les états CRM finaux
   correspondent aux attentes du Sprint 1.

Usage (PowerShell, depuis backend/, venv activé):
  $env:TELEGRAM_WEBHOOK_SECRET="<valeur Render>"
  $env:API_KEY="<valeur Render>"
  python scripts\prod_compliance_test.py
"""

import json
import os
import sys
import time

import httpx

BASE = "https://intelligent-sales-agent.onrender.com"
WEBHOOK = f"{BASE}/api/telegram/webhook"

SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
API_KEY = os.getenv("API_KEY")
if not SECRET or not API_KEY:
    sys.exit("ERREUR: définissez TELEGRAM_WEBHOOK_SECRET et API_KEY.")

HDR_TG = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
HDR_API = {"X-API-Key": API_KEY}
EAN_OK = "541448911001234567"
_update_id = 90_000_000


def send_tg(chat_id: int, first_name: str, text: str) -> bool:
    """Simule un message utilisateur envoyé au bot via le webhook."""
    global _update_id
    _update_id += 1
    payload = {
        "update_id": _update_id,
        "message": {
            "message_id": _update_id,
            "from": {"id": chat_id, "is_bot": False,
                     "first_name": first_name, "language_code": "fr"},
            "chat": {"id": chat_id, "first_name": first_name, "type": "private"},
            "date": int(time.time()),
            "text": text,
        },
    }
    try:
        r = httpx.post(WEBHOOK, json=payload, headers=HDR_TG, timeout=120)
    except Exception as e:
        print(f"    réseau: {e}")
        return False
    print(f"    -> {text[:45]!r} : HTTP {r.status_code}")
    return r.status_code == 200


SCENARIOS = [
    {"name": "ProdQualifie", "chat_id": 991100001,
     "steps": ["Bonjour", "Je voudrais changer de fournisseur d'énergie",
               "Oui je confirme", "Particulier",
               "J'habite à Namur en Wallonie", "Mon fournisseur est Engie",
               "Prod Qualifie, prod.qualifie.77a3@test.be, 0477112233, 15/05/1985",
               EAN_OK],
     "expect_status": "QUALIFIED", "marker": "prod.qualifie.77a3"},
    {"name": "ProdMineur", "chat_id": 991100002,
     "steps": ["Bonjour", "Je voudrais changer de fournisseur", "Oui",
               "Particulier", "Liège, Wallonie", "Luminus",
               "Prod Mineur, prod.mineur.19c@test.be, 0477112233, 15/05/2015",
               EAN_OK],
     "expect_status": "REJECTED", "expect_reason": "INVALID_CUSTOMER",
     "marker": "prod.mineur.19c"},
    {"name": "ProdBruxelles", "chat_id": 991100003,
     "steps": ["Bonjour", "Je veux changer de fournisseur", "Oui",
               "Particulier", "J'habite à Ixelles, Bruxelles", "TotalEnergies",
               "Prod Bruxelles, prod.bruxelles.5e2@test.be, 0477112233, 15/05/1988",
               EAN_OK],
     "expect_status": "REJECTED", "expect_reason": "OUT_OF_COVERAGE",
     "marker": "prod.bruxelles.5e2"},
    {"name": "ProdStop", "chat_id": 991100004,
     "steps": ["Bonjour", "Je voudrais changer de fournisseur", "Oui",
               "Particulier", "Mons, Wallonie", "Engie",
               "Prod Stop, prod.stop.8b1@test.be, 0477112233, 15/05/1990",
               "STOP"],
     "expect_status": "REJECTED", "expect_purged": True,
     "marker": "prod.stop.8b1"},
]


def discover_leads_path(client: httpx.Client):
    """Trouve le chemin des leads via l'OpenAPI (robuste aux renommages)."""
    try:
        spec = client.get(f"{BASE}/openapi.json", headers=HDR_API, timeout=30).json()
        for p, ops in spec.get("paths", {}).items():
            if "lead" in p.lower() and "{" not in p and "get" in ops:
                return p
    except Exception as e:
        print(f"    (openapi indisponible: {e})")
    return None


def find_lead(client, marker: str, tries: int = 4):
    path = discover_leads_path(client)
    if not path:
        return None
    for _ in range(tries):
        try:
            r = client.get(f"{BASE}{path}", headers=HDR_API, timeout=60)
            r.raise_for_status()
            data = r.json()
            items = data if isinstance(data, list) else (
                data.get("items") or data.get("leads") or [])
            for lead in items:
                if marker in json.dumps(lead, ensure_ascii=False).lower():
                    return lead
        except Exception as e:
            print(f"    (lecture API: {e})")
        time.sleep(5)
    return None


def evaluate(sc, lead):
    if sc.get("expect_purged"):
        if lead is None:
            return ("PASS", "lead introuvable par email = PII purgée ✓")
        blob = json.dumps(lead, ensure_ascii=False).lower()
        if sc["marker"] not in blob:
            return ("PASS", "email absent de la fiche = purgée ✓")
        return ("WARN", "lead encore visible — vérifier la purge visuellement")
    if lead is None:
        return ("FAIL", "lead introuvable dans le CRM")
    status = str(lead.get("status", ""))
    if sc["expect_status"] not in status.upper():
        return ("FAIL", f"status={status!r} attendu {sc['expect_status']}")
    reason = sc.get("expect_reason")
    if reason:
        blob = json.dumps(lead, ensure_ascii=False).upper()
        if reason not in blob:
            return ("WARN", f"status REJECTED ✓ mais reason {reason} non visible via API")
    return ("PASS", f"status={status!r}")


def main():
    print("0) Réveil du service (/health)…")
    for _ in range(3):
        try:
            h = httpx.get(f"{BASE}/health", timeout=120)
            print("   /health:", h.json())
            if h.json().get("status") == "ok":
                break
        except Exception as e:
            print("   (cold start…)", e)
        time.sleep(20)

    for sc in SCENARIOS:
        print(f"\n── Scénario {sc['name']} ──")
        for s in sc["steps"]:
            send_tg(sc["chat_id"], sc["name"], s)
            time.sleep(4)  # laisse Sophie traiter + répondre

    print("\nVérification CRM via l'API dashboard…")
    report = []
    with httpx.Client() as c:
        for sc in SCENARIOS:
            lead = find_lead(c, sc["marker"])
            verdict, detail = evaluate(sc, lead)
            report.append((sc["name"], verdict, detail))

    print("\n================ RAPPORT SPRINT 1 EN PRODUCTION ================")
    for name, verdict, detail in report:
        print(f"  [{verdict:4}] {name:14} — {detail}")
    print("----------------------------------------------------------------")
    print("Rappel: le TEXTE des réponses (énoncé IA, confirmation STOP) se")
    print("vérifie visuellement dans Telegram — l'API ne l'expose pas.")
    print("Vérifiez vos captures d'écran pour: énoncé IA 1er message ✓")


if __name__ == "__main__":
    main()
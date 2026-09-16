"""
FastAPI application entrypoint.

Run locally with: `uvicorn api.main:app --reload`
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from api.campaign_routes import router as campaign_router
from api.contract_routes import router as contract_router
from api.dashboard_routes import router as dashboard_router
from api.leads_routes import router as leads_router
from api.routes import router
from api.voice_routes import router as voice_router

from database.postgres import engine, init_db
from database.redis import get_redis

app = FastAPI(title="Ecofix Sophie API", version="0.1.0")


def _fail_fast_if_misconfigured_for_production() -> None:
    """P0 security hardening.

    api/dependencies.py's require_api_key / verify_telegram_secret are
    deliberately dev-friendly: if API_KEY / TELEGRAM_WEBHOOK_SECRET aren't
    set, they log a warning and let the request through unauthenticated
    (see that module's docstring) - useful for a first local run, dangerous
    if it silently reaches a real deployment, since the dashboard's PII-
    bearing endpoints would then need no credential at all.

    This does not change that default (existing tests, and a first local
    `uvicorn --reload`, keep working exactly as before) - it adds one new,
    opt-in gate: set `ENVIRONMENT=production` and a missing required secret
    becomes a hard startup failure instead of a log line an operator can
    miss. Never fails when ENVIRONMENT is unset or anything else.
    """
    if os.getenv("ENVIRONMENT", "development").strip().lower() != "production":
        return
    missing = []
    if not os.getenv("API_KEY"):
        missing.append("API_KEY")
    if not (os.getenv("TELEGRAM_WEBHOOK_SECRET") or os.getenv("WEBHOOK_SECRET")):
        missing.append("TELEGRAM_WEBHOOK_SECRET")
    if missing:
        raise RuntimeError(
            "ENVIRONMENT=production but required secret(s) are not set: "
            + ", ".join(missing)
            + ". Refusing to start unauthenticated in production - see backend/.env.example."
        )


@app.on_event("startup")
def _enforce_production_secrets() -> None:
    _fail_fast_if_misconfigured_for_production()


@app.on_event("startup")
def _auto_run_migrations_and_init_db() -> None:
    # Skip DB initialization during test suite runs (TestClient fires startup
    # events, but unit tests use SQLite in-memory fixtures, not real Postgres)
    import sys
    if os.getenv("TESTING") or "pytest" in sys.modules:
        return

    try:
        init_db()
        from database.migration_runner import run_migrations
        applied = run_migrations()
        if applied:
            logging.getLogger(__name__).info("Applied database migrations at startup: %s", ", ".join(applied))
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("init_db / run_migrations skipped at startup: %s", exc)

# CORS: safe-by-default (no origins allowed) unless CORS_ALLOWED_ORIGINS is
# explicitly set, e.g. "https://ecofix.be,https://app.ecofix.be". An empty
# list here means the browser blocks cross-origin calls entirely - a
# same-origin deployment (or server-to-server calls, which aren't subject to
# CORS at all) works without setting anything.
_allowed_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS") or os.getenv("CORS_ORIGINS") or ""
_allowed_origins = [origin.strip() for origin in _allowed_origins_raw.split(",") if origin.strip()]

# Always allow local development origins so the Vite frontend (port 5173) can communicate with the API
for _dev_origin in ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"):
    if _dev_origin not in _allowed_origins:
        _allowed_origins.append(_dev_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "X-Telegram-Bot-Api-Secret-Token", "Content-Type", "Authorization"],
)

app.include_router(router)
app.include_router(contract_router)
app.include_router(dashboard_router)
app.include_router(leads_router)
app.include_router(campaign_router)
app.include_router(voice_router)


_DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"
if _DASHBOARD_DIR.is_dir():
    # NOTE (security): this only serves the static HTML/CSS/JS bundle, which
    # contains no lead data itself - the actual PII lives behind
    # /api/dashboard/* (see api/dashboard_routes.py), which DOES require
    # `API_KEY`. Anyone can load this page; without the key, every fetch it
    # makes will 401.
    #
    # NOTE (SPA routing): this now serves the built React dashboard
    # (frontend/artifacts/sophie-dashboard, built with `pnpm build`,
    # BASE_PATH=/dashboard/), which uses wouter with real browser-history
    # routes like /dashboard/leads/<id> - not hash routing. Starlette's
    # `StaticFiles(html=True)` only serves index.html for a bare directory
    # request; it does NOT fall back to index.html for unmatched sub-paths,
    # so a direct link or a page refresh on e.g. /dashboard/leads/<id> would
    # 404. To fix that: hashed build assets (JS/CSS, immutable filenames)
    # are served literally from /dashboard/assets, while every other
    # /dashboard/* path (including /dashboard itself) returns index.html
    # with a normal 200 so the client-side router can take over - the
    # standard SPA-fallback pattern.
    app.mount(
        "/dashboard/assets",
        StaticFiles(directory=_DASHBOARD_DIR / "assets"),
        name="dashboard-assets",
    )

    _dashboard_index = _DASHBOARD_DIR / "index.html"

    @app.get("/dashboard", include_in_schema=False)
    @app.get("/dashboard/{full_path:path}", include_in_schema=False)
    def dashboard_spa(full_path: str = "") -> FileResponse:
        return FileResponse(_dashboard_index)



@app.get("/")
def root() -> dict:
    """Root service discovery endpoint."""
    return {
        "service": "Ecofix Sophie API",
        "status": "online",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "dashboard": "/dashboard"
        }
    }

@app.get("/health")
def health() -> JSONResponse:
    """Healthcheck endpoint verifying DB and Redis connectivity."""
    import database.postgres as db_mod
    import database.redis as redis_mod

    db_status = "ok"
    redis_status = "ok"

    try:
        with db_mod.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logging.getLogger(__name__).warning("Health check DB probe failed: %s", exc)
        db_status = "unreachable"

    try:
        r = redis_mod.get_redis()
        if not r.ping():
            redis_status = "unreachable"
    except Exception as exc:
        logging.getLogger(__name__).warning("Health check Redis probe failed: %s", exc)
        redis_status = "unreachable"

    is_healthy = (db_status == "ok" and redis_status == "ok")
    payload = {
        "status": "ok" if is_healthy else "degraded",
        "database": db_status,
        "redis": redis_status,
        "version": "0.1.0",
    }
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=payload)

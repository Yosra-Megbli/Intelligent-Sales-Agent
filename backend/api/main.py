"""
FastAPI application entrypoint.

Run locally with: `uvicorn api.main:app --reload`
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.campaign_routes import router as campaign_router
from api.dashboard_routes import router as dashboard_router
from api.leads_routes import router as leads_router
from api.routes import router
from api.voice_routes import router as voice_router
from database.postgres import init_db

app = FastAPI(title="Ecofix Sophie API", version="0.1.0")


@app.on_event("startup")
def _create_tables_if_missing() -> None:
    # Nothing else in this codebase ever called init_db(): there is no
    # Alembic migrations folder despite alembic being in requirements.txt,
    # and the only caller was a leftover local-machine script
    # (task_backend_setup.py, hardcoded to one developer's Windows path)
    # that was never part of the documented "Pour lancer" steps. Without
    # this, a fresh `docker-compose up` + `uvicorn --reload` connects to an
    # empty database and every request fails on the first query. create_all
    # only creates tables that don't already exist, so this is safe to run
    # on every startup - a real production deployment should still replace
    # this with proper Alembic migrations (see database/postgres.py).
    #
    # Swallow (and just log) connection errors rather than crash the app on
    # startup: FastAPI's TestClient used as a context manager
    # (`with TestClient(app) as client`) fires this same startup event, and
    # the test suite talks to its own SQLite fixture, never the real
    # Postgres `engine` this module imports - it should never need a real
    # database available to run.
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001 - see note above
        logging.getLogger(__name__).warning("init_db() skipped at startup: %s", exc)

# CORS: safe-by-default (no origins allowed) unless CORS_ALLOWED_ORIGINS is
# explicitly set, e.g. "https://ecofix.be,https://app.ecofix.be". An empty
# list here means the browser blocks cross-origin calls entirely - a
# same-origin deployment (or server-to-server calls, which aren't subject to
# CORS at all) works without setting anything.
_allowed_origins = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "X-Telegram-Bot-Api-Secret-Token", "Content-Type"],
)

app.include_router(router)
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

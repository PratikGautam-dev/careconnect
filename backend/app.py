# app.py
"""
ARCHITECTURE_PLAN.md Phase 4: the composition root -- FastAPI app
construction, middleware, lifespan, and include_router calls only. Split
out of the former single core/main.py module, which mixed this with
webhook routing, the WA-client cache, and message locking (now
webhook/routes.py, webhook/dispatch.py, webhook/cron_routes.py).

Deployment note: the ASGI app is now `app:app`, not `core.main:app` -- see
ARCHITECTURE_PLAN.md's Phase A/Phase 4 status notes for what else that
touches (Dockerfile CMD, railway.toml startCommand).
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()  # must run before os.environ[...] reads below, or db.init_db()'s env reads

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

from admin.onboarding import router as onboarding_router
from admin.onboarding_api import router as onboarding_api_router
from admin.tenants_api import router as tenants_api_router
from portal.routes import router as portal_api_router
from auth.google_oauth import AUTH_SECRET, router as user_auth_router

# uvicorn only configures its own "uvicorn"/"uvicorn.error"/"uvicorn.access" loggers
# (see uvicorn.config.LOGGING_CONFIG) — it never touches the root logger. Every logger
# in this app (core.whatsapp, webhook.routes, ...) propagates up to the root logger
# instead, which without this call has no handler and falls back to Python's "last
# resort" handler (WARNING+ only) — so logger.info(...) calls anywhere in the app
# would be silently invisible even though the logging calls themselves are correct.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# webhook.dispatch's own import creates the HISTORY/SESSIONS singletons;
# init_db() must run right after that and before webhook.routes' own
# import-time WHATSAPP_VERIFY_TOKEN check -- same relative ordering
# core/main.py had, preserved here since tests/conftest.py documents a real
# ordering dependency on when init_db() first runs (see its own comments).
import webhook.dispatch  # noqa: F401
from db.init_db import init_db

# Creates the schema + seeds the one real hospital from .env if not already present
# (idempotent, safe on every startup — SPEC Section 12.6 Tier 1).
init_db()

from webhook.cron_routes import router as cron_router
from webhook.routes import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)

# Next.js frontend (frontend/) runs on a separate origin/port (localhost:3000
# in dev, a Vercel domain in prod) and calls this API directly from the
# browser, so it needs CORS -- everything else in this app is either a
# same-origin server-rendered page or a webhook Meta calls server-to-server,
# neither of which needed this before. FRONTEND_ORIGIN lets the deployed
# Vercel URL be added without another code change.
_frontend_origins = ["http://localhost:3000"]
if os.environ.get("FRONTEND_ORIGIN"):
    _frontend_origins.append(os.environ["FRONTEND_ORIGIN"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Section 15: only used by auth/google_oauth.py's Google OAuth handshake to hold the
# short-lived state/nonce Authlib generates between /auth/google/login and
# /auth/google/callback -- both routes are on THIS backend's own origin
# (see auth/google_oauth.py's module docstring), so this cookie is same-origin
# throughout and never faces the cross-origin-cookie problem portal/routes/*'s
# Bearer-token session already had to work around. Reuses AUTH_SECRET rather
# than adding yet another secret, since it's scoped to the same
# "user identity" concern that secret already covers.
app.add_middleware(SessionMiddleware, secret_key=AUTH_SECRET or "insecure-dev-only-session-secret")

app.include_router(onboarding_router)
app.include_router(onboarding_api_router)
app.include_router(tenants_api_router)
app.include_router(portal_api_router)
app.include_router(user_auth_router)
app.include_router(webhook_router)
app.include_router(cron_router)

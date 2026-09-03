# app.py
"""
ARCHITECTURE_PLAN.md Phase 4: the composition root -- FastAPI app
construction, middleware, lifespan, and include_router calls only. Split
out of the former single core/main.py module, which mixed this with
webhook routing, the WA-client cache, and message locking (now
webhook/routes.py, webhook/dispatch.py, webhook/cron_routes.py).

Deployment note: the ASGI app is now `main:app`, not `core.main:app` -- see
ARCHITECTURE_PLAN.md's Phase A/Phase 4 status notes for what else that
touches (Dockerfile CMD, railway.toml startCommand).
"""
import logging
import os
import threading
import time
import uuid

import uvicorn
from dotenv import load_dotenv

load_dotenv()  # must run before os.environ[...] reads below, or db.init_db()'s env reads

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

from admin.onboarding import router as onboarding_router
from admin.onboarding_api import router as onboarding_api_router
from admin.platform_settings_api import router as platform_settings_api_router
from admin.super_auth import router as super_auth_router
from admin.tenants_api import router as tenants_api_router
from admin.users_api import router as users_api_router
from portal.routes import router as portal_api_router
from auth.google_oauth import AUTH_SECRET, router as user_auth_router
from auth.google_calendar_oauth import router as google_calendar_oauth_router

# core/logging_config.py's own module docstring covers the full reasoning --
# in short, every logger in this app (core.whatsapp, webhook.routes, ...)
# propagates to the ROOT logger, so configuring root's handler/formatter
# here is what makes every one of them emit structured JSON, with no changes
# needed to any of those files. Replaces the old
# `logging.basicConfig(level=logging.INFO, format="...")` plain-text call.
from core.logging_config import configure_logging
from core.request_context import get_request_id, reset_request_id, set_request_id

configure_logging()
_request_logger = logging.getLogger("request")

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
    _start_perms_invalidate_subscriber()
    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def _request_logging(request, call_next):
    """One JSON log line per request (method/path/status/duration), and the
    thing that actually populates request_id (core/request_context.py) for
    every OTHER log line emitted anywhere during this request's handling --
    route handlers, repository functions, the rollback middleware below,
    anything that does logging.getLogger(__name__).info(...) downstream of
    here sees the same request_id automatically, without it being passed
    through every function signature. set/reset in a try/finally so the
    ContextVar is always cleared at the end of this request's task, even on
    an unhandled exception -- a value must never leak into whatever request
    this same asyncio task (or a pooled thread reusing it) handles next.

    Always server-generated for now, deliberately not reading an incoming
    X-Request-ID header -- honoring a client-supplied id (the standard
    "propagate if present, generate if absent" pattern) is real future work
    once a frontend actually sends one, but needs its own input validation
    (a client-controlled value flowing into logs/response headers) done
    properly at that point rather than half-built ahead of the frontend
    change it depends on."""
    request_id = uuid.uuid4().hex[:12]
    token = set_request_id(request_id)
    start = time.monotonic()
    try:
        # Both log calls below must run BEFORE the outer finally resets the
        # context var -- get_request_id() (core/logging_config.py's
        # JSONFormatter) reads it at format() time, so logging "request
        # completed"/"request failed" AFTER the reset would log request_id
        # as None for the one line that most needs it.
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            _request_logger.exception(
                "request failed",
                extra={"extra_data": {"method": request.method, "path": request.url.path, "duration_ms": duration_ms}},
            )
            raise
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        _request_logger.info(
            "request completed",
            extra={"extra_data": {
                "method": request.method, "path": request.url.path,
                "status_code": response.status_code, "duration_ms": duration_ms,
            }},
        )
        # Lets the frontend/browser network tab and this backend's own JSON
        # logs be correlated for the same request -- cheap, standard
        # practice, no downside for a same-origin-or-CORS-allowed API.
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        reset_request_id(token)


@app.middleware("http")
async def _rollback_shared_session_on_error(request, call_next):
    """db/connection.py's get_session() returns ONE SQLAlchemy Session
    reused for the process lifetime (by design, mirrors get_connection()'s
    single reused raw connection) -- isolation_level="AUTOCOMMIT" on the
    underlying engine keeps a failed statement from poisoning Postgres's
    own transaction state, but the ORM Session ALSO tracks its own
    in_transaction() bookkeeping, independent of that, and nothing anywhere
    else ever called session.rollback() to clear it after a request-level
    exception. Left alone, the first ORM statement to fail on ANY request
    (a bad query, a constraint violation, a stale column) leaves the SAME
    shared session stuck for every request afterward -- including ones with
    nothing to do with whatever failed originally -- raising
    sqlalchemy.exc.PendingRollbackError until the process restarts.

    Production incident: a plain .rollback() isn't enough for the OTHER way
    this session gets stuck -- Neon (serverless Postgres) closing the
    underlying connection server-side after a period of inactivity
    ("SSL connection has been closed unexpectedly", sqlalchemy.exc.
    OperationalError). pool_pre_ping=True on the engine can't catch this,
    because this Session never returns its connection to the pool between
    requests (get_session() hands back the SAME Session/connection for the
    process lifetime) -- pre_ping only re-validates a connection AT
    CHECKOUT, which happens exactly once here. .rollback() on an already-
    dead connection just fails silently (caught below) and leaves that same
    dead connection wired in for every request after it, forever, until the
    whole process restarts. reset_session() (db/connection.py) is the real
    fix for that case: it discards the Session outright, so the NEXT
    get_session() call builds a fresh one bound to a fresh pool checkout
    (where pre_ping DOES get to run). Using it here unconditionally instead
    of a plain rollback() is a strict superset -- it also clears the
    poisoned-transaction case above, just via a fresh Session instead of a
    rolled-back one, at the negligible cost of one extra connection
    checkout on the next request."""
    try:
        return await call_next(request)
    except Exception:
        from db.connection import reset_session

        reset_session()
        raise

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
app.include_router(users_api_router)
app.include_router(platform_settings_api_router)
app.include_router(super_auth_router)
app.include_router(portal_api_router)
app.include_router(user_auth_router)
app.include_router(google_calendar_oauth_router)
app.include_router(webhook_router)
app.include_router(cron_router)

# RBAC (docs/rbac-redis-plan.md): a background subscriber on the
# `perms:invalidate` Redis pub/sub channel -- portal/permission_cache.py's
# invalidate() (called by PUT /api/portal/roles/permissions) already clears
# ITS OWN process's local cache directly; this subscriber is what makes an
# edit take effect immediately on every OTHER worker process/instance too,
# rather than only lazily once each of their cached matrices happens to
# expire (up to permission_cache.py's own 5-minute TTL later). A daemon
# thread, not an asyncio task -- redis-py's pubsub().listen() is a blocking
# generator; wrapping it in a thread keeps it off the event loop without
# needing an async Redis client just for this one subscriber. No Redis ->
# get_redis() returns None -> this entire function no-ops immediately,
# matching every other Redis touch in this app's "optional, degrade
# silently" posture.
from core.redis_client import get_redis
from portal.permission_cache import INVALIDATE_CHANNEL, drop_local_cache


def _run_perms_invalidate_subscriber() -> None:
    import json

    client = get_redis()
    if client is None:
        return
    try:
        pubsub = client.pubsub()
        pubsub.subscribe(INVALIDATE_CHANNEL)
        for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                hospital_id = json.loads(message["data"])["hospital_id"]
            except (TypeError, ValueError, KeyError):
                continue
            drop_local_cache(hospital_id)
    except Exception:
        # A subscriber that dies mid-stream (Redis restarted, network blip)
        # simply stops invalidating OTHER processes' local caches early --
        # each process still falls back to Postgres once its own 5-minute
        # local/Redis TTL lapses (permission_cache.py's _CACHE_TTL_SECONDS),
        # so this is a staleness-window regression, never a 500 or a crash.
        pass


def _start_perms_invalidate_subscriber() -> None:
    threading.Thread(target=_run_perms_invalidate_subscriber, daemon=True).start()


def main():
    """`uv run main.py` -- local dev only. Production (Dockerfile/railway.toml)
    invokes `uv run --no-sync uvicorn main:app ...` directly instead, with
    --proxy-headers and no --reload; reload=True here would be wrong there."""
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()

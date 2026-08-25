# auth/google_oauth.py
"""
Section 15: Google OAuth sign-in -- the one NEW identity layer this app
gets. Deliberately does NOT replace auth/session.py/portal/*'s existing
hospital-scoped session token (`_sign_session`/`_verify_session`, still
gating every /api/portal/* route) -- once a Google-authenticated user's
owned hospital is resolved (db.get_hospitals_for_user), /api/auth/select-hospital
below just ISSUES that exact same token, so the whole rest of the portal
(dashboard, settings, doctors, ...) runs completely unchanged. This module
only owns the bit in FRONT of that: resolving "which Google account is
this" and "which hospital(s) do they own."

Session token here is a SEPARATE HMAC-signed "user_id.expires_epoch.sig"
string, using its own AUTH_SECRET (not PORTAL_SECRET) -- same reasoning
this project already applies to ADMIN_SECRET vs TENANTS_ADMIN_SECRET being
different secrets (admin/tenants_api.py's module docstring): a leaked
PORTAL_SECRET today only forges a hospital session; reusing it for user
identity too would let a leak forge arbitrary user identities as well, a
strictly bigger blast radius.

Delivered to the frontend the same way portal/routes/auth.py's token is: a Bearer
token stored in localStorage, not a cookie -- the frontend runs on a
different origin (Vercel vs Railway/localhost:8000), the exact cross-origin
cookie problem portal/routes/auth.py's own module docstring already worked through.
The one place this module DOES use a real browser redirect is the OAuth
dance itself (Google requires a full-page redirect, not a fetch/XHR call),
which stays entirely on THIS backend's own origin throughout (frontend ->
/auth/google/login -> accounts.google.com -> /auth/google/callback, all
same-origin from the browser's perspective except the middle hop to
Google) -- no cross-origin cookie problem there either. The callback then
hands the resulting token to the frontend via a one-time `?token=...` query
param on a redirect to FRONTEND_ORIGIN, not a JSON body, since a redirect
can't carry a response body for the frontend to read directly.

Sign-up vs sign-in is deliberately NOT two different flows: Google OAuth
doesn't naturally distinguish them the way a password form does, so there
is exactly one entry point (/auth/google/login) used both from the landing
page and from /portal/login -- the frontend decides where to go next
(onboarding wizard vs. straight into a hospital vs. a picker) based on
/api/auth/me's owned_hospitals count, not based on which button was
clicked.
"""
import hashlib
import hmac
import time

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, RedirectResponse

import db.repository as db
from core.config import get_settings
from auth.session import _SESSION_TTL_SECONDS, _sign_session

router = APIRouter()

_settings = get_settings()
AUTH_SECRET = _settings.AUTH_SECRET
GOOGLE_CLIENT_ID = _settings.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = _settings.GOOGLE_CLIENT_SECRET
FRONTEND_ORIGIN = _settings.FRONTEND_ORIGIN
# Deliberately shorter-lived than auth/session.py's own 24h hospital session --
# this token only exists to get through /api/auth/me + /api/auth/select-hospital
# right after signing in, not to be browsed against over a whole day the way
# the hospital-scoped session is.
_USER_SESSION_TTL_SECONDS = 60 * 60

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def _sign_user_session(user_id: int, expires_at: int) -> str:
    payload = f"{user_id}.{expires_at}"
    sig = hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _verify_user_session(token: str) -> int | None:
    """Returns the user_id the token is valid for, or None if missing,
    malformed, tampered with, or expired. Byte-for-byte the same shape as
    auth/session.py's _verify_session(), just keyed to user_id + AUTH_SECRET."""
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    user_id_str, expires_str, sig = parts
    payload = f"{user_id_str}.{expires_str}"
    expected_sig = hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        user_id = int(user_id_str)
        expires_at = int(expires_str)
    except ValueError:
        return None
    if time.time() > expires_at:
        return None
    return user_id


def authenticate_user(authorization: str | None):
    """Returns the db.User for a valid 'Bearer <token>' header, or None.
    Exported (not prefixed _) -- admin/onboarding_api.py's wizard-submit
    route needs this too, to link a newly created hospital to whichever
    Google account is currently signed in."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    user_id = _verify_user_session(token)
    if user_id is None:
        return None
    return db.get_user(user_id)


@router.get("/auth/google/login")
async def google_login(request: Request):
    redirect_uri = str(request.url_for("google_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback", name="google_callback")
async def google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse(f"{FRONTEND_ORIGIN}/auth?error=google_sign_in_failed")

    userinfo = token.get("userinfo") or {}
    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name")
    if not google_id or not email:
        return RedirectResponse(f"{FRONTEND_ORIGIN}/auth?error=google_sign_in_failed")

    user = db.get_or_create_user_for_google_login(google_id, email, name)
    expires_at = int(time.time()) + _USER_SESSION_TTL_SECONDS
    session_token = _sign_user_session(user.id, expires_at)
    return RedirectResponse(f"{FRONTEND_ORIGIN}/auth/callback?token={session_token}")


@router.get("/api/auth/me")
async def auth_me(authorization: str | None = Header(default=None)):
    user = authenticate_user(authorization)
    if user is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    hospitals = db.get_hospitals_for_user(user.id)
    return JSONResponse({
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "owned_hospitals": [{"id": h.id, "name": h.name} for h in hospitals],
    })


@router.post("/api/auth/select-hospital")
async def auth_select_hospital(payload: dict, authorization: str | None = Header(default=None)):
    """Issues the exact same hospital-scoped session token
    portal/routes/auth.py's password login issues (_sign_session) -- the frontend
    saves it via the existing savePortalSession() and every /api/portal/*
    route works unchanged from here on. hospital_id is never trusted from
    the client without re-checking ownership server-side."""
    user = authenticate_user(authorization)
    if user is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    hospital_id = (payload or {}).get("hospital_id")
    if not isinstance(hospital_id, int) or not db.user_owns_hospital(hospital_id, user.id):
        return JSONResponse({"error": "You don't have access to that hospital."}, status_code=403)

    hospital = db.get_hospital(hospital_id)
    expires_at = int(time.time()) + _SESSION_TTL_SECONDS
    portal_token = _sign_session(hospital.id, expires_at)
    return JSONResponse({
        "token": portal_token,
        "expires_at": expires_at,
        "hospital": {
            "id": hospital.id,
            "name": hospital.name,
            "data_tier": hospital.data_tier,
            "enabled_features": hospital.enabled_features,
        },
    })

# auth/google_oauth.py
"""
Section 15: Google OAuth sign-in -- the one NEW identity layer this app
gets. This module owns "which Google account is this" and what happens
right after: if that identity already has a staff_details row (an admin
created via the staff-management UI, or the person who onboarded this
hospital -- migration 0018 folded hospital ownership into StaffDetail,
role='admin', no separate 'owner' role, confirmed with the user), the
callback below issues a real staff refresh token directly (auth/refresh_tokens.py's
issue_refresh_token(), the same one portal/routes/staff_auth.py's password
login issues) and the frontend exchanges it for a full session via
/api/portal/staff/refresh -- so Google sign-in and staff email+password
sign-in land the SAME session type, and the whole rest of the portal only
ever needs to understand one. One identity, one hospital
(confirmed with the user: staff_details.identity_id is a 1:1 PK), so there
is no multi-hospital picker step here -- an identity with a staff_details
row goes straight into that one hospital.

If the identity has NO staff_details row yet (nobody has run
db.link_hospital_owner for them -- a brand new Google sign-in that hasn't
onboarded a hospital), this falls back to the short-lived user-only session
(`_sign_user_session`, this module's own separate AUTH_SECRET-signed
"user_id.expires_epoch.sig" scheme) just long enough for the onboarding
wizard to authenticate its submission (authenticate_user(), still used by
admin/onboarding_api.py) -- once submit_onboarding() calls
db.link_hospital_owner() for this same identity, their NEXT Google sign-in
takes the staff-session branch above instead.

Both token schemes are delivered to the frontend the same way
portal/routes/staff_auth.py's are: query params on a redirect to
FRONTEND_ORIGIN, not a JSON body, since a redirect can't carry a response
body for the frontend to read directly. The OAuth dance itself (Google
requires a full-page redirect, not a fetch/XHR call) stays entirely on THIS
backend's own origin throughout (frontend -> /auth/google/login ->
accounts.google.com -> /auth/google/callback, all same-origin from the
browser's perspective except the middle hop to Google) -- no cross-origin
cookie problem, which is also why every session here is a Bearer token in
localStorage, never a cookie (frontend runs on a different origin --
Vercel/Vercel-preview vs Railway/localhost:8000).
"""
import hashlib
import hmac
import time

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, RedirectResponse

import db.repository as db
from auth.refresh_tokens import issue_refresh_token
from core.config import get_settings

router = APIRouter()

_settings = get_settings()
AUTH_SECRET = _settings.AUTH_SECRET
GOOGLE_CLIENT_ID = _settings.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = _settings.GOOGLE_CLIENT_SECRET
FRONTEND_ORIGIN = _settings.FRONTEND_ORIGIN
# Short-lived: this token only exists to get through /api/auth/me and the
# onboarding wizard's own submission call right after signing in, for a
# Google identity that has no staff_details row yet -- not to be browsed
# against over a long session the way a staff JWT is.
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

    staff = db.get_staff_user_by_email(email)
    if staff is not None and staff["is_active"]:
        # This identity already has a staff_details row (an admin created
        # via the staff-management UI, or someone db.link_hospital_owner()
        # was already called for) -- skip the short-lived user-only session
        # entirely and go straight to a real staff session, same as
        # portal/routes/staff_auth.py's password login issues. Only the
        # refresh token travels in the URL (not the access token too) --
        # /api/portal/staff/refresh mints the access token + full session
        # (staff summary, permissions) the frontend actually needs, so
        # nothing sensitive beyond a single-use-rotating refresh token ever
        # sits in a URL that could end up in browser history or a server log.
        refresh_token = issue_refresh_token(staff["id"], staff["hospital_id"], staff["role"])
        return RedirectResponse(f"{FRONTEND_ORIGIN}/auth/callback?staff_refresh_token={refresh_token}")

    # No staff_details row yet -- a brand new Google sign-in that hasn't
    # onboarded a hospital. Short-lived user-only session, just long enough
    # for the onboarding wizard to authenticate its submission
    # (authenticate_user(), used by admin/onboarding_api.py) -- once
    # submit_onboarding() calls db.link_hospital_owner() for this identity,
    # their next Google sign-in takes the staff-session branch above.
    expires_at = int(time.time()) + _USER_SESSION_TTL_SECONDS
    session_token = _sign_user_session(user.id, expires_at)
    return RedirectResponse(f"{FRONTEND_ORIGIN}/auth/callback?token={session_token}")


@router.get("/api/auth/me")
async def auth_me(authorization: str | None = Header(default=None)):
    """Only reached for the "no staff_details row yet" case now (the
    callback above routes a Google sign-in with an existing staff account
    straight to a staff session, bypassing this entirely) -- the frontend
    calls this to confirm there's still no hospital before sending the
    person to the onboarding wizard."""
    user = authenticate_user(authorization)
    if user is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    hospitals = db.get_hospitals_for_user(user.id)
    return JSONResponse({
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "owned_hospitals": [{"id": h.id, "name": h.name} for h in hospitals],
    })

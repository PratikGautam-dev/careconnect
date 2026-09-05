# auth/google_calendar_oauth.py
"""Google Meet integration (Spec.md Section 0): the OAuth dance a hospital
ADMIN goes through to connect ONE Google account for the whole hospital, so
every doctor's tele-consultation bookings there can create a real Calendar
event with a Meet link instead of the existing Jitsi room
(flows/booking/types/tele_consultation.py falls back to Jitsi for any
hospital not connected -- this module never touches that fallback directly,
it only ever populates db.repositories.google_calendar's table). Not a
per-doctor connection (confirmed with the user, a revision of the original
per-doctor plan) -- doctors never see this flow at all; it lives on the
hospital admin's own Settings page.

A SEPARATE authlib OAuth client from auth/google_oauth.py's hospital-owner
sign-in flow (confirmed with the user) -- its own GOOGLE_CALENDAR_CLIENT_ID/
SECRET (core/config.py), so a leaked credential for one can never be used
for the other's scope. Registered the same way google_oauth.py's client is
(unconditionally, even with empty strings -- authlib doesn't touch the
network at registration time, only on first actual use, so this never
crashes the app at import/boot time regardless of whether these env vars
are set).

Carries the connecting admin's hospital_id across the Google redirect via
Starlette's session cookie (the same SessionMiddleware instance
auth/google_oauth.py's own OAuth dance already relies on for CSRF state --
see main.py), not a query param on the callback -- Google's own `state`
param is authlib's to manage internally. The initial /connect hit itself is
authenticated via a `token` QUERY param (not an Authorization header),
because this is a full-page browser navigation (an <a href>, not a fetch)
that the browser initiates directly, so there is no way to attach a custom
header to it -- same reasoning portal token-delivery-via-redirect already
follows in the other direction (auth/google_oauth.py's own docstring). Only
a staff member with "settings" write permission (i.e. an admin) can start
this -- checked the same way portal/routes/settings.py's own
/api/portal/calendar/disconnect route is gated, since this action is
equally sensitive.

access_type=offline + prompt=consent on every /connect: Google only returns
a refresh_token on a consent screen (not a silent, cached-consent redirect),
so prompt=consent is forced every time to guarantee one comes back, even for
a hospital reconnecting after a prior disconnect."""
import logging
from datetime import datetime

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

import db.repository as db
from core.config import get_settings
from core.crypto import CryptoNotConfiguredError, encrypt_secret
from modules.google_calendar import CALENDAR_SCOPES, is_calendar_integration_configured
from portal.deps import get_current_staff, require_permission

logger = logging.getLogger(__name__)
router = APIRouter()

_settings = get_settings()
FRONTEND_ORIGIN = _settings.FRONTEND_ORIGIN

oauth_calendar = OAuth()
oauth_calendar.register(
    name="google_calendar",
    client_id=_settings.GOOGLE_CALENDAR_CLIENT_ID,
    client_secret=_settings.GOOGLE_CALENDAR_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": " ".join(CALENDAR_SCOPES)},
)

_SESSION_HOSPITAL_ID_KEY = "gcal_connect_hospital_id"
_SETTINGS_REDIRECT_PATH = "/portal/settings"


@router.get("/auth/google/calendar/connect")
async def google_calendar_connect(request: Request, token: str = ""):
    """Graceful, non-500 errors for every way this can be unusable right
    now: feature not configured (the env vars this whole build was asked to
    tolerate being unset), or a missing/invalid/expired admin token, or a
    valid staff token that simply isn't an admin's."""
    if not is_calendar_integration_configured():
        return _json_error("Google Calendar integration isn't configured yet.", 503)
    principal = get_current_staff(f"Bearer {token}" if token else None)
    if principal is None:
        return _json_error("Not authenticated.", 401)
    forbidden = require_permission(principal, "settings", "write")
    if forbidden:
        return forbidden
    request.session[_SESSION_HOSPITAL_ID_KEY] = principal.hospital.id
    redirect_uri = str(request.url_for("google_calendar_callback"))
    return await oauth_calendar.google_calendar.authorize_redirect(
        request, redirect_uri, access_type="offline", prompt="consent",
    )


@router.get("/auth/google/calendar/callback", name="google_calendar_callback")
async def google_calendar_callback(request: Request):
    hospital_id = request.session.pop(_SESSION_HOSPITAL_ID_KEY, None)
    if not hospital_id:
        return RedirectResponse(f"{FRONTEND_ORIGIN}{_SETTINGS_REDIRECT_PATH}?calendar_error=session_expired")
    if not is_calendar_integration_configured():
        return RedirectResponse(f"{FRONTEND_ORIGIN}{_SETTINGS_REDIRECT_PATH}?calendar_error=not_configured")

    try:
        token = await oauth_calendar.google_calendar.authorize_access_token(request)
    except Exception:
        logger.warning("Google Calendar OAuth callback failed for hospital %s.", hospital_id, exc_info=True)
        return RedirectResponse(f"{FRONTEND_ORIGIN}{_SETTINGS_REDIRECT_PATH}?calendar_error=google_auth_failed")

    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")
    if not access_token or not refresh_token:
        # No refresh token means Google didn't grant offline access this
        # time (rare with prompt=consent, but possible) -- a connection we
        # can't renew is worse than no connection, so this is a clean error,
        # not a half-working row.
        return RedirectResponse(f"{FRONTEND_ORIGIN}{_SETTINGS_REDIRECT_PATH}?calendar_error=no_refresh_token")

    expires_at = token.get("expires_at")
    expires_at_iso = datetime.fromtimestamp(expires_at).isoformat() if expires_at else datetime.now().isoformat()
    userinfo = token.get("userinfo") or {}
    google_email = userinfo.get("email")

    key = get_settings().CALENDAR_TOKEN_ENCRYPTION_KEY
    try:
        encrypted_access = encrypt_secret(access_token, key)
        encrypted_refresh = encrypt_secret(refresh_token, key)
    except CryptoNotConfiguredError:
        return RedirectResponse(f"{FRONTEND_ORIGIN}{_SETTINGS_REDIRECT_PATH}?calendar_error=not_configured")

    db.upsert_calendar_connection(hospital_id, google_email, encrypted_access, encrypted_refresh, expires_at_iso)
    return RedirectResponse(f"{FRONTEND_ORIGIN}{_SETTINGS_REDIRECT_PATH}?calendar=connected")


def _json_error(message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)

# modules/google_calendar.py
"""Google Meet integration (Spec.md Section 0): creates a real Google
Calendar event (with a Meet link) for a tele-consultation appointment, using
the ONE Google account a hospital's admin has connected on the hospital's
own behalf (auth/google_calendar_oauth.py, db/repositories/google_calendar.py)
-- not a per-doctor connection. Every doctor at a connected hospital's
tele-consultation bookings use that same hospital-level calendar; a hospital
with no connection (everyone, until GOOGLE_CALENDAR_CLIENT_ID/SECRET/
CALENDAR_TOKEN_ENCRYPTION_KEY are set AND an admin explicitly connects) keeps
getting a Jitsi room exactly as before -- alongside, not replacing, that
existing link (flows/booking/types/tele_consultation.py).

Uses google-api-python-client + google-auth (both already project
dependencies -- modules/booking/calendar.py, the now-retired original
fork's Google Calendar module, pulled them in) rather than hand-rolled REST
calls, specifically for Credentials' built-in expired-token refresh handling.

Every function here is written to NEVER raise into its caller for anything
that isn't a genuine programming error -- a misconfigured/revoked/expired-
beyond-refresh connection, a Google API outage, or a malformed response all
return None, so tele_consultation.py's caller can unconditionally fall back
to Jitsi. This mirrors the project's established discipline (delay_doctor_
remaining_today_appointments()'s own per-row try/except) of never letting a
best-effort integration fail the actual booking it's attached to."""
import logging
from datetime import datetime, timedelta

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import db.repository as db
from core.config import get_settings
from core.crypto import CryptoNotConfiguredError, decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)

CALENDAR_SCOPES = ["openid", "email", "https://www.googleapis.com/auth/calendar.events"]


def is_calendar_integration_configured() -> bool:
    """All three settings must be set -- a partially-configured deployment
    (e.g. the OAuth client set up but the encryption key not yet generated)
    is treated as fully unconfigured, never a partial/degraded mode."""
    settings = get_settings()
    return bool(
        settings.GOOGLE_CALENDAR_CLIENT_ID
        and settings.GOOGLE_CALENDAR_CLIENT_SECRET
        and settings.CALENDAR_TOKEN_ENCRYPTION_KEY
    )


def _valid_credentials_for(hospital_id: int) -> Credentials | None:
    """Decrypts this hospital's stored tokens and returns live google-auth
    Credentials, refreshing (and persisting the new access token) first if
    expired. None for any failure -- no connection, misconfigured
    encryption key, or a refresh that Google itself rejects (e.g. the
    connected admin account revoked access from their own Google account
    settings)."""
    if not is_calendar_integration_configured():
        return None
    connection = db.get_calendar_connection(hospital_id)
    if connection is None:
        return None
    settings = get_settings()
    key = settings.CALENDAR_TOKEN_ENCRYPTION_KEY
    try:
        access_token = decrypt_secret(connection["encrypted_access_token"], key)
        refresh_token = decrypt_secret(connection["encrypted_refresh_token"], key)
    except CryptoNotConfiguredError:
        logger.warning("Google Calendar: could not decrypt stored tokens for hospital %s.", hospital_id)
        return None
    creds = Credentials(
        token=access_token, refresh_token=refresh_token, token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CALENDAR_CLIENT_ID, client_secret=settings.GOOGLE_CALENDAR_CLIENT_SECRET,
        scopes=CALENDAR_SCOPES,
    )
    if creds.expired or creds.token is None:
        try:
            creds.refresh(GoogleAuthRequest())
        except Exception:
            logger.warning("Google Calendar: refresh failed for hospital %s (connection may be revoked).", hospital_id)
            return None
        try:
            new_encrypted_access = encrypt_secret(creds.token, key)
        except CryptoNotConfiguredError:
            return None
        db.update_calendar_access_token(hospital_id, new_encrypted_access, creds.expiry.isoformat() if creds.expiry else "")
    return creds


def create_meet_event(hospital_id: int, summary: str, scheduled_at: datetime, duration_minutes: int) -> str | None:
    """Creates a Calendar event on this hospital's connected calendar with a
    Google Meet link, returning that link's URL -- or None (never raises)
    if the hospital isn't connected, the connection can't be refreshed, or
    Google's API call itself fails for any reason."""
    creds = _valid_credentials_for(hospital_id)
    if creds is None:
        return None
    connection = db.get_calendar_connection(hospital_id)
    end_at = scheduled_at + timedelta(minutes=duration_minutes)
    event_body = {
        "summary": summary,
        "start": {"dateTime": scheduled_at.isoformat()},
        "end": {"dateTime": end_at.isoformat()},
        "conferenceData": {
            "createRequest": {
                "requestId": f"careconnect-{hospital_id}-{scheduled_at.timestamp():.0f}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            },
        },
    }
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        event = service.events().insert(
            calendarId=connection["calendar_id"] if connection else "primary",
            body=event_body, conferenceDataVersion=1,
        ).execute()
    except HttpError:
        logger.warning("Google Calendar: event creation failed for hospital %s.", hospital_id, exc_info=True)
        return None
    except Exception:
        logger.warning("Google Calendar: unexpected error creating event for hospital %s.", hospital_id, exc_info=True)
        return None
    entry_points = (event.get("conferenceData") or {}).get("entryPoints") or []
    for entry_point in entry_points:
        if entry_point.get("entryPointType") == "video" and entry_point.get("uri"):
            return entry_point["uri"]
    return None

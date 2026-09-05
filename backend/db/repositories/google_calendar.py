# db/repositories/google_calendar.py
"""Google Meet integration (Spec.md Section 0): storage for one HOSPITAL's
optional Google Calendar connection -- one admin-connected account per
hospital, used for every doctor's tele-consultation Meet links (confirmed
with the user: not one connection per doctor). A row's mere EXISTENCE means
"this hospital is connected" -- unlike db/repositories/hospital_settings.py's
lazy blank-row pattern, no row is ever created except by a successful OAuth
callback (auth/google_calendar_oauth.py), and disconnect deletes it outright
(no soft-delete column -- reconnecting just inserts a fresh row).

access_token/refresh_token are ALREADY Fernet-encrypted by the caller
(core/crypto.py) before reaching every function here -- this module only
ever stores/returns opaque strings, never encrypts/decrypts anything itself.
That split keeps this repository ignorant of CALENDAR_TOKEN_ENCRYPTION_KEY
entirely, same as every other repository module never touching a secret
value's own crypto."""
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.connection import get_session
from db.orm_models import GoogleCalendarConnection


def _row_to_dict(row: GoogleCalendarConnection) -> dict:
    return {
        "hospital_id": row.hospital_id,
        "google_email": row.google_email,
        "encrypted_access_token": row.encrypted_access_token,
        "encrypted_refresh_token": row.encrypted_refresh_token,
        "access_token_expires_at": row.access_token_expires_at,
        "calendar_id": row.calendar_id,
        "connected_at": row.connected_at,
        "updated_at": row.updated_at,
    }


def get_calendar_connection(hospital_id: int) -> dict | None:
    session = get_session()
    row = session.execute(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.hospital_id == hospital_id)
    ).scalar_one_or_none()
    return _row_to_dict(row) if row else None


def upsert_calendar_connection(
    hospital_id: int, google_email: str | None,
    encrypted_access_token: str, encrypted_refresh_token: str, access_token_expires_at: str,
    calendar_id: str = "primary",
) -> dict:
    """The OAuth callback's own write -- a fresh connect, or the hospital's
    admin reconnecting/re-consenting overwrites the existing row entirely
    (including a possibly-new refresh token; Google only returns one on the
    first consent unless prompt=consent forces a new one every time, which
    auth/google_calendar_oauth.py always passes for exactly this reason)."""
    now = datetime.now().isoformat()
    session = get_session()
    session.execute(
        pg_insert(GoogleCalendarConnection)
        .values(
            hospital_id=hospital_id, google_email=google_email,
            encrypted_access_token=encrypted_access_token, encrypted_refresh_token=encrypted_refresh_token,
            access_token_expires_at=access_token_expires_at, calendar_id=calendar_id,
            connected_at=now, updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["hospital_id"],
            set_={
                "google_email": google_email,
                "encrypted_access_token": encrypted_access_token, "encrypted_refresh_token": encrypted_refresh_token,
                "access_token_expires_at": access_token_expires_at, "calendar_id": calendar_id,
                "updated_at": now,
            },
        )
    )
    session.commit()
    return get_calendar_connection(hospital_id)


def update_calendar_access_token(hospital_id: int, encrypted_access_token: str, access_token_expires_at: str) -> None:
    """Called after a refresh-token round trip (modules/google_calendar.py)
    for an ALREADY-connected hospital -- only the access token/expiry
    actually change; the refresh token itself is long-lived and untouched
    here. A plain UPDATE (not an upsert): this is never the first write for
    a hospital, so there is nothing to insert a fallback row for."""
    session = get_session()
    session.execute(
        update(GoogleCalendarConnection)
        .where(GoogleCalendarConnection.hospital_id == hospital_id)
        .values(encrypted_access_token=encrypted_access_token, access_token_expires_at=access_token_expires_at,
                updated_at=datetime.now().isoformat())
    )
    session.commit()


def delete_calendar_connection(hospital_id: int) -> bool:
    session = get_session()
    result = session.execute(delete(GoogleCalendarConnection).where(GoogleCalendarConnection.hospital_id == hospital_id))
    session.commit()
    return result.rowcount > 0

# auth/session.py
"""
Session-signing logic that
portal/*, auth/google_oauth.py both still import directly (a Bearer-token
session, not a cookie, is the only session mechanism either of those
actually uses now) plus one shared query helper for the new-booking flow.

No FastAPI router in this module anymore -- there are no routes left to
register, so app.py no longer includes one for this module.
"""
import hashlib
import hmac
import time

import connectors
from core.config import get_settings

PORTAL_SECRET = get_settings().PORTAL_SECRET
# Deliberately short given the "basic protection, not production-grade
# auth" posture this project applies to every shared-secret/session scheme
# -- re-issued via a fresh password login rather than silently extended.
# Google OAuth sign-in doesn't issue this token at all (auth/google_oauth.py's
# callback issues a staff JWT session directly); only portal/routes/auth.py's
# shared-hospital-password login does.
_SESSION_TTL_SECONDS = 24 * 60 * 60


def _sign_session(hospital_id: int, expires_at: int) -> str:
    payload = f"{hospital_id}.{expires_at}"
    sig = hmac.new(PORTAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _verify_session(cookie_value: str) -> int | None:
    """Returns the hospital_id the token is valid for, or None if missing,
    malformed, tampered with, or expired. Despite the parameter name (kept
    for compatibility with existing callers), this verifies a Bearer token
    now, not a cookie -- see portal/routes/auth.py's module docstring for why."""
    if not cookie_value:
        return None
    parts = cookie_value.split(".")
    if len(parts) != 3:
        return None
    hospital_id_str, expires_str, sig = parts
    payload = f"{hospital_id_str}.{expires_str}"
    expected_sig = hmac.new(PORTAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        hospital_id = int(hospital_id_str)
        expires_at = int(expires_str)
    except ValueError:
        return None
    if time.time() > expires_at:
        return None
    return hospital_id


def _build_new_booking_context(hospital) -> tuple[list[dict], dict, list[dict]]:
    """Shared by portal/routes/bookings.py's new-booking GET endpoint --
    departments/doctors and resources (diagnostic tests), all hospital-
    scoped and read through the SAME connector interface the WhatsApp flow
    uses, not a parallel query path.

    A form only ever needs ONE doctor's or ONE resource's slots at
    a time (whichever the user just picked, or whichever the appointment/
    visit already has, for RescheduleDialog and the patient page's "Book
    now" panel), so slots aren't eager-loaded for every doctor/resource
    here -- that would turn one page open into N doctors + M resources,
    each several real DB round trips (a Redis hit still means 2+ queries; a
    miss means several more plus a write), not a single cheap query per
    item. Slots are fetched lazily, one entity
    at a time, via GET /api/portal/new-booking/slots?doctor_id=/?diagnostic_test_id=
    (portal_new_booking_slots() in bookings.py) instead."""
    connector = connectors.get_connector_for_hospital(hospital)
    # get_all_departments (not get_departments) -- this builds the STAFF
    # portal's own new-booking form context, which must still offer a
    # department a staff member hid from the WhatsApp picker (they can
    # still manually book a walk-in/phone patient into it).
    departments = connector.get_all_departments(hospital.id)
    doctors_by_department = {dept["id"]: connector.get_doctors(hospital.id, dept["id"]) for dept in departments}
    resources = connector.get_diagnostic_test_summaries(hospital.id)
    return departments, doctors_by_department, resources

# auth/session.py
"""
Section 15 follow-up: this used to be a full server-rendered HTML staff
portal (login, dashboard, appointments, doctors, settings, new-booking).
That's genuinely redundant now that the Next.js frontend
(frontend/src/app/portal/*, backed by portal/routes/*'s JSON endpoints) does
all of it -- removed. What's left is the session-signing logic
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
# Google OAuth sign-in no longer issues this token at all (migration 0018 --
# auth/google_oauth.py's callback issues a staff JWT session directly now);
# only portal/routes/auth.py's legacy shared-hospital-password login still
# does.
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


def _build_new_booking_context(hospital) -> tuple[list[dict], dict, dict]:
    """Shared by portal/routes/bookings.py's new-booking GET (blank form) and POST
    (re-render on error) endpoints -- departments/doctors/available-slots,
    all hospital-scoped and all read through the SAME connector interface
    (Section 12.6.2) the WhatsApp flow uses, not a parallel query path."""
    connector = connectors.get_connector_for_hospital(hospital)
    departments = connector.get_departments(hospital.id)
    doctors_by_department: dict[str, list[dict]] = {}
    slots_by_doctor: dict[str, dict[str, list[dict]]] = {}
    for dept in departments:
        doctors = connector.get_doctors(hospital.id, dept["id"])
        doctors_by_department[dept["id"]] = doctors
        for doc in doctors:
            slots = connector.get_available_slots(hospital.id, doc["id"])
            by_date: dict[str, list[dict]] = {}
            for s in slots:
                by_date.setdefault(s["date"], []).append({"id": s["id"], "label": s["label"]})
            slots_by_doctor[doc["id"]] = by_date
    return departments, doctors_by_department, slots_by_doctor

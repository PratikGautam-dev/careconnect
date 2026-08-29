# auth/doctor_session.py
"""
Dedicated doctor-login session token -- a THIRD, separate auth path
alongside the shared staff-portal password (auth/session.py) and Google
OAuth (auth/google_oauth.py). Deliberately its own module, not a variant of
auth/session.py's `_sign_session`, because the thing it authenticates is a
different scope: `_sign_session` proves "this bearer may act as HOSPITAL X's
shared staff account" (every doctor, every note, every appointment at that
hospital); this proves "this bearer may act as DOCTOR Y at hospital X",
nothing more.

Same HMAC-signed "field.field....sig" shape as auth/session.py's own token
(a Bearer token, not a cookie -- same cross-origin reasoning
auth/google_oauth.py's own module docstring already worked through), but
carries doctor_id as well as hospital_id, and is signed with its own
DOCTOR_SECRET (core/config.py) rather than PORTAL_SECRET -- so a leaked
PORTAL_SECRET can never forge a doctor-scoped token, and a leaked
DOCTOR_SECRET can never forge a hospital-wide staff session. This is the
structural half of the doctor-login isolation guarantee: every
doctor-portal route (portal/routes/doctor_portal.py) reads doctor_id from
THIS verified token, never from a request parameter, so there is no route
that can be asked for "some other doctor's" data in the first place.
"""
import hashlib
import hmac
import time

from core.config import get_settings

DOCTOR_SECRET = get_settings().DOCTOR_SECRET
# Same short-lived, re-issued-not-extended posture as auth/session.py's own
# _SESSION_TTL_SECONDS -- this project's standing "basic protection, not
# production-grade auth" posture for every shared-secret/session scheme.
_DOCTOR_SESSION_TTL_SECONDS = 24 * 60 * 60


def sign_doctor_session(hospital_id: int, doctor_id: str, expires_at: int) -> str:
    payload = f"{hospital_id}.{doctor_id}.{expires_at}"
    sig = hmac.new(DOCTOR_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def issue_doctor_session(hospital_id: int, doctor_id: str) -> str:
    expires_at = int(time.time()) + _DOCTOR_SESSION_TTL_SECONDS
    return sign_doctor_session(hospital_id, doctor_id, expires_at)


def verify_doctor_session(token: str) -> tuple[int, str] | None:
    """Returns (hospital_id, doctor_id) the token is valid for, or None if
    missing, malformed, tampered with, or expired. doctor_id can itself
    contain '.' (schema: doctors.id is a free-form TEXT slug) -- the payload
    is split from the RIGHT (hospital_id first, then sig last) so an
    embedded '.' in doctor_id can't desync the split, using the same
    rsplit-from-known-ends approach as the fixed hospital_id/expires_at
    fields around it."""
    if not token:
        return None
    parts = token.split(".")
    if len(parts) < 4:
        return None
    hospital_id_str = parts[0]
    sig = parts[-1]
    expires_str = parts[-2]
    doctor_id = ".".join(parts[1:-2])
    if not doctor_id:
        return None
    payload = f"{hospital_id_str}.{doctor_id}.{expires_str}"
    expected_sig = hmac.new(DOCTOR_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        hospital_id = int(hospital_id_str)
        expires_at = int(expires_str)
    except ValueError:
        return None
    if time.time() > expires_at:
        return None
    return hospital_id, doctor_id

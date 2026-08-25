import hashlib

import db.repository as db
from auth.session import _verify_session


def _hospital_summary(hospital) -> dict:
    return {
        "id": hospital.id,
        "name": hospital.name,
        "data_tier": hospital.data_tier,
        "enabled_features": hospital.enabled_features,
    }


def _authenticate(authorization: str | None):
    """Returns the Hospital for a valid 'Bearer <token>' header, or None."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    hospital_id = _verify_session(token)
    if hospital_id is None:
        return None
    return db.get_hospital(hospital_id)


def _session_id(authorization: str | None) -> str | None:
    """Section 12.10's deliberate partial audit trail: real per-staff
    accounts don't exist (portal auth is one shared password per hospital),
    so a note/document can only be traced back to a *login session*, not a
    named person. A hash of the Bearer token (not the raw token) uniquely
    identifies one login session -- storing it raw in a DB row that other
    staff at the same hospital can read via a future admin view would be a
    real credential leak, since the raw token still authenticates."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return hashlib.sha256(token.encode()).hexdigest()[:16]

import hashlib

from fastapi.responses import JSONResponse

import db.repository as db
from auth.doctor_session import verify_doctor_session
from auth.session import _verify_session
from portal.capabilities import get_capabilities, has_capability


def _hospital_summary(hospital) -> dict:
    return {
        "id": hospital.id,
        "name": hospital.name,
        "data_tier": hospital.data_tier,
        "enabled_features": hospital.enabled_features,
        # Tenant-type-driven capability gating (tenant-capability-gating-plan.md):
        # lets the portal frontend hide nav entries (e.g. "Doctors" for a
        # clinic) instead of only relying on the backend's 403 -- same
        # get_capabilities() the backend routes already gate on, so the two
        # can never disagree.
        "tenant_type": hospital.tenant_type,
        "admin_capabilities": sorted(get_capabilities(hospital)),
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


def _authenticate_doctor(authorization: str | None):
    """Returns (Hospital, doctor_id) for a valid doctor-scoped 'Bearer
    <token>' header, or None. Deliberately separate from `_authenticate`
    above, not a variant of it -- a doctor token and a shared-staff-portal
    token are signed with different secrets (auth/doctor_session.py's own
    module docstring) and are never interchangeable, so this can't
    accidentally accept a staff token or vice versa.

    Every route in portal/routes/doctor_portal.py calls this, and reads
    doctor_id ONLY from its return value, never from a path/query/body
    parameter -- that's what makes it structurally impossible for a doctor's
    own valid token to be used to ask for a DIFFERENT doctor's data at the
    same hospital (the isolation gap the shared staff portal has today,
    since it has no doctor-scoped concept at all)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    verified = verify_doctor_session(token)
    if verified is None:
        return None
    hospital_id, doctor_id = verified
    hospital = db.get_hospital(hospital_id)
    if hospital is None:
        return None
    return hospital, doctor_id


def require_capability(hospital, capability: str) -> JSONResponse | None:
    """Tenant-type-driven capability gating (tenant-capability-gating-plan.md).
    Deliberately a plain helper following this file's OWN established
    manual-guard-clause idiom (`if hospital is None: return JSONResponse(...)`)
    rather than a FastAPI `Depends(...)` factory -- `_authenticate` above is
    itself a plain function every route calls manually (ARCHITECTURE_PLAN.md's
    Phase 6 note: converting to dependency injection is a real behavior-shape
    change, not a pure move, and out of scope here too) -- so this matches
    the pattern already used everywhere else in `portal/routes/*.py` instead
    of introducing a second, inconsistent authorization style.

    Call AFTER the existing `_authenticate` 401 check, same "if result:
    return result" early-return shape:

        hospital = _authenticate(authorization)
        if hospital is None:
            return JSONResponse({"error": "Not authenticated."}, status_code=401)
        forbidden = require_capability(hospital, "manage_doctors")
        if forbidden:
            return forbidden

    Returns a 403 JSONResponse if `hospital` lacks `capability`, else None."""
    if not has_capability(hospital, capability):
        return JSONResponse(
            {"error": f"This tenant does not have the '{capability}' capability."}, status_code=403,
        )
    return None


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

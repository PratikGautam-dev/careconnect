import hashlib

from fastapi.responses import JSONResponse

import db.repository as db
from auth.doctor_session import verify_doctor_session
from auth.jwt_session import verify_access_token
from auth.session import _verify_session
from portal.capabilities import get_capabilities, has_capability
from portal.permissions import has_permission


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
    """Returns the Hospital for a valid 'Bearer <token>' header, or None.

    RBAC (docs/rbac-redis-plan.md): the vast majority of portal/routes/*.py
    files (settings, patients, dashboard, doctors, appointment_types,
    daycare_duration_options, documents, bookings, handoffs) were written
    against ONLY this function, before staff_users/JWTs existed, and every
    one of them just needs a Hospital -- none of them call
    require_permission(), only (some of them) require_capability(), which is
    the orthogonal tenant-level gate and is untouched by any of this. Rather
    than touching every one of those route files to also try
    get_current_staff(), this function itself now accepts EITHER token: the
    legacy shared-hospital-password session (_verify_session, tried first
    since it's cheaper -- no DB round trip) OR a staff JWT (verify_access_token),
    resolved to that staff member's hospital. This is what makes logging in
    through the NEW unified staff login work on every existing route
    immediately, not just the handful (doctor_portal.py, staff_auth.py,
    roles.py, staff.py) written against get_current_staff() directly.

    Deliberately loses role/doctor_id granularity here -- a staff JWT
    authenticated through this path is only ever a Hospital, same as the old
    shared-password token always was, so a receptionist or doctor logging in
    still gets whatever these NOT-yet-permission-gated routes always granted
    every authenticated caller. That's an accepted gap for this rollout
    phase (docs/rbac-redis-plan.md's Phase 6 cleanup is what tightens these
    routes to require_permission() one at a time), not a regression -- it's
    exactly the access level the legacy shared password already gave
    everyone at this hospital."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    hospital_id = _verify_session(token)
    if hospital_id is not None:
        return db.get_hospital(hospital_id)

    claims = verify_access_token(token, expected_typ="staff")
    if claims is None:
        return None
    staff = db.get_staff_user_by_id(claims["sub"])
    if staff is None or not staff["is_active"] or staff["token_version"] != claims["tv"]:
        return None
    return db.get_hospital(staff["hospital_id"])


def _authenticate_with_role(authorization: str | None):
    """Like `_authenticate()`, but also returns (role, doctor_id) when the
    caller is a staff JWT -- both None for the legacy shared-hospital-
    password session, same "no role concept" gap `_authenticate()` already
    documents. For routes that need to scope data to "this doctor's own"
    while still accepting that legacy session."""
    principal = get_current_staff(authorization)
    if principal is not None:
        return principal.hospital, principal.role, principal.doctor_id
    hospital = _authenticate(authorization)
    if hospital is None:
        return None, None, None
    return hospital, None, None


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


class StaffPrincipal:
    """The unified, individually-logged-in identity docs/rbac-redis-plan.md
    introduces -- returned by get_current_staff() below in place of the bare
    Hospital `_authenticate` returns, since a permission check needs `role`
    (and a Doctor route needs `doctor_id`) that a Hospital alone can't carry.
    Deliberately a plain attribute-holding object, not a dataclass/pydantic
    model -- nothing here is (de)serialized independently of the route that
    builds the JSON response, so there's no validation/parsing this would
    buy over a constructor that just assigns."""

    def __init__(self, hospital, staff_id: int, role: str, name: str, doctor_id: str | None):
        self.hospital = hospital
        self.staff_id = staff_id
        self.role = role
        self.name = name
        self.doctor_id = doctor_id


def get_current_staff(authorization: str | None) -> StaffPrincipal | None:
    """Returns the StaffPrincipal for a valid staff-scoped 'Bearer <JWT>'
    header, or None. Verifying the JWT signature/expiry alone is NOT enough
    to trust `role`/`hospital_id` off the token's own claims -- both can go
    stale the instant an admin edits this staff member's row (a promotion, a
    deactivation, a password reset elsewhere), and the access token can live
    for up to 15 minutes (auth/jwt_session.py's TTL) before it would
    naturally re-verify against fresh data on its own. So this ALWAYS
    re-fetches the staff_users row fresh from Postgres and:
      - rejects if the row no longer exists or is_active is now False
        (deactivation takes effect immediately, not at next natural expiry);
      - rejects if the row's CURRENT token_version no longer matches the
        token's `tv` claim (the actual revocation mechanism -- see
        staff_users.py's _bump_token_version() callers for what bumps it);
      - returns a StaffPrincipal built from the FRESH row's hospital_id/
        role/doctor_id, never the token's own claims, so a role change is
        honored on the very next request, not just the next login.
    This DB round-trip is the tradeoff explicitly accepted for real,
    immediate revocation -- token_version-only checking (skipping the
    is_active/role refresh) would still be revocable but could serve a
    request against a role the DB no longer agrees this person has."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    claims = verify_access_token(token, expected_typ="staff")
    if claims is None:
        return None
    staff = db.get_staff_user_by_id(claims["sub"])
    if staff is None or not staff["is_active"] or staff["token_version"] != claims["tv"]:
        return None
    hospital = db.get_hospital(staff["hospital_id"])
    if hospital is None:
        return None
    return StaffPrincipal(hospital, staff["id"], staff["role"], staff["name"], staff["doctor_id"])


def require_permission(principal: StaffPrincipal, page_key: str, action: str) -> JSONResponse | None:
    """Same "forbidden = require_permission(...); if forbidden: return
    forbidden" early-return shape as require_capability() above -- call
    AFTER the get_current_staff() 401 check:

        principal = get_current_staff(authorization)
        if principal is None:
            return JSONResponse({"error": "Not authenticated."}, status_code=401)
        forbidden = require_permission(principal, "staff", "write")
        if forbidden:
            return forbidden

    Returns a 403 JSONResponse if this principal's role lacks `action` on
    `page_key` at its own hospital, else None."""
    if not has_permission(principal.hospital.id, principal.role, page_key, action):
        return JSONResponse(
            {"error": f"Your role does not have '{action}' access to '{page_key}'."}, status_code=403,
        )
    return None


def get_current_super_admin(authorization: str | None):
    """Returns the super_admins row (a dict, matching db.repository's own
    dict-based row shape rather than introducing a new dataclass for a
    single-table, no-hospital-scope identity) for a valid super-admin-scoped
    'Bearer <JWT>' header, or None. Same shape as _authenticate() above and
    the same fresh-row re-check get_current_staff() does (is_active,
    token_version) -- a deactivated/rotated super admin's outstanding token
    stops working immediately, not at its next natural 15-minute expiry.
    Replaces the X-Admin-Secret/ADMIN_SECRET/TENANTS_ADMIN_SECRET shared-
    secret checks in admin/tenants_api.py, admin/onboarding_api.py,
    admin/platform_settings_api.py (docs/rbac-redis-plan.md)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    claims = verify_access_token(token, expected_typ="super_admin")
    if claims is None:
        return None
    super_admin = db.get_super_admin_by_id(claims["sub"])
    if super_admin is None or not super_admin["is_active"] or super_admin["token_version"] != claims["tv"]:
        return None
    return super_admin


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

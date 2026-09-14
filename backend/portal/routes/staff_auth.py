# portal/routes/staff_auth.py
"""Unified staff login (docs/rbac-redis-plan.md) -- Admin/Receptionist/
Doctor all authenticate here now. Replaces both the old shared hospital-wide
password (portal/routes/auth.py's /api/portal/login, kept alive unchanged
for anyone not yet migrated to a staff_users row) and the old dedicated
doctor login (a separate DOCTOR_SECRET-token /api/doctor/login, since
removed -- it was never wired into the frontend, so this unified path was
already the only one actually reachable for a doctor).

email is globally unique (staff_users.email, ux_staff_users_email) so login
is email+password alone, no hospital selector -- the caller learns
hospital_id FROM the matched row."""
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import core.rate_limit as rate_limit
import db.repository as db
from auth.jwt_session import issue_access_token
from auth.refresh_tokens import consume_refresh_token, issue_refresh_token, revoke_refresh_token
from db.repositories.hospitals import hash_portal_password, verify_portal_password
from portal.deps import _hospital_summary, get_current_staff
from portal.permissions import get_permission_matrix

router = APIRouter()


def _staff_summary(staff: dict, hospital) -> dict:
    # Nests the same hospital summary shape auth.py's /api/portal/login and
    # dashboard.py already return (PortalHospital on the frontend) -- the
    # staff-portal UI reads hospital.name/tenant_type/etc. off the SAME
    # session object it reads role/permissions off of, rather than needing a
    # second round-trip keyed by hospital_id alone. role_id/role_name/
    # role_id/role_name/is_doctor_role/doctor_id (dynamic-roles migration)
    # replace the old bare "role" string -- is_doctor_role is computed as
    # doctor_id IS NOT NULL (db/repositories/staff_users.py), independent of
    # role entirely, and is the signal every frontend `role === "doctor"`
    # branch switches to.
    return {
        "id": staff["id"], "name": staff["name"],
        "role_id": staff["role_id"], "role_name": staff["role_name"], "is_doctor_role": staff["is_doctor_role"],
        "doctor_id": staff["doctor_id"],
        "hospital_id": staff["hospital_id"], "hospital": _hospital_summary(hospital),
    }


def _issue_tokens(staff: dict) -> dict:
    """Shared by login and refresh -- always re-reads the CURRENT
    role/token_version off the fresh `staff` row passed in (never a cached
    one), so a role change or password reset that happened between a
    refresh call and the one before it is reflected in the very next access
    token issued, not just at the next full login. The JWT's own `role`
    claim carries role_name (display-only, dead weight for authorization --
    see portal/deps.py's get_current_staff() docstring, which never reads
    it, always re-fetching role_id fresh from Postgres instead)."""
    hospital = db.get_hospital(staff["hospital_id"])
    access_token = issue_access_token(staff["id"], staff["hospital_id"], staff["role_name"], staff["token_version"])
    refresh_token = issue_refresh_token(staff["id"], staff["hospital_id"], staff["role_name"])
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "staff": _staff_summary(staff, hospital),
        "permissions": get_permission_matrix(staff["hospital_id"]).get(staff["role_id"], {}),
    }


class StaffLoginPayload(BaseModel):
    email: str = ""
    password: str = ""


@router.post("/api/portal/staff/login")
async def staff_login(payload: StaffLoginPayload, request: Request):
    key = rate_limit.client_key("staff_login", request)
    if rate_limit.is_locked_out(key):
        return JSONResponse(
            {"error": "Too many attempts. Please wait a while before trying again."}, status_code=429
        )

    email = payload.email.strip()
    if not email or not payload.password:
        return JSONResponse({"error": "Email and password are required."}, status_code=400)

    staff = db.get_staff_user_by_email(email)
    # Same deliberately generic error for "no such email", "wrong password",
    # AND "deactivated" -- a request with a valid password for a deactivated
    # account must not confirm the account's existence/active-state to an
    # unauthenticated caller, same reasoning doctor_login()'s own comment
    # documents for its identical error collapsing.
    if (
        staff is None or not staff["is_active"]
        or not verify_portal_password(payload.password, staff["password_hash"])
    ):
        rate_limit.record_failure(key)
        return JSONResponse({"error": "Invalid email or password."}, status_code=401)

    rate_limit.reset(key)
    return JSONResponse(_issue_tokens(staff))


class RefreshPayload(BaseModel):
    refresh_token: str = ""


@router.post("/api/portal/staff/refresh")
async def staff_refresh(payload: RefreshPayload):
    """Rotation: the submitted refresh_token is consumed (deleted) here
    whether or not the rest of this request succeeds past that point -- see
    auth/refresh_tokens.py's own module docstring for why a single-use
    token, not just short-TTL-access-token-plus-long-lived-refresh, is the
    actual anti-theft property this buys."""
    record = consume_refresh_token(payload.refresh_token) if payload.refresh_token else None
    if record is None:
        return JSONResponse({"error": "Invalid or expired refresh token."}, status_code=401)

    # Re-fetch fresh, never trust hospital_id/role out of the refresh
    # record -- see _issue_tokens()'s own docstring for why.
    staff = db.get_staff_user_by_id(record["staff_id"])
    if staff is None or not staff["is_active"]:
        return JSONResponse({"error": "Account no longer active."}, status_code=401)
    return JSONResponse(_issue_tokens(staff))


class ChangePasswordPayload(BaseModel):
    current_password: str = ""
    new_password: str = ""


@router.post("/api/portal/staff/change-password")
async def staff_change_password(payload: ChangePasswordPayload, authorization: str | None = Header(default=None)):
    """Self-service change, from the portal itself -- db.update_staff_user_password()
    already existed for this (an admin-reset route may reuse it later) but had
    no caller yet. Re-issues fresh tokens in the response, same shape as
    login/refresh: update_staff_user_password() bumps token_version to force
    every OTHER outstanding session to re-authenticate, which would otherwise
    also log THIS request's own caller out on its very next request."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    staff = db.get_staff_user_by_id(principal.staff_id)
    if staff is None or not verify_portal_password(payload.current_password, staff["password_hash"]):
        return JSONResponse({"error": "Current password is incorrect."}, status_code=400)
    if len(payload.new_password) < 8:
        return JSONResponse({"error": "New password must be at least 8 characters."}, status_code=400)

    db.update_staff_user_password(staff["id"], hash_portal_password(payload.new_password))
    return JSONResponse(_issue_tokens(db.get_staff_user_by_id(staff["id"])))


def _split_csv(value: str | None) -> list[str]:
    return [x for x in (value or "").split(",") if x]


@router.get("/api/portal/staff/me")
async def staff_me(authorization: str | None = Header(default=None)):
    """Self profile (name/email/role/permissions/hospital) -- serves two
    frontend consumers: the Profile page's own cards, and
    StaffSessionProvider's in-memory StaffSessionContext (replaces the old
    localStorage-cached staff_session; see staffAuth.ts). StaffSession on the
    frontend has no email today (login/refresh never returned it), and
    staff.py's GET /api/portal/staff is gated on the "staff" permission (a
    receptionist/doctor viewing their OWN profile shouldn't need staff-
    management access), so this is its own authenticated-only route rather
    than reusing either.

    Uses get_own_profile() (not get_staff_user_by_id()) so a doctor-role
    login gets its real profile data -- specialization/qualification/
    years_experience/location plus phone/employee_id/department/schedule
    all sourced from the linked doctors row, not this login's own separate,
    usually-blank staff_details copies (same coalescing join
    list_staff_users_for_hospital() already uses for the Staff page)."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    staff = db.get_own_profile(principal.staff_id)
    if staff is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({
        "id": staff["id"], "name": staff["name"], "email": staff["email"],
        "role_id": staff["role_id"], "role_name": staff["role_name"], "is_doctor_role": staff["is_doctor_role"],
        "doctor_id": staff["doctor_id"],
        "hospital": _hospital_summary(principal.hospital),
        "permissions": get_permission_matrix(principal.hospital.id).get(staff["role_id"], {}),
        "employee_id": staff["employee_id"],
        "phone": staff["phone"],
        "address": staff["address"],
        "department_id": staff["department_id"],
        "department_name": staff["department_name"],
        "reports_to_name": staff["reports_to_name"],
        "working_days": _split_csv(staff["working_days"]),
        "working_hours": _split_csv(staff["working_hours"]),
        "breaks": _split_csv(staff["breaks"]),
        "created_at": staff["created_at"],
        "specialization": staff["specialization"],
        "qualification": staff["qualification"],
        "years_experience": staff["years_experience"],
        "location": staff["location"],
    })


class LogoutPayload(BaseModel):
    refresh_token: str = ""


@router.post("/api/portal/staff/logout")
async def staff_logout(payload: LogoutPayload, authorization: str | None = Header(default=None)):
    """Single-device logout -- revokes the ONE refresh token supplied, not
    every session for this staff member (that's a future admin "force
    logout everywhere" action, auth/refresh_tokens.py's revoke_all_for_staff()).
    Also accepts (and ignores the validity of) an already-expired access
    token in `authorization` -- a logout call racing its own access token's
    natural 15-minute expiry must still succeed at revoking the refresh
    token, so this never gates on verify_access_token() succeeding."""
    if payload.refresh_token:
        revoke_refresh_token(payload.refresh_token)
    return JSONResponse({"ok": True})

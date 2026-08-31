# portal/routes/staff_auth.py
"""Unified staff login (docs/rbac-redis-plan.md) -- Admin/Receptionist/
Doctor all authenticate here now, replacing the shared hospital-wide
password (portal/routes/auth.py's /api/portal/login) and the dedicated
doctor login (portal/routes/doctor_auth.py's /api/doctor/login) for anyone
who's been migrated to a staff_users row. Both of those stay alive
unchanged (docs/rbac-redis-plan.md's explicit dual-path rollout window) --
this is an ADDITIVE third path, not a replacement deployed in the same
change.

email is globally unique (staff_users.email, ux_staff_users_email) so login
is email+password alone, no hospital selector -- the caller learns
hospital_id FROM the matched row, same pattern
find_doctor_by_email()/doctors.py already established for dedicated doctor
login."""
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import core.rate_limit as rate_limit
import db.repository as db
from auth.jwt_session import issue_access_token
from auth.refresh_tokens import consume_refresh_token, issue_refresh_token, revoke_refresh_token
from db.repositories.hospitals import verify_portal_password
from portal.deps import _hospital_summary
from portal.permissions import get_permission_matrix

router = APIRouter()


def _staff_summary(staff: dict, hospital) -> dict:
    # Nests the same hospital summary shape auth.py's /api/portal/login and
    # dashboard.py already return (PortalHospital on the frontend) -- the
    # staff-portal UI reads hospital.name/tenant_type/etc. off the SAME
    # session object it reads role/permissions off of, rather than needing a
    # second round-trip keyed by hospital_id alone.
    return {
        "id": staff["id"], "name": staff["name"], "role": staff["role"],
        "hospital_id": staff["hospital_id"], "hospital": _hospital_summary(hospital),
    }


def _issue_tokens(staff: dict) -> dict:
    """Shared by login and refresh -- always re-reads the CURRENT
    role/token_version off the fresh `staff` row passed in (never a cached
    one), so a role change or password reset that happened between a
    refresh call and the one before it is reflected in the very next access
    token issued, not just at the next full login."""
    hospital = db.get_hospital(staff["hospital_id"])
    access_token = issue_access_token(staff["id"], staff["hospital_id"], staff["role"], staff["token_version"])
    refresh_token = issue_refresh_token(staff["id"], staff["hospital_id"], staff["role"])
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "staff": _staff_summary(staff, hospital),
        "permissions": get_permission_matrix(staff["hospital_id"]).get(staff["role"], {}),
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

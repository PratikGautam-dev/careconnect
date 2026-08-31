# admin/super_auth.py
"""Individual super-admin login (docs/rbac-redis-plan.md), replacing the
X-Admin-Secret/ADMIN_SECRET/TENANTS_ADMIN_SECRET shared-secret gates with a
real per-operator account and audit trail. Own rate-limit scope ("super_admin_login",
distinct from "admin_secret"/"tenants_admin_secret" so this doesn't share a
lockout bucket with the now-legacy secret checks it's replacing) and own JWT
secret (SUPER_ADMIN_JWT_SECRET) -- typ="super_admin" tokens verify only
against get_current_super_admin() (portal/deps.py), never the staff-portal
get_current_staff(), same structural non-interchangeability
auth/jwt_session.py's own module docstring establishes.

No refresh-token dance here, deliberately unlike portal/routes/staff_auth.py --
super-admin sessions are rare, low-frequency, high-privilege actions (editing
tenant credentials, onboarding a hospital), not an all-day-every-day staff
workflow the 15-minute access-token TTL would otherwise interrupt
constantly. A super admin simply logs in again after 15 minutes; adding
refresh-token infrastructure for a login this infrequent isn't worth the
extra revocable-credential surface."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import core.rate_limit as rate_limit
import db.repository as db
from auth.jwt_session import issue_access_token
from db.repositories.hospitals import verify_portal_password

router = APIRouter()


class SuperAdminLoginPayload(BaseModel):
    email: str = ""
    password: str = ""


@router.post("/api/admin/super/login")
async def super_admin_login(payload: SuperAdminLoginPayload, request: Request):
    key = rate_limit.client_key("super_admin_login", request)
    if rate_limit.is_locked_out(key):
        return JSONResponse(
            {"error": "Too many attempts. Please wait a while before trying again."}, status_code=429
        )

    email = payload.email.strip()
    if not email or not payload.password:
        return JSONResponse({"error": "Email and password are required."}, status_code=400)

    super_admin = db.get_super_admin_by_email(email)
    if (
        super_admin is None or not super_admin["is_active"]
        or not verify_portal_password(payload.password, super_admin["password_hash"])
    ):
        rate_limit.record_failure(key)
        return JSONResponse({"error": "Invalid email or password."}, status_code=401)

    rate_limit.reset(key)
    access_token = issue_access_token(
        super_admin["id"], hospital_id=None, role="super_admin",
        token_version=super_admin["token_version"], typ="super_admin",
    )
    return JSONResponse({
        "access_token": access_token,
        "super_admin": {"id": super_admin["id"], "name": super_admin["name"], "email": super_admin["email"]},
    })

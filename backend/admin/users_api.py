# admin/users_api.py
"""Cross-tenant, read-only staff directory for the platform admin's
/admin/users page (docs/rbac-redis-plan.md) -- a hospital's OWN staff
management (create/deactivate/change role) already lives at
/api/portal/staff, gated per-hospital by that hospital's own admin role.
This is deliberately view-only: a super admin browsing every tenant's staff
list is a different concern from editing one, and giving this route write
access would mean two independent paths that can mutate the same
staff_users rows with different audit trails. Gated by the same
get_current_super_admin() tenants_api.py/platform_settings_api.py use."""
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

import db.repository as db
from portal.deps import get_current_super_admin

router = APIRouter()


@router.get("/api/admin/staff-users")
async def list_staff_users_route(
    request: Request,
    authorization: str | None = Header(default=None),
    hospital_id: int | None = None,
    role: str | None = None,
    is_active: bool | None = None,
):
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    rows = db.list_all_staff_users(hospital_id=hospital_id, role=role, is_active=is_active)
    staff = [
        {
            "id": r["id"], "name": r["name"], "email": r["email"], "role": r["role"],
            "hospital_id": r["hospital_id"], "hospital_name": r["hospital_name"], "is_active": r["is_active"],
        }
        for r in rows
    ]
    return JSONResponse({"staff": staff})

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
    search: str | None = None,
):
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    rows = db.list_all_staff_users(hospital_id=hospital_id, role=role, is_active=is_active, search=search)
    staff = [
        {
            "id": r["id"], "name": r["name"], "email": r["email"], "role": r["role"],
            "hospital_id": r["hospital_id"], "hospital_name": r["hospital_name"], "is_active": r["is_active"],
        }
        for r in rows
    ]
    return JSONResponse({"staff": staff})


@router.get("/api/admin/staff-summary")
async def staff_summary_route(
    authorization: str | None = Header(default=None), search: str | None = None,
):
    """Per-hospital staff headcounts for the /admin/users overview's cards
    (one card per hospital, Admin/Doctor/Receptionist/Total counts) --
    db.get_staff_summary_by_hospital() does the counting in one grouped
    query rather than this route fetching every staff row itself."""
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    rows = db.get_staff_summary_by_hospital(search=search)
    hospitals = [
        {
            "id": r["id"], "name": r["name"], "is_active": r["is_active"], "data_tier": r["data_tier"],
            "admin_count": r["admin_count"], "doctor_count": r["doctor_count"],
            "receptionist_count": r["receptionist_count"], "total_count": r["total_count"],
        }
        for r in rows
    ]
    return JSONResponse({"hospitals": hospitals})


@router.get("/api/admin/staff-users/{staff_id}")
async def staff_user_detail_route(staff_id: int, authorization: str | None = Header(default=None)):
    """Single-staff detail view (/admin/users/[hospitalId]/[staffId]) --
    same super-admin gate as the list/summary routes above; still read-only
    (see this module's own docstring for why edits stay on the hospital's
    own /api/portal/staff instead)."""
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    row = db.get_staff_user_detail(staff_id)
    if row is None:
        return JSONResponse({"error": "No such staff member."}, status_code=404)
    return JSONResponse({
        "staff": {
            "id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"],
            "hospital_id": row["hospital_id"], "hospital_name": row["hospital_name"],
            "is_active": row["is_active"], "created_at": row["created_at"],
            "doctor_name": row["doctor_name"], "specialization": row["specialization"],
            "qualification": row["qualification"], "years_experience": row["years_experience"],
            "department_name": row["department_name"],
        }
    })

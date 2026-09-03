# portal/routes/staff.py
"""Staff Management admin UI's backend (docs/rbac-redis-plan.md) -- list,
create, and deactivate/reactivate staff_users rows for the caller's own
hospital. Distinct from portal/routes/staff_auth.py (login/refresh/logout,
unauthenticated-caller-facing) -- this is the admin-facing CRUD surface, same
"auth vs. management are different files" split doctor_auth.py/doctor_portal.py
already established for doctors.

Gated by require_permission(principal, "staff", ...) like every other page,
not a hardcoded "only role == admin" check -- admin gets view+write on
PAGE_STAFF by default (portal/permissions.py's DEFAULT_PERMISSIONS_BY_ROLE),
but a hospital could in principle grant a receptionist read-only visibility
into the staff list."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db.repository as db
from db.repositories.hospitals import hash_portal_password
from portal.deps import get_current_staff, require_permission

router = APIRouter()

_VALID_ROLES = {"admin", "receptionist", "doctor"}


def _staff_row(staff: dict) -> dict:
    return {
        "id": staff["id"], "name": staff["name"], "email": staff["email"],
        "role": staff["role"], "doctor_id": staff["doctor_id"], "is_active": staff["is_active"],
    }


@router.get("/api/portal/staff")
async def list_staff(authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "staff", "view")
    if forbidden:
        return forbidden
    staff = db.list_staff_users_for_hospital(principal.hospital.id)
    return JSONResponse([_staff_row(s) for s in staff])


class CreateStaffPayload(BaseModel):
    name: str = ""
    email: str = ""
    password: str = ""
    role: str = ""
    doctor_id: str | None = None


@router.post("/api/portal/staff")
async def create_staff(payload: CreateStaffPayload, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "staff", "write")
    if forbidden:
        return forbidden

    name = payload.name.strip()
    email = payload.email.strip()
    errors = []
    if not name:
        errors.append("Name is required.")
    if not email:
        errors.append("Email is required.")
    if not payload.password or len(payload.password) < 8:
        errors.append("A password of at least 8 characters is required.")
    if payload.role not in _VALID_ROLES:
        errors.append(f'Unrecognized role "{payload.role}".')
    if payload.role == "doctor" and not (payload.doctor_id or "").strip():
        errors.append("A doctor must be selected for the Doctor role.")
    if payload.role != "doctor" and payload.doctor_id:
        errors.append("doctor_id may only be set for the Doctor role.")
    if errors:
        # {"error": "..."} (a single joined string), not {"errors": [...]} --
        # matching every other route's error-response shape in this codebase
        # (and what staffFetch/the frontend's setFormError() actually reads,
        # via result.error). The plural/array shape here was silently
        # swallowed by the frontend, which fell back to a generic
        # "Something went wrong." instead of ever showing these real reasons.
        return JSONResponse({"error": " ".join(errors)}, status_code=400)

    try:
        staff = db.create_staff_user(
            principal.hospital.id, payload.role, email, hash_portal_password(payload.password),
            name, doctor_id=payload.doctor_id,
        )
    except db.IntegrityError:
        return JSONResponse(
            {"error": f'"{email}" is already in use by another staff account, or the selected doctor already has a login.'},
            status_code=400,
        )

    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>", "staff.create",
        entity_type="staff_users", entity_id=str(staff["id"]),
        after={"email": email, "role": payload.role},
    )
    return JSONResponse(_staff_row(staff), status_code=201)


class UpdateStaffPayload(BaseModel):
    is_active: bool | None = None


@router.patch("/api/portal/staff/{staff_id}")
async def update_staff(staff_id: int, payload: UpdateStaffPayload, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "staff", "write")
    if forbidden:
        return forbidden

    if payload.is_active is None:
        return JSONResponse({"error": "Nothing to update."}, status_code=400)

    # Scope check: set_staff_user_active() itself has no hospital_id filter
    # (staff_users.id is already globally unique), so this lookup is what
    # stops an admin at hospital A from deactivating a staff row at hospital B.
    staff = [s for s in db.list_staff_users_for_hospital(principal.hospital.id) if s["id"] == staff_id]
    if not staff:
        return JSONResponse({"error": "Staff member not found."}, status_code=404)

    db.set_staff_user_active(staff_id, payload.is_active)
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>",
        "staff.set_active" if payload.is_active else "staff.deactivate",
        entity_type="staff_users", entity_id=str(staff_id), after={"is_active": payload.is_active},
    )
    updated = [s for s in db.list_staff_users_for_hospital(principal.hospital.id) if s["id"] == staff_id][0]
    return JSONResponse(_staff_row(updated))

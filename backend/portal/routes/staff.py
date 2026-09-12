# portal/routes/staff.py
"""Staff Management admin UI's backend (docs/rbac-redis-plan.md) -- list,
create, and deactivate/reactivate staff_users rows for the caller's own
hospital. Distinct from portal/routes/staff_auth.py (login/refresh/logout,
unauthenticated-caller-facing) -- this is the admin-facing CRUD surface.

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
_VALID_SHIFTS = {"day", "evening", "night"}
_VALID_ATTENDANCE_STATUSES = {"present", "on_leave", "half_day"}


def _staff_row(staff: dict, leave_usage: dict[int, int], leave_policy: dict) -> dict:
    # Leave balance (migration 20260912065049) is doctor/receptionist only
    # (confirmed with the user) -- an admin row gets None/None here, shown
    # as "not tracked" on the frontend, same as this staff list already
    # does for every field a given role doesn't have.
    tracked = staff["role"] == "receptionist"
    return {
        "id": staff["id"], "name": staff["name"], "email": staff["email"],
        "role": staff["role"], "doctor_id": staff["doctor_id"], "is_active": staff["is_active"],
        "created_at": staff.get("created_at"),
        "phone": staff.get("phone"), "address": staff.get("address"), "shift": staff.get("shift"),
        "attendance_status": staff.get("attendance_status"),
        "department_id": staff.get("department_id"), "department_name": staff.get("department_name"),
        "reports_to_id": staff.get("reports_to_id"), "reports_to_name": staff.get("reports_to_name"),
        "leave_balance_total": leave_policy["staff_annual_leave_days"] if tracked else None,
        "leave_balance_used": leave_usage.get(staff["id"], 0) if tracked else None,
    }


@router.get("/api/portal/staff")
async def list_staff(authorization: str | None = Header(default=None)):
    """The Staff page's own directory -- doctors excluded at the query
    level (see list_staff_users_for_hospital()'s own docstring): they have
    their own dedicated page + "Create login" action there, and aren't
    meant to also appear as a row in this "hospital staff" list. A caller
    that genuinely needs every role, doctors included (the Add/Edit Staff
    dialogs' "reports to" picker), uses GET /api/portal/staff/options
    instead -- a separate endpoint, not a query flag on this one, so each
    URL has exactly one, unambiguous meaning."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "staff", "view")
    if forbidden:
        return forbidden
    staff = db.list_staff_users_for_hospital(principal.hospital.id, exclude_doctors=True)
    leave_usage = db.get_leave_usage_by_identity(principal.hospital.id)
    leave_policy = db.get_leave_policy(principal.hospital.id)
    return JSONResponse([_staff_row(s, leave_usage, leave_policy) for s in staff])


@router.get("/api/portal/staff/options")
async def list_staff_options(authorization: str | None = Header(default=None)):
    """Lightweight {id, name} pairs for EVERY staff role, doctors included --
    used only by the Add/Edit Staff dialogs' "reports to" picker, which
    needs to be able to name a doctor as another staff member's manager even
    though doctors don't appear in the main directory above."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "staff", "view")
    if forbidden:
        return forbidden
    staff = db.list_staff_users_for_hospital(principal.hospital.id)
    return JSONResponse([{"id": s["id"], "name": s["name"]} for s in staff])


class CreateStaffPayload(BaseModel):
    name: str = ""
    email: str = ""
    password: str = ""
    role: str = ""
    doctor_id: str | None = None
    phone: str | None = None
    address: str | None = None
    department_id: str | None = None
    shift: str | None = None
    reports_to_id: int | None = None


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
    if payload.role == "doctor" and payload.department_id:
        errors.append("A doctor's department comes from their linked doctor profile, not department_id.")
    if payload.department_id and db.find_department(principal.hospital.id, payload.department_id) is None:
        errors.append("Choose a valid department.")
    if payload.shift and payload.shift not in _VALID_SHIFTS:
        errors.append(f'Unrecognized shift "{payload.shift}".')
    if payload.reports_to_id and payload.reports_to_id not in {
        s["id"] for s in db.list_staff_users_for_hospital(principal.hospital.id)
    }:
        errors.append("Choose a valid staff member to report to.")
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
            phone=payload.phone, address=payload.address, department_id=payload.department_id,
            shift=payload.shift, reports_to_id=payload.reports_to_id,
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
    # A brand-new staff member has taken zero leave yet -- {} rather than a
    # real db.get_leave_usage_by_identity() call, same effect without a
    # query neither this row nor anyone else's balance actually needs here.
    return JSONResponse(_staff_row(staff, {}, db.get_leave_policy(principal.hospital.id)), status_code=201)


class UpdateStaffPayload(BaseModel):
    is_active: bool | None = None
    # "Edit staff details" fields -- all nullable, all optional. Whether one
    # of these was actually SENT (vs. just defaulting to None) is read off
    # model_fields_set below, not off "is this None" -- several of these are
    # themselves nullable columns (address, department_id, reports_to_id),
    # so a null-but-sent value has to be distinguishable from "wasn't part
    # of this PATCH at all" in order to support clearing one.
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    department_id: str | None = None
    shift: str | None = None
    reports_to_id: int | None = None
    attendance_status: str | None = None


@router.patch("/api/portal/staff/{staff_id}")
async def update_staff(staff_id: int, payload: UpdateStaffPayload, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "staff", "write")
    if forbidden:
        return forbidden

    detail_keys = {"name", "phone", "address", "department_id", "shift", "reports_to_id", "attendance_status"}
    sent_detail_keys = payload.model_fields_set & detail_keys
    if payload.is_active is None and not sent_detail_keys:
        return JSONResponse({"error": "Nothing to update."}, status_code=400)

    # Scope check: set_staff_user_active()/update_staff_user_details() have
    # no hospital_id filter of their own (identities.id is already globally
    # unique), so this lookup is what stops an admin at hospital A from
    # editing a staff row at hospital B.
    staff = [s for s in db.list_staff_users_for_hospital(principal.hospital.id) if s["id"] == staff_id]
    if not staff:
        return JSONResponse({"error": "Staff member not found."}, status_code=404)
    target = staff[0]

    if "department_id" in sent_detail_keys and payload.department_id:
        if target["role"] == "doctor":
            return JSONResponse(
                {"error": "A doctor's department comes from their linked doctor profile, not this field."},
                status_code=400,
            )
        if db.find_department(principal.hospital.id, payload.department_id) is None:
            return JSONResponse({"error": "Choose a valid department."}, status_code=400)
    if "shift" in sent_detail_keys and payload.shift and payload.shift not in _VALID_SHIFTS:
        return JSONResponse({"error": f'Unrecognized shift "{payload.shift}".'}, status_code=400)
    if "attendance_status" in sent_detail_keys and payload.attendance_status not in _VALID_ATTENDANCE_STATUSES:
        return JSONResponse(
            {"error": f'Unrecognized attendance status "{payload.attendance_status}".'}, status_code=400,
        )
    if "reports_to_id" in sent_detail_keys and payload.reports_to_id is not None:
        if payload.reports_to_id == staff_id:
            return JSONResponse({"error": "A staff member can't report to themselves."}, status_code=400)
        if payload.reports_to_id not in {s["id"] for s in db.list_staff_users_for_hospital(principal.hospital.id)}:
            return JSONResponse({"error": "Choose a valid staff member to report to."}, status_code=400)

    if payload.is_active is not None:
        db.set_staff_user_active(staff_id, payload.is_active)
        db.record_audit_log(
            "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>",
            "staff.set_active" if payload.is_active else "staff.deactivate",
            entity_type="staff_users", entity_id=str(staff_id), after={"is_active": payload.is_active},
        )

    if sent_detail_keys:
        identity_fields = {"name": payload.name} if "name" in sent_detail_keys else {}
        staff_fields = {k: getattr(payload, k) for k in sent_detail_keys if k != "name"}
        db.update_staff_user_details(staff_id, identity_fields=identity_fields, staff_fields=staff_fields)
        db.record_audit_log(
            "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>", "staff.update_details",
            entity_type="staff_users", entity_id=str(staff_id), after={k: getattr(payload, k) for k in sent_detail_keys},
        )

    updated = [s for s in db.list_staff_users_for_hospital(principal.hospital.id) if s["id"] == staff_id][0]
    leave_usage = db.get_leave_usage_by_identity(principal.hospital.id)
    leave_policy = db.get_leave_policy(principal.hospital.id)
    return JSONResponse(_staff_row(updated, leave_usage, leave_policy))


class SetStaffPasswordPayload(BaseModel):
    new_password: str = ""


@router.post("/api/portal/staff/{staff_id}/password")
async def set_staff_password(staff_id: int, payload: SetStaffPasswordPayload, authorization: str | None = Header(default=None)):
    """Admin-initiated reset -- unlike staff_auth.py's self-service
    change-password, there's no current-password check and no token re-issue
    (that route re-issues because it's changing the CALLER's own password;
    here the caller and the target are different people, so nothing about
    the admin's own session needs to change). update_staff_user_password()
    still bumps the target's token_version, so their other sessions are
    force-logged-out same as the self-service path."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "staff", "write")
    if forbidden:
        return forbidden

    if len(payload.new_password) < 8:
        return JSONResponse({"error": "New password must be at least 8 characters."}, status_code=400)

    # Same hospital-scope guard as update_staff() above.
    staff = [s for s in db.list_staff_users_for_hospital(principal.hospital.id) if s["id"] == staff_id]
    if not staff:
        return JSONResponse({"error": "Staff member not found."}, status_code=404)

    db.update_staff_user_password(staff_id, hash_portal_password(payload.new_password))
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>", "staff.reset_password",
        entity_type="staff_users", entity_id=str(staff_id),
    )
    return JSONResponse({"ok": True})

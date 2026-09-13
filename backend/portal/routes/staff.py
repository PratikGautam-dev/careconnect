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
from pydantic import BaseModel, Field

import db.repository as db
from admin.validation import _validate_staff_schedule_fields
from db.repositories.hospitals import hash_portal_password
from portal.deps import get_current_staff, require_permission

router = APIRouter()

_VALID_ATTENDANCE_STATUSES = {"present", "on_leave", "half_day"}


def _split_csv(value: str | None) -> list[str]:
    return [x for x in (value or "").split(",") if x]


def _staff_row(staff: dict, leave_usage: dict[int, int], leave_policy: dict) -> dict:
    # Leave balance (migration 20260912065049) is receptionist-role only
    # (confirmed with the user) -- an admin row gets None/None here, shown
    # as "not tracked" on the frontend, same as this staff list already
    # does for every field a given role doesn't have. Matched by role NAME
    # (dynamic-roles migration) -- "receptionist-ness" has no structural/FK
    # flag on roles, so a hospital that renames this role loses leave
    # tracking for it -- an accepted, pre-existing-shape limitation this
    # migration doesn't attempt to fix (same posture as
    # db/repositories/users.py's get_owners_for_hospital()).
    tracked = staff["role_name"].lower() == "receptionist"
    return {
        "id": staff["id"], "name": staff["name"], "email": staff["email"],
        "role_id": staff["role_id"], "role_name": staff["role_name"], "is_doctor_role": staff["is_doctor_role"],
        "doctor_id": staff["doctor_id"], "is_active": staff["is_active"],
        "created_at": staff.get("created_at"),
        "employee_id": staff.get("employee_id"),
        "phone": staff.get("phone"), "address": staff.get("address"),
        # Staff schedule feature -- replaces the old shift enum with the
        # same comma-stored working_days/working_hours/breaks model doctors
        # already have; split back into lists here, same as
        # db/repositories/doctors.py does at its own layer (this is the one
        # shared serialization point every staff response funnels through).
        "working_days": _split_csv(staff.get("working_days")),
        "working_hours": _split_csv(staff.get("working_hours")),
        "breaks": _split_csv(staff.get("breaks")),
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
    role_id: int | None = None
    doctor_id: str | None = None
    phone: str | None = None
    address: str | None = None
    department_id: str | None = None
    working_days: list[str] = Field(default_factory=list)
    working_hours: list[str] = Field(default_factory=list)
    breaks: list[str] = Field(default_factory=list)
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
    role = db.get_role(principal.hospital.id, payload.role_id) if payload.role_id is not None else None
    if role is None:
        errors.append("Unrecognized role.")
    if (payload.doctor_id or "").strip() and payload.department_id:
        errors.append("A doctor's department comes from their linked doctor profile, not department_id.")
    if payload.department_id and db.find_department(principal.hospital.id, payload.department_id) is None:
        errors.append("Choose a valid department.")
    schedule, schedule_errors = _validate_staff_schedule_fields(
        name, ",".join(payload.working_days), ",".join(payload.working_hours), ",".join(payload.breaks),
    )
    errors.extend(schedule_errors)
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
            principal.hospital.id, payload.role_id, email, hash_portal_password(payload.password),
            name, doctor_id=payload.doctor_id,
            phone=payload.phone, address=payload.address, department_id=payload.department_id,
            reports_to_id=payload.reports_to_id,
            working_days=schedule["working_days"], working_hours=schedule["working_hours"], breaks=schedule["breaks"],
        )
    except (db.IntegrityError, ValueError):
        return JSONResponse(
            {"error": f'"{email}" is already in use by another staff account, or the selected doctor already has a login.'},
            status_code=400,
        )

    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>", "staff.create",
        entity_type="staff_users", entity_id=str(staff["id"]),
        after={"email": email, "role_id": payload.role_id},
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
    working_days: list[str] = Field(default_factory=list)
    working_hours: list[str] = Field(default_factory=list)
    breaks: list[str] = Field(default_factory=list)
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

    detail_keys = {
        "name", "phone", "address", "department_id",
        "working_days", "working_hours", "breaks",
        "reports_to_id", "attendance_status",
    }
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
        if target["doctor_id"]:
            return JSONResponse(
                {"error": "A doctor's department comes from their linked doctor profile, not this field."},
                status_code=400,
            )
        if db.find_department(principal.hospital.id, payload.department_id) is None:
            return JSONResponse({"error": "Choose a valid department."}, status_code=400)
    # working_days/working_hours/breaks are one logical unit (a schedule) --
    # only ever partially sent if the frontend genuinely means to touch just
    # one of them (rare; EditStaffDialog always sends all three together),
    # so a not-sent one falls back to this staff member's CURRENT value
    # (the raw comma-string `target` already carries, pre-`_staff_row()`
    # split) rather than being silently blanked out.
    schedule = None
    schedule_keys_sent = sent_detail_keys & {"working_days", "working_hours", "breaks"}
    if schedule_keys_sent:
        days_raw = ",".join(payload.working_days) if "working_days" in sent_detail_keys else (target.get("working_days") or "")
        hours_raw = ",".join(payload.working_hours) if "working_hours" in sent_detail_keys else (target.get("working_hours") or "")
        breaks_raw = ",".join(payload.breaks) if "breaks" in sent_detail_keys else (target.get("breaks") or "")
        schedule, schedule_errors = _validate_staff_schedule_fields(target["name"], days_raw, hours_raw, breaks_raw)
        if schedule_errors:
            return JSONResponse({"error": " ".join(schedule_errors)}, status_code=400)
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
        staff_fields = {
            k: getattr(payload, k) for k in sent_detail_keys if k != "name" and k not in schedule_keys_sent
        }
        # working_days/working_hours/breaks are comma-stored TEXT columns
        # (Staff schedule feature) -- staff_fields must hold the joined
        # strings validation returned, not the raw list(s) the payload
        # carries, since update_staff_user_details() writes these values
        # straight into the DB.
        if schedule is not None:
            staff_fields["working_days"] = ",".join(schedule["working_days"])
            staff_fields["working_hours"] = ",".join(schedule["working_hours"])
            staff_fields["breaks"] = ",".join(schedule["breaks"])
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

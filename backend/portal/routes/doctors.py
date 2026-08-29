import secrets
from datetime import datetime

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db.repository as db
from admin.validation import _validate_doctor_fields
from db.connection import IntegrityError
from db.repositories.hospitals import hash_portal_password
from portal.deps import _authenticate, require_capability
from portal.routes.bookings import _appointment_json

router = APIRouter()


@router.get("/api/portal/doctors")
async def portal_doctors(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    departments = db.get_departments(hospital.id)
    doctors = db.get_all_doctors_for_hospital(hospital.id)
    return JSONResponse({"departments": departments, "doctors": doctors})


@router.post("/api/portal/departments")
async def portal_create_department(payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_departments")
    if forbidden:
        return forbidden
    name = (payload or {}).get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Department name is required."}, status_code=400)
    department = db.create_department(hospital.id, name)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "department.create",
        entity_type="department", entity_id=department["id"], after={"name": name},
    )
    return JSONResponse({"department": department})


class DoctorPayload(BaseModel):
    department_id: str = ""
    name: str = ""
    specialization: str = ""
    qualification: str = ""
    years_experience: str = ""
    working_days: list[str] = Field(default_factory=list)
    working_hours: list[str] = Field(default_factory=list)
    slot_duration_minutes: str = ""
    breaks: list[str] = Field(default_factory=list)
    max_bookings_per_slot: str = "1"
    daily_booking_limit: str = ""
    online_quota: str = ""
    walkin_quota: str = ""
    followup_duration_minutes: str = ""
    effective_from: str = ""


@router.post("/api/portal/doctors")
async def portal_create_doctor(payload: DoctorPayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden

    department = db.find_department(hospital.id, payload.department_id)
    if department is None:
        return JSONResponse({"error": "Choose a valid department."}, status_code=400)

    doctor_data, errors, warnings = _validate_doctor_fields(
        0, payload.name, payload.specialization, payload.qualification, payload.years_experience,
        ",".join(payload.working_days), ",".join(payload.working_hours), payload.slot_duration_minutes,
        ",".join(payload.breaks), payload.max_bookings_per_slot, payload.daily_booking_limit,
        payload.online_quota, payload.walkin_quota, payload.followup_duration_minutes, payload.effective_from,
    )
    if errors:
        return JSONResponse({"errors": errors}, status_code=400)

    doctor = db.create_doctor(
        hospital.id, payload.department_id, doctor_data["name"],
        specialization=doctor_data["specialization"],
        qualification=doctor_data["qualification"],
        years_experience=doctor_data["years_experience"],
        working_days=doctor_data["working_days"],
        working_hours=doctor_data["working_hours"],
        slot_duration_minutes=doctor_data["slot_duration_minutes"],
        breaks=doctor_data["breaks"],
        max_bookings_per_slot=doctor_data["max_bookings_per_slot"],
        daily_booking_limit=doctor_data["daily_booking_limit"],
        online_quota=doctor_data["online_quota"],
        walkin_quota=doctor_data["walkin_quota"],
        followup_duration_minutes=doctor_data["followup_duration_minutes"],
        effective_from=doctor_data["effective_from"],
    )
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "doctor.create",
        entity_type="doctor", entity_id=doctor["id"], after={"name": doctor_data["name"]},
    )
    return JSONResponse({"doctor": doctor, "warnings": warnings})


@router.post("/api/portal/doctors/{doctor_id}/login-credentials")
async def portal_set_doctor_login_credentials(
    doctor_id: str, payload: dict, authorization: str | None = Header(default=None)
):
    """Admin-issued/reset dedicated doctor login (Spec.md Section 0's
    doctor-portal build) -- separate from this doctor's row otherwise; a
    doctor with no credentials set keeps working through the shared staff
    portal exactly as before. payload = {"email": str, "password"?: str} --
    if password is omitted, a random one is generated and returned ONCE in
    this response (never re-displayable after this), same "show it once,
    the admin relays it to the doctor directly" model the shared staff
    portal password already effectively uses on creation."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden
    if db.get_doctor_full(hospital.id, doctor_id) is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    email = ((payload or {}).get("email") or "").strip().lower()
    if not email:
        return JSONResponse({"error": "Email is required."}, status_code=400)
    password = (payload or {}).get("password") or secrets.token_urlsafe(9)
    password_hash = hash_portal_password(password)
    try:
        ok = db.set_doctor_login_credentials(hospital.id, doctor_id, email, password_hash)
    except IntegrityError:
        return JSONResponse({"error": "This email is already used by another doctor."}, status_code=409)
    if not ok:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "doctor.login_credentials_set",
        entity_type="doctor", entity_id=doctor_id, after={"email": email},
    )
    return JSONResponse({"ok": True, "email": email, "password": password})


@router.post("/api/portal/doctors/{doctor_id}/login-credentials/revoke")
async def portal_revoke_doctor_login_credentials(doctor_id: str, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden
    ok = db.clear_doctor_login_credentials(hospital.id, doctor_id)
    if not ok:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "doctor.login_credentials_revoked",
        entity_type="doctor", entity_id=doctor_id,
    )
    return JSONResponse({"ok": True})


@router.post("/api/portal/doctors/{doctor_id}/active")
async def portal_set_doctor_active(doctor_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden
    is_active = bool((payload or {}).get("is_active", True))
    ok = db.set_doctor_active(hospital.id, doctor_id, is_active)
    if not ok:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "doctor.active_toggle",
        entity_type="doctor", entity_id=doctor_id, after={"is_active": is_active},
    )
    return JSONResponse({"ok": True, "is_active": is_active})


@router.get("/api/portal/doctors/{doctor_id}/leave")
async def portal_get_doctor_leave(doctor_id: str, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_doctor_full(hospital.id, doctor_id) is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    return JSONResponse({"leave": db.get_doctor_leave(hospital.id, doctor_id)})


@router.post("/api/portal/doctors/{doctor_id}/leave")
async def portal_add_doctor_leave(doctor_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden
    # Audit follow-up (Spec.md Section 0): db.create_doctor_leave() itself has
    # no way to know whether doctor_id actually belongs to hospital_id -- its
    # INSERT would succeed either way -- so that check has to happen here,
    # same reason portal_create_doctor() validates the department first.
    if db.get_doctor_full(hospital.id, doctor_id) is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    leave_date = (payload or {}).get("date", "").strip()
    if not leave_date:
        return JSONResponse({"error": "A date is required."}, status_code=400)
    reason = (payload or {}).get("reason", "").strip() or None
    entry = db.create_doctor_leave(hospital.id, doctor_id, leave_date, reason)
    return JSONResponse({"leave": entry})


@router.post("/api/portal/doctors/{doctor_id}/leave/range")
async def portal_add_doctor_leave_range(doctor_id: str, payload: dict, authorization: str | None = Header(default=None)):
    """Item 10 (Spec.md Section 0): From/To range with one Confirm, instead
    of adding leave dates one at a time -- same ownership check
    portal_add_doctor_leave() above already established."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden
    if db.get_doctor_full(hospital.id, doctor_id) is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    from_date = (payload or {}).get("from_date", "").strip()
    to_date = (payload or {}).get("to_date", "").strip()
    if not from_date or not to_date:
        return JSONResponse({"error": "Both from_date and to_date are required."}, status_code=400)
    reason = (payload or {}).get("reason", "").strip() or None
    try:
        created_dates = db.create_doctor_leave_range(hospital.id, doctor_id, from_date, to_date, reason)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"dates": created_dates})


@router.post("/api/portal/doctors/{doctor_id}/leave/{leave_id}/delete")
async def portal_delete_doctor_leave(
    doctor_id: str, leave_id: int, authorization: str | None = Header(default=None)
):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden
    ok = db.delete_doctor_leave(hospital.id, doctor_id, leave_id)
    if not ok:
        return JSONResponse({"error": "No such leave date."}, status_code=404)
    return JSONResponse({"ok": True})


@router.get("/api/portal/doctors/{doctor_id}/slots")
async def portal_get_doctor_slots(doctor_id: str, date: str | None = None, authorization: str | None = Header(default=None)):
    """Item 1 (Spec.md Section 0): every generated slot for this doctor on
    one date (blocked/booked flags included) -- the manual per-slot-block
    admin view. "View all slots" follow-up: `date` is now optional --
    omitting it returns every upcoming slot across the doctor's whole
    generated window instead of just one day."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_doctor_full(hospital.id, doctor_id) is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    return JSONResponse({"slots": db.get_doctor_slots_for_admin(hospital.id, doctor_id, date)})


@router.post("/api/portal/doctors/{doctor_id}/slots/block")
async def portal_set_slot_blocked(doctor_id: str, payload: dict, authorization: str | None = Header(default=None)):
    """Item 1: payload = {"scheduled_at": "...", "blocked": true|false,
    "reason": "..."}. Refusing to block an already-BOOKED slot is
    db.set_slot_blocked()'s own guard, surfaced here as a clear 400."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden
    if db.get_doctor_full(hospital.id, doctor_id) is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    scheduled_at = (payload or {}).get("scheduled_at", "").strip()
    if not scheduled_at:
        return JSONResponse({"error": "scheduled_at is required."}, status_code=400)
    blocked = bool((payload or {}).get("blocked", True))
    reason = (payload or {}).get("reason", "").strip() or None
    ok = db.set_slot_blocked(hospital.id, doctor_id, scheduled_at, blocked, reason)
    if not ok:
        if blocked:
            return JSONResponse({"error": "This slot already has a booked appointment -- cancel or reschedule it first."}, status_code=400)
        return JSONResponse({"error": "No such slot."}, status_code=404)
    return JSONResponse({"ok": True, "blocked": blocked})


@router.post("/api/portal/doctors/{doctor_id}/slots/add")
async def portal_add_slot(doctor_id: str, payload: dict, authorization: str | None = Header(default=None)):
    """Add/remove-slot follow-up (Spec.md Section 0): a genuinely one-off
    extra slot outside the doctor's normal generated pattern -- payload =
    {"date": "YYYY-MM-DD", "time": "HH:MM"}. Distinct from the block
    endpoint above, which only ever toggles an already-generated row."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden
    if db.get_doctor_full(hospital.id, doctor_id) is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    date_str = (payload or {}).get("date", "").strip()
    time_str = (payload or {}).get("time", "").strip()
    if not date_str or not time_str:
        return JSONResponse({"error": "date and time are required."}, status_code=400)
    try:
        scheduled_at = datetime.fromisoformat(f"{date_str}T{time_str}").isoformat()
    except ValueError:
        return JSONResponse({"error": "Invalid date/time."}, status_code=400)
    db.add_custom_slot(hospital.id, doctor_id, scheduled_at)
    return JSONResponse({"ok": True, "scheduled_at": scheduled_at})


@router.post("/api/portal/doctors/{doctor_id}/slots/remove")
async def portal_remove_slot(doctor_id: str, payload: dict, authorization: str | None = Header(default=None)):
    """The other half of add/remove: a real hard delete, not a block/hide --
    refuses (via db.remove_slot()'s own guard) to remove a slot with a real
    booked appointment on it."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden
    if db.get_doctor_full(hospital.id, doctor_id) is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    scheduled_at = (payload or {}).get("scheduled_at", "").strip()
    if not scheduled_at:
        return JSONResponse({"error": "scheduled_at is required."}, status_code=400)
    ok = db.remove_slot(hospital.id, doctor_id, scheduled_at)
    if not ok:
        return JSONResponse({"error": "This slot either doesn't exist or already has a booked appointment -- cancel or reschedule it first."}, status_code=400)
    return JSONResponse({"ok": True})


@router.get("/api/portal/doctors/{doctor_id}/appointments/today")
async def portal_get_doctor_appointments_today(doctor_id: str, authorization: str | None = Header(default=None)):
    """Item 4: a specific doctor's own appointments scheduled for today,
    within the existing shared staff portal (no separate doctor login)."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_doctor_full(hospital.id, doctor_id) is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    appointments = db.get_doctor_appointments_today(hospital.id, doctor_id)
    return JSONResponse({"appointments": [_appointment_json(a) for a in appointments]})


class DoctorCsvRow(BaseModel):
    department_name: str = ""
    name: str = ""
    specialization: str = ""
    qualification: str = ""
    years_experience: str = ""
    working_days: str = ""  # "Mon,Tue,Wed" -- comma-separated, matches the wizard's own convention
    working_hours: str = ""  # "10:00-13:00,17:00-20:00"
    slot_duration_minutes: str = ""
    breaks: str = ""
    max_bookings_per_slot: str = "1"
    daily_booking_limit: str = ""
    online_quota: str = ""
    walkin_quota: str = ""
    followup_duration_minutes: str = ""
    effective_from: str = ""


class DoctorCsvImportPayload(BaseModel):
    rows: list[DoctorCsvRow] = Field(default_factory=list)


@router.post("/api/portal/doctors/csv-import")
async def portal_csv_import_doctors(
    payload: DoctorCsvImportPayload, authorization: str | None = Header(default=None)
):
    """Bulk doctor creation from a CSV the frontend has already parsed into
    rows (Field-name-matched against the same columns the single add-doctor
    form posts, comma-joined instead of arrays since CSV cells are plain
    strings) -- reuses _validate_doctor_fields() and create_department()'s
    own get-or-create-by-name behavior isn't a real function here, so a
    department named in the CSV that doesn't exist yet is created on the
    fly, matching what a staff member manually adding one row at a time
    would eventually do anyway. Every row is validated independently; one
    bad row doesn't block the good ones -- the response reports both."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden

    existing_departments = {d["name"].strip().lower(): d["id"] for d in db.get_departments(hospital.id)}
    created_count = 0
    row_errors: list[str] = []

    for i, row in enumerate(payload.rows):
        label = f"Row {i + 1}" + (f" ({row.name})" if row.name else "")
        dept_name = row.department_name.strip()
        if not dept_name:
            row_errors.append(f"{label}: department_name is required.")
            continue
        dept_key = dept_name.lower()
        if dept_key not in existing_departments:
            new_dept = db.create_department(hospital.id, dept_name)
            existing_departments[dept_key] = new_dept["id"]
        department_id = existing_departments[dept_key]

        doctor_data, errors, _warnings = _validate_doctor_fields(
            i, row.name, row.specialization, row.qualification, row.years_experience,
            row.working_days, row.working_hours, row.slot_duration_minutes, row.breaks,
            row.max_bookings_per_slot, row.daily_booking_limit, row.online_quota, row.walkin_quota,
            row.followup_duration_minutes, row.effective_from,
        )
        if errors:
            row_errors.extend(f"{label}: {e}" for e in errors)
            continue

        db.create_doctor(
            hospital.id, department_id, doctor_data["name"],
            specialization=doctor_data["specialization"],
            qualification=doctor_data["qualification"],
            years_experience=doctor_data["years_experience"],
            working_days=doctor_data["working_days"],
            working_hours=doctor_data["working_hours"],
            slot_duration_minutes=doctor_data["slot_duration_minutes"],
            breaks=doctor_data["breaks"],
            max_bookings_per_slot=doctor_data["max_bookings_per_slot"],
            daily_booking_limit=doctor_data["daily_booking_limit"],
            online_quota=doctor_data["online_quota"],
            walkin_quota=doctor_data["walkin_quota"],
            followup_duration_minutes=doctor_data["followup_duration_minutes"],
            effective_from=doctor_data["effective_from"],
        )
        created_count += 1

    return JSONResponse({"created_count": created_count, "row_errors": row_errors})


# Doctor editing follow-up (Spec.md Section 0) -- these two `{doctor_id}`
# routes MUST be registered after every static "/api/portal/doctors/..."
# path above (csv-import included) -- FastAPI matches routes in
# REGISTRATION order, so a `{doctor_id}` catch-all registered earlier would
# silently swallow a literal path segment like "csv-import" as if it were a
# doctor id (hit exactly this bug once while wiring this in -- caught by the
# existing CSV-import tests, not by inspection).
@router.get("/api/portal/doctors/{doctor_id}")
async def portal_get_doctor(doctor_id: str, authorization: str | None = Header(default=None)):
    """This Next.js portal only ever had create (`POST /api/portal/doctors`
    above); editing an EXISTING doctor's working hours/breaks/quotas was a
    known, explicitly flagged gap since the HTML-portal removal (Spec.md's
    own progress log: "doctor editing... stay FastAPI-only for now...
    Removing portal.py makes doctor editing genuinely unreachable").
    db.get_doctor_full()/db.update_doctor() already existed (the old HTML
    edit form's own backing functions) -- this just re-exposes them here."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    doctor = db.get_doctor_full(hospital.id, doctor_id)
    if doctor is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    return JSONResponse({"doctor": doctor})


@router.post("/api/portal/doctors/{doctor_id}")
async def portal_update_doctor(doctor_id: str, payload: DoctorPayload, authorization: str | None = Header(default=None)):
    """Same payload shape and validation as portal_create_doctor() above --
    reuses _validate_doctor_fields()/db.update_doctor() exactly, no
    duplicated business rules between create and edit."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_doctors")
    if forbidden:
        return forbidden
    if db.get_doctor_full(hospital.id, doctor_id) is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)

    doctor_data, errors, warnings = _validate_doctor_fields(
        0, payload.name, payload.specialization, payload.qualification, payload.years_experience,
        ",".join(payload.working_days), ",".join(payload.working_hours), payload.slot_duration_minutes,
        ",".join(payload.breaks), payload.max_bookings_per_slot, payload.daily_booking_limit,
        payload.online_quota, payload.walkin_quota, payload.followup_duration_minutes, payload.effective_from,
    )
    if errors:
        return JSONResponse({"errors": errors}, status_code=400)

    doctor = db.update_doctor(
        hospital.id, doctor_id, doctor_data["name"],
        specialization=doctor_data["specialization"],
        qualification=doctor_data["qualification"],
        years_experience=doctor_data["years_experience"],
        working_days=doctor_data["working_days"],
        working_hours=doctor_data["working_hours"],
        slot_duration_minutes=doctor_data["slot_duration_minutes"],
        breaks=doctor_data["breaks"],
        max_bookings_per_slot=doctor_data["max_bookings_per_slot"],
        daily_booking_limit=doctor_data["daily_booking_limit"],
        online_quota=doctor_data["online_quota"],
        walkin_quota=doctor_data["walkin_quota"],
        followup_duration_minutes=doctor_data["followup_duration_minutes"],
        effective_from=doctor_data["effective_from"],
    )
    if doctor is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "doctor.update",
        entity_type="doctor", entity_id=doctor_id, after={"name": doctor_data["name"]},
    )
    return JSONResponse({"doctor": doctor, "warnings": warnings})

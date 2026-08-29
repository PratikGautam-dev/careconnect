# portal/routes/doctor_portal.py
"""Doctor-scoped routes for the new dedicated doctor login (Spec.md Section
0's doctor-portal build) -- a SEPARATE surface from the shared staff portal
(portal/routes/*.py's existing /api/portal/* routes), gated by
`_authenticate_doctor` (portal/deps.py) instead of `_authenticate`.

The one rule every route here follows, without exception: doctor_id is
read ONLY from `_authenticate_doctor`'s verified token, never from a path,
query, or body parameter. This is deliberate, not an oversight -- it's the
actual fix for the cross-doctor isolation gap the doctor-login audit found
(the shared staff portal has no doctor-scoped concept at all today, so any
staff member can view any doctor's appointments/notes/video links by
passing a different doctor_id). A route here structurally cannot be asked
for "some other doctor's" data, because there is no parameter through
which a caller could ever supply one."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import db.repository as db
from portal.deps import _authenticate_doctor
from portal.routes.bookings import _appointment_json

router = APIRouter()


def _require_doctor(authorization: str | None):
    """Returns (hospital, doctor_id) or raises via an early-return JSONResponse
    from the caller -- mirrors this codebase's own established manual-guard
    idiom (portal/deps.py's require_capability docstring) rather than a
    FastAPI Depends() factory, matching every existing /api/portal/* route."""
    auth = _authenticate_doctor(authorization)
    if auth is None:
        return None, JSONResponse({"error": "Not authenticated."}, status_code=401)
    hospital, doctor_id = auth
    return (hospital, doctor_id), None


@router.get("/api/doctor/me")
async def doctor_me(authorization: str | None = Header(default=None)):
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    doctor = db.get_doctor_full(hospital.id, doctor_id)
    if doctor is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    return JSONResponse({"doctor": doctor, "hospital": {"id": hospital.id, "name": hospital.name}})


@router.get("/api/doctor/appointments/today")
async def doctor_appointments_today(authorization: str | None = Header(default=None)):
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    appointments = db.get_doctor_appointments_today(hospital.id, doctor_id)
    return JSONResponse({"appointments": [_appointment_json(a) for a in appointments]})


def _owned_appointment_or_error(hospital_id: int, doctor_id: str, appointment_id: int):
    """Every route below that touches ONE specific appointment (attendance,
    video link, visit notes) must check the appointment actually belongs to
    THIS doctor, not just that it exists at this hospital -- get_appointment()
    alone only proves hospital-level scoping, which is exactly the isolation
    gap this whole build exists to close. Returns (appointment, None) or
    (None, JSONResponse) for the caller to return directly."""
    appointment = db.get_appointment(hospital_id, appointment_id)
    if appointment is None or appointment.doctor_id != doctor_id:
        return None, JSONResponse({"error": "No such appointment."}, status_code=404)
    return appointment, None


@router.get("/api/doctor/appointments/{appointment_id}")
async def doctor_appointment_detail(appointment_id: int, authorization: str | None = Header(default=None)):
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    appointment, err = _owned_appointment_or_error(hospital.id, doctor_id, appointment_id)
    if err:
        return err
    return JSONResponse({"appointment": _appointment_json(appointment)})


@router.post("/api/doctor/appointments/{appointment_id}/attendance")
async def doctor_mark_attendance(appointment_id: int, payload: dict, authorization: str | None = Header(default=None)):
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    _, err = _owned_appointment_or_error(hospital.id, doctor_id, appointment_id)
    if err:
        return err
    if "attended" not in (payload or {}):
        return JSONResponse({"error": "attended (true/false) is required."}, status_code=400)
    attended = bool(payload["attended"])
    ok = db.mark_attendance(hospital.id, appointment_id, attended)
    if not ok:
        return JSONResponse({"error": "No such booked appointment to update."}, status_code=404)
    # actor_level is DB-CHECK-constrained to 'platform_admin'/'portal' (see
    # record_audit_log()'s own docstring) -- 'portal' is correct here too,
    # the doctor-vs-staff distinction is carried in actor_label instead.
    db.record_audit_log(
        "portal", hospital.id, f"doctor:{doctor_id}", "booking.attendance",
        entity_type="appointment", entity_id=str(appointment_id),
        after={"status": "attended" if attended else "no_show"},
    )
    return JSONResponse({"ok": True, "status": "attended" if attended else "no_show"})


@router.post("/api/doctor/appointments/{appointment_id}/notes")
async def doctor_add_visit_note(appointment_id: int, payload: dict, authorization: str | None = Header(default=None)):
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    appointment, err = _owned_appointment_or_error(hospital.id, doctor_id, appointment_id)
    if err:
        return err
    note_text = ((payload or {}).get("note_text") or "").strip()
    if not note_text:
        return JSONResponse({"error": "Note text is required."}, status_code=400)
    if appointment.patient_id is None:
        return JSONResponse({"error": "This appointment has no linked patient record."}, status_code=400)
    note = db.create_patient_visit_note(
        hospital.id, appointment.patient_id, note_text,
        appointment_id=appointment_id, doctor_id=doctor_id,
    )
    return JSONResponse({"note": note})


@router.get("/api/doctor/schedule")
async def doctor_schedule(authorization: str | None = Header(default=None)):
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    doctor = db.get_doctor_full(hospital.id, doctor_id)
    if doctor is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    leave = db.get_doctor_leave(hospital.id, doctor_id)
    return JSONResponse({"doctor": doctor, "leave": leave})


@router.post("/api/doctor/schedule")
async def doctor_update_schedule(payload: dict, authorization: str | None = Header(default=None)):
    """Deliberately narrower than the staff portal's own doctor-edit route
    (portal/routes/doctors.py's DoctorPayload/update_doctor call): a doctor
    may only change working_days/working_hours/breaks/slot_duration_minutes/
    effective_from -- update_doctor() has no partial-update mode (every
    field it takes is always written), so every OTHER field is read from
    this doctor's own current row and passed through unchanged, never left
    to a request body default that would silently reset admin-configured
    values like max_bookings_per_slot/daily_booking_limit/quotas/department."""
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    current = db.get_doctor_full(hospital.id, doctor_id)
    if current is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    payload = payload or {}
    updated = db.update_doctor(
        hospital.id, doctor_id,
        name=current["name"],
        specialization=current.get("specialization"),
        qualification=current.get("qualification"),
        years_experience=current.get("years_experience"),
        working_days=payload.get("working_days", current["working_days"]),
        working_hours=payload.get("working_hours", current["working_hours"]),
        slot_duration_minutes=payload.get("slot_duration_minutes", current["slot_duration_minutes"]),
        breaks=payload.get("breaks", current["breaks"]),
        max_bookings_per_slot=current["max_bookings_per_slot"],
        daily_booking_limit=current.get("daily_booking_limit"),
        online_quota=current.get("online_quota"),
        walkin_quota=current.get("walkin_quota"),
        followup_duration_minutes=current.get("followup_duration_minutes"),
        effective_from=payload.get("effective_from", current.get("effective_from")),
    )
    return JSONResponse({"doctor": updated})


@router.post("/api/doctor/leave")
async def doctor_add_leave(payload: dict, authorization: str | None = Header(default=None)):
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    leave_date = (payload or {}).get("date", "").strip()
    if not leave_date:
        return JSONResponse({"error": "date is required."}, status_code=400)
    reason = (payload or {}).get("reason") or None
    leave = db.create_doctor_leave(hospital.id, doctor_id, leave_date, reason=reason)
    return JSONResponse({"leave": leave})


@router.post("/api/doctor/leave/{leave_id}/delete")
async def doctor_delete_leave(leave_id: int, authorization: str | None = Header(default=None)):
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    ok = db.delete_doctor_leave(hospital.id, doctor_id, leave_id)
    if not ok:
        return JSONResponse({"error": "No such leave date."}, status_code=404)
    return JSONResponse({"ok": True})

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
import logging
from datetime import datetime

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import db.repository as db
from portal.deps import _authenticate_doctor, get_current_staff
from portal.routes.bookings import _appointment_json
from portal.routes.patients import _patient_json
from webhook.dispatch import _get_whatsapp_client

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_doctor(authorization: str | None):
    """Returns (hospital, doctor_id) or raises via an early-return JSONResponse
    from the caller -- mirrors this codebase's own established manual-guard
    idiom (portal/deps.py's require_capability docstring) rather than a
    FastAPI Depends() factory, matching every existing /api/portal/* route.

    Dual-path (docs/rbac-redis-plan.md Phase 3): tries the new unified
    get_current_staff() FIRST (a staff_users row with role='doctor', reading
    doctor_id off the verified StaffPrincipal), falling back to the original
    _authenticate_doctor() (auth/doctor_session.py's dedicated doctor token)
    for any doctor not yet migrated off doctors.email/password_hash. Both
    paths preserve the exact same isolation guarantee this module's own
    header docstring describes: doctor_id is read ONLY from a verified
    token/session, never from a request parameter, regardless of which of
    the two auth schemes actually authenticated this caller. A StaffPrincipal
    whose role isn't 'doctor' (an Admin/Receptionist's own staff login) is
    deliberately rejected here, not silently allowed through with
    doctor_id=None -- these routes are Doctor-scoped by definition."""
    principal = get_current_staff(authorization)
    if principal is not None and principal.role == "doctor" and principal.doctor_id is not None:
        return (principal.hospital, principal.doctor_id), None
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


@router.get("/api/doctor/dashboard")
async def doctor_dashboard(authorization: str | None = Header(default=None)):
    """Doctor-portal follow-up: a smaller, doctor-scoped counterpart to
    /api/portal/dashboard -- same visual language (StatTile cards, a weekly
    trend line) on the frontend, but every number here is this doctor's own,
    never hospital-wide. The calendar view lives at its own endpoint (see
    doctor_appointments_calendar() below), not here -- it needs independent
    month navigation, unlike this route's own 20s dashboard poll."""
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    doctor = db.get_doctor_full(hospital.id, doctor_id)
    if doctor is None:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
    stats = db.get_doctor_dashboard_stats(hospital.id, doctor_id)
    today = db.get_doctor_appointments_today(hospital.id, doctor_id)
    weekly_counts = db.get_doctor_weekly_appointment_counts(hospital.id, doctor_id)
    recent = db.get_doctor_appointments(hospital.id, doctor_id, limit=10)
    return JSONResponse({
        "doctor": doctor,
        "hospital": {"id": hospital.id, "name": hospital.name},
        "stats": stats,
        "today_appointments": [_appointment_json(a) for a in today],
        "weekly_counts": weekly_counts,
        "recent_appointments": [_appointment_json(a) for a in recent],
    })


@router.get("/api/doctor/appointments/calendar")
async def doctor_appointments_calendar(
    year: int | None = None, month: int | None = None, authorization: str | None = Header(default=None),
):
    """Doctor-portal follow-up: replaces the dashboard's old 30-day status
    donut with an actual month calendar of this doctor's own appointments --
    defaults to the current month, navigable via year/month query params."""
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    if not 1 <= month <= 12:
        return JSONResponse({"error": "month must be between 1 and 12."}, status_code=400)
    appointments = db.get_doctor_appointments_for_month(hospital.id, doctor_id, year, month)
    return JSONResponse({
        "year": year,
        "month": month,
        "appointments": [_appointment_json(a) for a in appointments],
    })


@router.get("/api/doctor/appointments")
async def doctor_appointments_list(authorization: str | None = Header(default=None)):
    """Doctor-portal follow-up: this doctor's full appointment history (any
    status, any date), not just today -- the /doctor/appointments page's
    list, mirroring the shared /portal/appointments page's shape but
    doctor_id-scoped instead of hospital-wide."""
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    appointments = db.get_doctor_appointments(hospital.id, doctor_id)
    return JSONResponse({"appointments": [_appointment_json(a) for a in appointments]})


@router.get("/api/doctor/patients")
async def doctor_patients_list(authorization: str | None = Header(default=None)):
    """Doctor-portal follow-up: only patients this doctor has actually seen
    -- see db.get_patients_for_doctor()'s own docstring for why this is a
    dedicated, doctor_id-scoped query rather than the shared patients
    directory with a filter bolted on."""
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    patients = db.get_patients_for_doctor(hospital.id, doctor_id)
    return JSONResponse({"patients": patients})


@router.get("/api/doctor/patients/{patient_id}")
async def doctor_patient_detail(patient_id: int, authorization: str | None = Header(default=None)):
    """Doctor-portal follow-up: a patient's demographics, their appointment
    history WITH THIS DOCTOR, and every visit note THIS DOCTOR wrote for
    them -- the /doctor/patients/[id] detail page. A patient this doctor has
    never actually treated resolves to 404, never an empty-but-200 record --
    get_doctor_appointments_for_patient() returning nothing IS the ownership
    check here, the same way _owned_appointment_or_error() is for a single
    appointment elsewhere in this file."""
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    appointments = db.get_doctor_appointments_for_patient(hospital.id, doctor_id, patient_id)
    if not appointments:
        return JSONResponse({"error": "No such patient."}, status_code=404)
    patient = db.get_patient(hospital.id, patient_id)
    notes = db.get_patient_visit_notes_by_doctor(hospital.id, patient_id, doctor_id)
    return JSONResponse({
        "patient": _patient_json(patient) if patient else None,
        "appointments": [_appointment_json(a) for a in appointments],
        "notes": notes,
    })


@router.post("/api/doctor/appointments/delay")
async def doctor_delay_remaining_appointments(payload: dict, authorization: str | None = Header(default=None)):
    """"Running late" -- shifts every one of this doctor's still-'booked'
    appointments later TODAY forward by the given number of minutes, and
    sends each affected patient a WhatsApp message with their new time.
    See db.delay_doctor_remaining_today_appointments()'s own docstring for
    why this is scoped to today+still-booked only, and processed in a way
    that can't collide with itself. The WhatsApp send is fire-and-forget per
    patient -- one send failing (a bad/expired number, a transient Meta
    error) must never undo the already-committed time shift or block
    notifying everyone else, so it's wrapped in its own try/except and
    merely logged, same "never let a notification failure turn a real,
    already-applied change into an error response" posture
    portal_cancel_booking() already established for the shared staff
    portal's own cancel-with-message flow."""
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    try:
        minutes = int((payload or {}).get("minutes"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "minutes (a whole number) is required."}, status_code=400)
    if not (1 <= minutes <= 240):
        return JSONResponse({"error": "minutes must be between 1 and 240."}, status_code=400)

    shifted = db.delay_doctor_remaining_today_appointments(hospital.id, doctor_id, minutes)
    if not shifted:
        return JSONResponse({"ok": True, "notified": 0, "appointments": []})

    if hospital.whatsapp_phone_number_id and hospital.access_token:
        doctor = db.get_doctor_full(hospital.id, doctor_id)
        doctor_name = doctor["name"] if doctor else "your doctor"
        wa = _get_whatsapp_client(hospital)
        for appointment, new_time in shifted:
            try:
                await wa.send_text(
                    appointment.phone,
                    f"Update: {doctor_name} is running a little behind schedule. Your appointment has been "
                    f"moved to {new_time.strftime('%I:%M %p').lstrip('0')} today. Sorry for the inconvenience.",
                )
            except Exception:
                logger.exception(
                    "Failed to notify %s about a running-late shift for appointment %s",
                    appointment.phone, appointment.id,
                )
    db.record_audit_log(
        "portal", hospital.id, f"doctor:{doctor_id}", "doctor.running_late",
        entity_type="doctor", entity_id=doctor_id, after={"minutes": minutes, "appointments_shifted": len(shifted)},
    )
    return JSONResponse({
        "ok": True,
        "notified": len(shifted),
        "appointments": [_appointment_json(a) for a, _new_time in shifted],
    })


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
    """Beyond the bare appointment row, also resolves the owning patient's
    record (name/DOB/etc, same shape /api/portal/patients/{id} returns) and
    this patient's visit-note history -- a doctor actually needs to SEE who
    they're seeing, not just an id; neither is part of _appointment_json()'s
    shared shape with the staff portal's own appointments list. (Restored
    here after being lost from a concurrent branch merge -- see this
    module's own doctor-frontend-restoration note in Spec.md Section 0; the
    frontend at /doctor/appointments/[id] has always expected this shape.)"""
    ctx, err = _require_doctor(authorization)
    if err:
        return err
    hospital, doctor_id = ctx
    appointment, err = _owned_appointment_or_error(hospital.id, doctor_id, appointment_id)
    if err:
        return err
    patient = db.get_patient(hospital.id, appointment.patient_id) if appointment.patient_id else None
    notes = db.get_patient_visit_notes(hospital.id, appointment.patient_id) if appointment.patient_id else []
    return JSONResponse({
        "appointment": _appointment_json(appointment),
        "patient": _patient_json(patient) if patient else None,
        "notes": notes,
    })


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

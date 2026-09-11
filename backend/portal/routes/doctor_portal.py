# portal/routes/doctor_portal.py
"""Doctor self-service routes: this doctor's own dashboard/calendar and
this doctor's own schedule/leave/running-late-delay -- the ones with no
"whose" concept for any other role, so they can't live on the shared
/api/portal/* surface the way a hospital-wide resource can. Gated by
`_require_doctor()` below, not `_authenticate`.

Every other /api/doctor/* route that USED to live here (a full appointment
list/detail, a patients list/detail, attendance, visit notes -- anything
that's really just "the shared hospital-wide resource, filtered to one
doctor") has been deleted: /api/portal/bookings, /api/portal/bookings/
{id}, and /api/portal/patients(+{id}) now do that same doctor_id-scoping
inline (see their own docstrings in bookings.py/patients.py), so keeping a
second, structurally-separate copy here was pure duplication. See
docs/rbac-redis-plan.md for the consolidation history.

The one rule every route below still follows, without exception: doctor_id
is read ONLY from `_require_doctor()`'s verified token, never from a path,
query, or body parameter -- there is no parameter through which a caller
could ever ask for "some other doctor's" schedule/leave/delay."""
import logging
from datetime import datetime

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import db.repository as db
from portal.deps import get_current_staff
from portal.routes.bookings import _appointment_json
from webhook.dispatch import _get_whatsapp_client

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_doctor(authorization: str | None):
    """Returns (hospital, doctor_id) or raises via an early-return JSONResponse
    from the caller -- mirrors this codebase's own established manual-guard
    idiom (portal/deps.py's require_capability docstring) rather than a
    FastAPI Depends() factory, matching every existing /api/portal/* route.

    Backed entirely by the unified staff login (get_current_staff(): a
    staff_users row with role='doctor', reading doctor_id off the verified
    StaffPrincipal) -- the old dedicated doctor-session token
    (auth/doctor_session.py, doctors.email/password_hash) this used to fall
    back to has been removed; it was never wired into the frontend, so the
    unified path was already the only one actually reachable. doctor_id is
    read ONLY from the verified StaffPrincipal, never from a request
    parameter -- that's what makes it structurally impossible for a doctor's
    own valid token to be used to ask for a DIFFERENT doctor's data at the
    same hospital. A StaffPrincipal whose role isn't 'doctor' (an
    Admin/Receptionist's own staff login) is deliberately rejected here, not
    silently allowed through with doctor_id=None -- these routes are
    Doctor-scoped by definition."""
    principal = get_current_staff(authorization)
    if principal is None or principal.role != "doctor" or principal.doctor_id is None:
        return None, JSONResponse({"error": "Not authenticated."}, status_code=401)
    return (principal.hospital, principal.doctor_id), None


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
        phone=current.get("phone", ""),
        employee_id=current.get("employee_id", ""),
        location=current.get("location"),
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

# Google Meet integration (Spec.md Section 0): the "Connect Google Calendar"
# status/disconnect routes used to live here, per-doctor -- moved to
# portal/routes/settings.py as /api/portal/calendar/status and /disconnect,
# admin-gated (require_permission(principal, "settings", "write")), since
# the connection is now one per HOSPITAL (an admin connects it once, used
# for every doctor's tele-consultation Meet links), not something each
# doctor manages on their own schedule page.

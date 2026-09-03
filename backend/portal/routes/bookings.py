import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import connectors
import db.repository as db
from auth.session import _build_new_booking_context
from core.whatsapp import WhatsAppClient
from db.connection import IntegrityError
from portal.deps import _authenticate, _authenticate_with_role, get_current_staff, require_permission

logger = logging.getLogger(__name__)
router = APIRouter()


def _followup_valid_until(a, followup_validity_days: int | None) -> str | None:
    """Only meaningful for an ATTENDED appointment -- the date through which
    a follow-up can still be booked against THIS visit: its own scheduled_at
    + the hospital's followup_validity_days, extended (never shortened) by a
    staff-granted followup_override_until (migration 0024) if later. None
    when followup_validity_days wasn't supplied (most call sites don't need
    it) or the appointment isn't attended."""
    if followup_validity_days is None or a.status != db.STATUS_ATTENDED:
        return None
    valid_until = a.scheduled_at.date() + timedelta(days=followup_validity_days)
    if a.followup_override_until:
        valid_until = max(valid_until, date.fromisoformat(a.followup_override_until))
    return valid_until.isoformat()


def _appointment_json(a, followup_validity_days: int | None = None) -> dict:
    return {
        "id": a.id,
        "phone": a.phone,
        "department_id": a.department_id,
        "department_name": a.department_name,
        "doctor_id": a.doctor_id,
        "doctor_name": a.doctor_name,
        "scheduled_at": a.scheduled_at.isoformat(),
        "status": a.status,
        "source": a.source,
        # Item 8 (Spec.md Section 0): now surfaced to the frontend -- was
        # generated and stored since Section 12.12 but never actually
        # returned by this JSON shape.
        "reference_id": a.reference_id,
        # Patient identity system (Spec.md Section 0): the owning patient's
        # PERMANENT Patient ID (patients.patient_display_id, via
        # appointments.patient_id) -- was denormalized onto `appointments`
        # itself back in Item 8 (patient_id/patient_name/patient_phone) but
        # never actually surfaced anywhere, frontend included, until now.
        # Deliberately the same id shown on /portal/patients, not a
        # different one -- both read through Appointment.patient_display_id/
        # patients.patient_display_id, never a second identifier.
        "patient_display_id": a.patient_display_id,
        # Tele-consultation Phase 2 (confirmed with the user directly): the
        # staff portal is how a doctor actually gets the video link -- there's
        # no doctor login/notification channel of its own in this codebase.
        # appointment_type_id lets the frontend show the link only for a
        # tele-consultation row; video_link itself is None for every other
        # type, and for a tele appointment predating this column.
        "appointment_type_id": a.appointment_type_id,
        "video_link": a.video_link,
        # When this row was actually booked, distinct from scheduled_at (the
        # appointment's own time) -- the portal list shows both.
        "created_at": a.created_at.isoformat() if a.created_at else None,
        # Follow-up validity override (migration 0024): the raw staff-granted
        # date (None if never granted) and the fully-resolved date a
        # follow-up can still be booked against this visit through (None
        # unless the caller passed followup_validity_days -- see
        # _followup_valid_until's own docstring).
        "followup_override_until": a.followup_override_until,
        "followup_valid_until": _followup_valid_until(a, followup_validity_days),
    }


@router.get("/api/portal/bookings")
async def portal_bookings(authorization: str | None = Header(default=None)):
    """Scoped to the caller's own appointments when role=="doctor" -- this
    route is now shared by the doctor portal too, and a doctor must never
    see another doctor's patients/appointments through it."""
    hospital, role, doctor_id = _authenticate_with_role(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if role == "doctor" and doctor_id is not None:
        appointments = db.get_doctor_appointments(hospital.id, doctor_id)
    else:
        appointments = db.get_all_appointments_for_hospital(hospital.id)
    validity_days = db.get_followup_validity_days(hospital.id)
    return JSONResponse({"appointments": [_appointment_json(a, validity_days) for a in appointments]})


@router.get("/api/portal/bookings/needs-attendance-review")
async def portal_bookings_needing_attendance_review(authorization: str | None = Header(default=None)):
    """Item 9 (Spec.md Section 0): appointments whose scheduled time has
    passed but are still status='booked' -- the real, staff-actionable list
    behind the dashboard's existing no-show heuristic, for the appointments
    page to prompt "Did the patient visit?" against."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    appointments = db.get_appointments_needing_attendance_review(hospital.id)
    return JSONResponse({"appointments": [_appointment_json(a) for a in appointments]})


@router.post("/api/portal/bookings/delete")
async def portal_delete_bookings(payload: dict, authorization: str | None = Header(default=None)):
    """Bulk delete for the appointments list's row checkboxes + "Delete
    selected" action, mirroring portal_delete_patients() in patients.py.
    Registered ahead of the /{appointment_id} routes below -- FastAPI
    matches routes in registration order, and a later registration here
    would let POST /api/portal/bookings/{appointment_id}/... match "delete"
    as an appointment_id string first, failing int coercion with a 422.
    Reuses db.soft_delete_appointment()'s own status != 'booked' guard --
    a still-booked id in the batch is silently skipped (not included in
    `deleted`), same as portal_delete_booking()'s single-item 400 but
    without failing the whole batch over one row."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    appointment_ids = (payload or {}).get("appointment_ids") or []
    if not isinstance(appointment_ids, list) or not appointment_ids:
        return JSONResponse({"error": "appointment_ids is required."}, status_code=400)
    deleted = [aid for aid in appointment_ids if db.soft_delete_appointment(hospital.id, aid)]
    for aid in deleted:
        db.record_audit_log(
            "portal", hospital.id, "tenant portal", "booking.delete",
            entity_type="appointment", entity_id=str(aid),
        )
    return JSONResponse({"deleted": deleted})


@router.post("/api/portal/bookings/{appointment_id}/attendance")
async def portal_mark_attendance(
    appointment_id: int, payload: dict, authorization: str | None = Header(default=None)
):
    """Item 9: payload = {"attended": true|false}. Only ever moves a
    still-'booked' row to 'attended'/'no_show' -- db.mark_attendance()'s own
    WHERE status='booked' guard makes re-marking an already-resolved
    appointment (or a wrong-hospital/nonexistent one) a clean 404, not a
    silent overwrite."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if "attended" not in (payload or {}):
        return JSONResponse({"error": "attended (true/false) is required."}, status_code=400)
    attended = bool(payload["attended"])
    ok = db.mark_attendance(hospital.id, appointment_id, attended)
    if not ok:
        return JSONResponse({"error": "No such booked appointment to update."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "booking.attendance",
        entity_type="appointment", entity_id=str(appointment_id),
        after={"status": "attended" if attended else "no_show"},
    )
    return JSONResponse({"ok": True, "status": "attended" if attended else "no_show"})


@router.post("/api/portal/bookings/{appointment_id}/delete")
async def portal_delete_booking(appointment_id: int, authorization: str | None = Header(default=None)):
    """Item 3 (Spec.md Section 0): soft-delete only, per this project's
    standing never-hard-delete-appointments convention -- db.soft_delete_
    appointment()'s own guard refuses a still-'booked' row (cancel it
    first), surfaced here as a clear 400 rather than a generic failure."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    appointment = db.get_appointment(hospital.id, appointment_id)
    if appointment is None:
        return JSONResponse({"error": "No such appointment."}, status_code=404)
    if appointment.status == db.STATUS_BOOKED:
        return JSONResponse({"error": "Cancel this appointment before deleting it."}, status_code=400)
    ok = db.soft_delete_appointment(hospital.id, appointment_id)
    if not ok:
        return JSONResponse({"error": "No such appointment."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "booking.delete",
        entity_type="appointment", entity_id=str(appointment_id),
    )
    return JSONResponse({"ok": True})


@router.post("/api/portal/bookings/{appointment_id}/cancel")
async def portal_cancel_booking(
    appointment_id: int, payload: dict | None = None, authorization: str | None = Header(default=None)
):
    """`payload.message`, when given a non-empty string, is sent to the
    patient on WhatsApp AFTER the cancellation is committed (so a delivery
    failure never blocks the cancellation itself) -- the staff appointments
    page pre-fills this with a default "your appointment has been cancelled"
    message that staff can edit to add a reason before sending.

    Audit follow-up (Spec.md Section 0): routes through
    connectors.get_connector_for_hospital() rather than calling
    db.cancel_appointment() directly -- core/booking_flow.py's WhatsApp-side
    cancel already went through the connector; this staff-portal path was the
    one write in the app that bypassed it, which would have silently
    "succeeded" against the local DB only for a Tier 2/3 hospital instead of
    ever touching that hospital's real external system."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    appointment = db.get_appointment(hospital.id, appointment_id)
    if appointment is None:
        return JSONResponse({"error": "No such appointment."}, status_code=404)

    connector = connectors.get_connector_for_hospital(hospital)
    try:
        connector.cancel_booking(hospital.id, appointment_id)
    except connectors.ConnectorNotImplementedError as e:
        return JSONResponse({"error": str(e)}, status_code=501)

    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "booking.cancel",
        entity_type="appointment", entity_id=str(appointment_id),
    )

    message = ((payload or {}).get("message") or "").strip()
    if message and hospital.whatsapp_phone_number_id and hospital.access_token:
        try:
            wa = WhatsAppClient(phone_number_id=hospital.whatsapp_phone_number_id, access_token=hospital.access_token)
            await wa.send_text(appointment.phone, message)
        except Exception:
            # The cancellation itself already committed -- a WhatsApp delivery
            # failure (expired token, patient number issue, ...) must not turn
            # a successful cancel into a 500 that makes staff think it failed.
            logger.exception("Failed to send cancellation message for appointment %s", appointment_id)
    elif message:
        logger.warning(
            "Hospital %s has no WhatsApp credentials configured -- skipping cancellation message for appointment %s",
            hospital.id, appointment_id,
        )

    return JSONResponse({"ok": True})


@router.post("/api/portal/bookings/{appointment_id}/reschedule")
async def portal_reschedule_booking(
    appointment_id: int, payload: dict, authorization: str | None = Header(default=None)
):
    """Item 2 (staff-initiated reschedule with an optional reason message) --
    mirrors portal_cancel_booking() above exactly: same auth/lookup shape,
    same "message sent AFTER the write commits, delivery failure never turns
    a successful reschedule into an error" discipline. Reuses
    connector.reschedule_booking() (connectors.py) rather than a parallel
    write path -- the same call core/booking_flow.py's WhatsApp-side
    reschedule already uses, so both entry points share the exact
    "book the new slot before touching the old appointment" race-safety
    ordering (a losing IntegrityError here leaves the original appointment
    untouched, same as the WhatsApp flow's own _handle_slot_taken recovery --
    the portal surfaces it as a plain 400 rather than an alternate-slot
    picker, since staff can just pick a different slot from the same form
    and resubmit, unlike a WhatsApp conversation mid-flow)."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    appointment = db.get_appointment(hospital.id, appointment_id)
    if appointment is None:
        return JSONResponse({"error": "No such appointment."}, status_code=404)

    department_id = (payload or {}).get("department_id") or ""
    doctor_id = (payload or {}).get("doctor_id") or ""
    slot_id = (payload or {}).get("slot_id") or ""

    errors = []
    department = db.find_department(hospital.id, department_id)
    if department is None:
        errors.append("Choose a valid department.")
    doctor = db.find_doctor(hospital.id, department_id, doctor_id) if department else None
    if doctor is None:
        errors.append("Choose a valid doctor.")
    scheduled_at = None
    if not slot_id:
        errors.append("Choose an available slot.")
    else:
        try:
            scheduled_at = datetime.fromisoformat(slot_id)
        except ValueError:
            errors.append("That slot is no longer valid — pick another.")
    if errors:
        return JSONResponse({"errors": errors}, status_code=400)
    assert scheduled_at is not None  # only left None when "Choose an available slot." was added above

    connector = connectors.get_connector_for_hospital(hospital)
    try:
        connector.reschedule_booking(
            hospital_id=hospital.id,
            old_appointment_id=appointment_id,
            phone=appointment.phone,
            department_id=department_id,
            doctor_id=doctor_id,
            scheduled_at=scheduled_at,
        )
    except connectors.ConnectorNotImplementedError as e:
        return JSONResponse({"errors": [str(e)]}, status_code=501)
    except IntegrityError:
        return JSONResponse({"errors": ["That slot was just taken — please pick another."]}, status_code=400)

    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "booking.reschedule",
        entity_type="appointment", entity_id=str(appointment_id),
        before={"scheduled_at": appointment.scheduled_at.isoformat()},
        after={"scheduled_at": scheduled_at.isoformat(), "doctor_id": doctor_id},
    )

    message = ((payload or {}).get("message") or "").strip()
    if message and hospital.whatsapp_phone_number_id and hospital.access_token:
        try:
            wa = WhatsAppClient(phone_number_id=hospital.whatsapp_phone_number_id, access_token=hospital.access_token)
            await wa.send_text(appointment.phone, message)
        except Exception:
            logger.exception("Failed to send reschedule message for appointment %s", appointment_id)
    elif message:
        logger.warning(
            "Hospital %s has no WhatsApp credentials configured -- skipping reschedule message for appointment %s",
            hospital.id, appointment_id,
        )

    return JSONResponse({"ok": True})


@router.get("/api/portal/new-booking/context")
async def portal_new_booking_context(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    departments, doctors_by_department, slots_by_doctor = _build_new_booking_context(hospital)
    return JSONResponse({
        "departments": departments,
        "doctors_by_department": doctors_by_department,
        "slots_by_doctor": slots_by_doctor,
    })


@router.post("/api/portal/new-booking")
async def portal_create_new_booking(payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    patient_name = (payload.get("patient_name") or "").strip()
    patient_phone = (payload.get("patient_phone") or "").strip()
    department_id = payload.get("department_id") or ""
    doctor_id = payload.get("doctor_id") or ""
    slot_id = payload.get("slot_id") or ""

    errors = []
    if not db.is_valid_phone(patient_phone):
        errors.append("Patient phone is required and must contain at least one digit.")
    department = db.find_department(hospital.id, department_id)
    if department is None:
        errors.append("Choose a valid department.")
    doctor = db.find_doctor(hospital.id, department_id, doctor_id) if department else None
    if doctor is None:
        errors.append("Choose a valid doctor.")
    scheduled_at = None
    if not slot_id:
        errors.append("Choose an available slot.")
    else:
        try:
            scheduled_at = datetime.fromisoformat(slot_id)
        except ValueError:
            errors.append("That slot is no longer valid — pick another.")

    if errors:
        return JSONResponse({"errors": errors}, status_code=400)
    assert scheduled_at is not None  # only left None when "Choose an available slot." was added above

    connector = connectors.get_connector_for_hospital(hospital)
    try:
        created = connector.create_booking(
            hospital.id, patient_phone, department_id, doctor_id, scheduled_at,
            source=db.SOURCE_STAFF, patient_name=patient_name or None,
        )
    except db.QuotaExceededError as e:
        return JSONResponse({"errors": [str(e)]}, status_code=400)
    except IntegrityError:
        return JSONResponse({"errors": ["That slot was just taken — please pick another."]}, status_code=400)

    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "booking.create",
        entity_type="appointment", entity_id=str(created.id),
        after={"department_id": department_id, "doctor_id": doctor_id, "scheduled_at": scheduled_at.isoformat()},
    )

    return JSONResponse({"ok": True})


# --- Follow-up validity override (migration 0024) -- both routes below are
# admin/receptionist-only in practice (require_permission's "write" action on
# "appointments", which by default excludes neither role but a hospital can
# restrict via Roles & Permissions), unlike every other route in this file,
# which still only checks hospital-level auth (see portal/deps.py's
# _authenticate docstring on why the rest of this file hasn't been migrated
# yet). New routes, so there's no legacy-shared-password caller depending on
# reaching them without a real staff login. ---

@router.post("/api/portal/bookings/{appointment_id}/followup/extend")
async def portal_extend_followup_validity(
    appointment_id: int, payload: dict, authorization: str | None = Header(default=None)
):
    """Patient contacted the hospital after their normal follow-up window on
    THIS attended visit had already closed -- grants them `extra_days` more,
    after which they can book the follow-up themselves on WhatsApp as normal
    (get_followup_eligible_appointments() honors the override transparently,
    no other change needed there). payload = {"extra_days": <positive int>}."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "appointments", "write")
    if forbidden:
        return forbidden

    extra_days = (payload or {}).get("extra_days")
    if not isinstance(extra_days, int) or isinstance(extra_days, bool) or extra_days <= 0:
        return JSONResponse({"error": "extra_days must be a positive integer."}, status_code=400)

    updated = db.grant_followup_extension(principal.hospital.id, appointment_id, extra_days)
    if updated is None:
        return JSONResponse({"error": "No such attended appointment to extend."}, status_code=404)

    db.record_audit_log(
        "portal", principal.hospital.id, principal.name, "booking.followup_extend",
        entity_type="appointment", entity_id=str(appointment_id),
        after={"followup_override_until": updated.followup_override_until, "extra_days": extra_days},
    )
    validity_days = db.get_followup_validity_days(principal.hospital.id)
    return JSONResponse({"ok": True, "appointment": _appointment_json(updated, validity_days)})


@router.post("/api/portal/bookings/{appointment_id}/followup/book")
async def portal_book_followup_now(
    appointment_id: int, payload: dict, authorization: str | None = Header(default=None)
):
    """Direct override: books a follow-up right now against `appointment_id`
    (the past ATTENDED visit being followed up on) -- its own doctor and
    department, ignoring the eligibility window entirely. Unlike the extend
    action above, the patient never books this themselves; staff only pick
    the new slot (payload = {"scheduled_at": "<ISO datetime>"}), same as
    every other appointment-type flow's own "no doctor/department picker for
    follow-up" behavior."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "appointments", "write")
    if forbidden:
        return forbidden

    source_appointment = db.get_appointment(principal.hospital.id, appointment_id)
    if source_appointment is None or source_appointment.status != db.STATUS_ATTENDED:
        return JSONResponse({"error": "No such attended appointment to follow up on."}, status_code=404)

    slot_id = (payload or {}).get("scheduled_at") or ""
    try:
        scheduled_at = datetime.fromisoformat(slot_id)
    except ValueError:
        return JSONResponse({"errors": ["Choose a valid date/time."]}, status_code=400)

    connector = connectors.get_connector_for_hospital(principal.hospital)
    try:
        created = connector.create_booking(
            principal.hospital.id, source_appointment.phone, source_appointment.department_id,
            source_appointment.doctor_id, scheduled_at, source=db.SOURCE_STAFF,
            patient_id=source_appointment.patient_id, appointment_type_id="followup",
        )
    except db.QuotaExceededError as e:
        return JSONResponse({"errors": [str(e)]}, status_code=400)
    except db.DuplicateBookingError as e:
        return JSONResponse({"errors": [str(e)]}, status_code=400)
    except IntegrityError:
        return JSONResponse({"errors": ["That slot was just taken — please pick another."]}, status_code=400)

    db.record_audit_log(
        "portal", principal.hospital.id, principal.name, "booking.followup_override",
        entity_type="appointment", entity_id=str(created.id),
        after={
            "source_appointment_id": appointment_id, "doctor_id": source_appointment.doctor_id,
            "scheduled_at": scheduled_at.isoformat(),
        },
    )
    return JSONResponse({"ok": True, "appointment": _appointment_json(created)})

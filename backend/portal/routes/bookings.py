import logging
from datetime import datetime

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import connectors
import db.repository as db
from auth.session import _build_new_booking_context
from core.whatsapp import WhatsAppClient
from db.connection import IntegrityError
from portal.deps import _authenticate

logger = logging.getLogger(__name__)
router = APIRouter()


def _appointment_json(a) -> dict:
    return {
        "id": a.id,
        "phone": a.phone,
        "department_name": a.department_name,
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
    }


@router.get("/api/portal/bookings")
async def portal_bookings(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    appointments = db.get_all_appointments_for_hospital(hospital.id)
    return JSONResponse({"appointments": [_appointment_json(a) for a in appointments]})


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

    message = ((payload or {}).get("message") or "").strip()
    if message:
        try:
            wa = WhatsAppClient(phone_number_id=hospital.whatsapp_phone_number_id, access_token=hospital.access_token)
            await wa.send_text(appointment.phone, message)
        except Exception:
            # The cancellation itself already committed -- a WhatsApp delivery
            # failure (expired token, patient number issue, ...) must not turn
            # a successful cancel into a 500 that makes staff think it failed.
            logger.exception("Failed to send cancellation message for appointment %s", appointment_id)

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

    message = ((payload or {}).get("message") or "").strip()
    if message:
        try:
            wa = WhatsAppClient(phone_number_id=hospital.whatsapp_phone_number_id, access_token=hospital.access_token)
            await wa.send_text(appointment.phone, message)
        except Exception:
            logger.exception("Failed to send reschedule message for appointment %s", appointment_id)

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

    connector = connectors.get_connector_for_hospital(hospital)
    try:
        connector.create_booking(
            hospital.id, patient_phone, department_id, doctor_id, scheduled_at,
            source=db.SOURCE_STAFF, patient_name=patient_name or None,
        )
    except db.QuotaExceededError as e:
        return JSONResponse({"errors": [str(e)]}, status_code=400)
    except IntegrityError:
        return JSONResponse({"errors": ["That slot was just taken — please pick another."]}, status_code=400)

    return JSONResponse({"ok": True})

# portal_api.py
"""
JSON API for the Next.js hospital-staff portal (frontend/src/app/portal) --
portal.py is the original server-rendered HTML portal with an httponly
session cookie; this module exposes the same login + dashboard-read
operations as JSON, reusing portal.py's own session signing/verification and
db/repository.py's dashboard queries rather than re-implementing them.

Transport differs deliberately: portal.py's cookie is httponly + SameSite=lax,
fine for a same-origin server-rendered page, but the Next.js frontend runs on
a different origin/port (localhost:3000 vs this API's localhost:8000, a real
cross-site relationship even in dev) where a third-party cookie needs
SameSite=None + Secure -- not viable over plain http in local dev. Instead
the signed "hospital_id.expires_epoch.signature" token portal.py already
generates (_sign_session) is returned in the JSON body and sent back by the
frontend as a Bearer token, verified with the exact same _verify_session --
same signature, same TTL, same "basic protection" posture, just a different
transport.
"""
import hashlib
import logging
import time
from datetime import datetime

from fastapi import APIRouter, File, Header, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

import connectors
import core.rate_limit as rate_limit
import db.repository as db
from admin.onboarding import _validate_doctor_fields, _parse_offsets
from core.storage import get_storage
from core.translations import SUPPORTED_LANGUAGES, t
from core.whatsapp import WhatsAppClient
from db.connection import IntegrityError
from flows import REAL_FEATURES
from portal import _SESSION_TTL_SECONDS, _build_new_booking_context, _sign_session, _verify_session

# Section 12.13: minutes bounds mirror db/schema.sql's session_timeout_minutes
# CHECK constraint exactly -- validated here too so a bad value gets a clear
# 400 from this endpoint instead of surfacing as a raw IntegrityError from
# the DB constraint.
_MIN_SESSION_TIMEOUT_MINUTES = 2
_MAX_SESSION_TIMEOUT_MINUTES = 120

logger = logging.getLogger(__name__)
router = APIRouter()


def _hospital_summary(hospital) -> dict:
    return {
        "id": hospital.id,
        "name": hospital.name,
        "data_tier": hospital.data_tier,
        "enabled_features": hospital.enabled_features,
    }


def _authenticate(authorization: str | None):
    """Returns the Hospital for a valid 'Bearer <token>' header, or None."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    hospital_id = _verify_session(token)
    if hospital_id is None:
        return None
    return db.get_hospital(hospital_id)


def _session_id(authorization: str | None) -> str | None:
    """Section 12.10's deliberate partial audit trail: real per-staff
    accounts don't exist (portal auth is one shared password per hospital),
    so a note/document can only be traced back to a *login session*, not a
    named person. A hash of the Bearer token (not the raw token) uniquely
    identifies one login session -- storing it raw in a DB row that other
    staff at the same hospital can read via a future admin view would be a
    real credential leak, since the raw token still authenticates."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return hashlib.sha256(token.encode()).hexdigest()[:16]


@router.post("/api/portal/login")
async def portal_login(payload: dict, request: Request):
    key = rate_limit.client_key("portal_login", request)
    if rate_limit.is_locked_out(key):
        return JSONResponse(
            {"error": "Too many attempts. Please wait a while before trying again."}, status_code=429
        )

    password = (payload or {}).get("password", "")
    hospital = db.find_hospital_by_portal_password(password) if password else None
    if hospital is None:
        rate_limit.record_failure(key)
        return JSONResponse({"error": "Incorrect password."}, status_code=403)

    rate_limit.reset(key)
    expires_at = int(time.time()) + _SESSION_TTL_SECONDS
    token = _sign_session(hospital.id, expires_at)
    return JSONResponse({"token": token, "expires_at": expires_at, "hospital": _hospital_summary(hospital)})


@router.get("/api/portal/dashboard")
async def portal_dashboard(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    stats = db.get_dashboard_stats(hospital.id)
    weekly_counts = db.get_weekly_appointment_counts(hospital.id)
    dept_breakdown = db.get_appointments_by_department(hospital.id)
    recent_appointments = db.get_all_appointments_for_hospital(hospital.id, limit=10)
    activity_feed = db.get_recent_activity_feed(hospital.id, limit=10)
    recent_patients = db.get_recent_patients(hospital.id, limit=5)

    return JSONResponse({
        "hospital": _hospital_summary(hospital),
        "stats": stats,
        "weekly_counts": weekly_counts,
        "department_breakdown": dept_breakdown,
        "recent_patients": recent_patients,
        "recent_appointments": [
            {
                "id": a.id,
                "phone": a.phone,
                # Item 3 (Spec.md Section 0): the dashboard's separate "Patients"
                # widget was merged into this table -- patient name now shown
                # inline instead of a second, patient-centric list.
                "patient_name": (db.get_patient_by_phone(hospital.id, a.phone) or {}).get("name"),
                "department_name": a.department_name,
                "doctor_name": a.doctor_name,
                "scheduled_at": a.scheduled_at.isoformat(),
                "status": a.status,
                "source": a.source,
                # Item 9 (Spec.md Section 0): column parity with the full
                # Appointments page, which already surfaces this.
                "reference_id": a.reference_id,
            }
            for a in recent_appointments
        ],
        "activity_feed": [
            {
                "label": item["label"],
                "phone": item["phone"],
                "doctor_name": item["doctor_name"],
                "department_name": item["department_name"],
                "at": item["at"].isoformat(),
            }
            for item in activity_feed
        ],
    })


@router.get("/api/portal/patients")
async def portal_patients(search: str = "", authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({"patients": db.list_patients(hospital.id, search=search)})


# --- Patient detail: demographics, visit history, notes, documents
# (Section 12.10) ---

def _patient_json(p: dict) -> dict:
    return {
        "id": p["id"], "phone": p["phone"], "name": p["name"],
        "date_of_birth": p.get("date_of_birth"), "gender": p.get("gender"), "address": p.get("address"),
        "created_at": p["created_at"],
    }


@router.get("/api/portal/patients/{patient_id}")
async def portal_patient_detail(patient_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    patient = db.get_patient(hospital.id, patient_id)
    if patient is None:
        return JSONResponse({"error": "No such patient."}, status_code=404)

    visit_history = db.get_patient_visit_history(hospital.id, patient_id)
    notes = db.get_patient_visit_notes(hospital.id, patient_id)
    documents = db.get_patient_documents(hospital.id, patient_id)

    return JSONResponse({
        "patient": _patient_json(patient),
        "visit_history": [_appointment_json(a) for a in visit_history],
        "notes": notes,
        "documents": documents,
    })


@router.post("/api/portal/patients/{patient_id}")
async def portal_update_patient(patient_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    updated = db.update_patient_demographics(
        hospital.id, patient_id,
        date_of_birth=(payload or {}).get("date_of_birth") or None,
        gender=(payload or {}).get("gender") or None,
        address=(payload or {}).get("address") or None,
    )
    if updated is None:
        return JSONResponse({"error": "No such patient."}, status_code=404)
    return JSONResponse({"patient": _patient_json(updated)})


@router.post("/api/portal/patients/{patient_id}/notes")
async def portal_add_patient_note(patient_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_patient(hospital.id, patient_id) is None:
        return JSONResponse({"error": "No such patient."}, status_code=404)

    note_text = ((payload or {}).get("note_text") or "").strip()
    if not note_text:
        return JSONResponse({"error": "Note text is required."}, status_code=400)
    appointment_id = (payload or {}).get("appointment_id") or None
    doctor_id = (payload or {}).get("doctor_id") or None

    note = db.create_patient_visit_note(
        hospital.id, patient_id, note_text,
        appointment_id=appointment_id, doctor_id=doctor_id,
        created_by_session_id=_session_id(authorization),
    )
    return JSONResponse({"note": note})


@router.post("/api/portal/patients/{patient_id}/documents")
async def portal_upload_patient_document(
    patient_id: int, file: UploadFile = File(...), authorization: str | None = Header(default=None),
):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_patient(hospital.id, patient_id) is None:
        return JSONResponse({"error": "No such patient."}, status_code=404)
    if not file.filename:
        return JSONResponse({"error": "A file is required."}, status_code=400)

    content = await file.read()
    if not content:
        return JSONResponse({"error": "The uploaded file is empty."}, status_code=400)

    storage = get_storage()
    storage_key = storage.upload(
        hospital.id, patient_id, file.filename, content, file.content_type or "application/octet-stream",
    )
    document = db.create_patient_document(
        hospital.id, patient_id, file.filename, storage_key,
        uploaded_by_session_id=_session_id(authorization),
    )
    return JSONResponse({"document": document})


@router.post("/api/portal/patients/{patient_id}/documents/{document_id}/send")
async def portal_send_patient_document(
    patient_id: int, document_id: int, authorization: str | None = Header(default=None),
):
    """Sends the document directly to the patient's own WhatsApp chat.
    Deliberately calls WhatsAppClient directly rather than through
    connectors.py: the Connector interface (connectors.py's module
    docstring) exists to abstract WHERE booking/appointment/doctor data
    lives across data tiers (Tier 1 local DB vs Tier 2 external API vs
    Tier 3 direct DB) -- it has never been the path WhatsApp *sends*
    themselves go through, on any tier. Every existing send (reminders,
    the handoff-reply endpoint, the cancel-with-message endpoint) already
    calls WhatsAppClient directly with the hospital's own credentials,
    regardless of that hospital's data_tier -- sending a message isn't a
    booking-data operation, so there's no tier-specific behavior to
    abstract here. This follows that same established pattern rather than
    introducing a new, inconsistent one."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    patient = db.get_patient(hospital.id, patient_id)
    if patient is None:
        return JSONResponse({"error": "No such patient."}, status_code=404)
    document = db.get_patient_document(hospital.id, document_id)
    if document is None or document["patient_id"] != patient_id:
        return JSONResponse({"error": "No such document."}, status_code=404)

    storage = get_storage()
    document_url = storage.get_signed_url(document["file_url"], expires_in=3600)

    wa = WhatsAppClient(phone_number_id=hospital.whatsapp_phone_number_id, access_token=hospital.access_token)
    sent = await wa.send_document(patient["phone"], document_url, document["file_name"])
    if not sent:
        return JSONResponse(
            {"error": "Couldn't send the document on WhatsApp. Please check the connection and try again."},
            status_code=502,
        )
    db.mark_document_sent_to_whatsapp(hospital.id, document_id)
    return JSONResponse({"ok": True})


@router.get("/api/documents/local/{token:path}")
async def portal_serve_local_document(token: str):
    """Only reachable/meaningful when core/storage.py fell back to
    LocalFileStorage (no S3_BUCKET configured) -- S3Storage's signed URLs
    point directly at S3/R2 and never touch this app at all. No portal
    Bearer-token auth here: the signed, expiring token IS the capability --
    the same way an S3 presigned URL needs no separate auth header either."""
    storage = get_storage()
    if not hasattr(storage, "verify_token"):
        return JSONResponse({"error": "Not found."}, status_code=404)
    storage_key = storage.verify_token(token)
    if storage_key is None:
        return JSONResponse({"error": "This link has expired or is invalid."}, status_code=403)
    content = storage.read(storage_key)
    if content is None:
        return JSONResponse({"error": "Not found."}, status_code=404)
    file_name = storage_key.rsplit("_", 1)[-1]
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


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
    name = (payload or {}).get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Department name is required."}, status_code=400)
    department = db.create_department(hospital.id, name)
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
    return JSONResponse({"doctor": doctor, "warnings": warnings})


@router.post("/api/portal/doctors/{doctor_id}/active")
async def portal_set_doctor_active(doctor_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    is_active = bool((payload or {}).get("is_active", True))
    ok = db.set_doctor_active(hospital.id, doctor_id, is_active)
    if not ok:
        return JSONResponse({"error": "No such doctor."}, status_code=404)
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
    ok = db.delete_doctor_leave(hospital.id, doctor_id, leave_id)
    if not ok:
        return JSONResponse({"error": "No such leave date."}, status_code=404)
    return JSONResponse({"ok": True})


@router.get("/api/portal/doctors/{doctor_id}/slots")
async def portal_get_doctor_slots(doctor_id: str, date: str, authorization: str | None = Header(default=None)):
    """Item 1 (Spec.md Section 0): every generated slot for this doctor on
    one date (blocked/booked flags included) -- the manual per-slot-block
    admin view."""
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


@router.get("/api/portal/settings")
async def portal_get_settings(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({
        "name": hospital.name,
        "welcome_message_text": hospital.welcome_message_text or "",
        "reminder_offsets_hours": ",".join(str(h) for h in hospital.reminder_offsets_hours),
        "reminder_template_name": hospital.reminder_template_name or "",
        # Section 12.13: self-serve bot customization.
        "enabled_features": hospital.enabled_features,
        "feature_labels": hospital.feature_labels,
        # Fixed default label per real feature, in English, so the frontend
        # can show it as this field's placeholder ("leave blank to use ...")
        # rather than duplicating core/translations.py's copy itself.
        "feature_default_labels": {key: t(f"feature_{key}", "en") for key in REAL_FEATURES},
        "closing_message_text": hospital.closing_message_text or "",
        "business_hours_text": hospital.business_hours_text or "",
        "default_language": hospital.default_language,
        "language_prompt_enabled": hospital.language_prompt_enabled,
        "session_timeout_minutes": hospital.session_timeout_minutes or 30,
    })


@router.post("/api/portal/settings")
async def portal_update_settings(payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    # Section 12.13 validation -- a clear 400 instead of a raw DB error/silent
    # bad value.
    default_language = payload.get("default_language") or "en"
    if default_language not in SUPPORTED_LANGUAGES:
        return JSONResponse({"error": f"default_language must be one of {sorted(SUPPORTED_LANGUAGES)}."}, status_code=400)

    session_timeout_raw = payload.get("session_timeout_minutes")
    if session_timeout_raw in (None, ""):
        session_timeout_minutes = None
    else:
        try:
            session_timeout_minutes = int(session_timeout_raw)
        except (TypeError, ValueError):
            return JSONResponse({"error": "session_timeout_minutes must be a whole number of minutes."}, status_code=400)
        if not (_MIN_SESSION_TIMEOUT_MINUTES <= session_timeout_minutes <= _MAX_SESSION_TIMEOUT_MINUTES):
            return JSONResponse({
                "error": f"session_timeout_minutes must be between {_MIN_SESSION_TIMEOUT_MINUTES} and {_MAX_SESSION_TIMEOUT_MINUTES}.",
            }, status_code=400)

    # Only real, currently-enabled feature keys can get a custom label -- a
    # stray/typo'd key in the payload (or one for a feature this hospital
    # doesn't have enabled) is silently dropped rather than stored forever
    # unused. A blank override string means "use the default," not "set the
    # label to empty," so it's dropped too rather than stored as "".
    raw_feature_labels = payload.get("feature_labels") or {}
    feature_labels = {
        key: label.strip()
        for key, label in raw_feature_labels.items()
        if key in REAL_FEATURES and isinstance(label, str) and label.strip()
    }

    # Same restriction as portal.py's own settings form: credentials/data_tier/
    # portal_password_hash/enabled_features are never touched here, only
    # passed through unchanged -- WhatsApp connection details stay
    # operator-only via /admin/edit-tenant.
    db.update_hospital(
        hospital.id,
        name=hospital.name,
        whatsapp_phone_number_id=hospital.whatsapp_phone_number_id,
        access_token=hospital.access_token,
        app_secret=hospital.app_secret,
        timezone=hospital.timezone,
        welcome_message_text=(payload.get("welcome_message_text") or "").strip() or None,
        reminder_offsets_hours=_parse_offsets(payload.get("reminder_offsets_hours") or ""),
        reminder_template_name=(payload.get("reminder_template_name") or "").strip() or None,
        data_tier=hospital.data_tier,
        external_api_base_url=hospital.external_api_base_url,
        external_api_key=hospital.external_api_key,
        portal_password_hash=hospital.portal_password_hash,
        enabled_features=hospital.enabled_features,
        feature_labels=feature_labels,
        closing_message_text=(payload.get("closing_message_text") or "").strip() or None,
        business_hours_text=(payload.get("business_hours_text") or "").strip() or None,
        default_language=default_language,
        language_prompt_enabled=bool(payload.get("language_prompt_enabled", True)),
        session_timeout_minutes=session_timeout_minutes,
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


# --- Human handoff queue (Section 14.5 follow-up) ---

@router.get("/api/portal/handoffs")
async def portal_get_handoffs(
    status: str = "open", date: str | None = None, authorization: str | None = Header(default=None)
):
    """Item 6 (Spec.md Section 0): date ("YYYY-MM-DD"), when given, scopes
    to requests created that one calendar day -- status filtering
    (open/resolved/all) already existed."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    status_filter = None if status == "all" else status
    return JSONResponse({"handoffs": db.get_handoff_requests(hospital.id, status=status_filter, date_str=date)})


@router.post("/api/portal/handoffs/{handoff_id}/delete")
async def portal_delete_handoff(handoff_id: int, authorization: str | None = Header(default=None)):
    """Item 3: soft-delete only, same convention as bookings above."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    ok = db.soft_delete_handoff(hospital.id, handoff_id)
    if not ok:
        return JSONResponse({"error": "No such handoff request."}, status_code=404)
    return JSONResponse({"ok": True})


@router.post("/api/portal/handoffs/{handoff_id}/resolve")
async def portal_resolve_handoff(handoff_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    ok = db.resolve_handoff_request(hospital.id, handoff_id)
    if not ok:
        return JSONResponse({"error": "No such open handoff request."}, status_code=404)
    return JSONResponse({"ok": True})


@router.post("/api/portal/handoffs/{handoff_id}/reply")
async def portal_reply_handoff(handoff_id: int, payload: dict, authorization: str | None = Header(default=None)):
    """Sends a real WhatsApp message back to the patient (does NOT itself
    resolve the handoff -- a staff member may reply more than once before
    marking it done, e.g. asking a clarifying question first)."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    text = (payload or {}).get("text", "").strip()
    if not text:
        return JSONResponse({"error": "Reply text is required."}, status_code=400)

    matches = [h for h in db.get_handoff_requests(hospital.id, status=None) if h["id"] == handoff_id]
    if not matches:
        return JSONResponse({"error": "No such handoff request."}, status_code=404)
    phone = matches[0]["phone"]

    wa = WhatsAppClient(phone_number_id=hospital.whatsapp_phone_number_id, access_token=hospital.access_token)
    await wa.send_text(phone, text)
    return JSONResponse({"ok": True})

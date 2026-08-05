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
import time
from datetime import datetime

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import connectors
import db.repository as db
from admin.onboarding import _validate_doctor_fields, _parse_offsets
from db.connection import IntegrityError
from portal import _SESSION_TTL_SECONDS, _build_new_booking_context, _sign_session, _verify_session

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


@router.post("/api/portal/login")
async def portal_login(payload: dict):
    password = (payload or {}).get("password", "")
    hospital = db.find_hospital_by_portal_password(password) if password else None
    if hospital is None:
        return JSONResponse({"error": "Incorrect password."}, status_code=403)

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

    return JSONResponse({
        "hospital": _hospital_summary(hospital),
        "stats": stats,
        "weekly_counts": weekly_counts,
        "department_breakdown": dept_breakdown,
        "recent_appointments": [
            {
                "id": a.id,
                "phone": a.phone,
                "department_name": a.department_name,
                "doctor_name": a.doctor_name,
                "scheduled_at": a.scheduled_at.isoformat(),
                "status": a.status,
                "source": a.source,
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


def _appointment_json(a) -> dict:
    return {
        "id": a.id,
        "phone": a.phone,
        "department_name": a.department_name,
        "doctor_name": a.doctor_name,
        "scheduled_at": a.scheduled_at.isoformat(),
        "status": a.status,
        "source": a.source,
    }


@router.get("/api/portal/bookings")
async def portal_bookings(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    appointments = db.get_all_appointments_for_hospital(hospital.id)
    return JSONResponse({"appointments": [_appointment_json(a) for a in appointments]})


@router.post("/api/portal/bookings/{appointment_id}/cancel")
async def portal_cancel_booking(appointment_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    db.cancel_appointment(hospital.id, appointment_id)
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
    })


@router.post("/api/portal/settings")
async def portal_update_settings(payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

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

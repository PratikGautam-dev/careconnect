# admin/onboarding_api.py
"""
JSON API for the onboarding wizard, built for the Next.js frontend
(frontend/src/app/admin/onboard-hospital) — the original wizard in
admin/onboarding.py is a single server-rendered HTML page with vanilla JS
step navigation and a form-encoded POST; this module exposes the same
create-a-hospital operation as JSON in, JSON out, without duplicating any
validation or database-write logic. Field-level rules (doctor schedule
parsing, department/topic reconstruction, tier requirements) are imported
straight from admin.onboarding so the two entry points can never drift apart.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db.repository as db
import flows
from admin.onboarding import _VALID_TIERS, _parse_offsets, _validate_doctor_fields, check_admin_secret
from db.connection import IntegrityError

router = APIRouter()


class DoctorIn(BaseModel):
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


class DepartmentIn(BaseModel):
    name: str = ""
    doctors: list[DoctorIn] = Field(default_factory=list)


class TopicIn(BaseModel):
    topic_label: str = ""
    answer_text: str = ""


class OnboardingSubmission(BaseModel):
    admin_secret: str = ""
    name: str = ""
    whatsapp_phone_number_id: str = ""
    access_token: str = ""
    app_secret: str = ""
    welcome_message_text: str = ""
    reminder_offsets_hours: str = "24"
    reminder_template_name: str = ""
    portal_password: str = ""
    enabled_features: list[str] = Field(default_factory=list)
    data_tier: str = "tier1"
    api_base_url: str = ""
    api_key: str = ""
    departments: list[DepartmentIn] = Field(default_factory=list)
    topics: list[TopicIn] = Field(default_factory=list)


def _validate_departments(departments: list[DepartmentIn]) -> tuple[list[dict], list[str], list[str]]:
    """Nested-JSON equivalent of admin.onboarding._build_departments() --
    same per-doctor validation (_validate_doctor_fields), just walking a list
    of DepartmentIn objects instead of reconstructing them from parallel
    form-array fields."""
    built: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []
    doctor_index = 0
    for dept in departments:
        dept_name = dept.name.strip()
        built_doctors = []
        for doc in dept.doctors:
            doctor, doc_errors, doc_warnings = _validate_doctor_fields(
                doctor_index,
                doc.name,
                doc.specialization,
                doc.qualification,
                doc.years_experience,
                ",".join(doc.working_days),
                ",".join(doc.working_hours),
                doc.slot_duration_minutes,
                ",".join(doc.breaks),
                doc.max_bookings_per_slot,
                doc.daily_booking_limit,
                doc.online_quota,
                doc.walkin_quota,
                doc.followup_duration_minutes,
                doc.effective_from,
            )
            errors.extend(doc_errors)
            warnings.extend(doc_warnings)
            if doctor is not None:
                built_doctors.append(doctor)
            doctor_index += 1
        if built_doctors and not dept_name:
            errors.append(f'A department with doctors {[d["name"] for d in built_doctors]} is missing a name.')
        if dept_name and built_doctors:
            built.append({"name": dept_name, "doctors": built_doctors})
    return built, errors, warnings


def _validate_topics(topics: list[TopicIn]) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    built: list[dict] = []
    for i, t in enumerate(topics):
        label = t.topic_label.strip()
        answer = t.answer_text.strip()
        if not label and not answer:
            continue
        if not label:
            errors.append(f"Topic #{i + 1}: label is required (it has an answer but no label).")
            continue
        if not answer:
            errors.append(f'Topic #{i + 1} ("{label}"): answer text is required.')
            continue
        built.append({"topic_label": label, "answer_text": answer})
    return built, errors


@router.post("/api/onboarding")
async def submit_onboarding(payload: OnboardingSubmission, request: Request):
    if not check_admin_secret(payload.admin_secret, request):
        return JSONResponse({"errors": ["Incorrect admin secret."]}, status_code=403)

    name = payload.name.strip()
    whatsapp_phone_number_id = payload.whatsapp_phone_number_id.strip()
    errors: list[str] = []
    if not name:
        errors.append("Hospital name is required.")
    if not whatsapp_phone_number_id:
        errors.append("WhatsApp phone_number_id is required.")

    unknown_features = [f for f in payload.enabled_features if f not in flows.ALL_FEATURES]
    if unknown_features:
        errors.append(f'Unrecognized patient-experience option(s): {", ".join(unknown_features)}.')
    if not payload.enabled_features:
        errors.append("At least one patient-experience option is required.")

    if payload.data_tier not in _VALID_TIERS:
        errors.append(f'Unrecognized data connection tier "{payload.data_tier}".')
    elif payload.data_tier == "tier2" and not (payload.api_base_url.strip() and payload.api_key.strip()):
        errors.append('"Connect my existing system\'s API" requires both an API base URL and an API key.')

    departments, dept_errors, dept_warnings = _validate_departments(payload.departments)
    topics, topic_errors = _validate_topics(payload.topics)

    if "booking" in payload.enabled_features:
        errors.extend(dept_errors)
        if not departments:
            errors.append("At least one department with at least one doctor is required.")
        if not payload.portal_password.strip():
            errors.append("A bookings portal password is required.")
    if "faq" in payload.enabled_features:
        errors.extend(topic_errors)
        if not topics:
            errors.append("At least one topic with a label and an answer is required.")

    if errors:
        return JSONResponse({"errors": errors, "warnings": dept_warnings}, status_code=400)

    offsets = _parse_offsets(payload.reminder_offsets_hours)
    stored_api_base_url = payload.api_base_url.strip() or None if payload.data_tier == "tier2" else None
    stored_api_key = payload.api_key.strip() or None if payload.data_tier == "tier2" else None

    try:
        hospital = db.create_hospital(
            name=name,
            whatsapp_phone_number_id=whatsapp_phone_number_id,
            access_token=payload.access_token.strip() or None,
            app_secret=payload.app_secret.strip() or None,
            welcome_message_text=payload.welcome_message_text.strip() or None,
            reminder_offsets_hours=offsets,
            reminder_template_name=payload.reminder_template_name.strip() or None,
            data_tier=payload.data_tier,
            external_api_base_url=stored_api_base_url,
            external_api_key=stored_api_key,
            portal_password=payload.portal_password.strip() or None,
            enabled_features=payload.enabled_features,
        )
    except IntegrityError:
        return JSONResponse(
            {
                "errors": [
                    f'A hospital with WhatsApp phone_number_id "{whatsapp_phone_number_id}" already exists — '
                    "each hospital must have its own phone_number_id for message routing to work correctly."
                ]
            },
            status_code=400,
        )

    created_departments = []
    if "booking" in payload.enabled_features:
        for dept in departments:
            created_dept = db.create_department(hospital.id, dept["name"])
            created_doctors = [
                db.create_doctor(
                    hospital.id, created_dept["id"], doc["name"],
                    specialization=doc["specialization"],
                    qualification=doc["qualification"],
                    years_experience=doc["years_experience"],
                    working_days=doc["working_days"],
                    working_hours=doc["working_hours"],
                    slot_duration_minutes=doc["slot_duration_minutes"],
                    breaks=doc["breaks"],
                    max_bookings_per_slot=doc["max_bookings_per_slot"],
                    daily_booking_limit=doc["daily_booking_limit"],
                    online_quota=doc["online_quota"],
                    walkin_quota=doc["walkin_quota"],
                    followup_duration_minutes=doc["followup_duration_minutes"],
                    effective_from=doc["effective_from"],
                )
                for doc in dept["doctors"]
            ]
            created_departments.append({"name": created_dept["name"], "doctors": created_doctors})

    created_topics = []
    if "faq" in payload.enabled_features:
        created_topics = [db.create_faq_topic(hospital.id, t["topic_label"], t["answer_text"]) for t in topics]

    return JSONResponse({
        "hospital_id": hospital.id,
        "hospital_name": hospital.name,
        "whatsapp_phone_number_id": hospital.whatsapp_phone_number_id,
        "data_tier": hospital.data_tier,
        "portal_password_set": bool(hospital.portal_password_hash),
        "departments": created_departments,
        "topics": created_topics,
        "warnings": dept_warnings,
    })

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
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db.repository as db
import flows
from admin.onboarding import _VALID_TIERS
from admin.validation import _parse_offsets, _validate_doctor_fields
from db.connection import IntegrityError
from auth.google_oauth import authenticate_user
from portal.capabilities import DEFAULT_CAPABILITIES_BY_TYPE, resolve_default_capabilities
from portal.deps import get_current_super_admin
from portal.permissions import DEFAULT_PERMISSIONS_BY_ROLE, resolve_default_permissions

_VALID_TENANT_TYPES = set(DEFAULT_CAPABILITIES_BY_TYPE.keys())

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
    # RBAC (docs/rbac-redis-plan.md): replaces the old shared ADMIN_SECRET
    # check -- this is a super_admins JWT (from POST /api/admin/super/login),
    # verified via get_current_super_admin() below. Carried in the request
    # BODY rather than the Authorization header (unlike every other
    # get_current_super_admin() call site in this codebase) because this
    # endpoint's Authorization header is already spoken for by
    # authenticate_user() below -- the separate Google-account identity used
    # to link the new hospital's owner (hospital_users), a completely
    # different concern from "is this caller allowed to onboard a hospital
    # at all." One header can't carry two independent Bearer credentials at
    # once, so the super-admin token travels in the body here instead; every
    # OTHER super-admin-gated route (admin/tenants_api.py,
    # admin/platform_settings_api.py) has no such conflict and uses the
    # header normally.
    super_admin_token: str = ""
    name: str = ""
    whatsapp_phone_number_id: str = ""
    access_token: str = ""
    app_secret: str = ""
    welcome_message_text: str = ""
    reminder_offsets_hours: str = "24"
    reminder_template_name: str = ""
    portal_password: str = ""
    # RBAC: the new hospital's first staff_users admin row -- replaces
    # portal_password as the actual login going forward (portal_password is
    # still accepted/stored above during the migration window, per the
    # plan's dual-path rollout, but a NEW hospital's real login is this).
    admin_email: str = ""
    admin_password: str = ""
    enabled_features: list[str] = Field(default_factory=list)
    data_tier: str = "tier1"
    api_base_url: str = ""
    api_key: str = ""
    departments: list[DepartmentIn] = Field(default_factory=list)
    topics: list[TopicIn] = Field(default_factory=list)
    # Tenant-type-driven capability gating (tenant-capability-gating-plan.md):
    # defaults to "hospital" for backward compatibility -- every existing
    # onboarding caller that doesn't know about this field yet keeps getting
    # full admin capabilities, unchanged.
    tenant_type: str = "hospital"


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
async def submit_onboarding(
    payload: OnboardingSubmission, request: Request, authorization: str | None = Header(default=None)
):
    # Section 15: two independent gates, not one replacing the other -- a
    # super-admin identity stays required deliberately (this product isn't
    # open to public self-serve signup yet, only the two tenants actually
    # running today), while Google sign-in adds the real per-user identity
    # that alone never gave us (every prior onboarding was anonymous past
    # the old shared ADMIN_SECRET). Once public signup is ready, the
    # super-admin check below is the one block to remove. RBAC
    # (docs/rbac-redis-plan.md): the super-admin token travels in
    # payload.super_admin_token, not this Authorization header -- see
    # OnboardingSubmission's own field docstring for why.
    user = authenticate_user(authorization)
    if user is None:
        return JSONResponse({"errors": ["You must be signed in with Google to onboard a hospital."]}, status_code=401)
    if get_current_super_admin(f"Bearer {payload.super_admin_token}") is None:
        return JSONResponse({"errors": ["Not authenticated as a super admin."]}, status_code=403)

    name = payload.name.strip()
    whatsapp_phone_number_id = payload.whatsapp_phone_number_id.strip()
    admin_email = payload.admin_email.strip()
    errors: list[str] = []
    if not name:
        errors.append("Hospital name is required.")
    if not whatsapp_phone_number_id:
        errors.append("WhatsApp phone_number_id is required.")
    # RBAC: every new hospital gets its first staff_users admin row created
    # right here (below) -- this is that person's real login, so it's
    # required unconditionally, not gated on "booking" the way the legacy
    # portal_password check further down still is.
    if not admin_email or "@" not in admin_email:
        errors.append("A valid admin email address is required.")
    if not payload.admin_password.strip():
        errors.append("An admin password is required.")

    unknown_features = [f for f in payload.enabled_features if f not in flows.ALL_FEATURES]
    if unknown_features:
        errors.append(f'Unrecognized patient-experience option(s): {", ".join(unknown_features)}.')
    if not payload.enabled_features:
        errors.append("At least one patient-experience option is required.")

    if payload.data_tier not in _VALID_TIERS:
        errors.append(f'Unrecognized data connection tier "{payload.data_tier}".')
    elif payload.data_tier == "tier2" and not (payload.api_base_url.strip() and payload.api_key.strip()):
        errors.append('"Connect my existing system\'s API" requires both an API base URL and an API key.')

    if payload.tenant_type not in _VALID_TENANT_TYPES:
        errors.append(f'Unrecognized tenant type "{payload.tenant_type}".')

    departments, dept_errors, dept_warnings = _validate_departments(payload.departments)
    topics, topic_errors = _validate_topics(payload.topics)

    if "booking" in payload.enabled_features:
        errors.extend(dept_errors)
        if not departments:
            errors.append("At least one department with at least one doctor is required.")
        # RBAC (docs/rbac-redis-plan.md): a bookings portal password is no
        # longer required here -- admin_email/admin_password (validated
        # above) is this hospital's real login going forward. portal_password
        # stays ACCEPTED (below) for anyone who still submits one, but a new
        # hospital onboarded today never needs it.
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
            tenant_type=payload.tenant_type,
            admin_capabilities=resolve_default_capabilities(payload.tenant_type),
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

    db.link_hospital_owner(hospital.id, user.id)

    # RBAC (docs/rbac-redis-plan.md): this hospital's first staff_users
    # admin row + the default role_permissions matrix, seeded explicitly
    # right here -- same "write it now, don't rely on a runtime fallback"
    # discipline resolve_default_capabilities()/admin_capabilities already
    # established just above. A brand-new hospital_id can never already have
    # rows, so there's nothing to conflict with; create_staff_user()'s own
    # IntegrityError path (a duplicate email) is intentionally NOT caught
    # here -- it propagates as a 500, since a duplicate admin_email at this
    # point (globally unique across every hospital, ux_staff_users_email)
    # means someone already used this email as staff somewhere else, which
    # this wizard's own field validation above doesn't check for and isn't
    # expected to hit in practice (an operator-run onboarding flow, not
    # self-serve signup).
    db.create_staff_user(
        hospital.id, role="admin", email=admin_email,
        password_hash=db.hash_portal_password(payload.admin_password.strip()), name=f"{name} Admin",
    )
    db.seed_default_role_permissions(hospital.id, [
        {"role": role, "page_key": page_key, "can_view": actions["view"], "can_write": actions["write"], "can_delete": actions["delete"]}
        for role in DEFAULT_PERMISSIONS_BY_ROLE
        for page_key, actions in resolve_default_permissions(role).items()
    ])

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
        "admin_email": admin_email,
        "departments": created_departments,
        "topics": created_topics,
        "warnings": dept_warnings,
    })

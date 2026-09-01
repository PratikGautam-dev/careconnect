# admin/tenants_api.py
"""
JSON API for the Next.js platform-admin tenant pages
(frontend/src/app/admin/tenants, frontend/src/app/admin/edit-tenant) --
lists every onboarded hospital and lets an operator correct one, mirroring
admin/onboarding.py's server-rendered /admin/tenants and /admin/edit-tenant
routes but as JSON, reusing that module's exact validation/masking helpers
and db/repository.py's update_hospital() rather than duplicating them.

RBAC (docs/rbac-redis-plan.md): gated by get_current_super_admin() -- an
individual super_admins account's JWT, replacing the shared
TENANTS_ADMIN_SECRET/X-Admin-Secret header this file used before. Every
route below still re-verifies on every request (never trusted from
client-side "logged in" state), same "basic protection, not
production-grade auth" posture as before, just with a real per-operator
identity backing it now, which is what makes _tenant_update's own audit-log
call sites able to record WHO made a change instead of the literal string
"platform admin"."""
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db.repository as db
from admin.onboarding import _VALID_TIERS, _mask_secret
from admin.validation import _parse_offsets
from core.translations import t
from db.connection import IntegrityError
from flows import _FEATURE_MENU, REAL_FEATURES
from portal.capabilities import ALL_CAPABILITIES, DEFAULT_CAPABILITIES_BY_TYPE, get_capabilities
from portal.deps import get_current_super_admin
from webhook.dispatch import invalidate_whatsapp_client

_VALID_TENANT_TYPES = set(DEFAULT_CAPABILITIES_BY_TYPE.keys())

router = APIRouter()


def _actor_label(super_admin: dict) -> str:
    """audit_logs.actor_label real-identity population (docs/rbac-redis-plan.md's
    "Existing schema changes" note) -- now that platform-admin actions carry
    a real super_admins row, replaces the old literal "platform admin"
    string every call site in this file used to pass."""
    return f'{super_admin["name"]} <{super_admin["email"]}>'


def _tenant_summary(h) -> dict:
    return {
        "id": h.id,
        "name": h.name,
        "whatsapp_phone_number_id": h.whatsapp_phone_number_id,
        "data_tier": h.data_tier,
        "is_active": h.is_active,
    }


def _tenant_detail(h) -> dict:
    return {
        "id": h.id,
        "name": h.name,
        "whatsapp_phone_number_id": h.whatsapp_phone_number_id,
        "access_token_masked": _mask_secret(h.access_token),
        "app_secret_masked": _mask_secret(h.app_secret),
        "welcome_message_text": h.welcome_message_text or "",
        "reminder_offsets_hours": ",".join(str(o) for o in h.reminder_offsets_hours),
        "reminder_template_name": h.reminder_template_name or "",
        "data_tier": h.data_tier,
        "external_api_base_url": h.external_api_base_url or "",
        "external_api_key": h.external_api_key or "",
        "has_portal_password": bool(h.portal_password_hash),
        "is_active": h.is_active,
        # Section 15: which Google account(s), if any, own this hospital's
        # portal -- empty for hospitals onboarded before Google sign-in
        # existed (hospital #1, DaaPrime), which still fall back to
        # portal_password_hash login until an owner is assigned below.
        "owners": [{"id": u.id, "email": u.email, "name": u.name} for u in db.get_owners_for_hospital(h.id)],
        # Feature-toggle follow-up (Spec.md Section 0): enabled_features was
        # only ever SET once, at onboarding -- confirmed there was no way
        # anywhere in this app to turn a feature on/off for an
        # already-onboarded tenant afterward (portal/routes/settings.py's own settings
        # endpoint deliberately never touches it, grouping it with
        # credentials as operator-only). This is the fix -- an operator can
        # now toggle any REAL_FEATURES key here. feature_default_labels
        # mirrors portal/routes/settings.py's own settings endpoint, for a readable
        # checklist label per key.
        "enabled_features": h.enabled_features,
        "feature_default_labels": {key: t(f"feature_{key}", "en") for key in REAL_FEATURES},
        # Tenant-type-driven capability gating (tenant-capability-gating-plan.md):
        # get_capabilities() resolves the type default whenever
        # admin_capabilities is unset (None), so this always reflects the
        # EFFECTIVE set, not just whatever's literally in the column --
        # tenant_type is shown alongside it so an operator can tell whether
        # what they're looking at is an explicit override or the default.
        "tenant_type": h.tenant_type,
        "admin_capabilities": sorted(get_capabilities(h)),
        "all_capabilities": sorted(ALL_CAPABILITIES),
        # Lets the edit-tenant frontend offer a "reset to {type} defaults"
        # action when the operator flips tenant_type, instead of leaving the
        # capability checkboxes stale until manually rechecked (the map
        # itself is the same one resolve_default_capabilities()/
        # get_capabilities() already use, just shaped for the frontend to
        # read rather than hardcoding a second copy of it in TypeScript).
        "default_capabilities_by_type": {
            k: sorted(v) for k, v in DEFAULT_CAPABILITIES_BY_TYPE.items()
        },
        # Appointment-type allow-list (edit-tenant page): which of the fixed
        # catalog this tenant is whitelisted for at all, separate from
        # admin_capabilities' "manage_appointment_types" (which only gates
        # whether portal staff can toggle is_active WITHIN this whitelist).
        # is_active is included too so the operator can see whether a
        # currently-active type would be turned off by revoking it.
        "appointment_types": db.get_all_appointment_types_for_hospital(h.id),
    }


@router.get("/api/admin/tenants")
async def list_tenants(request: Request, authorization: str | None = Header(default=None)):
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    hospitals = db.get_all_hospitals()
    return JSONResponse({"tenants": [_tenant_summary(h) for h in hospitals]})


@router.get("/api/admin/stalled-signups")
async def list_stalled_signups(request: Request, authorization: str | None = Header(default=None)):
    """Item 5 (Spec.md Section 0): who's signed in with Google but never
    finished onboarding a hospital -- db.get_users_without_hospital() is
    already the correct query (a user row with zero hospital_users links),
    this just exposes it to the platform-admin frontend."""
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    users = db.get_users_without_hospital()
    return JSONResponse({
        "users": [{"id": u.id, "email": u.email, "name": u.name, "created_at": u.created_at} for u in users],
    })


@router.get("/api/admin/stats/total-bookings")
async def get_total_bookings_stat(request: Request, authorization: str | None = Header(default=None)):
    """Item 7 (Spec.md Section 0): platform-wide lifetime "how many times has
    this application been used for booking" -- every appointments row ever
    inserted, across every hospital, regardless of current status or later
    soft-deletion (db.get_total_bookings_count()'s own docstring has the
    full definition). Deliberately NOT the attended-status count from the
    earlier no-show work -- a separate metric entirely."""
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({"total_bookings": db.get_total_bookings_count()})


@router.get("/api/admin/tenants/{tenant_id}")
async def get_tenant(tenant_id: int, request: Request, authorization: str | None = Header(default=None)):
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    hospital = db.get_hospital(tenant_id)
    if hospital is None:
        return JSONResponse({"error": f"No tenant with id {tenant_id}."}, status_code=404)
    return JSONResponse({"tenant": _tenant_detail(hospital)})


class TenantUpdatePayload(BaseModel):
    name: str = ""
    whatsapp_phone_number_id: str = ""
    access_token: str = ""  # blank = keep current
    app_secret: str = ""  # blank = keep current
    welcome_message_text: str = ""
    reminder_offsets_hours: str = ""
    reminder_template_name: str = ""
    portal_password: str = ""  # blank = keep current
    data_tier: str = "tier1"
    api_base_url: str = ""
    api_key: str = ""
    enabled_features: list[str] = []
    # Tenant-type-driven capability gating (tenant-capability-gating-plan.md).
    tenant_type: str = "hospital"
    admin_capabilities: list[str] = []


@router.post("/api/admin/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int, payload: TenantUpdatePayload, request: Request, authorization: str | None = Header(default=None)
):
    super_admin = get_current_super_admin(authorization)
    if super_admin is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    hospital = db.get_hospital(tenant_id)
    if hospital is None:
        return JSONResponse({"error": f"No tenant with id {tenant_id}."}, status_code=404)

    errors: list[str] = []
    name = payload.name.strip()
    whatsapp_phone_number_id = payload.whatsapp_phone_number_id.strip()
    if not name:
        errors.append("Hospital name is required.")
    if not whatsapp_phone_number_id:
        errors.append("WhatsApp phone_number_id is required.")
    if payload.data_tier not in _VALID_TIERS:
        errors.append(f'Unrecognized data connection tier "{payload.data_tier}".')
    elif payload.data_tier == "tier2" and not (payload.api_base_url.strip() and payload.api_key.strip()):
        errors.append('"Connect my existing system\'s API" requires both an API base URL and an API key.')

    # Tenant-type-driven capability gating: "omitted" (any caller predating
    # these two fields) keeps both current values unchanged -- same
    # model_fields_set-based distinction enabled_features already uses just
    # below, for the same "an explicit [] is a deliberate choice, not the
    # same as not sending the field" reason.
    tenant_type = payload.tenant_type if "tenant_type" in payload.model_fields_set else hospital.tenant_type
    if tenant_type not in _VALID_TENANT_TYPES:
        errors.append(f'Unrecognized tenant type "{tenant_type}".')

    if errors:
        return JSONResponse({"errors": errors}, status_code=400)

    if "admin_capabilities" in payload.model_fields_set:
        admin_capabilities = [c for c in payload.admin_capabilities if c in ALL_CAPABILITIES]
    else:
        admin_capabilities = hospital.admin_capabilities

    # "Omitted from the request body" (any caller that predates this field,
    # or a partial direct API call) keeps the CURRENT value unchanged --
    # same "don't silently clobber a field this request didn't mean to
    # touch" rule every other field on this endpoint already follows
    # (blank token/secret/password = keep current). Checked via
    # model_fields_set, not `payload.enabled_features` being falsy, since an
    # explicit [] (every checkbox unticked) is a real, deliberate "disable
    # everything" and must NOT be treated the same as "field not sent."
    # Whichever value is used, filtered/reordered against _FEATURE_MENU's
    # own fixed display order (a plain set has none) and REAL_FEATURES (the
    # same "silently drop a stray/typo'd key" rule portal/routes/settings.py's own
    # feature_labels validation already uses) so re-saving never scrambles
    # the order the WhatsApp menu actually renders features in.
    if "enabled_features" in payload.model_fields_set:
        submitted = set(payload.enabled_features)
    else:
        submitted = set(hospital.enabled_features)
    enabled_features = [key for key in _FEATURE_MENU if key in submitted and key in REAL_FEATURES]

    offsets = _parse_offsets(payload.reminder_offsets_hours)
    stored_api_base_url = payload.api_base_url.strip() or None if payload.data_tier == "tier2" else None
    stored_api_key = payload.api_key.strip() or None if payload.data_tier == "tier2" else None

    # Blank token/secret/password fields mean "keep the current value" -- the
    # edit form never receives the real secret back from the API (only a
    # masked hint), so a blank submission is the normal case, not an
    # explicit request to erase it. Exact same rule admin/onboarding.py's
    # HTML edit-tenant route already uses.
    new_access_token = payload.access_token.strip() or hospital.access_token
    new_app_secret = payload.app_secret.strip() or hospital.app_secret
    new_portal_password_hash = (
        db.hash_portal_password(payload.portal_password.strip())
        if payload.portal_password.strip()
        else hospital.portal_password_hash
    )

    try:
        updated = db.update_hospital(
            tenant_id,
            name=name,
            whatsapp_phone_number_id=whatsapp_phone_number_id,
            access_token=new_access_token,
            app_secret=new_app_secret,
            timezone=hospital.timezone,
            welcome_message_text=payload.welcome_message_text.strip() or None,
            reminder_offsets_hours=offsets,
            reminder_template_name=payload.reminder_template_name.strip() or None,
            data_tier=payload.data_tier,
            external_api_base_url=stored_api_base_url,
            external_api_key=stored_api_key,
            portal_password_hash=new_portal_password_hash,
            enabled_features=enabled_features,
            feature_labels=hospital.feature_labels,
            closing_message_text=hospital.closing_message_text,
            business_hours_text=hospital.business_hours_text,
            default_language=hospital.default_language,
            language_prompt_enabled=hospital.language_prompt_enabled,
            session_timeout_minutes=hospital.session_timeout_minutes,
            require_patient_confirmation=hospital.require_patient_confirmation,
            privacy_notice_text=hospital.privacy_notice_text,
            tenant_type=tenant_type,
            admin_capabilities=admin_capabilities,
            dpdp_consent_required=hospital.dpdp_consent_required,
        )
    except IntegrityError:
        return JSONResponse({
            "errors": [
                f'A hospital with WhatsApp phone_number_id "{whatsapp_phone_number_id}" already exists — '
                "each hospital must have its own phone_number_id for message routing to work correctly."
            ]
        }, status_code=400)

    # webhook/dispatch.py caches one WhatsAppClient per hospital for the life
    # of the process, built from whatsapp_phone_number_id+access_token --
    # without this, a token rotation (or a phone_number_id change) saved here
    # wouldn't take effect until the process happened to restart (see that
    # cache's own module-level comment). Only these two fields matter to it;
    # everything else this route can change (name, features, offsets, ...) is
    # read fresh from the DB on every message already.
    if new_access_token != hospital.access_token or whatsapp_phone_number_id != hospital.whatsapp_phone_number_id:
        invalidate_whatsapp_client(tenant_id)

    # Audit trail (tenant-capability-gating-plan.md's follow-up): only the
    # access/billing-relevant fields that actually changed, not the full
    # before/after row (name/phone_number_id churn isn't interesting; secrets
    # are handled by db.repositories.audit_logs' own redaction regardless of
    # whether they show up here). One entry per PATCH call, not one per
    # field, so an operator's single "edit this tenant" action reads back as
    # one event.
    _audit_fields = {
        "name": (hospital.name, name),
        "data_tier": (hospital.data_tier, payload.data_tier),
        "tenant_type": (hospital.tenant_type, tenant_type),
        "admin_capabilities": (sorted(get_capabilities(hospital)), sorted(admin_capabilities or [])),
        "enabled_features": (hospital.enabled_features, enabled_features),
    }
    changed = {k: (old, new) for k, (old, new) in _audit_fields.items() if old != new}
    if changed:
        db.record_audit_log(
            "platform_admin", tenant_id, _actor_label(super_admin), "tenant.update",
            entity_type="hospital", entity_id=str(tenant_id),
            before={k: old for k, (old, new) in changed.items()},
            after={k: new for k, (old, new) in changed.items()},
        )

    return JSONResponse({"tenant": _tenant_detail(updated)})


class AssignOwnerPayload(BaseModel):
    email: str = ""


@router.post("/api/admin/tenants/{tenant_id}/assign-owner")
async def assign_tenant_owner(
    tenant_id: int, payload: AssignOwnerPayload, request: Request, authorization: str | None = Header(default=None)
):
    """Section 15's migration tool for hospitals onboarded before Google
    sign-in existed (hospital #1, DaaPrime): links a hospital to a Google
    account by email alone, without that person needing to have signed in
    yet -- db.assign_hospital_owner_by_email() creates a placeholder users
    row (google_id NULL) if none exists for that email, and the OAuth
    callback (user_auth.py) backfills google_id the first time that person
    actually signs in with a matching Google account. Doubles as the
    general "reassign ownership" tool going forward, not just a one-off
    script -- a hospital can have more than one owner (hospital_users is a
    join table), so calling this again for a second email just adds another
    owner rather than replacing the first."""
    super_admin = get_current_super_admin(authorization)
    if super_admin is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    hospital = db.get_hospital(tenant_id)
    if hospital is None:
        return JSONResponse({"error": f"No tenant with id {tenant_id}."}, status_code=404)

    email = payload.email.strip().lower()
    if not email or "@" not in email:
        return JSONResponse({"error": "A valid email address is required."}, status_code=400)

    owner = db.assign_hospital_owner_by_email(tenant_id, email)
    db.record_audit_log(
        "platform_admin", tenant_id, _actor_label(super_admin), "tenant.assign_owner",
        entity_type="hospital_owner", entity_id=str(owner.id), after={"email": email},
    )
    return JSONResponse({"tenant": _tenant_detail(hospital), "owner": {"id": owner.id, "email": owner.email}})


class AppointmentTypeAllowedPayload(BaseModel):
    is_allowed: bool = True


@router.post("/api/admin/tenants/{tenant_id}/appointment-types/{appointment_type_id}/allowed")
async def set_tenant_appointment_type_allowed(
    tenant_id: int, appointment_type_id: str, payload: AppointmentTypeAllowedPayload,
    request: Request, authorization: str | None = Header(default=None),
):
    """The platform-admin half of the appointment-type allow-list: which
    types a tenant may use at all (edit-tenant page's new "Appointment
    types" section). Turning one off also forces is_active=False for it
    (db.set_appointment_type_allowed()'s own docstring), so the tenant's own
    portal toggle (portal/routes/appointment_types.py) never has to
    reconcile a type that's active but no longer allowed."""
    super_admin = get_current_super_admin(authorization)
    if super_admin is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    hospital = db.get_hospital(tenant_id)
    if hospital is None:
        return JSONResponse({"error": f"No tenant with id {tenant_id}."}, status_code=404)

    updated = db.set_appointment_type_allowed(tenant_id, appointment_type_id, payload.is_allowed)
    if updated is None:
        return JSONResponse({"error": "No such appointment type."}, status_code=404)

    db.record_audit_log(
        "platform_admin", tenant_id, _actor_label(super_admin), "appointment_type.allow",
        entity_type="appointment_type", entity_id=appointment_type_id,
        after={"is_allowed": payload.is_allowed},
    )
    return JSONResponse({"appointment_type": updated})


@router.get("/api/admin/tenants/{tenant_id}/audit-log")
async def get_tenant_audit_log(
    tenant_id: int, request: Request, authorization: str | None = Header(default=None)
):
    """Platform-admin view of both audit levels for one tenant -- the portal-
    facing GET /api/portal/audit-log (portal/routes/settings.py) only ever
    shows that tenant's own 'portal'-level rows, never platform_admin ones
    (data_tier/API-key changes are operator-only concerns), so this is the
    only place both levels for a tenant are visible together."""
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_hospital(tenant_id) is None:
        return JSONResponse({"error": f"No tenant with id {tenant_id}."}, status_code=404)
    return JSONResponse({"entries": db.get_audit_logs(hospital_id=tenant_id)})


@router.get("/api/admin/audit-log")
async def get_platform_audit_log(
    request: Request,
    authorization: str | None = Header(default=None),
    hospital_id: int | None = None,
    actor_level: str | None = None,
):
    """Cross-tenant view -- unlike the per-tenant route above (only useful
    once you're already looking at one tenant), this is the "what's
    happening across the whole platform" view, so a platform admin doesn't
    have to open every tenant's edit page one at a time to spot activity.
    Optional hospital_id/actor_level query params narrow it down to what the
    per-tenant route already shows, for a "view this tenant's history from
    here" link back out of this page. Enriches each entry with hospital_name
    (a lookup dict built once, not a query per row) since these entries span
    tenants and an id alone isn't identifying enough here the way it is on
    the single-tenant route."""
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if actor_level is not None and actor_level not in ("platform_admin", "portal"):
        return JSONResponse({"error": f'Unrecognized actor_level "{actor_level}".'}, status_code=400)

    entries = db.get_audit_logs(hospital_id=hospital_id, actor_level=actor_level, limit=200)
    hospital_names = {h.id: h.name for h in db.get_all_hospitals()}
    for entry in entries:
        entry["hospital_name"] = hospital_names.get(entry["hospital_id"])
    return JSONResponse({"entries": entries})

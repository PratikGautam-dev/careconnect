# admin/tenants_api.py
"""
JSON API for the Next.js platform-admin tenant pages
(frontend/src/app/admin/tenants, frontend/src/app/admin/edit-tenant) --
lists every onboarded hospital and lets an operator correct one, mirroring
admin/onboarding.py's server-rendered /admin/tenants and /admin/edit-tenant
routes but as JSON, reusing that module's exact validation/masking helpers
and db/repository.py's update_hospital() rather than duplicating them.

Gated by TENANTS_ADMIN_SECRET, deliberately a DIFFERENT secret from
ADMIN_SECRET (which only gates *creating* a new hospital via the onboarding
wizard) -- this surface shows and can change every already-onboarded
tenant's stored credentials, a strictly higher-blast-radius operation, so it
doesn't share a credential with the lower-stakes one. Checked on every
request via an X-Admin-Secret header, re-validated server-side each time
(never trusted from client-side "logged in" state) -- same "basic
protection, not production-grade auth" posture as every other shared-secret
gate in this project.
"""
import hmac
import os

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import core.rate_limit as rate_limit
import db.repository as db
from admin.onboarding import _VALID_TIERS, _mask_secret, _parse_offsets
from core.translations import t
from db.connection import IntegrityError
from flows import _FEATURE_MENU, REAL_FEATURES

router = APIRouter()

TENANTS_ADMIN_SECRET = os.environ.get("TENANTS_ADMIN_SECRET", "")


def _check_secret(x_admin_secret: str | None, request: Request) -> bool:
    """Timing-safe (hmac.compare_digest, not a plain ==) and rate-limited
    (audit follow-up, Spec.md Section 0) -- this single secret gates every
    endpoint in this file, so the lockout is checked/recorded here once
    rather than duplicated per route."""
    key = rate_limit.client_key("tenants_admin_secret", request)
    if rate_limit.is_locked_out(key):
        return False
    ok = bool(TENANTS_ADMIN_SECRET) and hmac.compare_digest(x_admin_secret or "", TENANTS_ADMIN_SECRET)
    if ok:
        rate_limit.reset(key)
    else:
        rate_limit.record_failure(key)
    return ok


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
        # already-onboarded tenant afterward (portal_api.py's own settings
        # endpoint deliberately never touches it, grouping it with
        # credentials as operator-only). This is the fix -- an operator can
        # now toggle any REAL_FEATURES key here. feature_default_labels
        # mirrors portal_api.py's own settings endpoint, for a readable
        # checklist label per key.
        "enabled_features": h.enabled_features,
        "feature_default_labels": {key: t(f"feature_{key}", "en") for key in REAL_FEATURES},
    }


@router.post("/api/admin/tenants/login")
async def tenants_login(payload: dict, request: Request):
    if rate_limit.is_locked_out(rate_limit.client_key("tenants_admin_secret", request)):
        return JSONResponse(
            {"error": "Too many attempts. Please wait a while before trying again."}, status_code=429
        )
    secret = (payload or {}).get("secret", "")
    if not _check_secret(secret, request):
        return JSONResponse({"error": "Incorrect admin secret."}, status_code=403)
    return JSONResponse({"ok": True})


@router.get("/api/admin/tenants")
async def list_tenants(request: Request, x_admin_secret: str | None = Header(default=None)):
    if not _check_secret(x_admin_secret, request):
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    hospitals = db.get_all_hospitals()
    return JSONResponse({"tenants": [_tenant_summary(h) for h in hospitals]})


@router.get("/api/admin/stalled-signups")
async def list_stalled_signups(request: Request, x_admin_secret: str | None = Header(default=None)):
    """Item 5 (Spec.md Section 0): who's signed in with Google but never
    finished onboarding a hospital -- db.get_users_without_hospital() is
    already the correct query (a user row with zero hospital_users links),
    this just exposes it to the platform-admin frontend."""
    if not _check_secret(x_admin_secret, request):
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    users = db.get_users_without_hospital()
    return JSONResponse({
        "users": [{"id": u.id, "email": u.email, "name": u.name, "created_at": u.created_at} for u in users],
    })


@router.get("/api/admin/stats/total-bookings")
async def get_total_bookings_stat(request: Request, x_admin_secret: str | None = Header(default=None)):
    """Item 7 (Spec.md Section 0): platform-wide lifetime "how many times has
    this application been used for booking" -- every appointments row ever
    inserted, across every hospital, regardless of current status or later
    soft-deletion (db.get_total_bookings_count()'s own docstring has the
    full definition). Deliberately NOT the attended-status count from the
    earlier no-show work -- a separate metric entirely."""
    if not _check_secret(x_admin_secret, request):
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({"total_bookings": db.get_total_bookings_count()})


@router.get("/api/admin/tenants/{tenant_id}")
async def get_tenant(tenant_id: int, request: Request, x_admin_secret: str | None = Header(default=None)):
    if not _check_secret(x_admin_secret, request):
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


@router.post("/api/admin/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int, payload: TenantUpdatePayload, request: Request, x_admin_secret: str | None = Header(default=None)
):
    if not _check_secret(x_admin_secret, request):
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

    if errors:
        return JSONResponse({"errors": errors}, status_code=400)

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
    # same "silently drop a stray/typo'd key" rule portal_api.py's own
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
        )
    except IntegrityError:
        return JSONResponse({
            "errors": [
                f'A hospital with WhatsApp phone_number_id "{whatsapp_phone_number_id}" already exists — '
                "each hospital must have its own phone_number_id for message routing to work correctly."
            ]
        }, status_code=400)

    return JSONResponse({"tenant": _tenant_detail(updated)})


class AssignOwnerPayload(BaseModel):
    email: str = ""


@router.post("/api/admin/tenants/{tenant_id}/assign-owner")
async def assign_tenant_owner(
    tenant_id: int, payload: AssignOwnerPayload, request: Request, x_admin_secret: str | None = Header(default=None)
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
    if not _check_secret(x_admin_secret, request):
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    hospital = db.get_hospital(tenant_id)
    if hospital is None:
        return JSONResponse({"error": f"No tenant with id {tenant_id}."}, status_code=404)

    email = payload.email.strip().lower()
    if not email or "@" not in email:
        return JSONResponse({"error": "A valid email address is required."}, status_code=400)

    owner = db.assign_hospital_owner_by_email(tenant_id, email)
    return JSONResponse({"tenant": _tenant_detail(hospital), "owner": {"id": owner.id, "email": owner.email}})

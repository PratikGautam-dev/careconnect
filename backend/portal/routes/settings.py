from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from admin.validation import _parse_offsets
import db.repository as db
from core.translations import SUPPORTED_LANGUAGES
from db.repositories.handoffs import DEFAULT_HANDOFF_AUTO_RESOLVE_HOURS
from db.repositories.hospital_settings import DEFAULT_FOLLOWUP_VALIDITY_DAYS
from modules.google_calendar import is_calendar_integration_configured
from portal.deps import _authenticate, get_current_staff, require_capability, require_permission

router = APIRouter()

# Section 12.13: minutes bounds mirror db/schema.sql's session_timeout_minutes
# CHECK constraint exactly -- validated here too so a bad value gets a clear
# 400 from this endpoint instead of surfacing as a raw IntegrityError from
# the DB constraint.
_MIN_SESSION_TIMEOUT_MINUTES = 2
_MAX_SESSION_TIMEOUT_MINUTES = 120

# Messages page follow-up: bounds for hospitals.handoff_auto_resolve_hours,
# same "validate here for a clean 400" reasoning as the session-timeout
# bounds above. 1 hour minimum (shorter would risk auto-resolving a handoff
# staff simply hasn't gotten to yet within a normal shift), 1 week maximum
# (longer defeats the point of "don't leave it open indefinitely").
_MIN_HANDOFF_AUTO_RESOLVE_HOURS = 1
_MAX_HANDOFF_AUTO_RESOLVE_HOURS = 168

# Follow-up eligibility window (docs/per-appointment-type-flow-plan.md Phase 2
# Step 2 follow-up): same "validate here for a clean 400" reasoning as the
# bounds above. 1 day minimum (0 would mean no follow-up is ever eligible);
# 365 maximum is a generous ceiling against a fat-fingered entry.
_MIN_FOLLOWUP_VALIDITY_DAYS = 1
_MAX_FOLLOWUP_VALIDITY_DAYS = 365
# Fee ceiling is just a fat-finger guard (₹1,000,000), not a considered
# product limit -- consultation fees are always non-negative (DB CHECK
# constraint already enforces that floor).
_MAX_FEE = 1_000_000


@router.get("/api/portal/settings")
async def portal_get_settings(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    hospital_settings = db.get_hospital_settings(hospital.id)
    return JSONResponse(
        {
            "name": hospital.name,
            "welcome_message_text": hospital.welcome_message_text or "",
            "reminder_offsets_hours": ",".join(str(h) for h in hospital.reminder_offsets_hours),
            "reminder_template_name": hospital.reminder_template_name or "",
            # Section 12.13: self-serve bot customization.
            "enabled_features": hospital.enabled_features,
            "closing_message_text": hospital.closing_message_text or "",
            "business_hours_text": hospital.business_hours_text or "",
            "default_language": hospital.default_language,
            "language_prompt_enabled": hospital.language_prompt_enabled,
            "session_timeout_minutes": hospital.session_timeout_minutes or 30,
            "handoff_auto_resolve_hours": hospital.handoff_auto_resolve_hours or DEFAULT_HANDOFF_AUTO_RESOLVE_HOURS,
            # CareConnect architecture doc alignment (Spec.md Section 0):
            # unlike enabled_features (operator-only, /admin/edit-tenant),
            # these two ARE genuine self-serve bot customization -- same
            # category as closing_message_text/business_hours_text above.
            "require_patient_confirmation": hospital.require_patient_confirmation,
            "privacy_notice_text": hospital.privacy_notice_text or "",
            # docs/per-appointment-type-flow-plan.md Phase 2 Step 2 follow-up:
            # per-hospital Follow-up settings (db/repositories/hospital_settings.py),
            # not columns on `hospitals` itself.
            "followup_validity_days": hospital_settings["followup_validity_days"] or DEFAULT_FOLLOWUP_VALIDITY_DAYS,
            "followup_fee": hospital_settings["followup_fee"],
            "new_consultation_fee": hospital_settings["new_consultation_fee"],
            # Lab Test Phase 2 follow-up: flat fee added to a home-collection
            # Lab Test booking's price review.
            "home_collection_charge": hospital_settings["home_collection_charge"],
        },
        # Settings-not-updating bug follow-up (Spec.md Section 0): defensive
        # -- rules out any browser/CDN-level HTTP caching of this
        # authenticated GET as a contributing cause, even though the
        # in-process reproduction found the real bug was the frontend
        # trusting its own stale optimistic state after a save, not caching.
        headers={"Cache-Control": "no-store"},
    )


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

    handoff_hours_raw = payload.get("handoff_auto_resolve_hours")
    if handoff_hours_raw in (None, ""):
        handoff_auto_resolve_hours = None
    else:
        try:
            handoff_auto_resolve_hours = int(handoff_hours_raw)
        except (TypeError, ValueError):
            return JSONResponse({"error": "handoff_auto_resolve_hours must be a whole number of hours."}, status_code=400)
        if not (_MIN_HANDOFF_AUTO_RESOLVE_HOURS <= handoff_auto_resolve_hours <= _MAX_HANDOFF_AUTO_RESOLVE_HOURS):
            return JSONResponse({
                "error": f"handoff_auto_resolve_hours must be between {_MIN_HANDOFF_AUTO_RESOLVE_HOURS} and {_MAX_HANDOFF_AUTO_RESOLVE_HOURS}.",
            }, status_code=400)

    followup_days_raw = payload.get("followup_validity_days")
    if followup_days_raw in (None, ""):
        followup_validity_days = None
    else:
        try:
            followup_validity_days = int(followup_days_raw)
        except (TypeError, ValueError):
            return JSONResponse({"error": "followup_validity_days must be a whole number of days."}, status_code=400)
        if not (_MIN_FOLLOWUP_VALIDITY_DAYS <= followup_validity_days <= _MAX_FOLLOWUP_VALIDITY_DAYS):
            return JSONResponse({
                "error": f"followup_validity_days must be between {_MIN_FOLLOWUP_VALIDITY_DAYS} and {_MAX_FOLLOWUP_VALIDITY_DAYS}.",
            }, status_code=400)

    def _parse_fee(raw, field_name):
        if raw in (None, ""):
            return None, None
        try:
            fee = float(raw)
        except (TypeError, ValueError):
            return None, JSONResponse({"error": f"{field_name} must be a number."}, status_code=400)
        if not (0 <= fee <= _MAX_FEE):
            return None, JSONResponse({"error": f"{field_name} must be between 0 and {_MAX_FEE}."}, status_code=400)
        return fee, None

    followup_fee, error = _parse_fee(payload.get("followup_fee"), "followup_fee")
    if error:
        return error
    new_consultation_fee, error = _parse_fee(payload.get("new_consultation_fee"), "new_consultation_fee")
    if error:
        return error
    home_collection_charge, error = _parse_fee(payload.get("home_collection_charge"), "home_collection_charge")
    if error:
        return error

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
        # Migration 0014: feature_labels is no longer a per-hospital,
        # self-serve setting (moved to platform_settings, see that
        # migration's docstring) -- passed through unchanged, same
        # "operator-only, never touched here" discipline as enabled_features
        # above.
        feature_labels=hospital.feature_labels,
        closing_message_text=(payload.get("closing_message_text") or "").strip() or None,
        business_hours_text=(payload.get("business_hours_text") or "").strip() or None,
        default_language=default_language,
        language_prompt_enabled=bool(payload.get("language_prompt_enabled", True)),
        session_timeout_minutes=session_timeout_minutes,
        handoff_auto_resolve_hours=handoff_auto_resolve_hours,
        require_patient_confirmation=bool(payload.get("require_patient_confirmation", False)),
        privacy_notice_text=(payload.get("privacy_notice_text") or "").strip() or None,
        # Tenant-type-driven capability gating (tenant-capability-gating-plan.md):
        # not self-serve -- passed straight through unchanged, same
        # discipline every other operator-only field on this call already
        # follows (enabled_features, portal_password_hash, ...). Only
        # admin/tenants_api.py's tenant-edit endpoint actually changes these.
        tenant_type=hospital.tenant_type,
        admin_capabilities=hospital.admin_capabilities,
        # Migration 0014: same "moved to platform_settings, pass through
        # unchanged" treatment as feature_labels above.
        dpdp_consent_required=hospital.dpdp_consent_required,
    )
    db.update_hospital_settings(
        hospital.id, followup_validity_days=followup_validity_days,
        followup_fee=followup_fee, new_consultation_fee=new_consultation_fee,
        home_collection_charge=home_collection_charge,
    )
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "settings.update",
        entity_type="hospital", entity_id=str(hospital.id),
        before={"default_language": hospital.default_language, "session_timeout_minutes": hospital.session_timeout_minutes},
        after={"default_language": default_language, "session_timeout_minutes": session_timeout_minutes},
    )
    return JSONResponse({"ok": True})


@router.get("/api/portal/audit-log")
async def portal_audit_log(authorization: str | None = Header(default=None)):
    """This tenant's own 'portal'-level audit rows only -- never
    'platform_admin' rows (data_tier/API-key/tenant_type changes stay
    operator-only, visible through admin/tenants_api.py's own audit-log
    route instead). Gated by manage_settings, same capability that already
    gates this file's own settings-update route, rather than inventing a
    new one just for reading history."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_settings")
    if forbidden:
        return forbidden
    return JSONResponse({"entries": db.get_audit_logs(hospital_id=hospital.id, actor_level="portal")})


# --- Google Meet integration (Spec.md Section 0) ---
#
# One Google account connected per HOSPITAL by an admin, used for every
# doctor's tele-consultation Meet links -- not a per-doctor connection
# (confirmed with the user). Deliberately gated with the newer, genuinely
# role-aware get_current_staff()/require_permission() pair rather than this
# file's own older _authenticate()/require_capability(hospital, ...)
# pattern every other route above uses: those gate by TENANT PLAN
# (capability), not by STAFF ROLE, so a receptionist's own valid session
# would pass them -- initiating or revoking the hospital's shared Google
# account connection is sensitive enough to warrant the stricter, real
# admin-only check every time, not just a UI-level hide.

@router.get("/api/portal/calendar/status")
async def portal_calendar_status(authorization: str | None = Header(default=None)):
    """The hospital admin's own Settings page reads this to decide what to
    render -- `configured=False` means the feature itself isn't set up yet
    (GOOGLE_CALENDAR_CLIENT_ID/SECRET/CALENDAR_TOKEN_ENCRYPTION_KEY unset),
    a clean, expected state this whole build was required to degrade
    gracefully through, not an error."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "settings", "view")
    if forbidden:
        return forbidden
    connection = db.get_calendar_connection(principal.hospital.id) if is_calendar_integration_configured() else None
    return JSONResponse({
        "configured": is_calendar_integration_configured(),
        "connected": connection is not None,
        "google_email": connection["google_email"] if connection else None,
    })


@router.post("/api/portal/calendar/disconnect")
async def portal_calendar_disconnect(authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "settings", "write")
    if forbidden:
        return forbidden
    db.delete_calendar_connection(principal.hospital.id)
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>",
        "settings.google_calendar_disconnect", entity_type="hospital", entity_id=str(principal.hospital.id),
    )
    return JSONResponse({"ok": True})

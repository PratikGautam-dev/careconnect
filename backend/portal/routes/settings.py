from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from admin.validation import _parse_offsets
import db.repository as db
from core.translations import SUPPORTED_LANGUAGES, t
from flows import REAL_FEATURES
from portal.deps import _authenticate, require_capability

router = APIRouter()

# Section 12.13: minutes bounds mirror db/schema.sql's session_timeout_minutes
# CHECK constraint exactly -- validated here too so a bad value gets a clear
# 400 from this endpoint instead of surfacing as a raw IntegrityError from
# the DB constraint.
_MIN_SESSION_TIMEOUT_MINUTES = 2
_MAX_SESSION_TIMEOUT_MINUTES = 120


@router.get("/api/portal/settings")
async def portal_get_settings(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse(
        {
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
            # CareConnect architecture doc alignment (Spec.md Section 0):
            # unlike enabled_features (operator-only, /admin/edit-tenant),
            # these two ARE genuine self-serve bot customization -- same
            # category as closing_message_text/business_hours_text above.
            "require_patient_confirmation": hospital.require_patient_confirmation,
            "privacy_notice_text": hospital.privacy_notice_text or "",
            "dpdp_consent_required": hospital.dpdp_consent_required,
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
        require_patient_confirmation=bool(payload.get("require_patient_confirmation", False)),
        privacy_notice_text=(payload.get("privacy_notice_text") or "").strip() or None,
        # Tenant-type-driven capability gating (tenant-capability-gating-plan.md):
        # not self-serve -- passed straight through unchanged, same
        # discipline every other operator-only field on this call already
        # follows (enabled_features, portal_password_hash, ...). Only
        # admin/tenants_api.py's tenant-edit endpoint actually changes these.
        tenant_type=hospital.tenant_type,
        admin_capabilities=hospital.admin_capabilities,
        dpdp_consent_required=bool(payload.get("dpdp_consent_required", False)),
    )
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "settings.update",
        entity_type="hospital", entity_id=str(hospital.id),
        before={
            "default_language": hospital.default_language,
            "session_timeout_minutes": hospital.session_timeout_minutes,
            "dpdp_consent_required": hospital.dpdp_consent_required,
        },
        after={
            "default_language": default_language,
            "session_timeout_minutes": session_timeout_minutes,
            "dpdp_consent_required": bool(payload.get("dpdp_consent_required", False)),
        },
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

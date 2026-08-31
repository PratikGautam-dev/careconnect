# admin/platform_settings_api.py
"""JSON API for the platform/super admin's GLOBAL settings -- as opposed to
admin/tenants_api.py, which lists/edits one tenant's own row at a time, this
file is for values that apply identically across every hospital and have no
per-tenant override (confirmed with the user: max_active_patient_links is
NOT a hospital-configurable field). RBAC (docs/rbac-redis-plan.md): gated by
the same get_current_super_admin() tenants_api.py now uses -- this is
exactly the kind of cross-tenant, higher-blast-radius surface that
individual-account gate exists for, and a separate check for a second admin
page would just be one more thing to keep in sync (the same super admin
holds access to both)."""
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db.repository as db
from core.translations import t
from flows import REAL_FEATURES
from portal.deps import get_current_super_admin

router = APIRouter()


class PlatformSettingsUpdatePayload(BaseModel):
    max_active_patient_links: int
    # Migration 0014: WhatsApp menu label overrides and the DPDP Act consent
    # gate moved here from hospitals.feature_labels/dpdp_consent_required --
    # ONE value for every tenant, not a per-hospital setting anymore (see
    # that migration's docstring). feature_labels defaults to {} the same
    # way the old per-hospital form did.
    feature_labels: dict[str, str] = {}
    dpdp_consent_required: bool = False


@router.get("/api/admin/platform-settings")
async def get_platform_settings_route(request: Request, authorization: str | None = Header(default=None)):
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    settings = db.get_platform_settings()
    # Fixed default label per real feature, in English, so the frontend can
    # show it as this field's placeholder ("leave blank to use the
    # default") -- same convention portal/routes/settings.py's old
    # per-hospital GET used before this moved here.
    settings["feature_default_labels"] = {key: t(f"feature_{key}", "en") for key in REAL_FEATURES}
    return JSONResponse(settings)


@router.post("/api/admin/platform-settings")
async def update_platform_settings_route(
    payload: PlatformSettingsUpdatePayload, request: Request, authorization: str | None = Header(default=None),
):
    if get_current_super_admin(authorization) is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    # Same "unknown/typo'd key silently dropped, blank override means use
    # the default" restriction portal/routes/settings.py's old per-hospital
    # validation used, kept here since the field just moved, not the rule.
    feature_labels = {
        key: label.strip()
        for key, label in payload.feature_labels.items()
        if key in REAL_FEATURES and isinstance(label, str) and label.strip()
    }
    try:
        updated = db.update_platform_settings(
            payload.max_active_patient_links, feature_labels, payload.dpdp_consent_required,
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse(updated)

# admin/platform_settings_api.py
"""JSON API for the platform/super admin's GLOBAL settings -- as opposed to
admin/tenants_api.py, which lists/edits one tenant's own row at a time, this
file is for values that apply identically across every hospital and have no
per-tenant override (confirmed with the user: max_active_patient_links is
NOT a hospital-configurable field). Gated by the SAME TENANTS_ADMIN_SECRET
tenants_api.py uses (reusing its own _check_secret, including its shared
rate-limit lockout bucket) -- this is exactly the kind of cross-tenant,
higher-blast-radius surface that secret already exists to gate, and a
second secret for a second admin page would just be one more credential to
manage for no real isolation benefit (the same operator holds both)."""
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db.repository as db
from admin.tenants_api import _check_secret

router = APIRouter()


class PlatformSettingsUpdatePayload(BaseModel):
    max_active_patient_links: int


@router.get("/api/admin/platform-settings")
async def get_platform_settings_route(request: Request, x_admin_secret: str | None = Header(default=None)):
    if not _check_secret(x_admin_secret, request):
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse(db.get_platform_settings())


@router.post("/api/admin/platform-settings")
async def update_platform_settings_route(
    payload: PlatformSettingsUpdatePayload, request: Request, x_admin_secret: str | None = Header(default=None),
):
    if not _check_secret(x_admin_secret, request):
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    try:
        updated = db.update_platform_settings(payload.max_active_patient_links)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse(updated)

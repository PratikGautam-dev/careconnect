# portal/routes/appointment_types.py
"""Portal CRUD for appointment_types -- the gap tenant-capability-gating-
plan.md itself flagged ("no CRUD for appointment_types yet at all -- only
seeded at onboarding"). This is the literal "toggle a feature on/off per
tenant" mechanism for tenant-shaped features like the hospital-only
'daycare' type (db/repositories/appointment_types.py's
DEFAULT_ACTIVE_TYPES_BY_TENANT_TYPE): every tenant already has a row for
every type (is_active differs by tenant_type at seed time), so turning one on
for a clinic that's grown into needing it -- or after it upgrades to
tenant_type='hospital' -- is this one PATCH-shaped toggle, never a
re-seed/re-onboard."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import db.repository as db
from portal.deps import _authenticate, require_capability

router = APIRouter()


@router.get("/api/portal/appointment-types")
async def portal_appointment_types(authorization: str | None = Header(default=None)):
    """Active AND inactive, so the toggle UI can show what's currently off --
    unlike the WhatsApp-facing connector.get_appointment_types(), which only
    ever returns the active subset."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({"appointment_types": db.get_all_appointment_types_for_hospital(hospital.id)})


@router.post("/api/portal/appointment-types/{appointment_type_id}/active")
async def portal_set_appointment_type_active(
    appointment_type_id: str, payload: dict, authorization: str | None = Header(default=None)
):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    is_active = bool((payload or {}).get("is_active", True))
    updated = db.set_appointment_type_active(hospital.id, appointment_type_id, is_active)
    if updated is None:
        return JSONResponse({"error": "No such appointment type."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "appointment_type.toggle",
        entity_type="appointment_type", entity_id=appointment_type_id,
        after={"is_active": is_active},
    )
    return JSONResponse({"appointment_type": updated})

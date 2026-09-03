# portal/routes/lab_service_areas.py
"""Portal CRUD for lab_service_areas -- Lab Test Phase 2 follow-up's
serviceable-PIN-code list for home sample collection. Same shape as
portal/routes/daycare_duration_options.py, reusing manage_appointment_types
(same portal screen area, no new capability needed for a small config list)."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import db.repository as db
from portal.deps import _authenticate, require_capability

router = APIRouter()


@router.get("/api/portal/lab-service-areas")
async def portal_lab_service_areas(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({"lab_service_areas": db.get_all_service_areas_for_hospital(hospital.id)})


@router.post("/api/portal/lab-service-areas")
async def portal_create_lab_service_area(payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    pincode = (payload or {}).get("pincode", "").strip()
    if not pincode:
        return JSONResponse({"error": "pincode is required."}, status_code=400)
    area = db.create_service_area(hospital.id, pincode)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "lab_service_area.create",
        entity_type="lab_service_area", entity_id=str(area["id"]), after=area,
    )
    return JSONResponse({"lab_service_area": area})


@router.post("/api/portal/lab-service-areas/{area_id}/active")
async def portal_set_lab_service_area_active(
    area_id: int, payload: dict, authorization: str | None = Header(default=None)
):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    is_active = bool((payload or {}).get("is_active", True))
    updated = db.set_service_area_active(hospital.id, area_id, is_active)
    if updated is None:
        return JSONResponse({"error": "No such service area."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "lab_service_area.toggle",
        entity_type="lab_service_area", entity_id=str(area_id), after={"is_active": is_active},
    )
    return JSONResponse({"lab_service_area": updated})


@router.delete("/api/portal/lab-service-areas/{area_id}")
async def portal_delete_lab_service_area(area_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    deleted = db.delete_service_area(hospital.id, area_id)
    if not deleted:
        return JSONResponse({"error": "No such service area."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "lab_service_area.delete",
        entity_type="lab_service_area", entity_id=str(area_id),
    )
    return JSONResponse({"deleted": True})

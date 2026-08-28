# portal/routes/daycare_duration_options.py
"""Portal CRUD for daycare_duration_options -- Daycare Phase 2 (docs/
per-appointment-type-flow-plan.md), confirmed with the user directly: unlike
appointment_types (a closed catalog, portal only toggles is_active), a
hospital can add/relabel/remove its own duration options here, since these
are hospital-specific stay-length/pricing tiers rather than a fixed
appointment-type list. Reuses the manage_appointment_types capability --
same portal screen area, no new capability needed for this."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import db.repository as db
from portal.deps import _authenticate, require_capability

router = APIRouter()


@router.get("/api/portal/daycare-duration-options")
async def portal_daycare_duration_options(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({
        "daycare_duration_options": db.get_all_daycare_duration_options_for_hospital(hospital.id),
    })


@router.post("/api/portal/daycare-duration-options")
async def portal_create_daycare_duration_option(payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    label = (payload or {}).get("label", "").strip()
    hours = (payload or {}).get("hours")
    if not label or not isinstance(hours, int) or hours <= 0:
        return JSONResponse({"error": "label and a positive integer hours are required."}, status_code=400)
    option = db.create_daycare_duration_option(hospital.id, label, hours)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "daycare_duration_option.create",
        entity_type="daycare_duration_option", entity_id=str(option["id"]), after=option,
    )
    return JSONResponse({"daycare_duration_option": option})


@router.put("/api/portal/daycare-duration-options/{option_id}")
async def portal_update_daycare_duration_option(
    option_id: int, payload: dict, authorization: str | None = Header(default=None)
):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    label = (payload or {}).get("label", "").strip()
    hours = (payload or {}).get("hours")
    if not label or not isinstance(hours, int) or hours <= 0:
        return JSONResponse({"error": "label and a positive integer hours are required."}, status_code=400)
    updated = db.update_daycare_duration_option(hospital.id, option_id, label, hours)
    if updated is None:
        return JSONResponse({"error": "No such duration option."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "daycare_duration_option.update",
        entity_type="daycare_duration_option", entity_id=str(option_id), after=updated,
    )
    return JSONResponse({"daycare_duration_option": updated})


@router.post("/api/portal/daycare-duration-options/{option_id}/active")
async def portal_set_daycare_duration_option_active(
    option_id: int, payload: dict, authorization: str | None = Header(default=None)
):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    is_active = bool((payload or {}).get("is_active", True))
    updated = db.set_daycare_duration_option_active(hospital.id, option_id, is_active)
    if updated is None:
        return JSONResponse({"error": "No such duration option."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "daycare_duration_option.toggle",
        entity_type="daycare_duration_option", entity_id=str(option_id), after={"is_active": is_active},
    )
    return JSONResponse({"daycare_duration_option": updated})


@router.delete("/api/portal/daycare-duration-options/{option_id}")
async def portal_delete_daycare_duration_option(option_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    deleted = db.delete_daycare_duration_option(hospital.id, option_id)
    if not deleted:
        return JSONResponse({"error": "No such duration option."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "daycare_duration_option.delete",
        entity_type="daycare_duration_option", entity_id=str(option_id),
    )
    return JSONResponse({"deleted": True})

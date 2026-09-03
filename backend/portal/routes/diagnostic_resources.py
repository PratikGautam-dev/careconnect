# portal/routes/diagnostic_resources.py
"""Portal CRUD for diagnostic_resources (Diagnostic/Lab Phase 2, docs/
per-appointment-type-flow-plan.md Step 5) -- a bookable machine/equipment,
managed the same way doctors.py manages doctors (schedule fields, slots,
leave), under its own manage_diagnostic_resources capability since a
resource is a schedulable entity of the same weight as a doctor."""
from datetime import datetime

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db.repository as db
from portal.capabilities import MANAGE_DIAGNOSTIC_RESOURCES
from portal.deps import _authenticate, require_capability

router = APIRouter()


class ResourcePayload(BaseModel):
    name: str = ""
    department_id: str | None = None
    working_days: list[str] = Field(default_factory=list)
    working_hours: list[str] = Field(default_factory=list)
    slot_duration_minutes: int = 30
    breaks: list[str] = Field(default_factory=list)
    max_bookings_per_slot: int = 1
    daily_booking_limit: int | None = None
    effective_from: str | None = None


@router.get("/api/portal/diagnostic-resources")
async def portal_diagnostic_resources(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({"resources": db.get_all_resources_for_hospital(hospital.id)})


@router.post("/api/portal/diagnostic-resources")
async def portal_create_resource(payload: ResourcePayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    name = payload.name.strip()
    if not name:
        return JSONResponse({"error": "Resource name is required."}, status_code=400)
    if payload.department_id and db.find_department(hospital.id, payload.department_id) is None:
        return JSONResponse({"error": "Choose a valid department."}, status_code=400)
    resource = db.create_resource(
        hospital.id, name, department_id=payload.department_id,
        working_days=payload.working_days, working_hours=payload.working_hours,
        slot_duration_minutes=payload.slot_duration_minutes, breaks=payload.breaks,
        max_bookings_per_slot=payload.max_bookings_per_slot, daily_booking_limit=payload.daily_booking_limit,
        effective_from=payload.effective_from,
    )
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_resource.create",
        entity_type="diagnostic_resource", entity_id=resource["id"], after={"name": name},
    )
    return JSONResponse({"resource": resource})


@router.get("/api/portal/diagnostic-resources/{resource_id}")
async def portal_get_resource(resource_id: str, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    resource = db.get_resource_full(hospital.id, resource_id)
    if resource is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    return JSONResponse({"resource": resource})


@router.post("/api/portal/diagnostic-resources/{resource_id}")
async def portal_update_resource(resource_id: str, payload: ResourcePayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    if db.get_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    name = payload.name.strip()
    if not name:
        return JSONResponse({"error": "Resource name is required."}, status_code=400)
    resource = db.update_resource(
        hospital.id, resource_id, name, department_id=payload.department_id,
        working_days=payload.working_days, working_hours=payload.working_hours,
        slot_duration_minutes=payload.slot_duration_minutes, breaks=payload.breaks,
        max_bookings_per_slot=payload.max_bookings_per_slot, daily_booking_limit=payload.daily_booking_limit,
        effective_from=payload.effective_from,
    )
    if resource is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_resource.update",
        entity_type="diagnostic_resource", entity_id=resource_id, after={"name": name},
    )
    return JSONResponse({"resource": resource})


@router.post("/api/portal/diagnostic-resources/{resource_id}/active")
async def portal_set_resource_active(resource_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    is_active = bool((payload or {}).get("is_active", True))
    ok = db.set_resource_active(hospital.id, resource_id, is_active)
    if not ok:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_resource.active_toggle",
        entity_type="diagnostic_resource", entity_id=resource_id, after={"is_active": is_active},
    )
    return JSONResponse({"ok": True, "is_active": is_active})


@router.get("/api/portal/diagnostic-resources/{resource_id}/leave")
async def portal_get_resource_leave(resource_id: str, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    return JSONResponse({"leave_dates": db.get_resource_leave_dates(hospital.id, resource_id)})


@router.post("/api/portal/diagnostic-resources/{resource_id}/leave")
async def portal_add_resource_leave(resource_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    if db.get_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    leave_date = (payload or {}).get("date", "").strip()
    if not leave_date:
        return JSONResponse({"error": "A date is required."}, status_code=400)
    reason = (payload or {}).get("reason", "").strip() or None
    db.add_resource_leave(hospital.id, resource_id, leave_date, reason)
    return JSONResponse({"ok": True})


@router.post("/api/portal/diagnostic-resources/{resource_id}/leave/remove")
async def portal_remove_resource_leave(resource_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    leave_date = (payload or {}).get("date", "").strip()
    if not leave_date:
        return JSONResponse({"error": "A date is required."}, status_code=400)
    ok = db.remove_resource_leave(hospital.id, resource_id, leave_date)
    if not ok:
        return JSONResponse({"error": "No such leave date."}, status_code=404)
    return JSONResponse({"ok": True})


@router.get("/api/portal/diagnostic-resources/{resource_id}/slots")
async def portal_get_resource_slots(resource_id: str, date: str | None = None, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    return JSONResponse({"slots": db.get_resource_slots_for_admin(hospital.id, resource_id, date)})


@router.post("/api/portal/diagnostic-resources/{resource_id}/slots/block")
async def portal_set_resource_slot_blocked(resource_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    if db.get_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    scheduled_at = (payload or {}).get("scheduled_at", "").strip()
    if not scheduled_at:
        return JSONResponse({"error": "scheduled_at is required."}, status_code=400)
    blocked = bool((payload or {}).get("blocked", True))
    reason = (payload or {}).get("reason", "").strip() or None
    ok = db.set_resource_slot_blocked(hospital.id, resource_id, scheduled_at, blocked, reason)
    if not ok:
        if blocked:
            return JSONResponse({"error": "This slot already has a booked appointment -- cancel or reschedule it first."}, status_code=400)
        return JSONResponse({"error": "No such slot."}, status_code=404)
    return JSONResponse({"ok": True, "blocked": blocked})


@router.post("/api/portal/diagnostic-resources/{resource_id}/slots/add")
async def portal_add_resource_slot(resource_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    if db.get_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    date_str = (payload or {}).get("date", "").strip()
    time_str = (payload or {}).get("time", "").strip()
    if not date_str or not time_str:
        return JSONResponse({"error": "date and time are required."}, status_code=400)
    try:
        scheduled_at = datetime.fromisoformat(f"{date_str}T{time_str}").isoformat()
    except ValueError:
        return JSONResponse({"error": "Invalid date/time."}, status_code=400)
    db.add_custom_resource_slot(hospital.id, resource_id, scheduled_at)
    return JSONResponse({"ok": True, "scheduled_at": scheduled_at})


@router.post("/api/portal/diagnostic-resources/{resource_id}/slots/remove")
async def portal_remove_resource_slot(resource_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    if db.get_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    scheduled_at = (payload or {}).get("scheduled_at", "").strip()
    if not scheduled_at:
        return JSONResponse({"error": "scheduled_at is required."}, status_code=400)
    ok = db.remove_resource_slot(hospital.id, resource_id, scheduled_at)
    if not ok:
        return JSONResponse({"error": "This slot either doesn't exist or already has a booked appointment -- cancel or reschedule it first."}, status_code=400)
    return JSONResponse({"ok": True})

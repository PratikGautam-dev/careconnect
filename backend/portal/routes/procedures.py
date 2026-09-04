# portal/routes/procedures.py
"""Daycare/Procedure rebuild: portal CRUD for the procedure catalog
(procedures/procedure_required_resource_types/procedure_instructions) and
the bed/chair/equipment/staff resource pools (procedure_resources), gated by
the dedicated manage_procedures capability. Structurally cloned from
portal/routes/diagnostic_tests.py (catalog) and portal/routes/
diagnostic_resources.py (resource pools + leave)."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db.repository as db
from portal.capabilities import MANAGE_PROCEDURES
from portal.deps import _authenticate, require_capability

router = APIRouter()

_VALID_CATEGORIES = {
    "chemotherapy", "dialysis", "infusion_therapy", "dressing_wound_care", "injection", "minor_procedure", "other",
}
_VALID_BOOKING_MODES = {"instant", "approval_required"}
_VALID_RESOURCE_TYPES = {"bed_chair", "equipment", "staff"}
_VALID_INSTRUCTION_TYPES = {
    "documents", "preparation", "arrival_time", "medication", "insurance_authorization", "other",
}


class ProcedurePayload(BaseModel):
    category: str = ""
    name: str = ""
    booking_mode: str = "instant"
    duration_minutes: int = 30
    department_id: str | None = None
    estimated_price_min: float | None = None
    estimated_price_max: float | None = None


class ResourceTypesPayload(BaseModel):
    resource_types: list[str] = Field(default_factory=list)


class InstructionPayload(BaseModel):
    instruction_type: str = "other"
    instruction_text: str = ""


class ProcedureResourcePayload(BaseModel):
    resource_type: str = "staff"
    name: str = ""
    department_id: str | None = None
    working_days: list[str] = Field(default_factory=list)
    working_hours: list[str] = Field(default_factory=list)
    slot_duration_minutes: int = 30
    breaks: list[str] = Field(default_factory=list)
    max_bookings_per_slot: int = 1
    daily_booking_limit: int | None = None
    effective_from: str | None = None


@router.get("/api/portal/procedures")
async def portal_procedures(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({"procedures": db.get_all_procedures_for_hospital(hospital.id)})


@router.post("/api/portal/procedures")
async def portal_create_procedure(payload: ProcedurePayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    name = payload.name.strip()
    if payload.category not in _VALID_CATEGORIES or not name:
        return JSONResponse({"error": "A valid category and name are required."}, status_code=400)
    if payload.booking_mode not in _VALID_BOOKING_MODES:
        return JSONResponse({"error": "booking_mode must be 'instant' or 'approval_required'."}, status_code=400)
    if payload.duration_minutes <= 0:
        return JSONResponse({"error": "duration_minutes must be positive."}, status_code=400)
    if payload.department_id and db.find_department(hospital.id, payload.department_id) is None:
        return JSONResponse({"error": "Choose a valid department."}, status_code=400)
    procedure = db.create_procedure(
        hospital.id, payload.category, name, payload.booking_mode, payload.duration_minutes,
        department_id=payload.department_id, estimated_price_min=payload.estimated_price_min,
        estimated_price_max=payload.estimated_price_max,
    )
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "procedure.create",
        entity_type="procedure", entity_id=str(procedure["id"]), after=procedure,
    )
    return JSONResponse({"procedure": procedure})


@router.put("/api/portal/procedures/{procedure_id}")
async def portal_update_procedure(procedure_id: int, payload: ProcedurePayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    name = payload.name.strip()
    if payload.category not in _VALID_CATEGORIES or not name:
        return JSONResponse({"error": "A valid category and name are required."}, status_code=400)
    if payload.booking_mode not in _VALID_BOOKING_MODES:
        return JSONResponse({"error": "booking_mode must be 'instant' or 'approval_required'."}, status_code=400)
    if payload.department_id and db.find_department(hospital.id, payload.department_id) is None:
        return JSONResponse({"error": "Choose a valid department."}, status_code=400)
    procedure = db.update_procedure(
        hospital.id, procedure_id, payload.category, name, payload.booking_mode, payload.duration_minutes,
        department_id=payload.department_id, estimated_price_min=payload.estimated_price_min,
        estimated_price_max=payload.estimated_price_max,
    )
    if procedure is None:
        return JSONResponse({"error": "No such procedure."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "procedure.update",
        entity_type="procedure", entity_id=str(procedure_id), after=procedure,
    )
    return JSONResponse({"procedure": procedure})


@router.post("/api/portal/procedures/{procedure_id}/active")
async def portal_set_procedure_active(procedure_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    is_active = bool((payload or {}).get("is_active", True))
    ok = db.set_procedure_active(hospital.id, procedure_id, is_active)
    if not ok:
        return JSONResponse({"error": "No such procedure."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "procedure.active_toggle",
        entity_type="procedure", entity_id=str(procedure_id), after={"is_active": is_active},
    )
    return JSONResponse({"ok": True, "is_active": is_active})


@router.delete("/api/portal/procedures/{procedure_id}")
async def portal_delete_procedure(procedure_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    ok = db.delete_procedure(hospital.id, procedure_id)
    if not ok:
        return JSONResponse({"error": "No such procedure."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "procedure.delete", entity_type="procedure", entity_id=str(procedure_id),
    )
    return JSONResponse({"ok": True})


@router.post("/api/portal/procedures/{procedure_id}/required-resource-types")
async def portal_set_required_resource_types(procedure_id: int, payload: ResourceTypesPayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    if db.get_procedure(hospital.id, procedure_id) is None:
        return JSONResponse({"error": "No such procedure."}, status_code=404)
    invalid = set(payload.resource_types) - _VALID_RESOURCE_TYPES
    if invalid:
        return JSONResponse({"error": f"Invalid resource type(s): {', '.join(sorted(invalid))}."}, status_code=400)
    db.set_required_resource_types(hospital.id, procedure_id, payload.resource_types)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "procedure.required_resource_types_update",
        entity_type="procedure", entity_id=str(procedure_id), after={"resource_types": payload.resource_types},
    )
    return JSONResponse({"ok": True, "resource_types": payload.resource_types})


@router.post("/api/portal/procedures/{procedure_id}/instructions")
async def portal_create_instruction(procedure_id: int, payload: InstructionPayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    if db.get_procedure(hospital.id, procedure_id) is None:
        return JSONResponse({"error": "No such procedure."}, status_code=404)
    text = payload.instruction_text.strip()
    if payload.instruction_type not in _VALID_INSTRUCTION_TYPES or not text:
        return JSONResponse({"error": "A valid instruction_type and instruction_text are required."}, status_code=400)
    instruction = db.create_instruction(hospital.id, procedure_id, payload.instruction_type, text)
    return JSONResponse({"instruction": instruction})


@router.delete("/api/portal/procedures/instructions/{instruction_id}")
async def portal_delete_instruction(instruction_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    ok = db.delete_instruction(hospital.id, instruction_id)
    if not ok:
        return JSONResponse({"error": "No such instruction."}, status_code=404)
    return JSONResponse({"ok": True})


# --- Resource pools (bed/chair, equipment, staff) ---

@router.get("/api/portal/procedure-resources")
async def portal_procedure_resources(resource_type: str | None = None, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({"resources": db.get_all_procedure_resources_for_hospital(hospital.id, resource_type=resource_type)})


@router.post("/api/portal/procedure-resources")
async def portal_create_procedure_resource(payload: ProcedureResourcePayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    name = payload.name.strip()
    if payload.resource_type not in _VALID_RESOURCE_TYPES or not name:
        return JSONResponse({"error": "A valid resource_type and name are required."}, status_code=400)
    if payload.department_id and db.find_department(hospital.id, payload.department_id) is None:
        return JSONResponse({"error": "Choose a valid department."}, status_code=400)
    resource = db.create_procedure_resource(
        hospital.id, payload.resource_type, name, department_id=payload.department_id,
        working_days=payload.working_days, working_hours=payload.working_hours,
        slot_duration_minutes=payload.slot_duration_minutes, breaks=payload.breaks,
        max_bookings_per_slot=payload.max_bookings_per_slot, daily_booking_limit=payload.daily_booking_limit,
        effective_from=payload.effective_from,
    )
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "procedure_resource.create",
        entity_type="procedure_resource", entity_id=resource["id"], after={"name": name},
    )
    return JSONResponse({"resource": resource})


@router.get("/api/portal/procedure-resources/{resource_id}")
async def portal_get_procedure_resource(resource_id: str, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    resource = db.get_procedure_resource_full(hospital.id, resource_id)
    if resource is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    return JSONResponse({"resource": resource})


@router.put("/api/portal/procedure-resources/{resource_id}")
async def portal_update_procedure_resource(resource_id: str, payload: ProcedureResourcePayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    if db.get_procedure_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    name = payload.name.strip()
    if not name:
        return JSONResponse({"error": "Resource name is required."}, status_code=400)
    resource = db.update_procedure_resource(
        hospital.id, resource_id, name, department_id=payload.department_id,
        working_days=payload.working_days, working_hours=payload.working_hours,
        slot_duration_minutes=payload.slot_duration_minutes, breaks=payload.breaks,
        max_bookings_per_slot=payload.max_bookings_per_slot, daily_booking_limit=payload.daily_booking_limit,
        effective_from=payload.effective_from,
    )
    if resource is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "procedure_resource.update",
        entity_type="procedure_resource", entity_id=resource_id, after={"name": name},
    )
    return JSONResponse({"resource": resource})


@router.post("/api/portal/procedure-resources/{resource_id}/active")
async def portal_set_procedure_resource_active(resource_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    is_active = bool((payload or {}).get("is_active", True))
    ok = db.set_procedure_resource_active(hospital.id, resource_id, is_active)
    if not ok:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "procedure_resource.active_toggle",
        entity_type="procedure_resource", entity_id=resource_id, after={"is_active": is_active},
    )
    return JSONResponse({"ok": True, "is_active": is_active})


@router.delete("/api/portal/procedure-resources/{resource_id}")
async def portal_delete_procedure_resource(resource_id: str, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    ok = db.delete_procedure_resource(hospital.id, resource_id)
    if not ok:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    return JSONResponse({"ok": True})


@router.get("/api/portal/procedure-resources/{resource_id}/leave")
async def portal_get_procedure_resource_leave(resource_id: str, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_procedure_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    return JSONResponse({"leave_dates": db.get_procedure_resource_leave_dates(hospital.id, resource_id)})


@router.post("/api/portal/procedure-resources/{resource_id}/leave")
async def portal_add_procedure_resource_leave(resource_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    if db.get_procedure_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "No such resource."}, status_code=404)
    leave_date = ((payload or {}).get("date") or "").strip()
    if not leave_date:
        return JSONResponse({"error": "A date is required."}, status_code=400)
    reason = ((payload or {}).get("reason") or "").strip() or None
    db.add_procedure_resource_leave(hospital.id, resource_id, leave_date, reason)
    return JSONResponse({"ok": True})


@router.post("/api/portal/procedure-resources/{resource_id}/leave/remove")
async def portal_remove_procedure_resource_leave(resource_id: str, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_PROCEDURES)
    if forbidden:
        return forbidden
    leave_date = ((payload or {}).get("date") or "").strip()
    if not leave_date:
        return JSONResponse({"error": "A date is required."}, status_code=400)
    ok = db.remove_procedure_resource_leave(hospital.id, resource_id, leave_date)
    if not ok:
        return JSONResponse({"error": "No such leave date."}, status_code=404)
    return JSONResponse({"ok": True})

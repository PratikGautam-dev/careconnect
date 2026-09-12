# portal/routes/departments.py
"""Settings -> Departments tab's backend -- full department CRUD, split out
of doctors.py (which keeps only the original bare-bones POST /api/portal/
departments create route... actually moved here too, see below) now that
departments have grown a real profile/status/visibility surface (migration
20260912141027). Gated by require_capability(hospital, "manage_departments"),
same capability the original create route already used.

GET /api/portal/doctors' own bundled `departments: [{id,name}]` field is
untouched -- it still calls get_all_departments_for_hospital() (mapped down
to id/name) directly in doctors.py, so the Doctors page's existing simple
Departments view and its Add/Edit Doctor department picker keep working
unchanged."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db.repository as db
from portal.deps import _authenticate, require_capability

router = APIRouter()


@router.get("/api/portal/departments")
async def portal_departments(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    departments = db.get_all_departments_for_hospital(hospital.id)
    return JSONResponse({"departments": departments})


class DepartmentPayload(BaseModel):
    name: str = ""
    floor_wing: str | None = None
    consultation_hours: str | None = None
    description: str | None = None
    head_doctor_id: str | None = None


@router.post("/api/portal/departments")
async def portal_create_department(payload: DepartmentPayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_departments")
    if forbidden:
        return forbidden
    name = payload.name.strip()
    if not name:
        return JSONResponse({"error": "Department name is required."}, status_code=400)
    if payload.head_doctor_id and db.get_doctor_full(hospital.id, payload.head_doctor_id) is None:
        return JSONResponse({"error": "No such doctor for Head of Department."}, status_code=400)
    department = db.create_department(
        hospital.id, name,
        floor_wing=payload.floor_wing, consultation_hours=payload.consultation_hours,
        description=payload.description, head_doctor_id=payload.head_doctor_id,
    )
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "department.create",
        entity_type="department", entity_id=department["id"], after=payload.model_dump(),
    )
    return JSONResponse({"department": department})


@router.patch("/api/portal/departments/{department_id}")
async def portal_update_department(
    department_id: str, payload: DepartmentPayload, authorization: str | None = Header(default=None),
):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_departments")
    if forbidden:
        return forbidden
    name = payload.name.strip()
    if not name:
        return JSONResponse({"error": "Department name is required."}, status_code=400)
    if db.find_department(hospital.id, department_id) is None:
        return JSONResponse({"error": "No such department."}, status_code=404)
    if payload.head_doctor_id and db.get_doctor_full(hospital.id, payload.head_doctor_id) is None:
        return JSONResponse({"error": "No such doctor for Head of Department."}, status_code=400)
    ok = db.update_department(
        hospital.id, department_id, name,
        floor_wing=payload.floor_wing, consultation_hours=payload.consultation_hours,
        description=payload.description, head_doctor_id=payload.head_doctor_id,
    )
    if not ok:
        return JSONResponse({"error": "No such department."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "department.update",
        entity_type="department", entity_id=department_id, after=payload.model_dump(),
    )
    return JSONResponse({"ok": True})


@router.post("/api/portal/departments/{department_id}/active")
async def portal_set_department_active(
    department_id: str, payload: dict, authorization: str | None = Header(default=None),
):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_departments")
    if forbidden:
        return forbidden
    is_active = bool((payload or {}).get("is_active", True))
    ok = db.set_department_active(hospital.id, department_id, is_active)
    if not ok:
        return JSONResponse({"error": "No such department."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal",
        "department.activate" if is_active else "department.deactivate",
        entity_type="department", entity_id=department_id, after={"is_active": is_active},
    )
    return JSONResponse({"ok": True, "is_active": is_active})


class DepartmentVisibilityPayload(BaseModel):
    show_on_frontend: bool = True
    online_booking_enabled: bool = True
    whatsapp_booking_enabled: bool = True


@router.post("/api/portal/departments/{department_id}/visibility")
async def portal_set_department_visibility(
    department_id: str, payload: DepartmentVisibilityPayload, authorization: str | None = Header(default=None),
):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_departments")
    if forbidden:
        return forbidden
    ok = db.set_department_visibility(
        hospital.id, department_id,
        show_on_frontend=payload.show_on_frontend,
        online_booking_enabled=payload.online_booking_enabled,
        whatsapp_booking_enabled=payload.whatsapp_booking_enabled,
    )
    if not ok:
        return JSONResponse({"error": "No such department."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "department.visibility_update",
        entity_type="department", entity_id=department_id, after=payload.model_dump(),
    )
    return JSONResponse({"ok": True})

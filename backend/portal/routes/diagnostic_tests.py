# portal/routes/diagnostic_tests.py
"""Portal CRUD for diagnostic_tests, plus their own schedule/slots/leave
(Diagnostic/Lab Phase 2, docs/per-appointment-type-flow-plan.md Step 5).
Diagnostic tests/resources merge: a test used to be a thin catalog row
pointing at a separate diagnostic_resources row that carried the actual
machine/equipment's schedule -- hospitals always created exactly one
resource per test 1:1, so that indirection is gone. A test now IS the
schedulable resource (same weight as a doctor -- MANAGE_DIAGNOSTIC_RESOURCES
gates every mutation here, not just catalog edits), managed the same way
doctors.py manages doctors (schedule fields, slots, leave). Test/variant
merge: a test also carries its own price directly now -- it only ever
needed exactly one priced option, so the separate variants sub-resource
(and its endpoints below) is gone too."""
from datetime import datetime

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db.repository as db
from portal.capabilities import MANAGE_DIAGNOSTIC_RESOURCES
from portal.deps import _authenticate, require_capability

router = APIRouter()

_VALID_CATEGORIES = {"diagnostic", "lab"}


class DiagnosticTestPayload(BaseModel):
    category: str = ""
    name: str = ""
    price: float | None = None
    working_days: list[str] = Field(default_factory=list)
    working_hours: list[str] = Field(default_factory=list)
    slot_duration_minutes: int = 30
    breaks: list[str] = Field(default_factory=list)
    max_bookings_per_slot: int = 1
    daily_booking_limit: int | None = None
    effective_from: str | None = None


@router.get("/api/portal/diagnostic-tests")
async def portal_diagnostic_tests(category: str | None = None, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({"tests": db.get_all_diagnostic_tests_for_hospital(hospital.id, category=category)})


@router.get("/api/portal/diagnostic-tests/{test_id}")
async def portal_get_diagnostic_test(test_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    test = db.get_diagnostic_test_full(hospital.id, test_id)
    if test is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    return JSONResponse({"test": test})


@router.post("/api/portal/diagnostic-tests")
async def portal_create_diagnostic_test(payload: DiagnosticTestPayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    category = payload.category
    name = payload.name.strip()
    if category not in _VALID_CATEGORIES or not name:
        return JSONResponse({"error": "category ('diagnostic'/'lab') and name are required."}, status_code=400)
    test = db.create_diagnostic_test(
        hospital.id, category, name, price=payload.price,
        working_days=payload.working_days, working_hours=payload.working_hours,
        slot_duration_minutes=payload.slot_duration_minutes, breaks=payload.breaks,
        max_bookings_per_slot=payload.max_bookings_per_slot, daily_booking_limit=payload.daily_booking_limit,
        effective_from=payload.effective_from,
    )
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test.create",
        entity_type="diagnostic_test", entity_id=str(test["id"]), after={"name": name},
    )
    return JSONResponse({"test": test})


@router.put("/api/portal/diagnostic-tests/{test_id}")
async def portal_update_diagnostic_test(test_id: int, payload: DiagnosticTestPayload, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    name = payload.name.strip()
    if not name:
        return JSONResponse({"error": "name is required."}, status_code=400)
    updated = db.update_diagnostic_test(
        hospital.id, test_id, name, price=payload.price,
        working_days=payload.working_days, working_hours=payload.working_hours,
        slot_duration_minutes=payload.slot_duration_minutes, breaks=payload.breaks,
        max_bookings_per_slot=payload.max_bookings_per_slot, daily_booking_limit=payload.daily_booking_limit,
        effective_from=payload.effective_from,
    )
    if updated is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test.update",
        entity_type="diagnostic_test", entity_id=str(test_id), after={"name": name},
    )
    return JSONResponse({"test": updated})


@router.post("/api/portal/diagnostic-tests/{test_id}/active")
async def portal_set_diagnostic_test_active(test_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    is_active = bool((payload or {}).get("is_active", True))
    updated = db.set_diagnostic_test_active(hospital.id, test_id, is_active)
    if updated is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test.toggle",
        entity_type="diagnostic_test", entity_id=str(test_id), after={"is_active": is_active},
    )
    return JSONResponse({"test": updated})


@router.delete("/api/portal/diagnostic-tests/{test_id}")
async def portal_delete_diagnostic_test(test_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    deleted = db.delete_diagnostic_test(hospital.id, test_id)
    if not deleted:
        return JSONResponse({"error": "No such test."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test.delete",
        entity_type="diagnostic_test", entity_id=str(test_id),
    )
    return JSONResponse({"deleted": True})


# --- Leave (moved from the old portal/routes/diagnostic_resources.py) ---

@router.get("/api/portal/diagnostic-tests/{test_id}/leave")
async def portal_get_test_leave(test_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_diagnostic_test(hospital.id, test_id) is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    return JSONResponse({"leave_dates": db.get_test_leave_dates(hospital.id, test_id)})


@router.post("/api/portal/diagnostic-tests/{test_id}/leave")
async def portal_add_test_leave(test_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    if db.get_diagnostic_test(hospital.id, test_id) is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    leave_date = (payload or {}).get("date", "").strip()
    if not leave_date:
        return JSONResponse({"error": "A date is required."}, status_code=400)
    reason = (payload or {}).get("reason", "").strip() or None
    db.add_test_leave(hospital.id, test_id, leave_date, reason)
    return JSONResponse({"ok": True})


@router.post("/api/portal/diagnostic-tests/{test_id}/leave/remove")
async def portal_remove_test_leave(test_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    leave_date = (payload or {}).get("date", "").strip()
    if not leave_date:
        return JSONResponse({"error": "A date is required."}, status_code=400)
    ok = db.remove_test_leave(hospital.id, test_id, leave_date)
    if not ok:
        return JSONResponse({"error": "No such leave date."}, status_code=404)
    return JSONResponse({"ok": True})


# --- Slots (moved from the old portal/routes/diagnostic_resources.py) ---

@router.get("/api/portal/diagnostic-tests/{test_id}/slots")
async def portal_get_test_slots(test_id: int, date: str | None = None, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_diagnostic_test(hospital.id, test_id) is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    return JSONResponse({"slots": db.get_test_slots_for_admin(hospital.id, test_id, date)})


@router.post("/api/portal/diagnostic-tests/{test_id}/slots/block")
async def portal_set_test_slot_blocked(test_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    if db.get_diagnostic_test(hospital.id, test_id) is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    scheduled_at = (payload or {}).get("scheduled_at", "").strip()
    if not scheduled_at:
        return JSONResponse({"error": "scheduled_at is required."}, status_code=400)
    blocked = bool((payload or {}).get("blocked", True))
    reason = (payload or {}).get("reason", "").strip() or None
    ok = db.set_test_slot_blocked(hospital.id, test_id, scheduled_at, blocked, reason)
    if not ok:
        if blocked:
            return JSONResponse({"error": "This slot already has a booked appointment -- cancel or reschedule it first."}, status_code=400)
        return JSONResponse({"error": "No such slot."}, status_code=404)
    return JSONResponse({"ok": True, "blocked": blocked})


@router.post("/api/portal/diagnostic-tests/{test_id}/slots/add")
async def portal_add_test_slot(test_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    if db.get_diagnostic_test(hospital.id, test_id) is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    date_str = (payload or {}).get("date", "").strip()
    time_str = (payload or {}).get("time", "").strip()
    if not date_str or not time_str:
        return JSONResponse({"error": "date and time are required."}, status_code=400)
    try:
        scheduled_at = datetime.fromisoformat(f"{date_str}T{time_str}").isoformat()
    except ValueError:
        return JSONResponse({"error": "Invalid date/time."}, status_code=400)
    db.add_custom_test_slot(hospital.id, test_id, scheduled_at)
    return JSONResponse({"ok": True, "scheduled_at": scheduled_at})


@router.post("/api/portal/diagnostic-tests/{test_id}/slots/remove")
async def portal_remove_test_slot(test_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, MANAGE_DIAGNOSTIC_RESOURCES)
    if forbidden:
        return forbidden
    if db.get_diagnostic_test(hospital.id, test_id) is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    scheduled_at = (payload or {}).get("scheduled_at", "").strip()
    if not scheduled_at:
        return JSONResponse({"error": "scheduled_at is required."}, status_code=400)
    ok = db.remove_test_slot(hospital.id, test_id, scheduled_at)
    if not ok:
        return JSONResponse({"error": "This slot either doesn't exist or already has a booked appointment -- cancel or reschedule it first."}, status_code=400)
    return JSONResponse({"ok": True})

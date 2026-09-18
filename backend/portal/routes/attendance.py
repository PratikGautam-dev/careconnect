# portal/routes/attendance.py
"""Real check-in/check-out endpoints behind the previously frontend-mock
/portal/check-in-out page -- see db/repositories/attendance.py for the
geofence/IP verification + shift-status logic these routes just validate
input for and delegate to.

Gated by the real "check_in_out" page_key (migration 20260914130000) via
get_current_staff()/require_permission(), same pattern portal/routes/
settings.py's own Google Calendar routes use -- this is inherently a
per-STAFF action (whose own attendance), not a per-hospital one, so it needs
get_current_staff() rather than settings.py's older, hospital-only
_authenticate()."""
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

import db.repository as db
from core.rate_limit import client_ip as _client_ip
from db.repositories.attendance import AttendanceError
from portal.deps import get_current_staff, require_permission

router = APIRouter()


def _parse_coordinate(raw, field_name: str) -> float | None:
    if raw in (None, ""):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a number.")
    return value


@router.get("/api/portal/attendance/today")
async def portal_attendance_today(authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "check_in_out", "view")
    if forbidden:
        return forbidden
    return JSONResponse({
        "today": db.get_today_attendance(principal.hospital, principal.staff_id),
        "history": db.get_attendance_history(principal.hospital, principal.staff_id),
    })


@router.get("/api/portal/attendance/summary")
async def portal_attendance_summary(days: int = 120, authorization: str | None = Header(default=None)):
    """The /portal/attendance page's own data source -- a longer personal
    history window than /today's (which only needs enough for its own
    "recent" list) so the page can filter by month across the last few
    months. Gated by "attendance" (not "check_in_out" -- a hospital can
    grant one without the other, since they're separate page_keys)."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "attendance", "view")
    if forbidden:
        return forbidden
    days = max(1, min(days, 366))
    return JSONResponse({"history": db.get_attendance_history(principal.hospital, principal.staff_id, days=days)})


@router.post("/api/portal/attendance/check-in")
async def portal_attendance_check_in(payload: dict, request: Request, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "check_in_out", "write")
    if forbidden:
        return forbidden
    try:
        lat = _parse_coordinate(payload.get("latitude"), "latitude")
        lng = _parse_coordinate(payload.get("longitude"), "longitude")
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    try:
        record = db.check_in(principal.hospital, principal.staff_id, lat, lng, _client_ip(request))
    except AttendanceError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>",
        "attendance.check_in", entity_type="attendance_record", entity_id=str(principal.staff_id),
    )
    return JSONResponse({"ok": True, "record": record})


@router.post("/api/portal/attendance/check-out")
async def portal_attendance_check_out(authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "check_in_out", "write")
    if forbidden:
        return forbidden
    try:
        record = db.check_out(principal.hospital, principal.staff_id)
    except AttendanceError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>",
        "attendance.check_out", entity_type="attendance_record", entity_id=str(principal.staff_id),
    )
    return JSONResponse({"ok": True, "record": record})


@router.post("/api/portal/attendance/break/start")
async def portal_attendance_break_start(authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "check_in_out", "write")
    if forbidden:
        return forbidden
    try:
        record = db.start_break(principal.hospital, principal.staff_id)
    except AttendanceError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"ok": True, "record": record})


@router.post("/api/portal/attendance/break/end")
async def portal_attendance_break_end(authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "check_in_out", "write")
    if forbidden:
        return forbidden
    try:
        record = db.end_break(principal.hospital, principal.staff_id)
    except AttendanceError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"ok": True, "record": record})


@router.get("/api/portal/attendance/hospital")
async def portal_attendance_hospital(for_date: str | None = None, authorization: str | None = Header(default=None)):
    """Hospital-wide roll-up for the admin-facing /portal/attendance page --
    gated by "attendance" view (not "attendance_settings", which only
    covers editing the geofence/shift policy)."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "attendance", "view")
    if forbidden:
        return forbidden
    return JSONResponse({"records": db.get_hospital_attendance(principal.hospital.id, for_date)})

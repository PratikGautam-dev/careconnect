# portal/routes/leave_requests.py
"""Leave Requests admin page's backend (migration 20260912065049) -- list/
approve/reject doctor+receptionist leave requests for the caller's own
hospital, plus the admin-configurable annual leave policy (doctor/
receptionist only -- see db/repositories/leave_requests.py's own docstring
for why admin doesn't accrue an allowance).

Gated by require_permission(principal, "leave_requests", ...) like every
other page -- admin gets view+write by default (portal/permissions.py's
DEFAULT_PERMISSIONS_BY_ROLE), off for receptionist/doctor.

No POST /api/portal/leave-requests (create) route yet -- doctor/staff
self-service is a later page (confirmed with the user); this is
review-only for now, same scoping as the rest of this migration."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db.repository as db
from portal.deps import get_current_staff, require_permission

router = APIRouter()

_VALID_STATUSES = {"pending", "approved", "rejected"}


def _leave_request_row(row: dict) -> dict:
    return {
        "id": row["id"], "applicant_id": row["identity_id"], "applicant_name": row["applicant_name"],
        "role": row["role"], "department_name": row["department_name"], "reports_to_name": row["reports_to_name"],
        "leave_type": row["leave_type"], "from_date": row["from_date"], "to_date": row["to_date"],
        "duration_days": row["duration_days"], "reason": row["reason"], "status": row["status"],
        "submitted_at": row["created_at"], "decided_at": row["decided_at"], "decided_by_name": row["decided_by_name"],
    }


@router.get("/api/portal/leave-requests")
async def list_leave_requests(status: str | None = None, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "leave_requests", "view")
    if forbidden:
        return forbidden
    if status is not None and status not in _VALID_STATUSES:
        return JSONResponse({"error": f"status must be one of {sorted(_VALID_STATUSES)}."}, status_code=400)
    requests = db.list_leave_requests_for_hospital(principal.hospital.id, status=status)
    summary = db.get_leave_summary_counts(principal.hospital.id)
    return JSONResponse({"requests": [_leave_request_row(r) for r in requests], "summary": summary})


def _decide(request_id: int, status: str, principal) -> JSONResponse:
    forbidden = require_permission(principal, "leave_requests", "write")
    if forbidden:
        return forbidden
    ok = db.decide_leave_request(principal.hospital.id, request_id, principal.staff_id, status)
    if not ok:
        return JSONResponse({"error": "No such pending leave request."}, status_code=404)
    db.record_audit_log(
        "portal", principal.hospital.id, principal.name, f"leave_request.{status}",
        entity_type="leave_request", entity_id=str(request_id),
    )
    updated = db.get_leave_request(principal.hospital.id, request_id)
    return JSONResponse({"request": _leave_request_row(updated)})


@router.post("/api/portal/leave-requests/{request_id}/approve")
async def approve_leave_request(request_id: int, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return _decide(request_id, "approved", principal)


@router.post("/api/portal/leave-requests/{request_id}/reject")
async def reject_leave_request(request_id: int, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return _decide(request_id, "rejected", principal)


class LeavePolicyPayload(BaseModel):
    doctor_annual_leave_days: int
    staff_annual_leave_days: int


@router.get("/api/portal/leave-requests/policy")
async def get_leave_policy(authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "leave_requests", "view")
    if forbidden:
        return forbidden
    return JSONResponse(db.get_leave_policy(principal.hospital.id))


@router.post("/api/portal/leave-requests/policy")
async def set_leave_policy(payload: LeavePolicyPayload, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "leave_requests", "write")
    if forbidden:
        return forbidden
    if payload.doctor_annual_leave_days < 0 or payload.staff_annual_leave_days < 0:
        return JSONResponse({"error": "Leave allowances can't be negative."}, status_code=400)
    db.set_leave_policy(principal.hospital.id, payload.doctor_annual_leave_days, payload.staff_annual_leave_days)
    db.record_audit_log(
        "portal", principal.hospital.id, principal.name, "leave_policy.update",
        after={"doctor_annual_leave_days": payload.doctor_annual_leave_days,
               "staff_annual_leave_days": payload.staff_annual_leave_days},
    )
    return JSONResponse(db.get_leave_policy(principal.hospital.id))

# portal/routes/leave_requests.py
"""Leave Requests admin page's backend -- list/
approve/reject doctor+receptionist leave requests for the caller's own
hospital, plus the admin-configurable annual leave policy (doctor/
receptionist only -- see db/repositories/leave_requests.py's own docstring
for why admin doesn't accrue an allowance).

Review (list/approve/reject/policy) is gated by
require_permission(principal, "leave_requests", ...) -- admin gets view+
write by default, off for receptionist/doctor.

The OTHER side of this same table is self-
service submission, the Holiday Application page (my_leave_requests()/
submit_leave_request() below) -- gated by a SEPARATE page key,
"holiday_application", which defaults to view+write for every role
(doctor and receptionist both apply for their own leave through it, admin
too) -- being able to review everyone else's requests and being able to
submit your own are two different permissions on purpose, so an admin can
revoke one without the other."""
import logging

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db.repository as db
from portal.deps import get_current_staff, require_permission

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_STATUSES = {"pending", "approved", "rejected"}
_VALID_LEAVE_TYPES = {"casual", "sick", "annual", "maternity", "conference", "personal"}


def _leave_request_row(row: dict) -> dict:
    return {
        "id": row["id"], "applicant_id": row["identity_id"], "applicant_name": row["applicant_name"],
        "role_name": row["role_name"], "is_doctor_role": row["is_doctor_role"],
        "department_name": row["department_name"], "reports_to_name": row["reports_to_name"],
        "leave_type": row["leave_type"], "from_date": row["from_date"], "to_date": row["to_date"],
        "is_half_day": row["is_half_day"], "duration_days": row["duration_days"],
        "reason": row["reason"], "status": row["status"],
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
    updated = db.get_leave_request(principal.hospital.id, request_id)
    if status == "approved" and not updated["is_half_day"]:
        # Approving turns this from a record into something that actually
        # blocks new bookings -- reuses the pre-existing doctor_leave
        # range-block mechanism (db/repositories/leave.py), so a patient
        # can't be booked into a day this doctor is now on approved leave
        # for. Half-day requests are skipped -- doctor_leave has no
        # partial-day concept, so blocking the WHOLE day would over-block a
        # half-day request; a known, documented limitation, not a bug.
        # Only doctor-linked identities have a bookable calendar at all
        # (a receptionist's approved leave has nothing to block).
        applicant = db.get_staff_user_by_id(updated["identity_id"])
        if applicant and applicant.get("doctor_id"):
            try:
                db.create_doctor_leave_range(
                    principal.hospital.id, applicant["doctor_id"], updated["from_date"], updated["to_date"],
                    reason=f"Approved {updated['leave_type']} leave",
                )
            except ValueError:
                # Same "never let a side-effect failure undo the
                # already-committed change" posture doctor_portal.py's own
                # running-late WhatsApp send failure uses -- the approval
                # itself already succeeded and must stay approved.
                logger.exception(
                    "Approved leave_request %s but could not auto-block doctor_leave for doctor %s",
                    request_id, applicant.get("doctor_id"),
                )
    db.record_audit_log(
        "portal", principal.hospital.id, principal.name, f"leave_request.{status}",
        entity_type="leave_request", entity_id=str(request_id),
    )
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


@router.get("/api/portal/leave-requests/mine")
async def my_leave_requests(authorization: str | None = Header(default=None)):
    """Holiday Application page's own data -- this caller's OWN requests +
    balance, not gated by "leave_requests" (that continues to gate seeing/
    deciding on everyone ELSE's requests) but by "holiday_application",
    which defaults to view+write for every role, doctor or not."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "holiday_application", "view")
    if forbidden:
        return forbidden
    requests = db.list_leave_requests_for_identity(principal.hospital.id, principal.staff_id)
    policy = db.get_leave_policy(principal.hospital.id)
    quota = policy["doctor_annual_leave_days"] if principal.doctor_id else policy["staff_annual_leave_days"]
    used = db.get_leave_usage_by_identity(principal.hospital.id).get(principal.staff_id, 0)
    return JSONResponse({
        "requests": [_leave_request_row(r) for r in requests],
        "balance": {"quota_days": quota, "used_days": used, "remaining_days": max(quota - used, 0)},
    })


class SubmitLeaveRequestPayload(BaseModel):
    leave_type: str
    from_date: str
    to_date: str
    is_half_day: bool = False
    reason: str


@router.post("/api/portal/leave-requests/mine")
async def submit_leave_request(payload: SubmitLeaveRequestPayload, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "holiday_application", "write")
    if forbidden:
        return forbidden
    if payload.leave_type not in _VALID_LEAVE_TYPES:
        return JSONResponse({"error": f"leave_type must be one of {sorted(_VALID_LEAVE_TYPES)}."}, status_code=400)
    if payload.to_date < payload.from_date:
        return JSONResponse({"error": "to_date must not be before from_date."}, status_code=400)
    if payload.is_half_day and payload.to_date != payload.from_date:
        return JSONResponse({"error": "A half-day request must have the same from_date and to_date."}, status_code=400)
    if not payload.reason.strip():
        return JSONResponse({"error": "reason is required."}, status_code=400)
    created = db.create_leave_request(
        principal.hospital.id, principal.staff_id, payload.leave_type, payload.from_date, payload.to_date,
        reason=payload.reason.strip(), is_half_day=payload.is_half_day,
    )
    db.record_audit_log(
        "portal", principal.hospital.id, principal.name, "leave_request.submit",
        entity_type="leave_request", entity_id=str(created["id"]),
        after={"leave_type": payload.leave_type, "from_date": payload.from_date, "to_date": payload.to_date},
    )
    return JSONResponse({"request": _leave_request_row(created)})

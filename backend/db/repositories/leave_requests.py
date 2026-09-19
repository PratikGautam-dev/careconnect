# db/repositories/leave_requests.py
"""Leave Requests admin page -- doctors and receptionists can have a
leave_requests row, reviewed by an admin into one of
pending/approved/rejected. The doctor/staff self-service side (the
Holiday Application page, portal/routes/leave_requests.py's
my_leave_requests()/submit_leave_request()) calls create_leave_request() below.

Not the same thing as db/repositories/leave.py's doctor_leave -- that's a
simpler "block this doctor's bookable slots on this
whole day" scheduling mechanism with no approval workflow or balance,
predating this feature. The two ARE connected in one direction though:
approving a full-day leave request auto-creates the matching doctor_leave
range (see portal/routes/leave_requests.py's _decide()), so an approved
request actually blocks new bookings, not just changes a status label.

Leave balance = hospitals.doctor_annual_leave_days/staff_annual_leave_days
(the portal-admin-configurable policy, doctor/receptionist only -- admin
approves leave rather than accruing an allowance) minus this identity's
approved-request days that fall in the current calendar year
(get_leave_usage_by_identity() below) -- resets every year, and a request
spanning the year boundary only counts the days actually inside it."""
from datetime import date, datetime, timezone
from typing import cast

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import aliased

from db.connection import get_session
from db.orm_models import Department, DoctorRow, HospitalRow, Identity, LeaveRequest, RoleRow, StaffDetail

_VALID_STATUSES = ("pending", "approved", "rejected")
_VALID_LEAVE_TYPES = ("casual", "sick", "annual", "maternity", "conference", "personal")


def _request_duration_days(from_date_str: str, to_date_str: str, is_half_day: bool) -> float:
    """A half-day request only ever covers a single date (enforced at the
    route layer, not the DB) -- 0.5 day, not the inclusive whole-day count
    every other request uses."""
    if is_half_day and from_date_str == to_date_str:
        return 0.5
    return float((date.fromisoformat(to_date_str) - date.fromisoformat(from_date_str)).days + 1)


def _with_duration(row: dict) -> dict:
    row["duration_days"] = _request_duration_days(row["from_date"], row["to_date"], row["is_half_day"])
    return row


def _leave_request_query():
    decider = aliased(Identity)
    reports_to = aliased(Identity)
    own_department = aliased(Department)
    doctor_department = aliased(Department)
    return (
        select(
            LeaveRequest.id, LeaveRequest.identity_id, LeaveRequest.leave_type,
            LeaveRequest.from_date, LeaveRequest.to_date, LeaveRequest.is_half_day,
            LeaveRequest.reason, LeaveRequest.status,
            LeaveRequest.created_at, LeaveRequest.decided_at,
            Identity.name.label("applicant_name"),
            RoleRow.name.label("role_name"), StaffDetail.doctor_id.is_not(None).label("is_doctor_role"),
            func.coalesce(doctor_department.name, own_department.name).label("department_name"),
            decider.name.label("decided_by_name"), reports_to.name.label("reports_to_name"),
        )
        .join(StaffDetail, StaffDetail.identity_id == LeaveRequest.identity_id)
        .join(Identity, Identity.id == LeaveRequest.identity_id)
        .join(RoleRow, RoleRow.id == StaffDetail.role_id)
        .outerjoin(own_department, own_department.id == StaffDetail.department_id)
        .outerjoin(DoctorRow, DoctorRow.id == StaffDetail.doctor_id)
        .outerjoin(doctor_department, doctor_department.id == DoctorRow.department_id)
        .outerjoin(decider, decider.id == LeaveRequest.decided_by)
        .outerjoin(reports_to, reports_to.id == StaffDetail.reports_to_id)
    )


def list_leave_requests_for_identity(hospital_id: int, identity_id: int) -> list[dict]:
    """Holiday Application page's own "Leave Request History" -- this one
    applicant's requests only, most recent first. Same joined shape
    list_leave_requests_for_hospital() gives the admin review queue (role/
    department/decided-by names included, even though the self-service page
    mostly just needs its own leave_type/dates/status)."""
    session = get_session()
    rows = session.execute(
        _leave_request_query()
        .where(LeaveRequest.hospital_id == hospital_id, LeaveRequest.identity_id == identity_id)
        .order_by(LeaveRequest.created_at.desc())
    ).all()
    return [_with_duration(dict(r._mapping)) for r in rows]


def list_leave_requests_for_hospital(hospital_id: int, *, status: str | None = None) -> list[dict]:
    """The Leave Requests page's own table -- department_name resolves the
    same doctor-vs-own-department way list_staff_users_for_hospital()
    already does, since an applicant can be either role."""
    session = get_session()
    query = _leave_request_query().where(LeaveRequest.hospital_id == hospital_id)
    if status:
        query = query.where(LeaveRequest.status == status)
    rows = session.execute(query.order_by(LeaveRequest.created_at.desc())).all()
    return [_with_duration(dict(r._mapping)) for r in rows]


def get_leave_request(hospital_id: int, request_id: int) -> dict | None:
    session = get_session()
    row = session.execute(
        _leave_request_query().where(LeaveRequest.hospital_id == hospital_id, LeaveRequest.id == request_id)
    ).first()
    return _with_duration(dict(row._mapping)) if row is not None else None


def get_leave_summary_counts(hospital_id: int) -> dict:
    """Stat tiles: total/pending/approved/rejected request counts plus how
    many approved requests cover today specifically (\"on leave today\")."""
    session = get_session()
    counts = {"pending": 0, "approved": 0, "rejected": 0}
    for status, count in session.execute(
        select(LeaveRequest.status, func.count())
        .where(LeaveRequest.hospital_id == hospital_id)
        .group_by(LeaveRequest.status)
    ).all():
        counts[status] = count
    today = date.today().isoformat()
    on_leave_today = session.execute(
        select(func.count()).select_from(LeaveRequest).where(
            LeaveRequest.hospital_id == hospital_id, LeaveRequest.status == "approved",
            LeaveRequest.from_date <= today, LeaveRequest.to_date >= today,
        )
    ).scalar_one()
    return {"total": sum(counts.values()), **counts, "on_leave_today": on_leave_today}


def decide_leave_request(hospital_id: int, request_id: int, decided_by_identity_id: int, status: str) -> bool:
    """status must be 'approved' or 'rejected' (caller validates against
    _VALID_STATUSES). Only ever acts on a currently-pending request -- a
    request that's already been decided is immutable, so a second
    approve/reject call on it (a stale UI, a double-click) is a no-op that
    returns False rather than silently overwriting the first decision."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(LeaveRequest).where(
            LeaveRequest.hospital_id == hospital_id, LeaveRequest.id == request_id, LeaveRequest.status == "pending",
        ).values(status=status, decided_by=decided_by_identity_id, decided_at=datetime.now(timezone.utc).isoformat())
    ))
    session.commit()
    return result.rowcount > 0


def create_leave_request(
    hospital_id: int, identity_id: int, leave_type: str, from_date: str, to_date: str,
    reason: str | None = None, is_half_day: bool = False,
) -> dict:
    """Holiday Application page's own submit -- the route layer validates
    leave_type/date order/is_half_day-implies-same-day before calling this;
    this function trusts its caller the same way upsert_staff_override()
    trusts portal/routes/roles.py's own validation. Returns the full joined
    row (get_leave_request()'s shape), not just the new id, so the route can
    hand it straight back the same shape every other leave_requests response
    already uses."""
    session = get_session()
    new_id = session.execute(
        insert(LeaveRequest)
        .values(
            hospital_id=hospital_id, identity_id=identity_id, leave_type=leave_type,
            from_date=from_date, to_date=to_date, reason=reason, is_half_day=is_half_day,
        )
        .returning(LeaveRequest.id)
    ).scalar_one()
    session.commit()
    return get_leave_request(hospital_id, new_id)


def get_leave_policy(hospital_id: int) -> dict:
    session = get_session()
    row = session.execute(
        select(HospitalRow.doctor_annual_leave_days, HospitalRow.staff_annual_leave_days)
        .where(HospitalRow.id == hospital_id)
    ).first()
    return dict(row._mapping)


def set_leave_policy(hospital_id: int, doctor_annual_leave_days: int, staff_annual_leave_days: int) -> None:
    session = get_session()
    session.execute(
        update(HospitalRow).where(HospitalRow.id == hospital_id)
        .values(doctor_annual_leave_days=doctor_annual_leave_days, staff_annual_leave_days=staff_annual_leave_days)
    )
    session.commit()


def get_leave_usage_by_identity(hospital_id: int, year: int | None = None) -> dict[int, int]:
    """identity_id -> approved leave days used so far in `year` (defaults to
    the current calendar year). A request is clipped to the year's own
    [Jan 1, Dec 31] bounds before counting its days, so one spanning the
    year boundary never lets its far side inflate this year's usage (or a
    prior year's)."""
    year = year or date.today().year
    year_start, year_end = date(year, 1, 1), date(year, 12, 31)
    session = get_session()
    rows = session.execute(
        select(LeaveRequest.identity_id, LeaveRequest.from_date, LeaveRequest.to_date, LeaveRequest.is_half_day)
        .where(LeaveRequest.hospital_id == hospital_id, LeaveRequest.status == "approved")
    ).all()
    usage: dict[int, float] = {}
    for identity_id, from_date_str, to_date_str, is_half_day in rows:
        start = max(date.fromisoformat(from_date_str), year_start)
        end = min(date.fromisoformat(to_date_str), year_end)
        if start <= end:
            # A half-day request is always a single day (route-enforced), so
            # clipping it to the year boundary above never changes which day
            # it lands on -- 0.5 applies whenever the request itself was
            # marked half-day, not just when start == end after clipping.
            days = 0.5 if is_half_day else float((end - start).days + 1)
            usage[identity_id] = usage.get(identity_id, 0) + days
    return usage

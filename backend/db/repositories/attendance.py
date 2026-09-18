# db/repositories/attendance.py
"""Real staff check-in/check-out attendance -- the backend behind the
previously frontend-mock /portal/check-in-out (self-service) and
/portal/attendance (hospital roll-up) pages. One row per (staff, date) in
`attendance_records` (migration 20260918090100), gated on the way in by the
geofence/IP/shift-window policy a hospital configures via Settings ->
Attendance (db/repositories/hospital_settings.py's attendance_* columns).

Geofence + IP verification are each independently optional (see
_verify_geofence/_verify_ip below) -- a hospital that hasn't configured
attendance_latitude/longitude, or hasn't configured attendance_allowed_ip_
cidrs, simply isn't checked on that dimension, rather than blocking every
check-in until both are set up."""
import ipaddress
from datetime import date, datetime, time, timedelta, timezone
from typing import cast

import pytz
from geopy.distance import geodesic
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from db.connection import get_session
from db.orm_models import AttendanceRecord, HospitalRow, HospitalSettings, StaffDetail
from db.repositories.hospital_settings import DEFAULT_ATTENDANCE_ALLOWED_RADIUS_METERS, get_hospital_settings


def _local_now(hospital, now: datetime) -> datetime:
    """attendance_shift_start/end are hospital-LOCAL wall-clock strings
    ("09:00") -- comparing them against a bare UTC `now` (this table's own
    storage timezone) would silently misjudge on-time/late by the
    hospital's UTC offset. hospitals.timezone (an IANA name, default "UTC")
    is already how every other per-hospital local-time need in this
    codebase is meant to be resolved (db/repositories/hospitals.py)."""
    return now.astimezone(pytz.timezone(hospital.timezone or "UTC"))


class AttendanceError(ValueError):
    """Raised for any check-in/out rejection a route should surface as a
    clean 400 -- geofence/IP mismatch, outside the shift's check-in window,
    or an out-of-order action (checking out before checking in, starting a
    break twice). A dedicated subclass of ValueError (not bare ValueError)
    so route code can catch it specifically without also swallowing a
    genuine programming error from elsewhere in the call."""


def _geofence_distance_meters(settings: dict, lat: float | None, lng: float | None) -> float | None:
    """The actual distance between the caller's reported position and the
    hospital's configured location, or None when it can't be computed
    (hospital hasn't configured a location, or the caller sent none) --
    surfaced in check_in()'s own rejection message so a real mismatch (a
    laptop's WiFi/IP-based geolocation is often off by hundreds of meters
    to several kilometers, especially with no known WiFi network in range
    -- e.g. tethered to a mobile hotspot) is diagnosable from the error
    itself, not just a flat "denied"."""
    if settings["attendance_latitude"] is None or settings["attendance_longitude"] is None:
        return None
    if lat is None or lng is None:
        return None
    hospital_point = (settings["attendance_latitude"], settings["attendance_longitude"])
    return geodesic(hospital_point, (lat, lng)).meters


def _verify_geofence(settings: dict, lat: float | None, lng: float | None) -> bool | None:
    """Returns True/False when this hospital has a configured location to
    check against, or None when it hasn't configured one yet (so this
    dimension is skipped entirely, not treated as a failure)."""
    if settings["attendance_latitude"] is None or settings["attendance_longitude"] is None:
        return None
    if lat is None or lng is None:
        return False
    distance_meters = _geofence_distance_meters(settings, lat, lng)
    radius = settings["attendance_allowed_radius_meters"] or DEFAULT_ATTENDANCE_ALLOWED_RADIUS_METERS
    return distance_meters <= radius


def _verify_ip(settings: dict, ip: str | None) -> bool | None:
    """Same "None means not configured, skip this check" contract as
    _verify_geofence above. attendance_allowed_ip_cidrs is a comma-separated
    list of exact IPs and/or CIDR ranges."""
    raw = (settings["attendance_allowed_ip_cidrs"] or "").strip()
    if not raw:
        return None
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif addr == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def _verification_method(geofence_ok: bool | None, ip_ok: bool | None) -> str:
    if geofence_ok and ip_ok:
        return "both"
    if geofence_ok:
        return "gps"
    if ip_ok:
        return "ip"
    return "none"


def _today_row(session, hospital_id: int, staff_id: int, today: str) -> AttendanceRecord | None:
    return session.execute(
        select(AttendanceRecord).where(AttendanceRecord.staff_id == staff_id, AttendanceRecord.date == today)
    ).scalar_one_or_none()


def _iso(value):
    """SQLAlchemy hands back native date/datetime objects for this table's
    Date/DateTime(timezone=True) columns -- plain json.dumps() (what
    fastapi.responses.JSONResponse uses, unlike jsonable_encoder) can't
    serialize those, so every timestamp is converted to an ISO string here,
    same "dates/datetimes as ISO text" convention db/repositories/leave.py's
    own callers already follow."""
    return value.isoformat() if value is not None else None


def _serialize(row: AttendanceRecord) -> dict:
    return {
        "date": _iso(row.date),
        "check_in_at": _iso(row.check_in_at),
        "check_out_at": _iso(row.check_out_at),
        "break_started_at": _iso(row.break_started_at),
        "break_minutes": row.break_minutes,
        "status": row.status,
        "late_minutes": row.late_minutes,
        "working_minutes": row.working_minutes,
        "overtime_minutes": row.overtime_minutes,
        "check_in_verified_method": row.check_in_verified_method,
    }


def check_in(hospital, staff_id: int, lat: float | None, lng: float | None, ip: str | None) -> dict:
    """Rejects (AttendanceError) when this hospital has a configured
    geofence/IP allowlist and the caller matches NEITHER -- a hospital that
    configured only one of the two only needs that one to pass (an admin
    who hasn't set up hospital Wi-Fi's static IP yet isn't blocked by a
    check they never turned on)."""
    settings = get_hospital_settings(hospital.id)
    today = date.today().isoformat()
    session = get_session()
    existing = _today_row(session, hospital.id, staff_id, today)
    if existing is not None and existing.check_in_at is not None:
        raise AttendanceError("Already checked in today.")

    geofence_ok = _verify_geofence(settings, lat, lng)
    ip_ok = _verify_ip(settings, ip)
    # Each dimension is independently optional (None = not configured, skip
    # it) -- only reject when at least one IS configured and NEITHER passes.
    configured = geofence_ok is not None or ip_ok is not None
    if configured and geofence_ok is not True and ip_ok is not True:
        # Surface the ACTUAL distance when one was computable -- a rejection
        # is very often a browser location accuracy problem (WiFi/IP-based
        # geolocation on a laptop with no known WiFi network in range, e.g.
        # tethered to a mobile hotspot, can be off by hundreds of meters to
        # several kilometers) rather than a real "not at the hospital" case,
        # and a flat "denied" gives the staff member/admin nothing to act on.
        distance = _geofence_distance_meters(settings, lat, lng)
        if distance is not None:
            radius = settings["attendance_allowed_radius_meters"] or DEFAULT_ATTENDANCE_ALLOWED_RADIUS_METERS
            raise AttendanceError(
                f"You're {distance:.0f}m from the hospital (allowed: {radius}m). "
                "If you believe you're actually there, your device's location may be inaccurate -- "
                "this is common on a laptop with no known WiFi network in range (e.g. a mobile hotspot)."
            )
        raise AttendanceError("You must be at the hospital location or on its network to check in.")

    now = datetime.now(timezone.utc)
    working_hours = session.execute(
        select(StaffDetail.working_hours).where(StaffDetail.identity_id == staff_id)
    ).scalar_one_or_none()
    shift_start_minutes = _shift_start_minutes(working_hours)
    if shift_start_minutes is None:
        shift_start_minutes = _hhmm_to_minutes(settings["attendance_shift_start"])
    status, late_minutes = _shift_status(
        shift_start_minutes, settings["attendance_late_threshold_minutes"], _local_now(hospital, now),
    )
    session.execute(
        pg_insert(AttendanceRecord)
        .values(
            hospital_id=hospital.id, staff_id=staff_id, date=today, check_in_at=now,
            check_in_latitude=lat, check_in_longitude=lng, check_in_ip=ip,
            check_in_verified_method=_verification_method(geofence_ok, ip_ok),
            status=status, late_minutes=late_minutes,
        )
        .on_conflict_do_update(
            index_elements=["staff_id", "date"],
            set_={
                "check_in_at": now, "check_in_latitude": lat, "check_in_longitude": lng, "check_in_ip": ip,
                "check_in_verified_method": _verification_method(geofence_ok, ip_ok),
                "status": status, "late_minutes": late_minutes,
            },
        )
    )
    session.commit()
    return _serialize(_today_row(session, hospital.id, staff_id, today))


def _shift_status(shift_start_minutes: int | None, late_threshold_minutes: int | None, now: datetime) -> tuple[str, int]:
    """on_time/late against a shift start (minutes since midnight, already
    resolved by the caller -- see check_in()'s own "staff's own working_
    hours, falling back to the hospital-wide attendance_shift_start"
    resolution) -- 'on_time' with 0 late_minutes when there's no shift
    start to compare against at all, per-staff or hospital-wide."""
    if shift_start_minutes is None:
        return "on_time", 0
    shift_start_at = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=shift_start_minutes)
    late_by = int((now - shift_start_at).total_seconds() // 60)
    if late_by > (late_threshold_minutes or 10):
        return "late", late_by
    return "on_time", 0


def check_out(hospital, staff_id: int) -> dict:
    today = date.today().isoformat()
    session = get_session()
    row = _today_row(session, hospital.id, staff_id, today)
    if row is None or row.check_in_at is None:
        raise AttendanceError("You haven't checked in today.")
    if row.check_out_at is not None:
        raise AttendanceError("Already checked out today.")
    now = datetime.now(timezone.utc)
    break_minutes = row.break_minutes
    if row.break_started_at is not None:
        break_minutes += int((now - row.break_started_at).total_seconds() // 60)
    working_minutes = max(0, int((now - row.check_in_at).total_seconds() // 60) - break_minutes)
    session.execute(
        update(AttendanceRecord).where(AttendanceRecord.id == row.id).values(
            check_out_at=now, break_started_at=None, break_minutes=break_minutes, working_minutes=working_minutes,
        )
    )
    session.commit()
    return _serialize(_today_row(session, hospital.id, staff_id, today))


def start_break(hospital, staff_id: int) -> dict:
    today = date.today().isoformat()
    session = get_session()
    row = _today_row(session, hospital.id, staff_id, today)
    if row is None or row.check_in_at is None or row.check_out_at is not None:
        raise AttendanceError("You must be checked in to start a break.")
    if row.break_started_at is not None:
        raise AttendanceError("Break already in progress.")
    session.execute(
        update(AttendanceRecord).where(AttendanceRecord.id == row.id).values(break_started_at=datetime.now(timezone.utc))
    )
    session.commit()
    return _serialize(_today_row(session, hospital.id, staff_id, today))


def end_break(hospital, staff_id: int) -> dict:
    today = date.today().isoformat()
    session = get_session()
    row = _today_row(session, hospital.id, staff_id, today)
    if row is None or row.break_started_at is None:
        raise AttendanceError("No break in progress.")
    now = datetime.now(timezone.utc)
    break_minutes = row.break_minutes + int((now - row.break_started_at).total_seconds() // 60)
    session.execute(
        update(AttendanceRecord).where(AttendanceRecord.id == row.id).values(break_started_at=None, break_minutes=break_minutes)
    )
    session.commit()
    return _serialize(_today_row(session, hospital.id, staff_id, today))


def get_today_attendance(hospital, staff_id: int) -> dict | None:
    session = get_session()
    row = _today_row(session, hospital.id, staff_id, date.today().isoformat())
    return _serialize(row) if row is not None else None


def get_attendance_history(hospital, staff_id: int, days: int = 30) -> list[dict]:
    session = get_session()
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = session.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.staff_id == staff_id, AttendanceRecord.hospital_id == hospital.id, AttendanceRecord.date >= since)
        .order_by(AttendanceRecord.date.desc())
    ).scalars().all()
    return [_serialize(r) for r in rows]


def get_hospital_attendance(hospital_id: int, for_date: str | None = None) -> list[dict]:
    """Hospital-wide roll-up for one calendar day, for the admin-facing
    /portal/attendance page -- every staff member's row for `for_date`
    (defaults to today), joined with their name for display."""
    from db.orm_models import Identity

    session = get_session()
    the_date = for_date or date.today().isoformat()
    rows = session.execute(
        select(AttendanceRecord, Identity.name, StaffDetail.employee_id)
        .join(Identity, Identity.id == AttendanceRecord.staff_id)
        .outerjoin(StaffDetail, StaffDetail.identity_id == AttendanceRecord.staff_id)
        .where(AttendanceRecord.hospital_id == hospital_id, AttendanceRecord.date == the_date)
    ).all()
    return [{**_serialize(r[0]), "staff_name": r[1], "employee_id": r[2]} for r in rows]


def _parse_shift_ranges(working_hours: str | None) -> list[tuple[int, int]]:
    """Every HH:MM-HH:MM range in a comma-separated working_hours string
    (StaffDetail.working_hours -- the same shift range applies to every day
    a staff member works, admin/validation.py's own format), each as
    (start_minutes, end_minutes) since midnight. Unparseable entries are
    skipped rather than raising -- this reads already-admin-validated data,
    so a parse failure here would be a data anomaly, not a user input to
    reject."""
    ranges = []
    for r in (working_hours or "").split(","):
        r = r.strip()
        if "-" not in r:
            continue
        start, end = r.split("-", 1)
        try:
            sh, sm = start.split(":")
            eh, em = end.split(":")
            ranges.append((int(sh) * 60 + int(sm), int(eh) * 60 + int(em)))
        except ValueError:
            continue
    return ranges


def _shift_start_minutes(working_hours: str | None) -> int | None:
    """The EARLIEST start time (minutes since midnight) across a staff
    member's own shift ranges -- None when unset/unparseable, so the
    caller can fall back to the hospital-wide attendance_shift_start.
    check_in()'s own on-time/late calculation uses this (a staff member's
    OWN shift start, not a hospital-wide one that may not match their
    actual hours -- see the auto-checkout design discussion this mirrors)."""
    ranges = _parse_shift_ranges(working_hours)
    return min((r[0] for r in ranges), default=None)


def _shift_end_minutes(working_hours: str | None) -> int | None:
    """The LATEST end time (minutes since midnight) across a staff member's
    own shift ranges -- e.g. a split shift "09:00-13:00,14:00-18:00" ends
    at 18:00. None when unset/unparseable, so the caller can fall back to
    the hospital-wide attendance_shift_end."""
    ranges = _parse_shift_ranges(working_hours)
    return max((r[1] for r in ranges), default=None)


def _hhmm_to_minutes(hhmm: str | None) -> int | None:
    if not hhmm:
        return None
    try:
        hh, mm = hhmm.split(":")
        return int(hh) * 60 + int(mm)
    except ValueError:
        return None


def auto_checkout_overdue() -> list[dict]:
    """Closes out every still-open attendance_records row (check_in_at set,
    check_out_at still NULL) whose DEADLINE has already passed -- that
    staff member's OWN shift end (StaffDetail.working_hours, falling back
    to the hospital-wide attendance_shift_end when they have none
    configured) plus that hospital's own attendance_auto_checkout_grace_
    minutes. A single hospital-wide CLOCK TIME (the original, replaced
    design) can't correctly serve two staff on different shifts -- this
    computes each person's own deadline from their own shift instead.

    Only hospitals with attendance_auto_checkout_grace_minutes actually SET
    are considered at all (NULL means auto-checkout is off, same opt-in
    convention as every other attendance_* setting) -- filtered at the SQL
    level so a hospital that never touched this stays completely
    unaffected, not "defaulted on."

    Sets check_out_at to the DEADLINE MOMENT itself, not whenever this
    function happens to run -- a record reflects when the cutoff actually
    occurred, not sweep timing. Also naturally closes any OLDER forgotten
    check-outs (a record from days ago is already well past its own
    deadline), not just ones that just became overdue.

    Meant to be called from webhook/cron_routes.py's POST /internal/
    auto-checkout, hit by an external cron -- see that route for the Redis
    lock guarding against two overlapping runs; the conditional UPDATE
    below (`WHERE check_out_at IS NULL`) is a second, independent guard
    against the same, so this is safe even without the lock.

    Returns one dict per record actually closed, for the endpoint's own
    response payload."""
    session = get_session()
    rows = session.execute(
        select(AttendanceRecord, HospitalRow, HospitalSettings, StaffDetail.working_hours)
        .join(HospitalRow, HospitalRow.id == AttendanceRecord.hospital_id)
        .join(HospitalSettings, HospitalSettings.hospital_id == AttendanceRecord.hospital_id)
        .outerjoin(StaffDetail, StaffDetail.identity_id == AttendanceRecord.staff_id)
        .where(
            AttendanceRecord.check_in_at.is_not(None),
            AttendanceRecord.check_out_at.is_(None),
            HospitalSettings.attendance_auto_checkout_grace_minutes.is_not(None),
        )
    ).all()

    now = datetime.now(timezone.utc)
    closed = []
    for record, hospital, settings_row, working_hours in rows:
        shift_end_minutes = _shift_end_minutes(working_hours)
        if shift_end_minutes is None:
            shift_end_minutes = _hhmm_to_minutes(settings_row.attendance_shift_end)
        if shift_end_minutes is None:
            continue  # no shift end configured anywhere -- no deadline to compute

        tz = pytz.timezone(hospital.timezone or "UTC")
        grace = timedelta(minutes=settings_row.attendance_auto_checkout_grace_minutes)
        naive_shift_end = datetime.combine(record.date, time.min) + timedelta(minutes=shift_end_minutes)
        schedule_deadline = tz.localize(naive_shift_end).astimezone(timezone.utc) + grace
        # A LATE arrival (checked in after their own schedule_deadline has
        # already passed) must never get a deadline earlier than their own
        # check_in_at -- otherwise they'd be auto-checked-out within one
        # sweep of arriving, with a nonsensical check_out_at BEFORE their
        # check_in_at and 0 working minutes. Give them the same grace
        # period, just counted from when they actually checked in instead.
        deadline = max(schedule_deadline, record.check_in_at + grace)
        if now < deadline:
            continue

        break_minutes = record.break_minutes
        if record.break_started_at is not None:
            break_minutes += max(0, int((deadline - record.break_started_at).total_seconds() // 60))
        working_minutes = max(0, int((deadline - record.check_in_at).total_seconds() // 60) - break_minutes)

        result = cast(CursorResult, session.execute(
            update(AttendanceRecord)
            .where(AttendanceRecord.id == record.id, AttendanceRecord.check_out_at.is_(None))
            .values(
                check_out_at=deadline, break_started_at=None, break_minutes=break_minutes,
                working_minutes=working_minutes,
            )
        ))
        if result.rowcount:
            closed.append({
                "hospital_id": record.hospital_id, "staff_id": record.staff_id,
                "date": record.date.isoformat(), "check_out_at": deadline.isoformat(),
            })
    session.commit()
    return closed

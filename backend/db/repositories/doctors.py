# db/repositories/doctors.py
"""Departments, doctors, and doctor-slot candidate computation (Section
12.1/14.7). Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1.

compute_doctor_candidate_slots() (below generate_slots_for_doctor's old
location) replaces what used to be a bulk INSERT into a doctor_slots table --
found to scale badly (one row for every possible future slot, pre-generated
ahead of time) and to be the root cause of a stale-window bug: a doctor's
bookable grid is now computed in memory, live, from this same working_days/
working_hours/slot_duration_minutes/breaks/doctor_leave config every time
it's needed (db/repositories/slots.py), so there's no window that can ever
run dry. create_doctor()/update_doctor() below no longer generate or delete
any slot rows at all -- there's nothing left to generate ahead of time."""
import uuid
from datetime import date, datetime, timedelta
from typing import cast

import sqlalchemy.exc
from sqlalchemy import insert, select, update
from sqlalchemy.engine import CursorResult

from db.connection import get_session, reraise_as_driver_integrity_error
from db.orm_models import Department, DoctorLeave, DoctorRow
from core.redis_client import cache_delete

_WEEKDAY_ABBREVS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def invalidate_doctor_slots_cache(hospital_id: int, doctor_id: str) -> None:
    """Called wherever a doctor's schedule/leave/overrides change -- the
    connector-layer grid cache (connectors/tier1.py) is keyed exactly this
    way, and this is the one thing that must never be forgotten on a write,
    so it lives right next to the config it protects rather than being left
    to each caller to remember. No-ops when Redis is unset/unreachable, same
    contract as every core/redis_client.py function."""
    cache_delete(f"slots_grid:doctor:{hospital_id}:{doctor_id}")


# --- Departments / doctors ---

def get_departments(hospital_id: int) -> list[dict]:
    session = get_session()
    rows = session.execute(
        select(Department.id, Department.name).where(Department.hospital_id == hospital_id).order_by(Department.name)
    ).all()
    return [dict(r._mapping) for r in rows]


def find_department(hospital_id: int, department_id: str) -> dict | None:
    session = get_session()
    row = session.execute(
        select(Department.id, Department.name).where(Department.hospital_id == hospital_id, Department.id == department_id)
    ).first()
    return dict(row._mapping) if row else None


def get_doctors(hospital_id: int, department_id: str) -> list[dict]:
    """The connector interface's own get_doctors() (Section 12.6.2) -- both
    the WhatsApp bot's booking flow AND the staff portal's new-booking page
    read doctor lists through this one function, so excluding is_active=FALSE
    doctors here is the single enforcement point for "staff turned this
    doctor off" everywhere a booking could actually be created, not just the
    bot. The portal's own doctor MANAGEMENT list uses
    get_all_doctors_for_hospital() instead, which intentionally still shows
    inactive doctors so staff can toggle them back on."""
    session = get_session()
    rows = session.execute(
        select(DoctorRow.id, DoctorRow.name)
        .where(DoctorRow.hospital_id == hospital_id, DoctorRow.department_id == department_id, DoctorRow.is_active.is_(True))
        .order_by(DoctorRow.name)
    ).all()
    return [dict(r._mapping) for r in rows]


def find_doctor(hospital_id: int, department_id: str, doctor_id: str) -> dict | None:
    session = get_session()
    row = session.execute(
        select(DoctorRow.id, DoctorRow.name).where(
            DoctorRow.hospital_id == hospital_id, DoctorRow.department_id == department_id, DoctorRow.id == doctor_id,
        )
    ).first()
    return dict(row._mapping) if row else None


def create_department(hospital_id: int, name: str) -> dict:
    """id is a UUID-derived opaque string (not a slug of `name`), scoped by an
    h{hospital_id}_ prefix -- avoids both the collision risk of slugifying
    arbitrary user-entered text and the known Tier 1 limitation that
    departments.id is globally unique, not (hospital_id, id) composite-unique
    (db/schema.sql's comment on that table)."""
    department_id = f"h{hospital_id}_{uuid.uuid4().hex[:8]}"
    session = get_session()
    session.execute(insert(Department).values(id=department_id, hospital_id=hospital_id, name=name))
    session.commit()
    return {"id": department_id, "name": name}


def create_doctor(
    hospital_id: int,
    department_id: str,
    name: str,
    specialization: str | None = None,
    qualification: str | None = None,
    years_experience: int | None = None,
    working_days: list[str] | None = None,
    working_hours: list[str] | None = None,
    slot_duration_minutes: int = 30,
    breaks: list[str] | None = None,
    max_bookings_per_slot: int = 1,
    daily_booking_limit: int | None = None,
    online_quota: int | None = None,
    walkin_quota: int | None = None,
    followup_duration_minutes: int | None = None,
    effective_from: str | None = None,
) -> dict:
    """working_days (e.g. ["Mon", "Wed", "Fri"]) and working_hours (e.g.
    ["10:00-13:00", "17:00-20:00"]) are this doctor's working pattern (Section
    12.1 Step 7) -- nothing is generated or written here beyond this row
    itself; the bookable grid is computed live, on demand, from these same
    columns (db/repositories/slots.py's get_doctor_grid()). A doctor with no
    working_days/working_hours simply computes zero candidate slots.

    breaks (Section 14.7, e.g. ["11:20-11:40"]) is comma-stored exactly like
    working_hours, and applies the same way -- uniformly across every working
    day, not per-specific-day. effective_from has no effect on a brand-new
    doctor (nothing to preserve yet) -- it only matters on update_doctor()."""
    doctor_id = f"h{hospital_id}_{uuid.uuid4().hex[:8]}"
    session = get_session()
    session.execute(
        insert(DoctorRow).values(
            id=doctor_id, hospital_id=hospital_id, department_id=department_id, name=name,
            specialization=specialization, qualification=qualification, years_experience=years_experience,
            working_days=",".join(working_days or []), working_hours=",".join(working_hours or []),
            slot_duration_minutes=slot_duration_minutes, breaks=",".join(breaks or []),
            max_bookings_per_slot=max_bookings_per_slot, daily_booking_limit=daily_booking_limit,
            online_quota=online_quota, walkin_quota=walkin_quota,
            followup_duration_minutes=followup_duration_minutes, effective_from=effective_from,
        )
    )
    session.commit()
    return {"id": doctor_id, "name": name}


_DOCTOR_FULL_COLUMNS = (
    DoctorRow.id, DoctorRow.department_id, DoctorRow.name, DoctorRow.specialization, DoctorRow.qualification,
    DoctorRow.years_experience, DoctorRow.working_days, DoctorRow.working_hours, DoctorRow.slot_duration_minutes,
    DoctorRow.breaks, DoctorRow.max_bookings_per_slot, DoctorRow.daily_booking_limit, DoctorRow.online_quota,
    DoctorRow.walkin_quota, DoctorRow.followup_duration_minutes, DoctorRow.effective_from, DoctorRow.is_active,
)


def get_doctor_full(hospital_id: int, doctor_id: str) -> dict | None:
    """Every column, not just {id, name} like get_doctors()/find_doctor() --
    portal.py's doctor-edit form (Section 12.7 follow-up: self-serve doctor
    management) needs the full working pattern to pre-fill, and needs
    department_id from the doctor_id alone (the edit URL only carries the
    doctor's id, not which department it's under)."""
    session = get_session()
    row = session.execute(
        select(*_DOCTOR_FULL_COLUMNS).where(DoctorRow.hospital_id == hospital_id, DoctorRow.id == doctor_id)
    ).first()
    if row is None:
        return None
    return _parse_doctor_row(dict(row._mapping))


def _parse_doctor_row(d: dict) -> dict:
    d["working_days"] = [x for x in d["working_days"].split(",") if x]
    d["working_hours"] = [x for x in d["working_hours"].split(",") if x]
    d["breaks"] = [x for x in (d.get("breaks") or "").split(",") if x]
    return d


def get_all_doctors_for_hospital(hospital_id: int) -> list[dict]:
    """Every doctor at this hospital with its department name attached --
    portal.py's doctors list page (Section 12.7 follow-up), one query instead
    of walking get_departments() -> get_doctors() per department. Deliberately
    NOT filtered by is_active -- this is the management view, so an inactive
    doctor must still show up (with its off state) so staff can toggle it
    back on; get_doctors() is the one that hides them from bookable lists."""
    session = get_session()
    rows = session.execute(
        select(
            DoctorRow.id, DoctorRow.department_id, Department.name.label("department_name"),
            DoctorRow.name, DoctorRow.specialization, DoctorRow.is_active,
        )
        .join(Department, Department.id == DoctorRow.department_id)
        .where(DoctorRow.hospital_id == hospital_id)
        .order_by(Department.name, DoctorRow.name)
    ).all()
    return [dict(r._mapping) for r in rows]


def set_doctor_active(hospital_id: int, doctor_id: str, is_active: bool) -> bool:
    """Staff-facing on/off switch (distinct from doctor_leave's whole-day
    dates and from editing working hours) -- returns False if no matching
    doctor row exists for this hospital, True on a real update, so callers
    can 404 rather than silently no-op."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(DoctorRow).where(DoctorRow.hospital_id == hospital_id, DoctorRow.id == doctor_id).values(is_active=is_active)
    ))
    session.commit()
    return result.rowcount > 0


def set_doctor_login_credentials(hospital_id: int, doctor_id: str, email: str, password_hash: str) -> bool:
    """Admin-issued/reset doctor login (dedicated doctor portal, separate
    from the shared staff portal) -- called only from
    portal/routes/doctors.py's admin-only credential route, never
    self-service. Overwrites any existing email/password_hash outright, same
    "reset replaces, doesn't merge" semantics as a portal password reset.
    Returns False if no matching doctor row exists for this hospital (404 for
    the caller) or if `email` is already taken by a DIFFERENT doctor
    (ux_doctors_email is globally unique, not per-hospital) -- surfaced to
    the caller as a psycopg2 IntegrityError via reraise_as_driver_integrity_error,
    same pattern every other unique-constraint-backed write in this codebase uses."""
    session = get_session()
    try:
        result = cast(CursorResult, session.execute(
            update(DoctorRow).where(DoctorRow.hospital_id == hospital_id, DoctorRow.id == doctor_id)
            .values(email=email, password_hash=password_hash)
        ))
        session.commit()
    except sqlalchemy.exc.IntegrityError as e:
        session.rollback()
        raise reraise_as_driver_integrity_error(e)
    return result.rowcount > 0


def clear_doctor_login_credentials(hospital_id: int, doctor_id: str) -> bool:
    """Revokes a doctor's login (admin action) without touching anything
    else about the doctor row -- any outstanding doctor-session tokens still
    verify cryptographically (auth/doctor_session.py's HMAC has no server-side
    revocation list, same "re-issued rather than revoked" posture
    auth/session.py's own module docstring already accepts for the shared
    portal token), but a fresh login attempt fails immediately since
    find_doctor_by_email() can no longer find this doctor's email at all."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(DoctorRow).where(DoctorRow.hospital_id == hospital_id, DoctorRow.id == doctor_id)
        .values(email=None, password_hash=None)
    ))
    session.commit()
    return result.rowcount > 0


def find_doctor_by_email(email: str) -> dict | None:
    """Doctor-login lookup (auth path, not staff-portal) -- email is globally
    unique (ux_doctors_email), not scoped to one hospital first, so this is
    the one doctor-repository read that doesn't take hospital_id as a
    parameter; the caller learns hospital_id FROM this row instead of
    supplying it. Returns None for a doctor with no login configured
    (email IS NULL never matches) or an inactive doctor (is_active=False is
    excluded here the same way get_doctors() already excludes inactive
    doctors from every bookable/patient-facing path -- a doctor taken off
    the schedule shouldn't still be able to log in and touch data)."""
    session = get_session()
    row = session.execute(
        select(
            DoctorRow.id, DoctorRow.hospital_id, DoctorRow.name,
            DoctorRow.email, DoctorRow.password_hash,
        ).where(DoctorRow.email == email, DoctorRow.is_active.is_(True))
    ).first()
    return dict(row._mapping) if row is not None else None


def update_doctor(
    hospital_id: int,
    doctor_id: str,
    name: str,
    specialization: str | None = None,
    qualification: str | None = None,
    years_experience: int | None = None,
    working_days: list[str] | None = None,
    working_hours: list[str] | None = None,
    slot_duration_minutes: int = 30,
    breaks: list[str] | None = None,
    max_bookings_per_slot: int = 1,
    daily_booking_limit: int | None = None,
    online_quota: int | None = None,
    walkin_quota: int | None = None,
    followup_duration_minutes: int | None = None,
    effective_from: str | None = None,
) -> dict | None:
    """portal.py's doctor-edit form. Returns None if no such doctor exists at
    this hospital (nothing updated), same "hospital_id in the WHERE clause is
    the actual guard, not application logic" discipline as every other
    hospital-scoped write here.

    Section 14.7: if effective_from is a FUTURE date, the submitted pattern
    is queued into the pending_* columns instead of overwriting the active
    one -- compute_doctor_candidate_slots() below keeps serving the CURRENT
    pattern for near-term dates and switches to the pending one once its own
    date arrives, so a schedule change meant to start next month doesn't
    retroactively change next week's availability. effective_from=None (or a
    non-future date) applies the submitted pattern immediately and clears
    any previously-queued pending change (this submission supersedes it) --
    matches the exact pre-migration-0032 behavior, just computed live now
    instead of via regenerating persisted rows."""
    today = date.today()
    is_future_change = effective_from is not None and date.fromisoformat(effective_from) > today
    values = {
        "name": name, "specialization": specialization, "qualification": qualification,
        "years_experience": years_experience, "max_bookings_per_slot": max_bookings_per_slot,
        "online_quota": online_quota, "walkin_quota": walkin_quota,
        "followup_duration_minutes": followup_duration_minutes,
    }
    if is_future_change:
        values.update(
            pending_working_days=",".join(working_days or []), pending_working_hours=",".join(working_hours or []),
            pending_slot_duration_minutes=slot_duration_minutes, pending_breaks=",".join(breaks or []),
            pending_daily_booking_limit=daily_booking_limit, pending_effective_from=effective_from,
        )
    else:
        values.update(
            working_days=",".join(working_days or []), working_hours=",".join(working_hours or []),
            slot_duration_minutes=slot_duration_minutes, breaks=",".join(breaks or []),
            daily_booking_limit=daily_booking_limit, effective_from=effective_from,
            pending_working_days=None, pending_working_hours=None, pending_slot_duration_minutes=None,
            pending_breaks=None, pending_daily_booking_limit=None, pending_effective_from=None,
        )
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(DoctorRow).where(DoctorRow.hospital_id == hospital_id, DoctorRow.id == doctor_id).values(**values)
    ))
    if result.rowcount == 0:
        return None
    session.commit()
    invalidate_doctor_slots_cache(hospital_id, doctor_id)
    return {"id": doctor_id, "name": name}


def _parse_time_range(time_range: str) -> tuple[str, str]:
    start, end = time_range.split("-")
    return start.strip(), end.strip()


def _overlaps_break(slot_start: datetime, slot_end: datetime, breaks: list[tuple[str, str]], day: date) -> bool:
    for break_start_str, break_end_str in breaks:
        break_start = datetime.combine(day, datetime.strptime(break_start_str, "%H:%M").time())
        break_end = datetime.combine(day, datetime.strptime(break_end_str, "%H:%M").time())
        if break_start < slot_end and break_end > slot_start:
            return True
    return False


def _pattern_for_date(doctor_row: DoctorRow, d: date):
    """Picks whichever of this doctor's CURRENT or PENDING pattern (Section
    14.7's queued-future-schedule-change columns) applies to date `d` -- the
    pending one once its own pending_effective_from has arrived, the current
    one otherwise (gated by the current pattern's own effective_from, if
    set). Returns None if no pattern is active for `d` at all (e.g. a
    brand-new doctor whose effective_from hasn't arrived yet, or an
    incompletely-configured doctor)."""
    if doctor_row.pending_effective_from and d >= date.fromisoformat(doctor_row.pending_effective_from):
        working_days_raw, working_hours_raw = doctor_row.pending_working_days, doctor_row.pending_working_hours
        slot_duration = doctor_row.pending_slot_duration_minutes
        breaks_raw, daily_booking_limit = doctor_row.pending_breaks, doctor_row.pending_daily_booking_limit
    else:
        if doctor_row.effective_from and d < date.fromisoformat(doctor_row.effective_from):
            return None
        working_days_raw, working_hours_raw = doctor_row.working_days, doctor_row.working_hours
        slot_duration = doctor_row.slot_duration_minutes
        breaks_raw, daily_booking_limit = doctor_row.breaks, doctor_row.daily_booking_limit

    working_days = {x.strip() for x in (working_days_raw or "").split(",") if x.strip()}
    working_hours = [x.strip() for x in (working_hours_raw or "").split(",") if x.strip()]
    if not working_days or not working_hours or not slot_duration:
        return None
    breaks = [_parse_time_range(b) for b in (breaks_raw or "").split(",") if b.strip()]
    return working_days, working_hours, slot_duration, breaks, daily_booking_limit


def compute_doctor_candidate_slots(
    hospital_id: int, doctor_id: str, days_ahead: int, now: date | None = None,
) -> list[str]:
    """The doctor's bookable grid for the next `days_ahead` days, computed
    live from working_days/working_hours/slot_duration_minutes/breaks/
    doctor_leave (and pending_* -- see _pattern_for_date()) -- ISO
    scheduled_at strings only, no DB write. Replaces the old
    generate_slots_for_doctor()'s bulk INSERT into a doctor_slots table
    (removed in migration 0032, found to scale badly and be the root cause
    of a stale-window bug). db/repositories/slots.py's get_doctor_grid() is
    the only caller, merging this with doctor_slot_overrides (blocked/
    custom-added exceptions) to build the final grid.

    Section 14.7 features, all read from the doctor's own row:
    - breaks: any candidate overlapping a break window is skipped entirely
      (breaks apply uniformly to every working day, not a specific one).
    - doctor_leave: any date present there is skipped entirely.
    - daily_booking_limit: caps candidates per date (soonest-in-the-day
      first, since candidates are built in ascending time order) -- doesn't
      affect other dates."""
    session = get_session()
    doctor_row = session.execute(
        select(DoctorRow).where(DoctorRow.hospital_id == hospital_id, DoctorRow.id == doctor_id)
    ).scalar_one_or_none()
    if doctor_row is None:
        return []

    today = now or date.today()
    leave_dates = set(session.execute(
        select(DoctorLeave.date).where(DoctorLeave.hospital_id == hospital_id, DoctorLeave.doctor_id == doctor_id)
    ).scalars().all())

    candidates: list[str] = []
    for i in range(1, days_ahead + 1):
        d = today + timedelta(days=i)
        if d.isoformat() in leave_dates:
            continue
        pattern = _pattern_for_date(doctor_row, d)
        if pattern is None:
            continue
        working_days, working_hours, slot_duration, breaks, daily_booking_limit = pattern
        if _WEEKDAY_ABBREVS[d.weekday()] not in working_days:
            continue
        day_count = 0
        for time_range in working_hours:
            start_str, end_str = _parse_time_range(time_range)
            current = datetime.combine(d, datetime.strptime(start_str, "%H:%M").time())
            end = datetime.combine(d, datetime.strptime(end_str, "%H:%M").time())
            step = timedelta(minutes=slot_duration)
            while current + step <= end:
                if daily_booking_limit is not None and day_count >= daily_booking_limit:
                    break
                if not _overlaps_break(current, current + step, breaks, d):
                    candidates.append(current.isoformat())
                    day_count += 1
                current += step
    return candidates



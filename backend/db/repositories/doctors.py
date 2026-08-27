# db/repositories/doctors.py
"""Departments, doctors, and doctor-slot generation (Section 12.1/14.7).
Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1."""
import uuid
from datetime import date, datetime, timedelta
from typing import cast

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import CursorResult

from db.connection import get_connection, get_session
from db.orm_models import Department, DoctorRow, DoctorSlot

_SLOT_DAYS_AHEAD = 14

_WEEKDAY_ABBREVS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


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
    12.1 Step 7) -- generate_slots_for_doctor() is called immediately below to
    produce the initial rolling window of real doctor_slots rows from it
    (Section 12.1.1), so onboarding a doctor through this function is what
    "run slot generation at onboarding submission time" means in practice. A
    doctor with no working_days/working_hours simply generates zero slots.

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
    # generate_slots_for_doctor() is still raw-SQL/conn-based (see its own
    # docstring) -- not passed a conn here, same "already-committed, safe to
    # read from a different autocommit connection" reasoning as leave.py's
    # calls into it.
    generate_slots_for_doctor(hospital_id, doctor_id)
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

    Regenerates doctor_slots against the (possibly changed) working pattern,
    rather than trying to reconcile old vs. new slots row by row -- safe to do
    because doctor_slots carries no foreign key from appointments (get_slots()
    matches them only by scheduled_at string equality, see that function's
    docstring), so dropping and rebuilding a doctor's still-just-offered slots
    never touches an appointment a patient has already booked.

    Section 14.7: if effective_from is set, regeneration only touches slots
    dated on/after it -- any earlier still-unbooked slots (generated under
    this doctor's PREVIOUS pattern) are left exactly as they were, so a
    schedule change that's meant to start next month doesn't retroactively
    rewrite next week's already-offered slots. effective_from=None (the
    default, matching every doctor before this column existed) wipes and
    regenerates the whole window, same as before this change."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(DoctorRow)
        .where(DoctorRow.hospital_id == hospital_id, DoctorRow.id == doctor_id)
        .values(
            name=name, specialization=specialization, qualification=qualification, years_experience=years_experience,
            working_days=",".join(working_days or []), working_hours=",".join(working_hours or []),
            slot_duration_minutes=slot_duration_minutes, breaks=",".join(breaks or []),
            max_bookings_per_slot=max_bookings_per_slot, daily_booking_limit=daily_booking_limit,
            online_quota=online_quota, walkin_quota=walkin_quota,
            followup_duration_minutes=followup_duration_minutes, effective_from=effective_from,
        )
    ))
    if result.rowcount == 0:
        return None
    slot_delete = delete(DoctorSlot).where(DoctorSlot.hospital_id == hospital_id, DoctorSlot.doctor_id == doctor_id)
    if effective_from:
        slot_delete = slot_delete.where(DoctorSlot.scheduled_at >= effective_from)
    session.execute(slot_delete)
    session.commit()
    # generate_slots_for_doctor() is still raw-SQL/conn-based -- see
    # create_doctor()'s identical comment above.
    generate_slots_for_doctor(hospital_id, doctor_id)
    return {"id": doctor_id, "name": name}


def list_doctor_ids(hospital_id: int) -> list[str]:
    """Used by the slot top-up job (slots/scheduler.py) to loop every doctor
    at a hospital without needing to walk departments first."""
    session = get_session()
    rows = session.execute(select(DoctorRow.id).where(DoctorRow.hospital_id == hospital_id)).all()
    return [r.id for r in rows]


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


def generate_slots_for_doctor(
    hospital_id: int,
    doctor_id: str,
    days_ahead: int = _SLOT_DAYS_AHEAD,
    now: date | None = None,
    conn=None,
) -> int:
    """Generates real doctor_slots rows for the next `days_ahead` days (Section
    12.1.1) from this doctor's stored working_days/working_hours/
    slot_duration_minutes. ON CONFLICT DO NOTHING against doctor_slots' UNIQUE
    (doctor_id, scheduled_at) (db/schema.sql) is what makes this idempotent --
    calling it again for a window that's already partly populated (the
    periodic top-up job, slots/scheduler.py) only adds the new days, never
    duplicates existing ones. Returns the number of *new* slot rows inserted.

    Section 14.7 additions, all read from the same doctor row:
    - breaks: any candidate slot overlapping a break window (see
      _overlaps_break()) on that day is skipped entirely -- breaks apply
      uniformly to every working day, not a specific one (db/schema.sql's
      comment on doctors.breaks explains why).
    - doctor_leave: any date present there for this doctor is skipped
      entirely, no slots generated for it at all.
    - daily_booking_limit: once a given date would have this many candidate
      slots, generation stops for THAT date (soonest-in-the-day slots first,
      since candidates are already built in ascending time order) -- doesn't
      affect other dates.
    - effective_from: dates before it are skipped -- update_doctor() only
      deletes existing slots on/after this date (see its own docstring), so
      generating for earlier dates here would incorrectly add new-pattern
      slots alongside still-standing old-pattern ones.

    conn is an optional explicit connection (rather than get_connection())
    because db/seed.py calls this against a connection it's still assembling,
    before db.connection's shared connection has been repointed to it.

    Deliberately NOT migrated to get_session()/ORM along with the rest of
    this file: that conn override is exactly what makes db/seed.py's
    bootstrap-time call correct (a fresh, not-yet-global raw connection,
    per that file's own comment) -- get_session() has no equivalent notion
    of "a session bound to a connection that isn't the global one yet", and
    bridging a raw psycopg2 connection into a SQLAlchemy engine/session
    isn't worth the risk for a function this correctness-critical (it
    directly determines booking availability). create_doctor()/
    update_doctor() above call this WITHOUT conn=, so it falls back to its
    own get_connection() -- safe because both that raw connection and the
    ORM session's engine run in Postgres autocommit, so a write already
    committed by one is immediately visible to a read from the other, same
    reasoning verified for leave.py's identical pattern."""
    conn = conn or get_connection()
    doctor_row = conn.execute(
        "SELECT working_days, working_hours, slot_duration_minutes, breaks, daily_booking_limit, effective_from "
        "FROM doctors WHERE hospital_id = ? AND id = ?",
        (hospital_id, doctor_id),
    ).fetchone()
    if doctor_row is None:
        return 0

    working_days = {d.strip() for d in doctor_row["working_days"].split(",") if d.strip()}
    working_hours = [h.strip() for h in doctor_row["working_hours"].split(",") if h.strip()]
    slot_duration = doctor_row["slot_duration_minutes"]
    if not working_days or not working_hours or not slot_duration:
        return 0

    breaks = [_parse_time_range(b) for b in doctor_row["breaks"].split(",") if b.strip()] if doctor_row["breaks"] else []
    daily_booking_limit = doctor_row["daily_booking_limit"]
    effective_from = date.fromisoformat(doctor_row["effective_from"]) if doctor_row["effective_from"] else None

    today = now or date.today()
    leave_dates = {
        row["date"] for row in
        conn.execute("SELECT date FROM doctor_leave WHERE hospital_id = ? AND doctor_id = ?", (hospital_id, doctor_id)).fetchall()
    }

    candidates: list[tuple] = []
    for i in range(1, days_ahead + 1):
        d = today + timedelta(days=i)
        if _WEEKDAY_ABBREVS[d.weekday()] not in working_days:
            continue
        if effective_from and d < effective_from:
            continue
        if d.isoformat() in leave_dates:
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
                    candidates.append((hospital_id, doctor_id, current.isoformat()))
                    day_count += 1
                current += step

    if not candidates:
        return 0

    # One multi-row INSERT instead of one round-trip per slot -- this used to
    # be a per-slot conn.execute() in a loop, which against a real (non-local)
    # Postgres like Neon meant one network round-trip per slot: a doctor with
    # even a single ordinary shift over a 14-day window is 100+ slots, so
    # onboarding a hospital with a few doctors could take tens of seconds just
    # here. Building one INSERT with all rows' worth of "(?, ?, ?)" placeholders
    # (well within Postgres's ~65535 parameter limit for any realistic doctor
    # count/window) turns that into a single round-trip per doctor.
    placeholders = ", ".join(["(?, ?, ?)"] * len(candidates))
    flat_params = [value for row in candidates for value in row]
    cur = conn.execute(
        f"INSERT INTO doctor_slots (hospital_id, doctor_id, scheduled_at) VALUES {placeholders} "
        "ON CONFLICT (doctor_id, scheduled_at) DO NOTHING",
        flat_params,
    )
    inserted = cur.rowcount
    conn.commit()
    return inserted



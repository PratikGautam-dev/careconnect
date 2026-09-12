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

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import aliased

from db.connection import get_session
from db.orm_models import Department, DoctorLeave, DoctorRow, Identity, StaffDetail
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
    """The connector interface's own get_departments() (Section 12.6.2) --
    the WhatsApp bot's booking flow reads the department picker menu through
    this one function (connectors/tier1.py -> here), so filtering to
    is_active/show_on_frontend/whatsapp_booking_enabled here is the single
    enforcement point for "staff hid/deactivated this department" everywhere
    a patient could actually book, not just one call site. The portal's own
    department MANAGEMENT list uses get_all_departments_for_hospital()
    instead, which intentionally still shows hidden/inactive departments so
    staff can toggle them back on -- same is_active split as
    get_doctors()/get_all_doctors_for_hospital() above."""
    session = get_session()
    rows = session.execute(
        select(Department.id, Department.name)
        .where(
            Department.hospital_id == hospital_id, Department.is_active.is_(True),
            Department.show_on_frontend.is_(True), Department.whatsapp_booking_enabled.is_(True),
        )
        .order_by(Department.name)
    ).all()
    return [dict(r._mapping) for r in rows]


def get_all_departments_for_hospital(hospital_id: int) -> list[dict]:
    """Every department at this hospital, active or not, hidden or not --
    Settings -> Departments' own management list (deliberately NOT filtered
    the way get_departments() above is, same reasoning as
    get_all_doctors_for_hospital()). Carries the full profile plus two
    real, correlated-subquery counts (doctor_count from `doctors`,
    support_staff_count from `staff_details` -- already exclusively
    non-doctor rows there, enforced by ck_staff_details_department_doctor_
    role) and the head doctor's own name/qualification/phone/email via an
    outer join (None when head_doctor_id is unset). "Email" is the head
    doctor's own portal-login email (identities.email via staff_details --
    doctors.email was dropped in migration 20260911190251, every doctor
    login now goes through the unified staff login), so it's None for a
    head doctor with no portal login of their own, same as
    get_all_doctors_for_hospital()'s own login_email column."""
    session = get_session()
    head_doctor = aliased(DoctorRow)
    head_doctor_staff = aliased(StaffDetail)
    head_doctor_identity = aliased(Identity)
    doctor_count = (
        select(func.count(DoctorRow.id))
        .where(DoctorRow.department_id == Department.id, DoctorRow.hospital_id == hospital_id)
        .correlate(Department)
        .scalar_subquery()
    )
    support_staff_count = (
        select(func.count(StaffDetail.identity_id))
        .where(StaffDetail.department_id == Department.id, StaffDetail.hospital_id == hospital_id)
        .correlate(Department)
        .scalar_subquery()
    )
    rows = session.execute(
        select(
            Department.id, Department.name, Department.floor_wing, Department.consultation_hours,
            Department.description, Department.is_active, Department.show_on_frontend,
            Department.online_booking_enabled, Department.whatsapp_booking_enabled,
            Department.head_doctor_id,
            head_doctor.name.label("head_doctor_name"), head_doctor.qualification.label("head_doctor_qualification"),
            head_doctor.phone.label("head_doctor_phone"),
            head_doctor_identity.email.label("head_doctor_email"),
            doctor_count.label("doctor_count"), support_staff_count.label("support_staff_count"),
        )
        .outerjoin(head_doctor, head_doctor.id == Department.head_doctor_id)
        .outerjoin(head_doctor_staff, head_doctor_staff.doctor_id == head_doctor.id)
        .outerjoin(head_doctor_identity, head_doctor_identity.id == head_doctor_staff.identity_id)
        .where(Department.hospital_id == hospital_id)
        .order_by(Department.name)
    ).all()
    departments = []
    for r in rows:
        d = dict(r._mapping)
        head_doctor_id = d.pop("head_doctor_id")
        name = d.pop("head_doctor_name")
        qualification = d.pop("head_doctor_qualification")
        phone = d.pop("head_doctor_phone")
        email = d.pop("head_doctor_email")
        d["head_doctor"] = (
            {"id": head_doctor_id, "name": name, "qualification": qualification, "phone": phone, "email": email}
            if head_doctor_id else None
        )
        departments.append(d)
    return departments


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


def create_department(
    hospital_id: int, name: str,
    floor_wing: str | None = None, consultation_hours: str | None = None,
    description: str | None = None, head_doctor_id: str | None = None,
) -> dict:
    """id is a UUID-derived opaque string (not a slug of `name`), scoped by an
    h{hospital_id}_ prefix -- avoids both the collision risk of slugifying
    arbitrary user-entered text and the known Tier 1 limitation that
    departments.id is globally unique, not (hospital_id, id) composite-unique
    (db/schema.sql's comment on that table). Profile fields are all optional
    at creation (Settings -> Departments' Add Department dialog can fill
    them in later via update_department()) -- is_active/show_on_frontend/
    online_booking_enabled/whatsapp_booking_enabled all default true at the
    DB level, same as every other department."""
    department_id = f"h{hospital_id}_{uuid.uuid4().hex[:8]}"
    session = get_session()
    session.execute(insert(Department).values(
        id=department_id, hospital_id=hospital_id, name=name,
        floor_wing=floor_wing, consultation_hours=consultation_hours,
        description=description, head_doctor_id=head_doctor_id,
    ))
    session.commit()
    return {"id": department_id, "name": name}


def update_department(
    hospital_id: int, department_id: str, name: str,
    floor_wing: str | None, consultation_hours: str | None,
    description: str | None, head_doctor_id: str | None,
) -> bool:
    """Edit Department -- returns False if no matching department row
    exists for this hospital, True on a real update, same contract as
    set_doctor_active()/update_doctor() above."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(Department).where(Department.hospital_id == hospital_id, Department.id == department_id).values(
            name=name, floor_wing=floor_wing, consultation_hours=consultation_hours,
            description=description, head_doctor_id=head_doctor_id,
        )
    ))
    session.commit()
    return result.rowcount > 0


def set_department_active(hospital_id: int, department_id: str, is_active: bool) -> bool:
    """Deactivate/Activate Department quick action -- same contract as
    set_doctor_active() above. Deactivating does NOT clear show_on_frontend/
    whatsapp_booking_enabled -- get_departments() already ANDs is_active in,
    so a deactivated department is hidden from the WhatsApp picker
    regardless of those two flags' own state, and re-activating restores
    whatever visibility it had before without the staff needing to re-set
    it."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(Department).where(Department.hospital_id == hospital_id, Department.id == department_id)
        .values(is_active=is_active)
    ))
    session.commit()
    return result.rowcount > 0


def set_department_visibility(
    hospital_id: int, department_id: str,
    show_on_frontend: bool, online_booking_enabled: bool, whatsapp_booking_enabled: bool,
) -> bool:
    """The Department Details panel's "Patient-Facing Availability" toggles.
    show_on_frontend/whatsapp_booking_enabled both feed directly into
    get_departments()'s filter (the WhatsApp department picker, this app's
    one real patient channel) -- online_booking_enabled is stored/returned
    but not read by get_departments() or anywhere else yet, since no
    separate online booking channel exists in this codebase to gate
    (confirmed with the user; forward-compatible schema, not dead code)."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(Department).where(Department.hospital_id == hospital_id, Department.id == department_id).values(
            show_on_frontend=show_on_frontend, online_booking_enabled=online_booking_enabled,
            whatsapp_booking_enabled=whatsapp_booking_enabled,
        )
    ))
    session.commit()
    return result.rowcount > 0


def create_doctor(
    hospital_id: int,
    department_id: str,
    name: str,
    specialization: str = "",
    qualification: str = "",
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
    phone: str = "",
    employee_id: str = "",
    location: str | None = None,
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
    doctor (nothing to preserve yet) -- it only matters on update_doctor().

    specialization/qualification/phone/employee_id default to "" (not None)
    since migration 20260911190007 made all four NOT NULL -- the Doctors
    page's own Add/Edit form (admin/validation.py's _validate_doctor_fields)
    is what actually requires a real value; callers that don't collect these
    at all (CSV import defaults aside, onboarding, tests) still work
    unchanged, just persisting an empty string instead of NULL."""
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
            phone=phone, employee_id=employee_id, location=location,
        )
    )
    session.commit()
    return {"id": doctor_id, "name": name}


_DOCTOR_FULL_COLUMNS = (
    DoctorRow.id, DoctorRow.department_id, DoctorRow.name, DoctorRow.specialization, DoctorRow.qualification,
    DoctorRow.years_experience, DoctorRow.working_days, DoctorRow.working_hours, DoctorRow.slot_duration_minutes,
    DoctorRow.breaks, DoctorRow.max_bookings_per_slot, DoctorRow.daily_booking_limit, DoctorRow.online_quota,
    DoctorRow.walkin_quota, DoctorRow.followup_duration_minutes, DoctorRow.effective_from, DoctorRow.is_active,
    DoctorRow.phone, DoctorRow.employee_id, DoctorRow.location,
)


def get_doctor_full(hospital_id: int, doctor_id: str) -> dict | None:
    """Every column, not just {id, name} like get_doctors()/find_doctor() --
    portal.py's doctor-edit form (Section 12.7 follow-up: self-serve doctor
    management) needs the full working pattern to pre-fill, and needs
    department_id from the doctor_id alone (the edit URL only carries the
    doctor's id, not which department it's under).

    Also carries this doctor's unified-login status via an outer join to
    staff_details/identities (login_staff_id/login_email/login_active are
    all None when no staff_details row is linked to this doctor_id yet) --
    the Doctors page's detail panel uses this to show "Create login" vs the
    real login state, replacing the old dedicated doctors.email/password_hash
    columns (migration 20260912xxxxxx dropped them, see its own docstring)."""
    session = get_session()
    row = session.execute(
        select(
            *_DOCTOR_FULL_COLUMNS,
            Identity.id.label("login_staff_id"), Identity.email.label("login_email"),
            Identity.is_active.label("login_active"),
        )
        .outerjoin(StaffDetail, StaffDetail.doctor_id == DoctorRow.id)
        .outerjoin(Identity, Identity.id == StaffDetail.identity_id)
        .where(DoctorRow.hospital_id == hospital_id, DoctorRow.id == doctor_id)
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
    back on; get_doctors() is the one that hides them from bookable lists.

    Carries qualification/years_experience/working_days/working_hours too
    (same query, no extra round trip) -- the doctors list page's own table +
    detail panel need these, and get_doctor_full() below is a separate
    per-doctor fetch this list intentionally avoids doing 1-per-row.

    Also outer-joins this doctor's unified-login status (staff_details/
    identities, doctor_id-linked) -- login_staff_id/login_email/login_active
    are all None when this doctor has no staff login yet. See
    get_doctor_full()'s own docstring for why (replaces the old dedicated
    doctors.email/password_hash columns)."""
    session = get_session()
    rows = session.execute(
        select(
            DoctorRow.id, DoctorRow.department_id, Department.name.label("department_name"),
            DoctorRow.name, DoctorRow.specialization, DoctorRow.is_active,
            DoctorRow.qualification, DoctorRow.years_experience,
            DoctorRow.working_days, DoctorRow.working_hours,
            DoctorRow.phone, DoctorRow.employee_id, DoctorRow.location,
            Identity.id.label("login_staff_id"), Identity.email.label("login_email"),
            Identity.is_active.label("login_active"),
        )
        .join(Department, Department.id == DoctorRow.department_id)
        .outerjoin(StaffDetail, StaffDetail.doctor_id == DoctorRow.id)
        .outerjoin(Identity, Identity.id == StaffDetail.identity_id)
        .where(DoctorRow.hospital_id == hospital_id)
        .order_by(Department.name, DoctorRow.name)
    ).all()
    doctors = [dict(r._mapping) for r in rows]
    for d in doctors:
        d["working_days"] = [x for x in d["working_days"].split(",") if x]
        d["working_hours"] = [x for x in d["working_hours"].split(",") if x]
    return doctors


def get_doctors_on_leave_today_count(hospital_id: int, today: date | None = None) -> int:
    """Doctors list page's "On leave" stat tile -- distinct doctors with a
    doctor_leave row for today's date (Section 14.7's whole-day leave)."""
    session = get_session()
    today = today or date.today()
    return session.execute(
        select(func.count(func.distinct(DoctorLeave.doctor_id)))
        .where(DoctorLeave.hospital_id == hospital_id, DoctorLeave.date == today.isoformat())
    ).scalar_one()


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
    specialization: str = "",
    qualification: str = "",
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
    phone: str = "",
    employee_id: str = "",
    location: str | None = None,
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
        "phone": phone, "employee_id": employee_id, "location": location,
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



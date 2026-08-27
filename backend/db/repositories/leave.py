# db/repositories/leave.py
"""Doctor whole-day leave (Section 14.7). Split out of db/repository.py --
see ARCHITECTURE_PLAN.md Phase 1."""
from datetime import date, timedelta

from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from db.connection import get_session
from db.orm_models import DoctorLeave, DoctorSlot
from db.repositories.doctors import generate_slots_for_doctor

# --- Doctor leave (Section 14.7 -- whole-day unavailability) ---

def get_doctor_leave(hospital_id: int, doctor_id: str) -> list[dict]:
    session = get_session()
    rows = session.execute(
        select(DoctorLeave.id, DoctorLeave.date, DoctorLeave.reason)
        .where(DoctorLeave.hospital_id == hospital_id, DoctorLeave.doctor_id == doctor_id)
        .order_by(DoctorLeave.date)
    ).all()
    return [dict(r._mapping) for r in rows]


def create_doctor_leave(hospital_id: int, doctor_id: str, leave_date: str, reason: str | None = None) -> dict:
    """leave_date is an ISO 'YYYY-MM-DD' string, matching doctor_slots'/
    appointments' own "store dates/datetimes as ISO text" convention.
    UNIQUE(doctor_id, date) (db/schema.sql) makes re-adding the same date
    harmless -- ON CONFLICT DO NOTHING rather than erroring, since a staff
    member re-submitting a date they already marked isn't a real problem.
    Regenerates this doctor's slots immediately so the new leave date takes
    effect right away, not just on the next periodic top-up.

    generate_slots_for_doctor() (doctors.py) deliberately stayed raw-SQL/
    conn-based even after the rest of that file migrated (see its own
    docstring -- db/seed.py's bootstrap-time conn override), so it isn't
    passed this function's session (unlike the original raw conn, which WAS
    passed through) -- it falls back to its own get_connection() instead.
    Safe because session.commit() below runs first: the DELETE is durably
    visible to any other connection by the time generate_slots_for_doctor()
    reads doctor_slots, exactly as it was when the original code passed the
    same (but already-committed, autocommit=True) conn through."""
    session = get_session()
    session.execute(
        pg_insert(DoctorLeave)
        .values(hospital_id=hospital_id, doctor_id=doctor_id, date=leave_date, reason=reason)
        .on_conflict_do_nothing(index_elements=["doctor_id", "date"])
    )
    session.execute(
        delete(DoctorSlot).where(
            DoctorSlot.hospital_id == hospital_id, DoctorSlot.doctor_id == doctor_id,
            DoctorSlot.scheduled_at >= leave_date,
        )
    )
    session.commit()
    generate_slots_for_doctor(hospital_id, doctor_id)
    return {"date": leave_date, "reason": reason}


_MAX_LEAVE_RANGE_DAYS = 366


def create_doctor_leave_range(
    hospital_id: int, doctor_id: str, from_date: str, to_date: str, reason: str | None = None,
) -> list[str]:
    """Item 10 (Spec.md Section 0): From/To range with one Confirm, instead
    of adding leave dates one at a time. Composes with the existing
    exclusion logic unchanged -- generate_slots_for_doctor() (Section 14.7)
    already skips any date present in doctor_leave, so a doctor
    automatically shows as unavailable for booking across the whole range
    the moment these rows exist and slots regenerate below; no SEPARATE
    availability-toggle mechanism is needed (a global is_active flip would
    be wrong here anyway -- it isn't date-scoped, so it would incorrectly
    block booking outside the leave range too). Regenerates slots ONCE after
    inserting every date in the range, not once per date (create_doctor_leave()'s
    own per-call regeneration would be wasteful looped N times here)."""
    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)
    if end < start:
        raise ValueError("to_date must not be before from_date.")
    if (end - start).days + 1 > _MAX_LEAVE_RANGE_DAYS:
        raise ValueError(f"Leave range cannot exceed {_MAX_LEAVE_RANGE_DAYS} days.")

    session = get_session()
    created_dates = []
    d = start
    while d <= end:
        iso = d.isoformat()
        session.execute(
            pg_insert(DoctorLeave)
            .values(hospital_id=hospital_id, doctor_id=doctor_id, date=iso, reason=reason)
            .on_conflict_do_nothing(index_elements=["doctor_id", "date"])
        )
        created_dates.append(iso)
        d += timedelta(days=1)
    session.execute(
        delete(DoctorSlot).where(
            DoctorSlot.hospital_id == hospital_id, DoctorSlot.doctor_id == doctor_id,
            DoctorSlot.scheduled_at >= start.isoformat(),
        )
    )
    session.commit()
    generate_slots_for_doctor(hospital_id, doctor_id)
    return created_dates


def delete_doctor_leave(hospital_id: int, doctor_id: str, leave_id: int) -> bool:
    """Returns False if no such leave row exists for this doctor/hospital
    (nothing deleted) -- same hospital_id-scoped-guard discipline as every
    other write here. Regenerates slots so the now-freed date becomes
    bookable again immediately."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        delete(DoctorLeave).where(
            DoctorLeave.id == leave_id, DoctorLeave.hospital_id == hospital_id, DoctorLeave.doctor_id == doctor_id,
        )
    ))
    if result.rowcount == 0:
        session.commit()  # nothing changed, but closes out this statement's implicit transaction
        return False
    session.commit()
    generate_slots_for_doctor(hospital_id, doctor_id)
    return True



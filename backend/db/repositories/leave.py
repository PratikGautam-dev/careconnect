# db/repositories/leave.py
"""Doctor whole-day leave (Section 14.7). Split out of db/repository.py --
see ARCHITECTURE_PLAN.md Phase 1."""
from datetime import date, timedelta

from db.connection import get_connection
from db.repositories.doctors import generate_slots_for_doctor

# --- Doctor leave (Section 14.7 -- whole-day unavailability) ---

def get_doctor_leave(hospital_id: int, doctor_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, date, reason FROM doctor_leave WHERE hospital_id = ? AND doctor_id = ? ORDER BY date",
        (hospital_id, doctor_id),
    ).fetchall()
    return [dict(r) for r in rows]


def create_doctor_leave(hospital_id: int, doctor_id: str, leave_date: str, reason: str | None = None) -> dict:
    """leave_date is an ISO 'YYYY-MM-DD' string, matching doctor_slots'/
    appointments' own "store dates/datetimes as ISO text" convention.
    UNIQUE(doctor_id, date) (db/schema.sql) makes re-adding the same date
    harmless -- ON CONFLICT DO NOTHING rather than erroring, since a staff
    member re-submitting a date they already marked isn't a real problem.
    Regenerates this doctor's slots immediately so the new leave date takes
    effect right away, not just on the next periodic top-up."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO doctor_leave (hospital_id, doctor_id, date, reason) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (doctor_id, date) DO NOTHING",
        (hospital_id, doctor_id, leave_date, reason),
    )
    conn.execute("DELETE FROM doctor_slots WHERE hospital_id = ? AND doctor_id = ? AND scheduled_at >= ?",
                 (hospital_id, doctor_id, leave_date))
    conn.commit()
    generate_slots_for_doctor(hospital_id, doctor_id, conn=conn)
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

    conn = get_connection()
    created_dates = []
    d = start
    while d <= end:
        iso = d.isoformat()
        conn.execute(
            "INSERT INTO doctor_leave (hospital_id, doctor_id, date, reason) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (doctor_id, date) DO NOTHING",
            (hospital_id, doctor_id, iso, reason),
        )
        created_dates.append(iso)
        d += timedelta(days=1)
    conn.execute(
        "DELETE FROM doctor_slots WHERE hospital_id = ? AND doctor_id = ? AND scheduled_at >= ?",
        (hospital_id, doctor_id, start.isoformat()),
    )
    conn.commit()
    generate_slots_for_doctor(hospital_id, doctor_id, conn=conn)
    return created_dates


def delete_doctor_leave(hospital_id: int, doctor_id: str, leave_id: int) -> bool:
    """Returns False if no such leave row exists for this doctor/hospital
    (nothing deleted) -- same hospital_id-scoped-guard discipline as every
    other write here. Regenerates slots so the now-freed date becomes
    bookable again immediately."""
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM doctor_leave WHERE id = ? AND hospital_id = ? AND doctor_id = ?",
        (leave_id, hospital_id, doctor_id),
    )
    if cur.rowcount == 0:
        return False
    conn.commit()
    generate_slots_for_doctor(hospital_id, doctor_id, conn=conn)
    return True



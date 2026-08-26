# db/repositories/appointments.py
"""Appointment booking, cancellation, rescheduling, and lookups -- the core
booking data path both the WhatsApp flow and the staff portal go through.
Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1."""
from datetime import datetime, timedelta

from db.connection import IntegrityError, get_connection
from db.models import (
    Appointment, DuplicateBookingError, QuotaExceededError,
    SOURCE_WHATSAPP, STATUS_ATTENDED, STATUS_BOOKED, STATUS_CANCELLED, STATUS_NO_SHOW, STATUS_RESCHEDULED,
    _APPOINTMENT_SELECT, _generate_patient_display_id, _generate_reference_id, _row_to_appointment,
)

# --- Appointments ---

def _upsert_patient(conn, hospital_id: int, phone: str, name: str | None, age: int | None = None) -> dict:
    """Keeps `patients` in sync on every booking. name/age passed in wins;
    missing ones keep the existing value (never clobbered to NULL). Returns
    {id, name, age, patient_display_id} -- the display id is only generated
    once, on first creation.

    No UNIQUE(hospital_id, phone) constraint anymore (multi-profile support),
    so this is an explicit lookup-then-update-or-insert guarded by a session-
    level advisory lock (scoped to hospital_id+phone) instead of an upsert.
    If more than one `patients` row already exists for this phone, updates
    the oldest one -- the original single-profile-per-phone row."""
    conn.execute("SELECT pg_advisory_lock(hashtext(?))", (f"upsert_patient|{hospital_id}|{phone}",))
    try:
        existing = conn.execute(
            "SELECT id, name, age, patient_display_id FROM patients "
            "WHERE hospital_id = ? AND phone = ? ORDER BY id LIMIT 1",
            (hospital_id, phone),
        ).fetchone()
        if existing is not None:
            resolved_name = name if name is not None else existing["name"]
            resolved_age = age if age is not None else existing["age"]
            conn.execute(
                "UPDATE patients SET name = ?, age = ? WHERE id = ?",
                (resolved_name, resolved_age, existing["id"]),
            )
            return {
                "id": existing["id"], "name": resolved_name, "age": resolved_age,
                "patient_display_id": existing["patient_display_id"],
            }
        row = conn.execute(
            "INSERT INTO patients (hospital_id, phone, name, age) VALUES (?, ?, ?, ?) RETURNING id, name, age",
            (hospital_id, phone, name, age),
        ).fetchone()
        assert row is not None  # INSERT ... RETURNING always returns the inserted row
        display_id = _generate_patient_display_id(conn, hospital_id)
        conn.execute("UPDATE patients SET patient_display_id = ? WHERE id = ?", (display_id, row["id"]))
        return {"id": row["id"], "name": row["name"], "age": row["age"], "patient_display_id": display_id}
    finally:
        conn.execute("SELECT pg_advisory_unlock(hashtext(?))", (f"upsert_patient|{hospital_id}|{phone}",))


def create_appointment(
    hospital_id: int,
    phone: str,
    department_id: str,
    doctor_id: str,
    scheduled_at: datetime,
    source: str = SOURCE_WHATSAPP,
    patient_name: str | None = None,
    patient_age: int | None = None,
    patient_id: int | None = None,
    exclude_appointment_id: int | None = None,
    appointment_type_id: str | None = None,
    consent_given_at: str | None = None,
) -> Appointment:
    """Raises IntegrityError if the doctor's slot capacity (max_bookings_per_slot)
    is full at scheduled_at, or the more specific QuotaExceededError if the
    doctor's daily_booking_limit or the source's online/walkin quota is
    exhausted for that date.

    `source` ("whatsapp"/"staff") is purely descriptive except for which
    quota column it counts against. `patient_id`, when given, resolves
    identity directly from that patient row (skips _upsert_patient) and the
    duplicate-booking check compares patient_id instead of name+age.
    `exclude_appointment_id` excludes the old appointment from the duplicate
    check during a reschedule -- it's still 'booked' at this point, and
    would otherwise self-block against the very appointment being replaced.

    Uses an advisory transaction lock per (doctor_id, date) to serialize
    quota checks + ordinal assignment against concurrent bookings, inside a
    real BEGIN/COMMIT/ROLLBACK block -- the one multi-statement transaction
    on the shared connection in this file (every other function here relies
    on autocommit). No retry-on-conflict inside it: once any statement in an
    explicit Postgres transaction fails, the whole transaction is aborted, so
    retrying with more statements would raise a wrong-typed error instead of
    the real IntegrityError/QuotaExceededError (see
    tests/test_create_appointment_transaction_safety.py)."""
    conn = get_connection()
    scheduled_at_iso = scheduled_at.isoformat()
    scheduled_date = scheduled_at.date()
    day_start = datetime.combine(scheduled_date, datetime.min.time()).isoformat()
    day_end = datetime.combine(scheduled_date, datetime.max.time()).isoformat()

    doctor_row = conn.execute(
        "SELECT max_bookings_per_slot, daily_booking_limit, online_quota, walkin_quota "
        "FROM doctors WHERE hospital_id = ? AND id = ?",
        (hospital_id, doctor_id),
    ).fetchone()
    max_bookings_per_slot = doctor_row["max_bookings_per_slot"] if doctor_row else 1
    daily_booking_limit = doctor_row["daily_booking_limit"] if doctor_row else None
    source_quota = None
    if doctor_row:
        source_quota = doctor_row["online_quota"] if source == SOURCE_WHATSAPP else doctor_row["walkin_quota"]

    # _upsert_patient runs BEFORE "BEGIN" (own durable statement) so a
    # QuotaExceededError/DuplicateBookingError later doesn't roll it back too.
    # patient_id given -> identity already resolved, read that row directly.
    if patient_id is not None:
        patient_row = conn.execute(
            "SELECT id, name, age FROM patients WHERE hospital_id = ? AND id = ?",
            (hospital_id, patient_id),
        ).fetchone()
        if patient_row is None:
            raise ValueError(f"patient_id {patient_id} not found for hospital {hospital_id}")
        patient = {"id": patient_row["id"], "name": patient_row["name"], "age": patient_row["age"]}
    else:
        patient = _upsert_patient(conn, hospital_id, phone, patient_name, patient_age)

    conn.execute("BEGIN")
    try:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext(?))",
            (f"{doctor_id}|{scheduled_date.isoformat()}",),
        )

        if daily_booking_limit is not None:
            day_count_row = conn.execute(
                "SELECT COUNT(*) AS c FROM appointments WHERE hospital_id = ? AND doctor_id = ? "
                "AND scheduled_at >= ? AND scheduled_at <= ? AND status = ?",
                (hospital_id, doctor_id, day_start, day_end, STATUS_BOOKED),
            ).fetchone()
            assert day_count_row is not None  # COUNT(*) with no GROUP BY always returns one row
            if day_count_row["c"] >= daily_booking_limit:
                raise QuotaExceededError("This doctor has reached today's booking limit.")

        if source_quota is not None:
            source_count_row = conn.execute(
                "SELECT COUNT(*) AS c FROM appointments WHERE hospital_id = ? AND doctor_id = ? "
                "AND scheduled_at >= ? AND scheduled_at <= ? AND status = ? AND source = ?",
                (hospital_id, doctor_id, day_start, day_end, STATUS_BOOKED, source),
            ).fetchone()
            assert source_count_row is not None
            if source_count_row["c"] >= source_quota:
                kind = "Online booking" if source == SOURCE_WHATSAPP else "Walk-in"
                raise QuotaExceededError(f"{kind} quota full for this doctor today.")

        # Smallest booking_ordinal in [0, max_bookings_per_slot) not already
        # taken by a booked row -- not a plain COUNT(*), since cancellations
        # leave gaps in the ordinal sequence rather than freeing them.
        free_ordinal_row = conn.execute(
            "SELECT MIN(o) AS ordinal FROM generate_series(0, ? - 1) AS o "
            "WHERE o NOT IN (SELECT booking_ordinal FROM appointments WHERE hospital_id = ? "
            "AND doctor_id = ? AND scheduled_at = ? AND status = ?)",
            (max_bookings_per_slot, hospital_id, doctor_id, scheduled_at_iso, STATUS_BOOKED),
        ).fetchone()
        assert free_ordinal_row is not None  # MIN() with no GROUP BY always returns one row
        if free_ordinal_row["ordinal"] is None:
            raise IntegrityError(f"doctor {doctor_id} has no free booking slot at {scheduled_at_iso}")

        # Prevents an accidental/duplicate re-booking with the same doctor.
        # patient_id given -> exact check against that patient's own active
        # appointments; otherwise (legacy/staff) falls back to name+age.
        effective_name = patient["name"]
        effective_age = patient["age"]
        if patient_id is not None:
            existing_by_patient = conn.execute(
                "SELECT id FROM appointments WHERE hospital_id = ? AND doctor_id = ? "
                "AND patient_id = ? AND status = ? AND id IS DISTINCT FROM ? ORDER BY scheduled_at",
                (hospital_id, doctor_id, patient_id, STATUS_BOOKED, exclude_appointment_id),
            ).fetchall()
            if existing_by_patient:
                raise DuplicateBookingError(
                    "An active appointment with this doctor already exists for this patient.",
                    existing_by_patient[0]["id"],
                )
        elif effective_name is not None and effective_age is not None:
            # Legacy path (staff portal, no patient_id): compare against
            # each existing booking's own denormalized name/age, so a
            # different family member (different name or age) still gets through.
            existing_appointments = conn.execute(
                "SELECT id, patient_name, patient_age FROM appointments WHERE hospital_id = ? AND phone = ? "
                "AND doctor_id = ? AND status = ? AND id IS DISTINCT FROM ? ORDER BY scheduled_at",
                (hospital_id, phone, doctor_id, STATUS_BOOKED, exclude_appointment_id),
            ).fetchall()
            for existing_appt in existing_appointments:
                same_name = (existing_appt["patient_name"] or "").strip().lower() == effective_name.strip().lower()
                same_age = existing_appt["patient_age"] == effective_age
                if same_name and same_age:
                    raise DuplicateBookingError(
                        "An active appointment with this doctor already exists for this patient.", existing_appt["id"],
                    )

        # No retry-on-conflict: under the lock this INSERT can't lose a race,
        # and a second statement after a failed one would fail with "current
        # transaction is aborted" instead of the real IntegrityError.
        cur = conn.execute(
            "INSERT INTO appointments (hospital_id, phone, department_id, doctor_id, scheduled_at, "
            "booking_ordinal, source, reference_id, patient_id, patient_name, patient_phone, patient_age, "
            "appointment_type_id, consent_given_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (hospital_id, phone, department_id, doctor_id, scheduled_at_iso, free_ordinal_row["ordinal"], source,
             _generate_reference_id(conn, hospital_id), patient["id"], patient["name"], phone, effective_age,
             appointment_type_id, consent_given_at),
        )
        new_id_row = cur.fetchone()
        assert new_id_row is not None  # INSERT ... RETURNING always returns the inserted row
        new_id = new_id_row["id"]

        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise

    created = get_appointment(hospital_id, new_id)
    assert created is not None  # the row was just committed above
    return created


def get_appointment(hospital_id: int, appointment_id: int) -> Appointment | None:
    conn = get_connection()
    row = conn.execute(
        _APPOINTMENT_SELECT + " AND a.id = ? AND a.hospital_id = ?",
        (appointment_id, hospital_id),
    ).fetchone()
    return _row_to_appointment(row) if row else None


def get_upcoming_appointments_for_phone(hospital_id: int, phone: str, now: datetime | None = None) -> list[Appointment]:
    """A patient's own future, still-booked appointments — soonest first.
    Past appointments and ones already cancelled/rescheduled are excluded here
    (not filtered later) so callers never have to remember to check status."""
    now = now or datetime.now()
    conn = get_connection()
    rows = conn.execute(
        _APPOINTMENT_SELECT + " AND a.hospital_id = ? AND a.phone = ? AND a.status = ? AND a.scheduled_at > ? "
        "ORDER BY a.scheduled_at ASC",
        (hospital_id, phone, STATUS_BOOKED, now.isoformat()),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]


def get_active_appointments_for_patient(hospital_id: int, patient_id: int) -> list[Appointment]:
    """All still-booked appointments for this patient_id (not phone --
    one phone can have several linked patients). Any time window."""
    conn = get_connection()
    rows = conn.execute(
        _APPOINTMENT_SELECT + " AND a.hospital_id = ? AND a.patient_id = ? AND a.status = ? ORDER BY a.scheduled_at ASC",
        (hospital_id, patient_id, STATUS_BOOKED),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]


def get_last_attended_appointment(hospital_id: int, patient_id: int) -> Appointment | None:
    """Most recent STATUS_ATTENDED appointment -- a no-show or a still-
    upcoming booking doesn't count."""
    conn = get_connection()
    row = conn.execute(
        _APPOINTMENT_SELECT + " AND a.hospital_id = ? AND a.patient_id = ? AND a.status = ? "
        "ORDER BY a.scheduled_at DESC LIMIT 1",
        (hospital_id, patient_id, STATUS_ATTENDED),
    ).fetchone()
    return _row_to_appointment(row) if row else None


def get_upcoming_appointments(hospital_id: int, offset_hours: float, now: datetime | None = None) -> list[Appointment]:
    """Still-booked appointments in [now, now+offset_hours] with no reminder
    sent yet for this specific offset -- a hospital can configure multiple
    offsets (e.g. 24h and 1h before), each tracked independently."""
    now = now or datetime.now()
    cutoff = now + timedelta(hours=offset_hours)
    conn = get_connection()
    rows = conn.execute(
        _APPOINTMENT_SELECT + """
        AND a.hospital_id = ? AND a.status = ?
          AND a.scheduled_at >= ? AND a.scheduled_at <= ?
          AND NOT EXISTS (
              SELECT 1 FROM appointment_reminders ar
              WHERE ar.appointment_id = a.id AND ar.offset_hours = ?
          )
        ORDER BY a.scheduled_at ASC
        """,
        (hospital_id, STATUS_BOOKED, now.isoformat(), cutoff.isoformat(), offset_hours),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]


def get_all_appointments_for_hospital(hospital_id: int, limit: int = 500) -> list[Appointment]:
    """Every appointment (any status) for the hospital's own dashboard --
    unlike the other lookups here, not filtered to booked/future-only."""
    conn = get_connection()
    rows = conn.execute(
        _APPOINTMENT_SELECT + " AND a.hospital_id = ? ORDER BY a.scheduled_at DESC LIMIT ?",
        (hospital_id, limit),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]


def soft_delete_appointment(hospital_id: int, appointment_id: int) -> bool:
    """Stamps deleted_at rather than removing the row (never hard-delete).
    Restricted to already-resolved appointments (status != 'booked') --
    an active booking must be cancelled first, not deleted out from under
    the patient."""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE appointments SET deleted_at = ? WHERE id = ? AND hospital_id = ? AND status != ? AND deleted_at IS NULL",
        (datetime.now().isoformat(), appointment_id, hospital_id, STATUS_BOOKED),
    )
    conn.commit()
    return cur.rowcount > 0


def get_total_bookings_count() -> int:
    """Platform-admin lifetime usage stat: every row ever inserted, any
    status, including soft-deleted (deliberately not built on
    _APPOINTMENT_SELECT, which excludes those). A reschedule counts as a
    2nd use -- it's a separate INSERT."""
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) AS c FROM appointments").fetchone()
    assert row is not None  # COUNT(*) with no GROUP BY always returns one row
    return row["c"]


def get_doctor_appointments_today(hospital_id: int, doctor_id: str, now: datetime | None = None) -> list[Appointment]:
    """A doctor's own appointments today, any status (full picture, not
    just still-booked)."""
    now = now or datetime.now()
    day_start = datetime.combine(now.date(), datetime.min.time()).isoformat()
    day_end = datetime.combine(now.date(), datetime.max.time()).isoformat()
    conn = get_connection()
    rows = conn.execute(
        _APPOINTMENT_SELECT + " AND a.hospital_id = ? AND a.doctor_id = ? AND a.scheduled_at >= ? AND a.scheduled_at <= ? "
        "ORDER BY a.scheduled_at ASC",
        (hospital_id, doctor_id, day_start, day_end),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]


def mark_reminded(hospital_id: int, appointment_id: int, offset_hours: float) -> None:
    """Records that this offset's reminder was sent. ON CONFLICT DO NOTHING
    makes calling this twice for the same offset a safe no-op."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO appointment_reminders (hospital_id, appointment_id, offset_hours) VALUES (?, ?, ?) "
        "ON CONFLICT (appointment_id, offset_hours) DO NOTHING",
        (hospital_id, appointment_id, offset_hours),
    )
    conn.commit()


def get_reminded_offsets(hospital_id: int, appointment_id: int) -> list[float]:
    """Which reminder offsets (in hours) have already fired for this appointment."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT offset_hours FROM appointment_reminders WHERE hospital_id = ? AND appointment_id = ? ORDER BY offset_hours DESC",
        (hospital_id, appointment_id),
    ).fetchall()
    return [r["offset_hours"] for r in rows]


def cancel_appointment(hospital_id: int, appointment_id: int) -> None:
    """Marks cancelled, doesn't delete the row. Stamps updated_at so the
    dashboard's activity feed reflects when this happened."""
    conn = get_connection()
    conn.execute(
        "UPDATE appointments SET status = ?, updated_at = ? WHERE id = ? AND hospital_id = ?",
        (STATUS_CANCELLED, datetime.now().isoformat(), appointment_id, hospital_id),
    )
    conn.commit()


def mark_rescheduled(hospital_id: int, appointment_id: int) -> None:
    """Marks the old appointment superseded by a reschedule -- doesn't
    delete the row. Caller books the new slot separately via create_appointment()."""
    conn = get_connection()
    conn.execute(
        "UPDATE appointments SET status = ?, updated_at = ? WHERE id = ? AND hospital_id = ?",
        (STATUS_RESCHEDULED, datetime.now().isoformat(), appointment_id, hospital_id),
    )
    conn.commit()


def mark_attendance(hospital_id: int, appointment_id: int, attended: bool) -> bool:
    """Staff-confirmed attended/no_show, replacing the dashboard's no-show
    heuristic. Freely re-toggleable (booked/attended/no_show), any time --
    not allowed from 'cancelled'/'rescheduled' (those never happened)."""
    conn = get_connection()
    new_status = STATUS_ATTENDED if attended else STATUS_NO_SHOW
    cur = conn.execute(
        "UPDATE appointments SET status = ?, updated_at = ? WHERE id = ? AND hospital_id = ? "
        "AND status IN (?, ?, ?)",
        (new_status, datetime.now().isoformat(), appointment_id, hospital_id,
         STATUS_BOOKED, STATUS_ATTENDED, STATUS_NO_SHOW),
    )
    conn.commit()
    return cur.rowcount > 0


def get_appointments_needing_attendance_review(hospital_id: int, now: datetime | None = None) -> list["Appointment"]:
    """Still 'booked' but scheduled_at has passed -- for staff to resolve
    via mark_attendance()."""
    now = now or datetime.now()
    conn = get_connection()
    rows = conn.execute(
        _APPOINTMENT_SELECT + " AND a.hospital_id = ? AND a.status = ? AND a.scheduled_at < ? ORDER BY a.scheduled_at DESC",
        (hospital_id, STATUS_BOOKED, now.isoformat()),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]



# db/repositories/appointments.py
"""Appointment booking, cancellation, rescheduling, and lookups -- the core
booking data path both the WhatsApp flow and the staff portal go through.
Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1."""
from datetime import datetime, timedelta
from typing import cast

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from db.connection import IntegrityError, get_connection, get_session
from db.models import (
    Appointment, DuplicateBookingError, QuotaExceededError,
    SOURCE_WHATSAPP, STATUS_ATTENDED, STATUS_BOOKED, STATUS_CANCELLED, STATUS_NO_SHOW, STATUS_RESCHEDULED,
    _generate_patient_identifiers, _generate_reference_id, _row_to_appointment,
)
from db.orm_models import AppointmentReminder, AppointmentRow, Department, DoctorRow, PatientRow


def _appointment_select_stmt():
    """ORM equivalent of db/models.py's _APPOINTMENT_SELECT -- the shared
    JOIN every appointment read here (and patient_records.py's
    get_patient_visit_history()) builds on. Callers append their own
    .where()/.order_by()/.limit(), same as callers of the raw SQL constant
    append "AND ...". _row_to_appointment() (db/models.py) maps a result row
    (via row._mapping) onto the Appointment dataclass unchanged -- it only
    needs dict-like column access, not a particular ORM/raw origin."""
    return (
        select(
            AppointmentRow.id, AppointmentRow.hospital_id, AppointmentRow.phone,
            AppointmentRow.department_id, Department.name.label("department_name"),
            AppointmentRow.doctor_id, DoctorRow.name.label("doctor_name"),
            AppointmentRow.scheduled_at, AppointmentRow.status, AppointmentRow.source, AppointmentRow.reference_id,
            AppointmentRow.patient_id, PatientRow.patient_display_id,
            AppointmentRow.appointment_type_id, AppointmentRow.consent_given_at,
        )
        .select_from(AppointmentRow)
        .join(Department, Department.id == AppointmentRow.department_id)
        .join(DoctorRow, DoctorRow.id == AppointmentRow.doctor_id)
        .outerjoin(PatientRow, PatientRow.id == AppointmentRow.patient_id)
        .where(AppointmentRow.deleted_at.is_(None))
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
    the oldest one -- the original single-profile-per-phone row.

    Deliberately NOT migrated to get_session()/ORM, permanently, along with
    create_appointment() below: pg_advisory_lock/unlock is SESSION-scoped --
    correctness depends on the lock() and unlock() calls running on the
    EXACT SAME physical connection, held for the full duration in between.
    The raw _PGConnection guarantees this (one literal psycopg2 connection
    for its whole process lifetime, never pooled/swapped). A SQLAlchemy
    Session backed by a pooled Engine has no such guarantee -- verifying
    it would require understanding exactly when the pool might check a
    session's underlying DBAPI connection back in and hand out a different
    one between statements, which isn't worth the risk for the single most
    concurrency-critical code path in the app (this function is called from
    inside create_appointment(), the actual booking-creation transaction).
    Same reasoning class as patients.py's create_patient_profile() trio and
    doctors.py's generate_slots_for_doctor()."""
    conn.execute("SELECT pg_advisory_lock(hashtext(?))", (f"upsert_patient|{hospital_id}|{phone}",))
    try:
        existing = conn.execute(
            "SELECT id, name, age, patient_display_id, mrn FROM patients "
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
                "patient_display_id": existing["patient_display_id"], "mrn": existing["mrn"],
            }
        row = conn.execute(
            "INSERT INTO patients (hospital_id, phone, name, age) VALUES (?, ?, ?, ?) RETURNING id, name, age",
            (hospital_id, phone, name, age),
        ).fetchone()
        assert row is not None  # INSERT ... RETURNING always returns the inserted row
        display_id, mrn = _generate_patient_identifiers(conn, hospital_id)
        conn.execute(
            "UPDATE patients SET patient_display_id = ?, mrn = ? WHERE id = ?", (display_id, mrn, row["id"]),
        )
        return {"id": row["id"], "name": row["name"], "age": row["age"], "patient_display_id": display_id, "mrn": mrn}
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
    tests/test_create_appointment_transaction_safety.py).

    Deliberately NOT migrated to get_session()/ORM, permanently: this
    function's pg_advisory_xact_lock only provides real protection inside a
    genuine multi-statement BEGIN/COMMIT block (built here via manual
    "BEGIN"/"COMMIT"/"ROLLBACK" text statements on one raw connection) --
    the ORM engine runs in AUTOCOMMIT (db/connection.py's get_engine()), so
    every session.execute() there is its own independent transaction,
    which would release this lock instantly instead of holding it across
    the quota checks + ordinal assignment + INSERT. This is THE booking-
    creation transaction -- the single most concurrency-critical code path
    in the app -- so it stays raw SQL permanently, same reasoning as
    patients.py's create_patient_profile()/link_existing_patient() and
    _upsert_patient() above. Every read function below IS migrated to ORM;
    only this function and _upsert_patient() are the exception."""
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


def set_appointment_video_link(hospital_id: int, appointment_id: int, video_link: str) -> None:
    """Tele-consultation Phase 2: called once, right after create_appointment()
    succeeds, by flows/booking/types/tele_consultation.py's on_booking_confirmed
    hook -- every other appointment type never calls this, so their rows keep
    video_link NULL. Same "small single-purpose UPDATE" shape as
    cancel_appointment()/mark_rescheduled() above."""
    conn = get_connection()
    conn.execute(
        "UPDATE appointments SET video_link = ? WHERE id = ? AND hospital_id = ?",
        (video_link, appointment_id, hospital_id),
    )
    conn.commit()


def get_appointment(hospital_id: int, appointment_id: int) -> Appointment | None:
    session = get_session()
    row = session.execute(
        _appointment_select_stmt().where(AppointmentRow.id == appointment_id, AppointmentRow.hospital_id == hospital_id)
    ).first()
    return _row_to_appointment(row._mapping) if row else None


def get_upcoming_appointments_for_phone(hospital_id: int, phone: str, now: datetime | None = None) -> list[Appointment]:
    """A patient's own future, still-booked appointments — soonest first.
    Past appointments and ones already cancelled/rescheduled are excluded here
    (not filtered later) so callers never have to remember to check status."""
    now = now or datetime.now()
    session = get_session()
    rows = session.execute(
        _appointment_select_stmt()
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.phone == phone,
            AppointmentRow.status == STATUS_BOOKED, AppointmentRow.scheduled_at > now.isoformat(),
        )
        .order_by(AppointmentRow.scheduled_at.asc())
    ).all()
    return [_row_to_appointment(r._mapping) for r in rows]


def get_active_appointments_for_patient(hospital_id: int, patient_id: int) -> list[Appointment]:
    """All still-booked appointments for this patient_id (not phone --
    one phone can have several linked patients). Any time window."""
    session = get_session()
    rows = session.execute(
        _appointment_select_stmt()
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.patient_id == patient_id,
            AppointmentRow.status == STATUS_BOOKED,
        )
        .order_by(AppointmentRow.scheduled_at.asc())
    ).all()
    return [_row_to_appointment(r._mapping) for r in rows]


def get_last_attended_appointment(hospital_id: int, patient_id: int) -> Appointment | None:
    """Most recent STATUS_ATTENDED appointment -- a no-show or a still-
    upcoming booking doesn't count."""
    session = get_session()
    row = session.execute(
        _appointment_select_stmt()
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.patient_id == patient_id,
            AppointmentRow.status == STATUS_ATTENDED,
        )
        .order_by(AppointmentRow.scheduled_at.desc())
        .limit(1)
    ).first()
    return _row_to_appointment(row._mapping) if row else None


def get_upcoming_appointments(hospital_id: int, offset_hours: float, now: datetime | None = None) -> list[Appointment]:
    """Still-booked appointments in [now, now+offset_hours] with no reminder
    sent yet for this specific offset -- a hospital can configure multiple
    offsets (e.g. 24h and 1h before), each tracked independently."""
    now = now or datetime.now()
    cutoff = now + timedelta(hours=offset_hours)
    session = get_session()
    reminder_exists = (
        select(AppointmentReminder.id)
        .where(AppointmentReminder.appointment_id == AppointmentRow.id, AppointmentReminder.offset_hours == offset_hours)
        .exists()
    )
    rows = session.execute(
        _appointment_select_stmt()
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.status == STATUS_BOOKED,
            AppointmentRow.scheduled_at >= now.isoformat(), AppointmentRow.scheduled_at <= cutoff.isoformat(),
            ~reminder_exists,
        )
        .order_by(AppointmentRow.scheduled_at.asc())
    ).all()
    return [_row_to_appointment(r._mapping) for r in rows]


def get_all_appointments_for_hospital(hospital_id: int, limit: int = 500) -> list[Appointment]:
    """Every appointment (any status) for the hospital's own dashboard --
    unlike the other lookups here, not filtered to booked/future-only."""
    session = get_session()
    rows = session.execute(
        _appointment_select_stmt()
        .where(AppointmentRow.hospital_id == hospital_id)
        .order_by(AppointmentRow.scheduled_at.desc())
        .limit(limit)
    ).all()
    return [_row_to_appointment(r._mapping) for r in rows]


def soft_delete_appointment(hospital_id: int, appointment_id: int) -> bool:
    """Stamps deleted_at rather than removing the row (never hard-delete).
    Restricted to already-resolved appointments (status != 'booked') --
    an active booking must be cancelled first, not deleted out from under
    the patient."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(AppointmentRow)
        .where(
            AppointmentRow.id == appointment_id, AppointmentRow.hospital_id == hospital_id,
            AppointmentRow.status != STATUS_BOOKED, AppointmentRow.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now().isoformat())
    ))
    session.commit()
    return result.rowcount > 0


def get_total_bookings_count() -> int:
    """Platform-admin lifetime usage stat: every row ever inserted, any
    status, including soft-deleted (deliberately not built on
    _APPOINTMENT_SELECT, which excludes those). A reschedule counts as a
    2nd use -- it's a separate INSERT."""
    session = get_session()
    return session.execute(select(func.count(AppointmentRow.id))).scalar_one()


def get_doctor_appointments_today(hospital_id: int, doctor_id: str, now: datetime | None = None) -> list[Appointment]:
    """A doctor's own appointments today, any status (full picture, not
    just still-booked)."""
    now = now or datetime.now()
    day_start = datetime.combine(now.date(), datetime.min.time()).isoformat()
    day_end = datetime.combine(now.date(), datetime.max.time()).isoformat()
    session = get_session()
    rows = session.execute(
        _appointment_select_stmt()
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id,
            AppointmentRow.scheduled_at >= day_start, AppointmentRow.scheduled_at <= day_end,
        )
        .order_by(AppointmentRow.scheduled_at.asc())
    ).all()
    return [_row_to_appointment(r._mapping) for r in rows]


def mark_reminded(hospital_id: int, appointment_id: int, offset_hours: float) -> None:
    """Records that this offset's reminder was sent. ON CONFLICT DO NOTHING
    makes calling this twice for the same offset a safe no-op."""
    session = get_session()
    session.execute(
        pg_insert(AppointmentReminder)
        .values(hospital_id=hospital_id, appointment_id=appointment_id, offset_hours=offset_hours)
        .on_conflict_do_nothing(index_elements=["appointment_id", "offset_hours"])
    )
    session.commit()


def get_reminded_offsets(hospital_id: int, appointment_id: int) -> list[float]:
    """Which reminder offsets (in hours) have already fired for this appointment."""
    session = get_session()
    rows = session.execute(
        select(AppointmentReminder.offset_hours)
        .where(AppointmentReminder.hospital_id == hospital_id, AppointmentReminder.appointment_id == appointment_id)
        .order_by(AppointmentReminder.offset_hours.desc())
    ).all()
    return [r.offset_hours for r in rows]


def cancel_appointment(hospital_id: int, appointment_id: int) -> None:
    """Marks cancelled, doesn't delete the row. Stamps updated_at so the
    dashboard's activity feed reflects when this happened."""
    session = get_session()
    session.execute(
        update(AppointmentRow)
        .where(AppointmentRow.id == appointment_id, AppointmentRow.hospital_id == hospital_id)
        .values(status=STATUS_CANCELLED, updated_at=datetime.now().isoformat())
    )
    session.commit()


def mark_rescheduled(hospital_id: int, appointment_id: int) -> None:
    """Marks the old appointment superseded by a reschedule -- doesn't
    delete the row. Caller books the new slot separately via create_appointment()."""
    session = get_session()
    session.execute(
        update(AppointmentRow)
        .where(AppointmentRow.id == appointment_id, AppointmentRow.hospital_id == hospital_id)
        .values(status=STATUS_RESCHEDULED, updated_at=datetime.now().isoformat())
    )
    session.commit()


def mark_attendance(hospital_id: int, appointment_id: int, attended: bool) -> bool:
    """Staff-confirmed attended/no_show, replacing the dashboard's no-show
    heuristic. Freely re-toggleable (booked/attended/no_show), any time --
    not allowed from 'cancelled'/'rescheduled' (those never happened)."""
    session = get_session()
    new_status = STATUS_ATTENDED if attended else STATUS_NO_SHOW
    result = cast(CursorResult, session.execute(
        update(AppointmentRow)
        .where(
            AppointmentRow.id == appointment_id, AppointmentRow.hospital_id == hospital_id,
            AppointmentRow.status.in_([STATUS_BOOKED, STATUS_ATTENDED, STATUS_NO_SHOW]),
        )
        .values(status=new_status, updated_at=datetime.now().isoformat())
    ))
    session.commit()
    return result.rowcount > 0


def get_appointments_needing_attendance_review(hospital_id: int, now: datetime | None = None) -> list["Appointment"]:
    """Still 'booked' but scheduled_at has passed -- for staff to resolve
    via mark_attendance()."""
    now = now or datetime.now()
    session = get_session()
    rows = session.execute(
        _appointment_select_stmt()
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.status == STATUS_BOOKED,
            AppointmentRow.scheduled_at < now.isoformat(),
        )
        .order_by(AppointmentRow.scheduled_at.desc())
    ).all()
    return [_row_to_appointment(r._mapping) for r in rows]



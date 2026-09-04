# db/repositories/appointments.py
"""Appointment booking, cancellation, rescheduling, and lookups -- the core
booking data path both the WhatsApp flow and the staff portal go through.
Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1."""
from datetime import datetime, timedelta
from typing import cast

import sqlalchemy.exc
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from db.connection import IntegrityError, get_connection, get_session
from db.display_ids import _generate_reference_id
from db.models import (
    Appointment, DuplicateBookingError, QuotaExceededError,
    SOURCE_WHATSAPP, STATUS_ATTENDED, STATUS_BOOKED, STATUS_CANCELLED, STATUS_NO_SHOW, STATUS_RESCHEDULED,
    _generate_patient_identifiers, _row_to_appointment,
)
from db.orm_models import (
    AppointmentLabTest, AppointmentProcedureResource, AppointmentReminder, AppointmentRow, Department,
    DiagnosticResource, DoctorRow, PatientLink, PatientRow, Procedure,
)


def _appointment_select_stmt():
    """ORM equivalent of db/models.py's _APPOINTMENT_SELECT -- the shared
    JOIN every appointment read here (and patient_records.py's
    get_patient_visit_history()) builds on. Callers append their own
    .where()/.order_by()/.limit(), same as callers of the raw SQL constant
    append "AND ...". _row_to_appointment() (db/models.py) maps a result row
    (via row._mapping) onto the Appointment dataclass unchanged -- it only
    needs dict-like column access, not a particular ORM/raw origin.

    Diagnostic/Lab Phase 2: doctor/resource joins are both LEFT -- a booking
    has exactly one of doctor_id/resource_id set, never both."""
    return (
        select(
            AppointmentRow.id, AppointmentRow.hospital_id, AppointmentRow.phone,
            AppointmentRow.department_id, Department.name.label("department_name"),
            AppointmentRow.doctor_id, DoctorRow.name.label("doctor_name"),
            AppointmentRow.scheduled_at, AppointmentRow.status, AppointmentRow.source, AppointmentRow.reference_id,
            AppointmentRow.patient_id, PatientRow.patient_display_id,
            AppointmentRow.appointment_type_id, AppointmentRow.consent_given_at, AppointmentRow.video_link,
            AppointmentRow.created_at, AppointmentRow.followup_override_until,
            AppointmentRow.resource_id, DiagnosticResource.name.label("resource_name"),
            AppointmentRow.diagnostic_test_id, AppointmentRow.diagnostic_test_variant_id,
            AppointmentRow.diagnostic_test_label, AppointmentRow.diagnostic_variant_label,
            AppointmentRow.diagnostic_price,
            AppointmentRow.collection_method, AppointmentRow.collection_address, AppointmentRow.collection_pincode,
            AppointmentRow.home_collection_charge, AppointmentRow.lab_status,
            AppointmentRow.procedure_id, Procedure.name.label("procedure_name"), AppointmentRow.procedure_status,
            AppointmentRow.procedure_estimated_price_min, AppointmentRow.procedure_estimated_price_max,
            AppointmentRow.procedure_order_reference, AppointmentRow.procedure_reschedule_requested_at,
        )
        .select_from(AppointmentRow)
        .join(Department, Department.id == AppointmentRow.department_id)
        .outerjoin(DoctorRow, DoctorRow.id == AppointmentRow.doctor_id)
        .outerjoin(DiagnosticResource, DiagnosticResource.id == AppointmentRow.resource_id)
        .outerjoin(PatientRow, PatientRow.id == AppointmentRow.patient_id)
        .outerjoin(Procedure, Procedure.id == AppointmentRow.procedure_id)
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
    doctor_id: str | None,
    scheduled_at: datetime,
    source: str = SOURCE_WHATSAPP,
    patient_name: str | None = None,
    patient_age: int | None = None,
    patient_id: int | None = None,
    exclude_appointment_id: int | None = None,
    appointment_type_id: str | None = None,
    consent_given_at: str | None = None,
    resource_id: str | None = None,
    diagnostic_test_id: int | None = None,
    diagnostic_test_variant_id: int | None = None,
    diagnostic_test_label: str | None = None,
    diagnostic_variant_label: str | None = None,
    diagnostic_price: float | None = None,
    collection_method: str | None = None,
    collection_address: str | None = None,
    collection_pincode: str | None = None,
    home_collection_charge: float | None = None,
    lab_status: str | None = None,
) -> Appointment:
    """Raises IntegrityError if the doctor's (or resource's) slot capacity
    (max_bookings_per_slot) is full at scheduled_at, or the more specific
    QuotaExceededError if the daily_booking_limit or the source's
    online/walkin quota is exhausted for that date.

    Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5):
    exactly one of doctor_id/resource_id is ever set (appointments_doctor_or_
    resource_chk enforces this at the DB level too) -- a resource-bound
    booking runs the identical advisory-lock/quota/ordinal logic below, keyed
    on resource_id against diagnostic_resources' own max_bookings_per_slot/
    daily_booking_limit instead of doctors'. There's no online/walkin-quota
    or duplicate-booking-by-doctor equivalent for resources (both are
    doctor-consultation-specific concepts) -- skipped entirely when doctor_id
    is None.

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

    max_bookings_per_slot = 1
    daily_booking_limit = None
    source_quota = None
    if doctor_id is not None:
        doctor_row = conn.execute(
            "SELECT max_bookings_per_slot, daily_booking_limit, online_quota, walkin_quota "
            "FROM doctors WHERE hospital_id = ? AND id = ?",
            (hospital_id, doctor_id),
        ).fetchone()
        max_bookings_per_slot = doctor_row["max_bookings_per_slot"] if doctor_row else 1
        daily_booking_limit = doctor_row["daily_booking_limit"] if doctor_row else None
        if doctor_row:
            source_quota = doctor_row["online_quota"] if source == SOURCE_WHATSAPP else doctor_row["walkin_quota"]
    elif resource_id is not None:
        resource_row = conn.execute(
            "SELECT max_bookings_per_slot, daily_booking_limit FROM diagnostic_resources "
            "WHERE hospital_id = ? AND id = ?",
            (hospital_id, resource_id),
        ).fetchone()
        max_bookings_per_slot = resource_row["max_bookings_per_slot"] if resource_row else 1
        daily_booking_limit = resource_row["daily_booking_limit"] if resource_row else None

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

    # Fixed internal literal ("doctor_id"/"resource_id"), never user input --
    # safe to interpolate into the raw SQL below.
    resource_column = "doctor_id" if doctor_id is not None else "resource_id"
    resource_value = doctor_id if doctor_id is not None else resource_id

    conn.execute("BEGIN")
    try:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext(?))",
            (f"{resource_column}|{resource_value}|{scheduled_date.isoformat()}",),
        )

        if daily_booking_limit is not None:
            day_count_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM appointments WHERE hospital_id = ? AND {resource_column} = ? "
                "AND scheduled_at >= ? AND scheduled_at <= ? AND status = ?",
                (hospital_id, resource_value, day_start, day_end, STATUS_BOOKED),
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
            f"SELECT MIN(o) AS ordinal FROM generate_series(0, ? - 1) AS o "
            f"WHERE o NOT IN (SELECT booking_ordinal FROM appointments WHERE hospital_id = ? "
            f"AND {resource_column} = ? AND scheduled_at = ? AND status = ?)",
            (max_bookings_per_slot, hospital_id, resource_value, scheduled_at_iso, STATUS_BOOKED),
        ).fetchone()
        assert free_ordinal_row is not None  # MIN() with no GROUP BY always returns one row
        if free_ordinal_row["ordinal"] is None:
            raise IntegrityError(f"{resource_column} {resource_value} has no free booking slot at {scheduled_at_iso}")

        # Prevents an accidental/duplicate re-booking with the same doctor --
        # a doctor-consultation-specific concept, skipped entirely for a
        # resource-bound booking (doctor_id is None).
        effective_name = patient["name"]
        effective_age = patient["age"]
        if doctor_id is not None and patient_id is not None:
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
        elif doctor_id is not None and effective_name is not None and effective_age is not None:
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
            "appointment_type_id, consent_given_at, resource_id, diagnostic_test_id, "
            "diagnostic_test_variant_id, diagnostic_test_label, diagnostic_variant_label, diagnostic_price, "
            "collection_method, collection_address, collection_pincode, home_collection_charge, lab_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (hospital_id, phone, department_id, doctor_id, scheduled_at_iso, free_ordinal_row["ordinal"], source,
             _generate_reference_id(conn, hospital_id), patient["id"], patient["name"], phone, effective_age,
             appointment_type_id, consent_given_at, resource_id, diagnostic_test_id,
             diagnostic_test_variant_id, diagnostic_test_label, diagnostic_variant_label, diagnostic_price,
             collection_method, collection_address, collection_pincode, home_collection_charge, lab_status),
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


def set_appointment_diagnostic_details(
    hospital_id: int, appointment_id: int, diagnostic_test_id: int, diagnostic_test_variant_id: int,
    diagnostic_test_label: str, diagnostic_variant_label: str, diagnostic_price: float | None,
) -> None:
    """Diagnostic/Lab Phase 2: called once, right after create_appointment()
    succeeds, by flows/booking/types/_diagnostic_shared.py's
    on_booking_confirmed hook -- same shape as set_appointment_duration()
    above. resource_id itself is set at INSERT time (create_appointment()),
    not here, since it participates in the booking transaction's own
    advisory-lock/double-booking logic."""
    conn = get_connection()
    conn.execute(
        "UPDATE appointments SET diagnostic_test_id = ?, diagnostic_test_variant_id = ?, "
        "diagnostic_test_label = ?, diagnostic_variant_label = ?, diagnostic_price = ? "
        "WHERE id = ? AND hospital_id = ?",
        (diagnostic_test_id, diagnostic_test_variant_id, diagnostic_test_label, diagnostic_variant_label,
         diagnostic_price, appointment_id, hospital_id),
    )
    conn.commit()


def set_appointment_lab_order_details(
    hospital_id: int, appointment_id: int, collection_method: str, collection_address: str | None,
    collection_pincode: str | None, home_collection_charge: float | None, basket_items: list[dict],
) -> None:
    """Lab Test Phase 2 follow-up: called once, right after create_appointment()
    succeeds, by flows/booking/types/lab.py's on_booking_confirmed hook --
    same "safe post-hoc hook, doesn't need the concurrency-critical
    transaction" rationale as set_appointment_diagnostic_details() above.
    Sets lab_status to 'booked' (the start of the report lifecycle) and
    bulk-inserts the basket into appointment_lab_tests. `basket_items`: list
    of {diagnostic_test_id, diagnostic_test_variant_id, test_label,
    variant_label, price, preparation_instructions}."""
    conn = get_connection()
    conn.execute(
        "UPDATE appointments SET collection_method = ?, collection_address = ?, collection_pincode = ?, "
        "home_collection_charge = ?, lab_status = 'booked' WHERE id = ? AND hospital_id = ?",
        (collection_method, collection_address, collection_pincode, home_collection_charge, appointment_id, hospital_id),
    )
    for item in basket_items:
        conn.execute(
            "INSERT INTO appointment_lab_tests (hospital_id, appointment_id, diagnostic_test_id, "
            "diagnostic_test_variant_id, test_label, variant_label, price, preparation_instructions) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (hospital_id, appointment_id, item.get("diagnostic_test_id"), item.get("diagnostic_test_variant_id"),
             item["test_label"], item["variant_label"], item.get("price"), item.get("preparation_instructions")),
        )
    conn.commit()


def copy_lab_basket(hospital_id: int, from_appointment_id: int, to_appointment_id: int) -> None:
    """Reschedule's own carry-forward for the basket (the collection_*/
    lab_status columns on `appointments` itself carry forward via
    create_appointment()'s own params, same as diagnostic_test_id -- see
    Tier1Connector.reschedule_booking()). The basket lives in a child table,
    so it needs its own copy rather than a column value passed at INSERT
    time."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT diagnostic_test_id, diagnostic_test_variant_id, test_label, variant_label, price, "
        "preparation_instructions FROM appointment_lab_tests WHERE hospital_id = ? AND appointment_id = ?",
        (hospital_id, from_appointment_id),
    ).fetchall()
    for row in rows:
        conn.execute(
            "INSERT INTO appointment_lab_tests (hospital_id, appointment_id, diagnostic_test_id, "
            "diagnostic_test_variant_id, test_label, variant_label, price, preparation_instructions) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (hospital_id, to_appointment_id, row["diagnostic_test_id"], row["diagnostic_test_variant_id"],
             row["test_label"], row["variant_label"], row["price"], row["preparation_instructions"]),
        )
    conn.commit()


def get_lab_basket_for_appointment(hospital_id: int, appointment_id: int) -> list[dict]:
    """The confirmation/success cards' own read of the basket, and the
    reschedule flow's read of what to carry forward."""
    session = get_session()
    rows = session.execute(
        select(
            AppointmentLabTest.id, AppointmentLabTest.diagnostic_test_id, AppointmentLabTest.diagnostic_test_variant_id,
            AppointmentLabTest.test_label, AppointmentLabTest.variant_label, AppointmentLabTest.price,
            AppointmentLabTest.preparation_instructions,
        )
        .where(AppointmentLabTest.hospital_id == hospital_id, AppointmentLabTest.appointment_id == appointment_id)
        .order_by(AppointmentLabTest.id)
    ).all()
    items = []
    for r in rows:
        item = dict(r._mapping)
        if item["price"] is not None:
            item["price"] = float(item["price"])
        items.append(item)
    return items


def set_lab_status(hospital_id: int, appointment_id: int, lab_status: str) -> Appointment | None:
    """Lab Test Phase 2 follow-up's report lifecycle. Staff advance
    booked -> sample_collected -> processing manually (portal/routes/
    bookings.py); report_ready is set automatically instead, the moment a
    lab_report document is uploaded against this appointment (portal/routes/
    documents.py) -- never a direct staff action, so "report ready" always
    means an actual report exists."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(AppointmentRow)
        .where(AppointmentRow.hospital_id == hospital_id, AppointmentRow.id == appointment_id)
        .values(lab_status=lab_status)
    ))
    session.commit()
    if result.rowcount == 0:
        return None
    return get_appointment(hospital_id, appointment_id)


def create_procedure_appointment(
    hospital_id: int, phone: str, procedure_id: int, scheduled_at: datetime,
    patient_id: int | None = None, patient_name: str | None = None, patient_age: int | None = None,
    procedure_order_reference: str | None = None,
) -> Appointment:
    """Daycare/Procedure rebuild, instant-booking path (Step 4 straight
    through to a real slot). A procedure binds N resources (bed/chair +
    equipment + staff), not the single doctor_id/resource_id column
    create_appointment() already handles, so this is its own dedicated
    creation path -- same advisory-lock-protected BEGIN/COMMIT shape as
    create_appointment() (see that function's own docstring for why this
    stays raw SQL/conn-based permanently)."""
    from db.repositories.procedure_slots import reserve_procedure_resources
    from db.repositories.procedures import get_procedure

    conn = get_connection()
    procedure = get_procedure(hospital_id, procedure_id)
    if procedure is None:
        raise ValueError(f"procedure_id {procedure_id} not found for hospital {hospital_id}")
    dept_row = conn.execute(
        "SELECT id FROM departments WHERE hospital_id = ? ORDER BY name LIMIT 1", (hospital_id,),
    ).fetchone()
    department_id = procedure["department_id"] or (dept_row["id"] if dept_row else None)
    scheduled_at_iso = scheduled_at.isoformat()

    if patient_id is not None:
        patient_row = conn.execute(
            "SELECT id, name, age FROM patients WHERE hospital_id = ? AND id = ?", (hospital_id, patient_id),
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
            (f"procedure|{procedure_id}|{scheduled_at.date().isoformat()}",),
        )
        reserved = reserve_procedure_resources(hospital_id, procedure_id, scheduled_at, conn)
        cur = conn.execute(
            "INSERT INTO appointments (hospital_id, phone, department_id, doctor_id, scheduled_at, "
            "booking_ordinal, source, reference_id, patient_id, patient_name, patient_phone, patient_age, "
            "appointment_type_id, procedure_id, procedure_status, procedure_estimated_price_min, "
            "procedure_estimated_price_max, procedure_order_reference) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (hospital_id, phone, department_id, None, scheduled_at_iso, 0, SOURCE_WHATSAPP,
             _generate_reference_id(conn, hospital_id), patient["id"], patient["name"], phone, patient["age"],
             "daycare", procedure_id, "CONFIRMED", procedure["estimated_price_min"], procedure["estimated_price_max"],
             procedure_order_reference),
        )
        new_id_row = cur.fetchone()
        assert new_id_row is not None
        new_id = new_id_row["id"]
        for r in reserved:
            conn.execute(
                "INSERT INTO appointment_procedure_resources "
                "(hospital_id, appointment_id, resource_id, resource_type, resource_name) VALUES (?, ?, ?, ?, ?)",
                (hospital_id, new_id, r["resource_id"], r["resource_type"], r["resource_name"]),
            )
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    created = get_appointment(hospital_id, new_id)
    assert created is not None
    return created


def create_procedure_request(
    hospital_id: int, phone: str, procedure_id: int, patient_id: int | None = None,
    patient_name: str | None = None, patient_age: int | None = None, procedure_order_reference: str | None = None,
) -> Appointment:
    """Approval-required path (Step 3): a plain INSERT, no advisory lock
    needed -- no resource is reserved yet, no slot chosen yet. scheduled_at
    is stamped with the request's own creation time as a PLACEHOLDER
    (appointments.scheduled_at is NOT NULL, and every other read path across
    the codebase assumes a real value) -- never displayed or treated as real
    until procedure_status reaches CONFIRMED via confirm_procedure_appointment().
    Same discipline lab_status/collection_method already established: an
    extra nullable column (procedure_status) carries the "is this really
    scheduled" truth, not the base columns."""
    from db.repositories.procedures import get_procedure

    conn = get_connection()
    procedure = get_procedure(hospital_id, procedure_id)
    if procedure is None:
        raise ValueError(f"procedure_id {procedure_id} not found for hospital {hospital_id}")
    dept_row = conn.execute(
        "SELECT id FROM departments WHERE hospital_id = ? ORDER BY name LIMIT 1", (hospital_id,),
    ).fetchone()
    department_id = procedure["department_id"] or (dept_row["id"] if dept_row else None)

    if patient_id is not None:
        patient_row = conn.execute(
            "SELECT id, name, age FROM patients WHERE hospital_id = ? AND id = ?", (hospital_id, patient_id),
        ).fetchone()
        if patient_row is None:
            raise ValueError(f"patient_id {patient_id} not found for hospital {hospital_id}")
        patient = {"id": patient_row["id"], "name": patient_row["name"], "age": patient_row["age"]}
    else:
        patient = _upsert_patient(conn, hospital_id, phone, patient_name, patient_age)

    now = datetime.now()
    cur = conn.execute(
        "INSERT INTO appointments (hospital_id, phone, department_id, doctor_id, scheduled_at, "
        "booking_ordinal, source, reference_id, patient_id, patient_name, patient_phone, patient_age, "
        "appointment_type_id, procedure_id, procedure_status, procedure_estimated_price_min, "
        "procedure_estimated_price_max, procedure_order_reference) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (hospital_id, phone, department_id, None, now.isoformat(), 0, SOURCE_WHATSAPP,
         _generate_reference_id(conn, hospital_id), patient["id"], patient["name"], phone, patient["age"],
         "daycare", procedure_id, "REQUESTED", procedure["estimated_price_min"], procedure["estimated_price_max"],
         procedure_order_reference),
    )
    new_id_row = cur.fetchone()
    assert new_id_row is not None
    conn.commit()
    created = get_appointment(hospital_id, new_id_row["id"])
    assert created is not None
    return created


def confirm_procedure_appointment(hospital_id: int, appointment_id: int, scheduled_at: datetime) -> Appointment:
    """Once an APPROVED request's patient picks a real slot (Step 4, after
    approval): reserves the resources under the same advisory-lock
    discipline as create_procedure_appointment(), then moves the EXISTING
    row from its placeholder scheduled_at to the real one and flips
    procedure_status to CONFIRMED -- the request already has a reference_id/
    patient identity/order-reference, so this updates in place rather than
    creating a second appointment row."""
    from db.repositories.procedure_slots import reserve_procedure_resources

    conn = get_connection()
    appt_row = conn.execute(
        "SELECT procedure_id FROM appointments WHERE hospital_id = ? AND id = ?", (hospital_id, appointment_id),
    ).fetchone()
    if appt_row is None or appt_row["procedure_id"] is None:
        raise ValueError(f"appointment {appointment_id} is not a procedure appointment for hospital {hospital_id}")
    procedure_id = appt_row["procedure_id"]

    conn.execute("BEGIN")
    try:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext(?))",
            (f"procedure|{procedure_id}|{scheduled_at.date().isoformat()}",),
        )
        reserved = reserve_procedure_resources(hospital_id, procedure_id, scheduled_at, conn)
        conn.execute(
            "UPDATE appointments SET scheduled_at = ?, procedure_status = 'CONFIRMED', "
            "procedure_reschedule_requested_at = NULL WHERE id = ? AND hospital_id = ?",
            (scheduled_at.isoformat(), appointment_id, hospital_id),
        )
        for r in reserved:
            conn.execute(
                "INSERT INTO appointment_procedure_resources "
                "(hospital_id, appointment_id, resource_id, resource_type, resource_name) VALUES (?, ?, ?, ?, ?)",
                (hospital_id, appointment_id, r["resource_id"], r["resource_type"], r["resource_name"]),
            )
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    created = get_appointment(hospital_id, appointment_id)
    assert created is not None
    return created


def request_procedure_reschedule(hospital_id: int, appointment_id: int, requested_at: datetime | None) -> None:
    """"Request Reschedule" (approval-required procedures only): stores the
    patient's DESIRED new slot without touching scheduled_at -- a portal
    action approves (re-reserves resources for requested_at via
    confirm_procedure_appointment) or rejects it (requested_at=None clears
    the pending request, see portal/routes/bookings.py)."""
    conn = get_connection()
    conn.execute(
        "UPDATE appointments SET procedure_reschedule_requested_at = ? WHERE id = ? AND hospital_id = ?",
        (requested_at.isoformat() if requested_at is not None else None, appointment_id, hospital_id),
    )
    conn.commit()


def set_procedure_status(hospital_id: int, appointment_id: int, procedure_status: str) -> Appointment | None:
    """Portal-driven status transitions (approve/reject/advance-status,
    portal/routes/bookings.py) -- a plain single-column UPDATE, same shape
    as set_lab_status(). Never used for CONFIRMED (that's
    confirm_procedure_appointment()'s own job, since it also reserves
    resources and moves scheduled_at atomically)."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(AppointmentRow)
        .where(AppointmentRow.hospital_id == hospital_id, AppointmentRow.id == appointment_id)
        .values(procedure_status=procedure_status)
    ))
    session.commit()
    if result.rowcount == 0:
        return None
    return get_appointment(hospital_id, appointment_id)


def get_pending_procedure_request(hospital_id: int, phone: str, procedure_id: int) -> Appointment | None:
    """A phone's own still-open request for this exact procedure (REQUESTED/
    UNDER_REVIEW/APPROVED, most recent first) -- used by flows/booking/types/
    procedure.py's own Step 1 handler to avoid creating a second, duplicate
    request when the patient re-picks a procedure they already have a
    pending request for, and to resume an APPROVED one straight into
    date/time selection (via context["_procedure_appointment_id"]) instead
    of starting over."""
    session = get_session()
    rows = session.execute(
        _appointment_select_stmt()
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.phone == phone,
            AppointmentRow.procedure_id == procedure_id,
            AppointmentRow.procedure_status.in_(["REQUESTED", "UNDER_REVIEW", "APPROVED"]),
        )
        .order_by(AppointmentRow.id.desc())
    ).first()
    return _row_to_appointment(rows._mapping) if rows else None


def get_procedure_resources_for_appointment(hospital_id: int, appointment_id: int) -> list[dict]:
    """The confirmation/success cards' own read, and the portal's own
    appointment-detail read -- which concrete bed/chair/equipment/staff this
    booking is bound to."""
    session = get_session()
    rows = session.execute(
        select(
            AppointmentProcedureResource.id, AppointmentProcedureResource.resource_id,
            AppointmentProcedureResource.resource_type, AppointmentProcedureResource.resource_name,
        )
        .where(
            AppointmentProcedureResource.hospital_id == hospital_id,
            AppointmentProcedureResource.appointment_id == appointment_id,
        )
        .order_by(AppointmentProcedureResource.resource_type)
    ).all()
    return [dict(r._mapping) for r in rows]


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


def get_appointments_for_account_in_range(
    hospital_id: int, care_connect_account_id: int, range_start: datetime, range_end: datetime,
    statuses: list[str] | None = None,
) -> list[Appointment]:
    """"My Appointments" -> Previous/Upcoming 1 Month range view -- scoped to
    the durable care_connect_account_id (via patient_links), NOT
    appointments.phone. appointments.phone only records whatever number was
    used at booking time; if a person's WhatsApp number later changes but
    their account persists (e.g. an admin re-links the same identity to a
    new number), phone-keyed lookups would silently drop their older
    appointments. Joining through patient_links instead shows every
    appointment for every patient CURRENTLY linked to this account at this
    hospital, regardless of which phone booked it.

    Two deliberate consequences of the join, confirmed acceptable: (1) a
    handful of legacy pre-multi-patient-identity appointments with NULL
    patient_id can't match this join and are excluded (they showed up under
    the old phone-keyed query; negligible/historical); (2) unlinking a
    patient from the account also drops their appointments from this view,
    matching "who is currently under this account" (same framing as Manage
    Patients), not "who was ever linked".

    `statuses` narrows to specific statuses (e.g. upcoming callers pass
    [STATUS_BOOKED] so a cancelled future-dated row doesn't show as
    "upcoming"); None (the default, used for "previous") means any status,
    so a history view still shows cancelled appointments, not just
    completed ones."""
    session = get_session()
    stmt = (
        _appointment_select_stmt()
        .join(
            PatientLink,
            (PatientLink.patient_id == AppointmentRow.patient_id) & (PatientLink.hospital_id == AppointmentRow.hospital_id),
        )
        .where(
            AppointmentRow.hospital_id == hospital_id, PatientLink.care_connect_account_id == care_connect_account_id,
            PatientLink.unlinked_at.is_(None),
            AppointmentRow.scheduled_at >= range_start.isoformat(), AppointmentRow.scheduled_at < range_end.isoformat(),
        )
    )
    if statuses is not None:
        stmt = stmt.where(AppointmentRow.status.in_(statuses))
    rows = session.execute(stmt.order_by(AppointmentRow.scheduled_at.asc())).all()
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


def get_followup_eligible_appointments(
    hospital_id: int, patient_id: int, validity_days: int, now: datetime | None = None,
) -> list[Appointment]:
    """One row per department: that department's most recent STATUS_ATTENDED
    appointment, only if still within validity_days of its own scheduled_at
    (docs/per-appointment-type-flow-plan.md Phase 2 Step 2 follow-up --
    hospital_settings.followup_validity_days) OR a staff-granted
    followup_override_until (migration 0024) hasn't passed yet -- an
    admin/receptionist override widens the window for one specific visit,
    it never narrows it. Newest first. Dedup by department_id happens here
    in Python, not a SQL window function -- one patient's attended-
    appointment history is always a small list, same "keep it simple"
    precedent get_last_attended_appointment above sets."""
    now = now or datetime.now()
    cutoff = now - timedelta(days=validity_days)
    session = get_session()
    rows = session.execute(
        _appointment_select_stmt()
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.patient_id == patient_id,
            AppointmentRow.status == STATUS_ATTENDED,
            or_(
                AppointmentRow.scheduled_at >= cutoff.isoformat(),
                AppointmentRow.followup_override_until >= now.date().isoformat(),
            ),
        )
        .order_by(AppointmentRow.scheduled_at.desc())
    ).all()
    eligible: list[Appointment] = []
    seen_departments: set[str] = set()
    for row in rows:
        appt = _row_to_appointment(row._mapping)
        if appt.department_id in seen_departments:
            continue
        seen_departments.add(appt.department_id)
        eligible.append(appt)
    return eligible


def grant_followup_extension(
    hospital_id: int, appointment_id: int, extra_days: int, now: datetime | None = None,
) -> Appointment | None:
    """Portal-only staff action (admin/receptionist, gated by portal/deps.py's
    require_permission -- see portal/routes/bookings.py's followup/extend
    route): grants a patient extra_days beyond today to book a follow-up
    against THIS specific ATTENDED appointment, without changing the
    hospital-wide followup_validity_days setting. Widens (never narrows) the
    normal window -- get_followup_eligible_appointments() ORs the two, so
    this only matters once the normal window has already closed. Returns
    None if there's no such ATTENDED appointment for this hospital (a still-
    booked/cancelled/soft-deleted row, or a wrong hospital_id, is never
    extendable)."""
    now = now or datetime.now()
    override_until = (now.date() + timedelta(days=extra_days)).isoformat()
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(AppointmentRow)
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.id == appointment_id,
            AppointmentRow.status == STATUS_ATTENDED, AppointmentRow.deleted_at.is_(None),
        )
        .values(followup_override_until=override_until)
    ))
    session.commit()
    if result.rowcount == 0:
        return None
    return get_appointment(hospital_id, appointment_id)


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


def get_doctor_appointments(hospital_id: int, doctor_id: str, limit: int = 500) -> list[Appointment]:
    """Doctor-portal follow-up: this doctor's own full appointment history
    (any status, any date -- not just today), most recent first. The
    /doctor/appointments page's list, same "every appointment this scope
    owns" shape get_all_appointments_for_hospital() gives the shared staff
    portal, just doctor_id-scoped instead of hospital-wide -- doctor_id
    comes from the caller's own verified token (portal/routes/
    doctor_portal.py's _require_doctor()), never a request parameter."""
    session = get_session()
    rows = session.execute(
        _appointment_select_stmt()
        .where(AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id)
        .order_by(AppointmentRow.scheduled_at.desc())
        .limit(limit)
    ).all()
    return [_row_to_appointment(r._mapping) for r in rows]


def get_doctor_appointments_for_patient(hospital_id: int, doctor_id: str, patient_id: int) -> list[Appointment]:
    """Doctor-portal follow-up: the /doctor/patients/[id] detail page's own
    appointment-history list -- deliberately scoped to appointments WITH
    THIS DOCTOR only, not the patient's whole hospital history (which may
    include other doctors) -- same "personalised, not just filtered"
    discipline get_patients_for_doctor()'s own docstring already applies.
    An empty result is also how the route decides this doctor has never
    actually seen this patient at all (a 404, not silently empty data)."""
    session = get_session()
    rows = session.execute(
        _appointment_select_stmt()
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id,
            AppointmentRow.patient_id == patient_id,
        )
        .order_by(AppointmentRow.scheduled_at.desc())
    ).all()
    return [_row_to_appointment(r._mapping) for r in rows]


def get_doctor_weekly_appointment_counts(hospital_id: int, doctor_id: str, now: datetime | None = None) -> list[dict]:
    """Doctor-portal follow-up: same one-point-per-day-for-the-last-7-days
    shape as get_weekly_appointment_counts() (dashboard.py), doctor_id-scoped
    instead of hospital-wide, for the doctor dashboard's own trend chart."""
    now = now or datetime.now()
    session = get_session()
    points = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).date()
        day_start = datetime.combine(day, datetime.min.time()).isoformat()
        day_end = datetime.combine(day, datetime.max.time()).isoformat()
        count = session.execute(
            select(func.count()).where(
                AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id,
                AppointmentRow.scheduled_at >= day_start, AppointmentRow.scheduled_at <= day_end,
            )
        ).scalar_one()
        points.append({"date": day.isoformat(), "label": day.strftime("%a"), "count": count})
    return points


def get_doctor_appointments_for_month(
    hospital_id: int, doctor_id: str, year: int, month: int,
) -> list[Appointment]:
    """Doctor-portal follow-up: every one of this doctor's appointments
    falling within one calendar month (year/month, 1-12), for the dashboard's
    calendar view -- replaces the 30-day status donut with something a
    doctor can actually navigate month-to-month. Bounds computed the same
    "next month's day 1, minus nothing" way get_doctor_weekly_appointment_
    counts() computes a single day's bounds, just widened to a month."""
    month_start = datetime(year, month, 1)
    month_end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    session = get_session()
    rows = session.execute(
        _appointment_select_stmt()
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id,
            AppointmentRow.scheduled_at >= month_start.isoformat(),
            AppointmentRow.scheduled_at < month_end.isoformat(),
        )
        .order_by(AppointmentRow.scheduled_at.asc())
    ).all()
    return [_row_to_appointment(r._mapping) for r in rows]


def delay_doctor_remaining_today_appointments(
    hospital_id: int, doctor_id: str, minutes: int, now: datetime | None = None,
) -> list[tuple[Appointment, datetime]]:
    """"Running late" follow-up: shifts every one of this doctor's still-
    'booked' appointments later TODAY (scheduled_at > now, same calendar
    day) forward by `minutes` -- the actual feature is "I'm running late,
    push everyone after me back," not a general bulk-reschedule tool, so
    this deliberately never touches a different day or a non-'booked'
    (cancelled/attended/no_show) row.

    Processed LATEST-first, one UPDATE per row, so each row's new
    (doctor_id, scheduled_at) slot is either past every other still-unshifted
    appointment (the current latest, moving into open time) or a slot the
    previous iteration just vacated -- avoiding a transient collision with
    the partial unique booked-slot index that a naive earliest-first bulk
    shift could hit. A single row's shift failing (a genuine, currently
    unexplained collision) is skipped rather than aborting the whole
    batch -- this is a real-time "I'm late" action a doctor is taking
    between patients, not a transaction that should roll back over one
    unlucky row. Returns (appointment, new_scheduled_at) pairs for every
    row that WAS successfully shifted, so the caller knows exactly who to
    notify -- never guessed from the input list, since that could now
    include a row that failed."""
    now = now or datetime.now()
    day_end = datetime.combine(now.date(), datetime.max.time())
    session = get_session()
    rows = session.execute(
        _appointment_select_stmt()
        .where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id,
            AppointmentRow.status == STATUS_BOOKED,
            AppointmentRow.scheduled_at > now.isoformat(), AppointmentRow.scheduled_at <= day_end.isoformat(),
        )
        .order_by(AppointmentRow.scheduled_at.desc())
    ).all()
    appointments = [_row_to_appointment(r._mapping) for r in rows]

    shifted: list[tuple[Appointment, datetime]] = []
    for appointment in appointments:
        new_time = appointment.scheduled_at + timedelta(minutes=minutes)
        try:
            session.execute(
                update(AppointmentRow).where(AppointmentRow.id == appointment.id)
                .values(scheduled_at=new_time.isoformat())
            )
            session.commit()
            shifted.append((appointment, new_time))
        except sqlalchemy.exc.IntegrityError:
            session.rollback()
            continue
    return shifted


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



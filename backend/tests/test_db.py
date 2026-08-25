from datetime import date, datetime, timedelta

import pytest

import db.connection as db_connection
import db.repository as db
from db.connection import IntegrityError
from db.init_db import init_db_on_connection


# --- Departments / doctors (seeded data, scoped by hospital_id) ---

def test_departments_seeded_and_scoped_to_hospital(hospital_id):
    depts = db.get_departments(hospital_id)
    ids = {d["id"] for d in depts}
    assert ids == {"cardiology", "orthopedics", "general_medicine", "pediatrics"}


def test_find_department_found_and_not_found(hospital_id):
    assert db.find_department(hospital_id, "cardiology")["name"] == "Cardiology"
    assert db.find_department(hospital_id, "nope") is None


def test_get_doctors_returns_two_or_three_per_department(hospital_id):
    for dept in db.get_departments(hospital_id):
        doctors = db.get_doctors(hospital_id, dept["id"])
        assert 2 <= len(doctors) <= 3


def test_find_doctor_found_and_not_found(hospital_id):
    doctors = db.get_doctors(hospital_id, "cardiology")
    doctor = db.find_doctor(hospital_id, "cardiology", doctors[0]["id"])
    assert doctor == doctors[0]
    assert db.find_doctor(hospital_id, "cardiology", "nope") is None
    assert db.find_doctor(hospital_id, "orthopedics", doctors[0]["id"]) is None  # wrong department


def test_appointments_scoped_to_hospital_id_not_leaked_across_hospitals(hospital_id):
    """Central requirement of SPEC Section 12.2: a query scoped to one hospital
    must never return another hospital's rows.

    Note: db/schema.sql documents a known Tier 1 limitation — departments/doctors
    use a globally-unique text id (e.g. "cardiology"), not a (hospital_id, id)
    composite key, so two hospitals can't both seed identical department slugs
    yet (that's Phase 9 work, once a real second hospital is onboarded). This
    test seeds a second hospital with its own distinct department/doctor rows
    instead, and proves appointment queries are still correctly hospital-scoped.
    """
    conn = db_connection.get_connection()
    cur = conn.execute("INSERT INTO hospitals (name, whatsapp_phone_number_id) VALUES (?, ?) RETURNING id",
                        ("Other Hospital", "other-number"))
    other_id = cur.fetchone()["id"]
    assert other_id != hospital_id
    conn.execute("INSERT INTO departments (id, hospital_id, name) VALUES (?, ?, ?)", ("derm", other_id, "Dermatology"))
    conn.execute("INSERT INTO doctors (id, hospital_id, department_id, name) VALUES (?, ?, ?, ?)",
                 ("doc_derm_1", other_id, "derm", "Dr. Other Hospital"))
    conn.commit()

    # Each hospital only sees its own departments/doctors.
    assert "derm" not in {d["id"] for d in db.get_departments(hospital_id)}
    assert db.find_department(hospital_id, "derm") is None
    assert db.find_department(other_id, "derm")["name"] == "Dermatology"

    # Appointments created under one hospital must not appear in the other's queries,
    # even for the exact same phone number.
    now = datetime.now()
    doc_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    appt = db.create_appointment(hospital_id, "5490001", "cardiology", doc_id, now + timedelta(hours=5))
    other_appt = db.create_appointment(other_id, "5490001", "derm", "doc_derm_1", now + timedelta(hours=5))

    assert db.get_upcoming_appointments_for_phone(hospital_id, "5490001", now=now) == [appt]
    assert db.get_upcoming_appointments_for_phone(other_id, "5490001", now=now) == [other_appt]
    assert db.get_appointment(hospital_id, other_appt.id) is None  # wrong hospital_id -> not found
    assert db.get_appointment(other_id, appt.id) is None


# --- Slots (real, persisted doctor_slots rows — Section 12.1.1 — but still excludes booked ones) ---

def test_get_slots_returns_rolling_14_day_window_two_per_day(hospital_id):
    """Seeded doctors work all 7 days with two 60-minute ranges (10:00-11:00,
    15:00-16:00) -- db/seed.py's default pattern -- so the 14-day rolling
    window (Section 12.1.1) generated at seed time should offer exactly
    10:00/15:00 on each of the next 14 days, 28 slots total."""
    slots = db.get_slots(hospital_id, "doc_card_1")
    assert len(slots) == 28
    expected_dates = {(date.today() + timedelta(days=i)).isoformat() for i in range(1, 15)}
    assert {s["date"] for s in slots} == expected_dates
    for d in expected_dates:
        times = {s["time"] for s in slots if s["date"] == d}
        assert times == {"10:00", "15:00"}


def test_generate_slots_for_doctor_respects_working_days_and_hours(hospital_id):
    """A doctor working only Mon/Wed/Fri, 09:00-10:00 in 20-minute increments,
    must only get slots on those weekdays at those exact times -- proves slot
    generation actually reads the doctor's stored working pattern rather than
    always falling back to the old hardcoded 10:00/15:00 pair."""
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Pattern Test",
        working_days=["Mon", "Wed", "Fri"],
        working_hours=["09:00-10:00"],
        slot_duration_minutes=20,
    )
    slots = db.get_slots(hospital_id, doctor["id"])

    assert slots  # generation actually produced something
    for s in slots:
        d = date.fromisoformat(s["date"])
        assert d.strftime("%a") in ("Mon", "Wed", "Fri")
        assert s["time"] in ("09:00", "09:20", "09:40")

    # Exactly 3 slots (09:00, 09:20, 09:40) on each working day in the 14-day window
    working_day_dates = {s["date"] for s in slots}
    for d in working_day_dates:
        times = {s["time"] for s in slots if s["date"] == d}
        assert times == {"09:00", "09:20", "09:40"}


def test_doctor_with_no_working_pattern_generates_no_slots(hospital_id):
    doctor = db.create_doctor(hospital_id, "cardiology", "Dr. No Pattern")
    assert db.get_slots(hospital_id, doctor["id"]) == []


def test_generate_slots_for_doctor_is_idempotent_no_duplicates(hospital_id):
    """Simulates the periodic top-up job (slots/scheduler.py) re-running
    against a window that's already populated -- must not create duplicate
    slot rows, and the second call's "new rows inserted" count must be 0."""
    first_run = db.generate_slots_for_doctor(hospital_id, "doc_card_1")
    assert first_run == 0  # already generated at seed time

    second_run = db.generate_slots_for_doctor(hospital_id, "doc_card_1")
    assert second_run == 0
    assert len(db.get_slots(hospital_id, "doc_card_1")) == 28  # unchanged, no dupes


def test_generate_slots_for_doctor_extends_window_as_days_pass(hospital_id):
    """The rolling-window top-up job's actual job: as "now" advances, calling
    generate_slots_for_doctor again must add the newly-in-range future days
    without touching/duplicating the days generated on the first pass."""
    doctor_id = "topup_doc"
    conn = db_connection.get_connection()
    conn.execute(
        "INSERT INTO doctors (id, hospital_id, department_id, name, working_days, working_hours, slot_duration_minutes) "
        "VALUES (?, ?, 'cardiology', 'Dr. Topup', 'Mon,Tue,Wed,Thu,Fri,Sat,Sun', '10:00-11:00', 60)",
        (doctor_id, hospital_id),
    )
    conn.commit()

    first_run = db.generate_slots_for_doctor(hospital_id, doctor_id, days_ahead=5, now=date.today())
    assert first_run == 5
    slots_after_first = db.get_slots(hospital_id, doctor_id)
    assert len(slots_after_first) == 5

    # A week later, a top-up call for the same 5-day-ahead window must add the
    # 5 newly-in-range days without duplicating the original ones.
    later = date.today() + timedelta(days=7)
    second_run = db.generate_slots_for_doctor(hospital_id, doctor_id, days_ahead=5, now=later)
    assert second_run == 5
    slots_after_second = db.get_slots(hospital_id, doctor_id)
    assert len(slots_after_second) == 10
    assert {s["id"] for s in slots_after_first}.issubset({s["id"] for s in slots_after_second})


def test_find_slot_found_and_not_found(hospital_id):
    slots = db.get_slots(hospital_id, "doc_card_1")
    assert db.find_slot(hospital_id, "doc_card_1", slots[0]["id"]) == slots[0]
    assert db.find_slot(hospital_id, "doc_card_1", "nope") is None


def test_get_slots_excludes_already_booked_slots(hospital_id):
    """Phase 8: an already-booked slot must not be offered to another patient."""
    slots = db.get_slots(hospital_id, "doc_card_1")
    target = slots[0]
    db.create_appointment(hospital_id, "111", "cardiology", "doc_card_1", datetime.fromisoformat(f"{target['date']}T{target['time']}:00"))

    remaining = db.get_slots(hospital_id, "doc_card_1")

    assert target["id"] not in {s["id"] for s in remaining}
    assert len(remaining) == len(slots) - 1
    assert db.find_slot(hospital_id, "doc_card_1", target["id"]) is None


def test_get_slots_frees_up_again_once_booking_is_cancelled(hospital_id):
    slots = db.get_slots(hospital_id, "doc_card_1")
    target = slots[0]
    appt = db.create_appointment(hospital_id, "111", "cardiology", "doc_card_1", datetime.fromisoformat(f"{target['date']}T{target['time']}:00"))
    assert target["id"] not in {s["id"] for s in db.get_slots(hospital_id, "doc_card_1")}

    db.cancel_appointment(hospital_id, appt.id)

    assert target["id"] in {s["id"] for s in db.get_slots(hospital_id, "doc_card_1")}


def test_get_slots_scoped_to_doctor_not_shared_across_doctors(hospital_id):
    """Booking one doctor's slot must not remove another doctor's identical time."""
    slots = db.get_slots(hospital_id, "doc_card_1")
    target = slots[0]
    db.create_appointment(hospital_id, "111", "cardiology", "doc_card_1", datetime.fromisoformat(f"{target['date']}T{target['time']}:00"))

    other_doctor_slots = db.get_slots(hospital_id, "doc_card_2")

    assert target["id"] in {s["id"] for s in other_doctor_slots}


# --- Appointments ---

def test_create_appointment_returns_populated_record(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    appt = db.create_appointment(hospital_id, "5491112345678", "cardiology", doctor_id, datetime(2026, 1, 1, 10, 0))
    assert appt.phone == "5491112345678"
    assert appt.department_name == "Cardiology"
    assert appt.doctor_name == "Dr. Anjali Rao"
    assert appt.status == db.STATUS_BOOKED
    assert db.get_reminded_offsets(hospital_id, appt.id) == []
    assert appt.id is not None


def test_create_appointment_ids_are_unique(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    a = db.create_appointment(hospital_id, "111", "cardiology", doctor_id, datetime(2026, 1, 1, 10, 0))
    b = db.create_appointment(hospital_id, "222", "cardiology", doctor_id, datetime(2026, 1, 1, 15, 0))
    assert a.id != b.id


def test_double_booking_same_doctor_and_slot_raises_integrity_error(hospital_id):
    """The DB-level guard from db/schema.sql's partial unique index — the actual
    fix for double-booking races, not just application logic."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    when = datetime(2026, 1, 1, 10, 0)
    db.create_appointment(hospital_id, "111", "cardiology", doctor_id, when)
    with pytest.raises(IntegrityError):
        db.create_appointment(hospital_id, "222", "cardiology", doctor_id, when)


def test_double_booking_allowed_once_original_is_cancelled(hospital_id):
    """The unique index is a partial index (WHERE status='booked') — a cancelled
    appointment must free up its slot for a new booking."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    when = datetime(2026, 1, 1, 10, 0)
    first = db.create_appointment(hospital_id, "111", "cardiology", doctor_id, when)
    db.cancel_appointment(hospital_id, first.id)
    second = db.create_appointment(hospital_id, "222", "cardiology", doctor_id, when)  # should not raise
    assert second.id != first.id


def test_get_appointment_found_and_not_found(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    appt = db.create_appointment(hospital_id, "111", "cardiology", doctor_id, datetime(2026, 1, 1, 10, 0))
    assert db.get_appointment(hospital_id, appt.id) == appt
    assert db.get_appointment(hospital_id, 999999) is None


def test_cancel_appointment_sets_status_and_is_not_deleted(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    appt = db.create_appointment(hospital_id, "111", "cardiology", doctor_id, datetime(2026, 1, 1, 10, 0))
    db.cancel_appointment(hospital_id, appt.id)
    got = db.get_appointment(hospital_id, appt.id)
    assert got.status == db.STATUS_CANCELLED  # still present (audit trail), not deleted


def test_mark_rescheduled_sets_status_and_is_not_deleted(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    appt = db.create_appointment(hospital_id, "111", "cardiology", doctor_id, datetime(2026, 1, 1, 10, 0))
    db.mark_rescheduled(hospital_id, appt.id)
    got = db.get_appointment(hospital_id, appt.id)
    assert got.status == db.STATUS_RESCHEDULED


def test_get_upcoming_appointments_for_phone_excludes_past(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    now = datetime(2026, 1, 1, 12, 0)
    db.create_appointment(hospital_id, "5491112345678", "cardiology", doctor_id, now - timedelta(hours=1))
    assert db.get_upcoming_appointments_for_phone(hospital_id, "5491112345678", now=now) == []


def test_get_upcoming_appointments_for_phone_excludes_cancelled_and_rescheduled(hospital_id):
    doctors = db.get_doctors(hospital_id, "cardiology")
    now = datetime(2026, 1, 1, 0, 0)
    cancelled = db.create_appointment(hospital_id, "5491112345678", "cardiology", doctors[0]["id"], now + timedelta(hours=1))
    rescheduled = db.create_appointment(hospital_id, "5491112345678", "cardiology", doctors[1]["id"], now + timedelta(hours=2))
    still_booked = db.create_appointment(hospital_id, "5491112345678", "orthopedics", db.get_doctors(hospital_id, "orthopedics")[0]["id"], now + timedelta(hours=3))
    db.cancel_appointment(hospital_id, cancelled.id)
    db.mark_rescheduled(hospital_id, rescheduled.id)

    result = db.get_upcoming_appointments_for_phone(hospital_id, "5491112345678", now=now)

    assert result == [still_booked]


def test_get_upcoming_appointments_for_phone_scoped_to_phone_and_sorted(hospital_id):
    doctors = db.get_doctors(hospital_id, "cardiology")
    now = datetime(2026, 1, 1, 0, 0)
    other_phone = db.create_appointment(hospital_id, "000", "cardiology", doctors[0]["id"], now + timedelta(hours=1))
    later = db.create_appointment(hospital_id, "111", "orthopedics", db.get_doctors(hospital_id, "orthopedics")[0]["id"], now + timedelta(hours=5))
    sooner = db.create_appointment(hospital_id, "111", "pediatrics", db.get_doctors(hospital_id, "pediatrics")[0]["id"], now + timedelta(hours=2))

    result = db.get_upcoming_appointments_for_phone(hospital_id, "111", now=now)

    assert result == [sooner, later]  # soonest first
    assert other_phone not in result


def test_get_upcoming_appointments_within_window(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    now = datetime(2026, 1, 1, 0, 0)
    appt = db.create_appointment(hospital_id, "111", "cardiology", doctor_id, now + timedelta(hours=5))
    due = db.get_upcoming_appointments(hospital_id, offset_hours=24, now=now)
    assert due == [appt]


def test_get_upcoming_appointments_outside_window_excluded(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    now = datetime(2026, 1, 1, 0, 0)
    db.create_appointment(hospital_id, "111", "cardiology", doctor_id, now + timedelta(hours=48))
    due = db.get_upcoming_appointments(hospital_id, offset_hours=24, now=now)
    assert due == []


def test_mark_reminded_excludes_from_future_queries(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    now = datetime(2026, 1, 1, 0, 0)
    appt = db.create_appointment(hospital_id, "111", "cardiology", doctor_id, now + timedelta(hours=5))
    db.mark_reminded(hospital_id, appt.id, offset_hours=24)
    due = db.get_upcoming_appointments(hospital_id, offset_hours=24, now=now)
    assert due == []
    assert db.get_reminded_offsets(hospital_id, appt.id) == [24]


def test_mark_reminded_is_per_offset_not_global(hospital_id):
    """A hospital with multiple reminder_offsets_hours (e.g. [24, 1]) must get a
    reminder fired for EACH offset independently — marking the 24h one sent
    must not suppress the (still separately due) 1h one."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    now = datetime(2026, 1, 1, 0, 0)
    appt = db.create_appointment(hospital_id, "111", "cardiology", doctor_id, now + timedelta(minutes=30))
    db.mark_reminded(hospital_id, appt.id, offset_hours=24)

    due_at_1h = db.get_upcoming_appointments(hospital_id, offset_hours=1, now=now)

    assert due_at_1h == [appt]  # still due for the 1h offset
    assert db.get_reminded_offsets(hospital_id, appt.id) == [24]

    db.mark_reminded(hospital_id, appt.id, offset_hours=1)
    assert sorted(db.get_reminded_offsets(hospital_id, appt.id)) == [1, 24]
    assert db.get_upcoming_appointments(hospital_id, offset_hours=1, now=now) == []


def test_mark_reminded_same_offset_twice_is_idempotent(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    now = datetime(2026, 1, 1, 0, 0)
    appt = db.create_appointment(hospital_id, "111", "cardiology", doctor_id, now + timedelta(hours=5))

    db.mark_reminded(hospital_id, appt.id, offset_hours=24)
    db.mark_reminded(hospital_id, appt.id, offset_hours=24)  # must not raise or duplicate

    assert db.get_reminded_offsets(hospital_id, appt.id) == [24]


def test_cancelled_appointment_excluded_from_reminder_queries(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    now = datetime(2026, 1, 1, 0, 0)
    appt = db.create_appointment(hospital_id, "111", "cardiology", doctor_id, now + timedelta(hours=5))
    db.cancel_appointment(hospital_id, appt.id)
    due = db.get_upcoming_appointments(hospital_id, offset_hours=24, now=now)
    assert due == []


# --- init_db / seed idempotency ---

def test_init_db_on_connection_is_idempotent(hospital_id):
    """tests/conftest.py's autouse fixture already ran init_db_on_connection()
    once against this test's connection (that's where hospital_id came from,
    and where Test Hospital 2's own separate departments came from too, via
    that same fixture's seed_test_hospital() call) -- calling it again proves
    the schema/seed are safe to re-run, without needing a second, separate
    connection. Scoped to hospital_id specifically so Test Hospital 2's rows
    (also present in this same database) don't affect the count."""
    conn = db_connection.get_connection()

    second_id = init_db_on_connection(conn)

    assert second_id == hospital_id
    dept_count = conn.execute(
        "SELECT COUNT(*) AS c FROM departments WHERE hospital_id = ?", (hospital_id,)
    ).fetchone()["c"]
    assert dept_count == 4  # not doubled by the second call


# --- Connection resilience (Neon closes idle connections server-side) ---

def test_execute_reconnects_when_connection_already_closed(hospital_id):
    """Covers db/connection.py's pre-check path: if .closed is already known
    True (e.g. a previous statement on this connection already discovered it
    was dead) the next query must transparently reconnect, not raise."""
    conn = db_connection.get_connection()
    conn._conn.close()
    assert conn._conn.closed

    depts = db.get_departments(hospital_id)

    assert len(depts) == 4
    assert not conn._conn.closed  # a fresh connection is in place afterward


def test_execute_reconnects_when_connection_dies_server_side_mid_session(hospital_id):
    """Covers db/connection.py's catch-and-retry path -- the one that actually
    matters for Neon's real failure mode. Unlike an explicit .close(), a
    server-side idle-close (or here, pg_terminate_backend from a second
    connection, standing in for it) leaves psycopg2's .closed attribute at 0
    until the client actually tries to use the connection and the query
    itself fails -- so this specifically proves the retry-after-exception
    path, not just the "already known closed" pre-check."""
    import psycopg2

    conn = db_connection.get_connection()
    backend_pid = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]

    killer = psycopg2.connect(conn._dsn)
    killer.autocommit = True
    killer.cursor().execute("SELECT pg_terminate_backend(%s)", (backend_pid,))
    killer.close()

    assert conn._conn.closed == 0  # not yet detected -- this is the point

    depts = db.get_departments(hospital_id)  # must reconnect transparently, not raise

    assert len(depts) == 4

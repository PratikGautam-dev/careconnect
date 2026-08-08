# tests/test_create_appointment_transaction_safety.py
"""
SPEC Section 12.9: db.create_appointment() is the one function in this
codebase that opens a real, explicit Postgres transaction (BEGIN/COMMIT/
ROLLBACK) on the single shared connection, instead of relying on
db/connection.py's autocommit=True like everywhere else -- needed for the
per-(doctor,date) pg_advisory_xact_lock that makes online_quota/walkin_quota/
daily_booking_limit enforcement race-safe (Section 14.7/12.9).

That's exactly the situation db/connection.py's own docstring warns about:
Postgres aborts an ENTIRE explicit transaction after any failed statement,
and every further statement on it fails too ("current transaction is
aborted") until a ROLLBACK -- autocommit=True was chosen everywhere else
specifically to avoid this. This file directly verifies create_appointment()
gets this right: a genuine failure inside its transaction (1) still raises
the correct, catchable exception type (not a raw "transaction aborted"
error no caller's `except IntegrityError:` would recognize), and (2) leaves
the shared connection completely clean and reusable for the very next,
unrelated query -- never poisoned.

This test file also covers the bug this exact investigation turned up:
booking_ordinal was originally assigned as a plain COUNT(*) of currently-
booked rows, which breaks on a real (not contrived) book/cancel/book
sequence, since a cancellation doesn't free its ordinal -- see
test_ordinal_reassigned_correctly_after_cancellation_leaves_a_gap.
"""
import os
from datetime import datetime, timedelta

import pytest

import db.connection as db_connection
import db.repository as db
from db.connection import IntegrityError

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")


def test_failed_insert_inside_transaction_raises_a_real_integrity_error(hospital_id):
    """Forces a genuine SQL-level failure INSIDE create_appointment()'s
    BEGIN/COMMIT block: a nonexistent doctor_id sails through the free-
    ordinal check (no existing rows reference it) but then fails the
    INSERT's own doctors(id) foreign-key constraint -- a real Postgres
    error, not a Python-level "no room" check. The exception that reaches
    the caller must still be (or subclass) db.connection.IntegrityError --
    the whole point of every `except IntegrityError:` call site
    (core/booking_flow.py, portal.py) -- not some other psycopg2 error type
    that would silently skip that handling and surface as an unhandled 500."""
    department_id = db.get_departments(hospital_id)[0]["id"]
    scheduled_at = datetime.now() + timedelta(days=1)

    with pytest.raises(IntegrityError):
        db.create_appointment(hospital_id, "5490001111", department_id, "totally-fake-doctor-id", scheduled_at)


def test_connection_is_clean_and_reusable_after_a_failed_booking(hospital_id):
    """The actual question: after create_appointment() fails partway through
    its own explicit transaction, is the single shared connection left in a
    state where the very next, completely unrelated query still works? If
    the transaction weren't properly rolled back, this next query would fail
    with "current transaction is aborted, commands ignored until end of
    transaction block" -- silently breaking every OTHER request/tenant
    sharing this same process-wide connection, not just this one booking."""
    department_id = db.get_departments(hospital_id)[0]["id"]
    scheduled_at = datetime.now() + timedelta(days=1)

    with pytest.raises(IntegrityError):
        db.create_appointment(hospital_id, "5490001111", department_id, "totally-fake-doctor-id", scheduled_at)

    # An unrelated read, straight on the shared connection.
    conn = db_connection.get_connection()
    row = conn.execute("SELECT COUNT(*) AS c FROM hospitals").fetchone()
    assert row["c"] >= 1

    # And a normal, unrelated write through the full repository layer --
    # not just a raw SELECT -- to prove the connection is genuinely usable
    # for real application work afterward, not merely "not throwing."
    other_dept = db.create_department(hospital_id, "Post-Failure Department")
    assert other_dept["name"] == "Post-Failure Department"


def test_create_appointment_succeeds_normally_immediately_after_a_forced_failure(hospital_id):
    """The most direct version of the question: call the SAME function that
    just failed, again, for a real doctor, on the same connection -- it must
    succeed exactly as if the earlier failure never happened."""
    department_id = db.get_departments(hospital_id)[0]["id"]
    doctor_id = db.get_doctors(hospital_id, department_id)[0]["id"]
    scheduled_at = datetime.now() + timedelta(days=1)

    with pytest.raises(IntegrityError):
        db.create_appointment(hospital_id, "5490001111", department_id, "totally-fake-doctor-id", scheduled_at)

    appt = db.create_appointment(hospital_id, "5490002222", department_id, doctor_id, scheduled_at)
    assert appt.id is not None
    assert db.get_appointment(hospital_id, appt.id) is not None


def test_quota_rejection_also_leaves_connection_clean(hospital_id):
    """A QuotaExceededError is raised from a Python-level check (never an
    actual failed SQL statement), so this path was never at risk the same
    way -- but it goes through the identical ROLLBACK/raise machinery, so
    it's worth confirming explicitly too, not just assumed safe by
    resemblance to the SQL-failure case above."""
    department_id = db.get_departments(hospital_id)[0]["id"]
    doctor = db.create_doctor(
        hospital_id, department_id, "Dr. Quota Rollback Test",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=60, daily_booking_limit=0,
    )
    # daily_booking_limit=0 means generate_slots_for_doctor() produces no
    # doctor_slots rows at all for this doctor -- irrelevant here, since
    # create_appointment() only ever checks the appointments table itself,
    # not doctor_slots, so an explicit future time reaches the quota check
    # the same way a real (slot-picker-driven) booking attempt would.
    scheduled_at = datetime.now() + timedelta(days=1)

    with pytest.raises(db.QuotaExceededError):
        db.create_appointment(hospital_id, "5490003333", department_id, doctor["id"], scheduled_at)

    conn = db_connection.get_connection()
    row = conn.execute("SELECT COUNT(*) AS c FROM hospitals").fetchone()
    assert row["c"] >= 1


def test_ordinal_reassigned_correctly_after_cancellation_leaves_a_gap(hospital_id):
    """Regression test for the bug this investigation found: booking_ordinal
    used to be assigned as COUNT(*) of currently-booked rows at a slot, which
    breaks on a real book/cancel/book sequence -- book A (ordinal 0), book B
    (ordinal 1), cancel A (frees ordinal 0, but COUNT(booked) drops to 1),
    book C should reuse the freed ordinal 0, not collide with B's ordinal 1
    or be incorrectly rejected as "no free slot" when there plainly is one."""
    department_id = db.get_departments(hospital_id)[0]["id"]
    doctor = db.create_doctor(
        hospital_id, department_id, "Dr. Ordinal Gap Test",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=60, max_bookings_per_slot=2,
    )
    slot = db.get_slots(hospital_id, doctor["id"])[0]
    scheduled_at = datetime.fromisoformat(f"{slot['date']}T{slot['time']}:00")

    appt_a = db.create_appointment(hospital_id, "5490004444", department_id, doctor["id"], scheduled_at)
    appt_b = db.create_appointment(hospital_id, "5490005555", department_id, doctor["id"], scheduled_at)
    db.cancel_appointment(hospital_id, appt_a.id)

    # Must succeed -- there IS room (B holds only 1 of 2 seats) -- not raise
    # IntegrityError, and not collide with B's still-booked row.
    appt_c = db.create_appointment(hospital_id, "5490006666", department_id, doctor["id"], scheduled_at)
    assert appt_c.id is not None
    assert db.get_appointment(hospital_id, appt_c.id).status == "booked"

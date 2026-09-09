# tests/test_slots.py
"""
SPEC Section 12.1.1: the periodic slot top-up job (slots/scheduler.py) and its
/internal/top-up-slots endpoint (core/main.py) -- same pattern as
reminders/scheduler.py and /internal/send-reminders, proven the same way.

Migration 0032 moved DOCTOR slots off this pre-generation model entirely (a
doctor's grid is computed live -- db/repositories/doctors.py's
compute_doctor_candidate_slots()), so top_up_slots_for_hospital() no longer
covers doctors at all -- only diagnostic/procedure resources still use it.
Doctor-facing tests below instead cover connectors/tier1.py's grid cache +
invalidation, the mechanism that replaced doctor top-up.
"""
import os

import db.connection as db_connection
import db.repository as db
from connectors.tier1 import Tier1Connector
from slots.scheduler import top_up_slots_for_hospital

# Same defensive env-var setup as tests/test_main.py -- core.main is only
# actually imported the first time any test file does so.
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")
# DATABASE_URL is already pointed at the test Postgres instance by
# tests/conftest.py (loaded before this module).

from main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


# --- top_up_slots_for_hospital(): diagnostic/procedure resources only now ---

def test_top_up_slots_for_hospital_is_a_no_op_when_window_already_populated(hospital_id):
    """The seeded default hospital has no diagnostic/procedure resources at
    all -- a top-up run finds nothing to do (doctors are no longer part of
    this job, see module docstring)."""
    generated = top_up_slots_for_hospital(hospital_id)
    assert generated == 0


def test_top_up_slots_for_hospital_extends_a_resource_added_without_slots(hospital_id):
    """A diagnostic resource inserted directly (not through create_resource(),
    which auto-generates) has a working pattern but zero slots until topped
    up -- same "manually inserted, generation is separate" scenario the old
    doctor-based version of this test covered before migration 0032."""
    conn = db_connection.get_connection()
    conn.execute(
        "INSERT INTO diagnostic_resources (id, hospital_id, name, working_days, working_hours, slot_duration_minutes) "
        "VALUES ('manual_res', ?, 'MRI Machine', 'Mon,Tue,Wed,Thu,Fri,Sat,Sun', '10:00-11:00', 60)",
        (hospital_id,),
    )
    conn.commit()
    assert db.get_resource_slots(hospital_id, "manual_res") == []

    generated = top_up_slots_for_hospital(hospital_id)

    assert generated == 14  # one slot/day across the default 14-day window
    assert len(db.get_resource_slots(hospital_id, "manual_res")) == 14


def test_top_up_slots_endpoint_requires_internal_secret(hospital_id):
    resp = client.post("/internal/top-up-slots", headers={"X-Internal-Secret": "wrong"})
    assert resp.status_code == 403


def test_top_up_slots_endpoint_reports_zero_when_already_topped_up(hospital_id, second_hospital_id):
    resp = client.post("/internal/top-up-slots", headers={"X-Internal-Secret": "internalsecret"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["generated"] == 0
    assert body["by_hospital"]["Default Hospital"] == 0
    assert body["by_hospital"]["Test Hospital 2"] == 0


def test_top_up_slots_endpoint_only_covers_active_hospitals(hospital_id):
    """Mirrors reminders' own active-hospitals scoping (SPEC Section 12.2):
    a deactivated hospital is never topped up."""
    conn = db_connection.get_connection()
    conn.execute("UPDATE hospitals SET is_active = 0 WHERE id = ?", (hospital_id,))
    conn.commit()

    resp = client.post("/internal/top-up-slots", headers={"X-Internal-Secret": "internalsecret"})

    assert resp.status_code == 200
    assert "Default Hospital" not in resp.json()["by_hospital"]


def test_top_up_slots_for_hospital_respects_configured_future_booking_days(hospital_id):
    """future_booking_days (hospital_settings) replaces the old hardcoded
    14-day default -- a hospital that configures a longer window gets it
    applied here without needing to pass days_ahead explicitly."""
    db.update_hospital_settings(
        hospital_id, followup_validity_days=None, followup_fee=None, new_consultation_fee=None,
        future_booking_days=20,
    )
    conn = db_connection.get_connection()
    conn.execute(
        "INSERT INTO diagnostic_resources (id, hospital_id, name, working_days, working_hours, slot_duration_minutes) "
        "VALUES ('manual_res_20', ?, 'CT Scanner', 'Mon,Tue,Wed,Thu,Fri,Sat,Sun', '10:00-11:00', 60)",
        (hospital_id,),
    )
    conn.commit()

    top_up_slots_for_hospital(hospital_id)

    assert len(db.get_resource_slots(hospital_id, "manual_res_20")) == 20  # one slot/day, 20-day window


def test_self_healing_top_up_recovers_a_resource_whose_window_ran_dry(hospital_id):
    """Diagnostic/procedure resources still depend on connectors/tier1.py's
    self-healing top-up (doctors no longer do -- migration 0032 replaced
    their whole pre-generation model). The live bug this covers: a
    resource's rolling window can run out entirely if nothing ever tops it
    up (the external cron this depends on isn't guaranteed to exist) -- the
    very next bot-facing read must regenerate the window automatically, with
    no manual intervention."""
    resource = db.create_resource(
        hospital_id, "Ultrasound Machine",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-17:00"], slot_duration_minutes=60,
    )
    assert db.get_resource_slots(hospital_id, resource["id"]) != []  # sanity: freshly created, has slots

    conn = db_connection.get_connection()
    conn.execute(
        "DELETE FROM diagnostic_resource_slots WHERE hospital_id = ? AND resource_id = ?",
        (hospital_id, resource["id"]),
    )
    conn.commit()
    assert db.get_resource_slots(hospital_id, resource["id"]) == []

    connector = Tier1Connector()
    slots = connector.get_available_resource_slots(hospital_id, resource["id"])

    assert slots != []


# --- Doctors: grid cache (connectors/tier1.py) + invalidation, the
# mechanism that replaced pre-generation + top-up for doctors entirely ---

def test_doctor_grid_cache_reflects_schedule_change_immediately(hospital_id):
    """The grid cache (up to an hour TTL) must never show a stale schedule --
    db/repositories/doctors.py's invalidate_doctor_slots_cache(), called from
    update_doctor(), is what keeps it correct despite the long TTL."""
    department = db.get_departments(hospital_id)[0]
    doctor = db.create_doctor(
        hospital_id, department["id"], "Dr. Cache Freshness",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=60,
    )
    connector = Tier1Connector()
    first_read = connector.get_available_slots(hospital_id, doctor["id"])
    assert first_read
    assert all(s["time"] == "09:00" for s in first_read)

    db.update_doctor(
        hospital_id, doctor["id"], "Dr. Cache Freshness",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["14:00-15:00"], slot_duration_minutes=60,
    )

    second_read = connector.get_available_slots(hospital_id, doctor["id"])
    assert second_read
    assert all(s["time"] == "14:00" for s in second_read)


def test_doctor_grid_cache_reflects_leave_immediately(hospital_id):
    department = db.get_departments(hospital_id)[0]
    doctor = db.create_doctor(
        hospital_id, department["id"], "Dr. Cache Leave",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=60,
    )
    connector = Tier1Connector()
    first_read = connector.get_available_slots(hospital_id, doctor["id"])
    leave_date = first_read[0]["date"]

    db.create_doctor_leave(hospital_id, doctor["id"], leave_date, reason="Conference")

    second_read = connector.get_available_slots(hospital_id, doctor["id"])
    assert all(s["date"] != leave_date for s in second_read)

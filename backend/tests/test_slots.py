# tests/test_slots.py
"""
SPEC Section 12.1.1: the periodic slot top-up job (slots/scheduler.py) and its
/internal/top-up-slots endpoint (core/main.py) -- same pattern as
reminders/scheduler.py and /internal/send-reminders, proven the same way.
"""
import os

import db.connection as db_connection
import db.repository as db
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

from backend.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


def test_top_up_slots_for_hospital_is_a_no_op_when_window_already_populated(hospital_id):
    """db/seed.py already generates the full 14-day window for every seeded
    doctor -- a top-up run right after seeding must find nothing new to add."""
    generated = top_up_slots_for_hospital(hospital_id)
    assert generated == 0


def test_top_up_slots_for_hospital_extends_a_doctor_added_without_slots(hospital_id):
    """A doctor created directly (not through create_doctor(), which
    auto-generates) has a working pattern but zero slots until topped up."""
    conn = db_connection.get_connection()
    conn.execute(
        "INSERT INTO doctors (id, hospital_id, department_id, name, working_days, working_hours, slot_duration_minutes) "
        "VALUES ('manual_doc', ?, 'cardiology', 'Dr. Manually Inserted', 'Mon,Tue,Wed,Thu,Fri,Sat,Sun', '10:00-11:00', 60)",
        (hospital_id,),
    )
    conn.commit()
    assert db.get_slots(hospital_id, "manual_doc") == []

    generated = top_up_slots_for_hospital(hospital_id)

    assert generated == 14  # one slot/day across the 14-day window
    assert len(db.get_slots(hospital_id, "manual_doc")) == 14


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
    a deactivated hospital's doctors are never topped up."""
    conn = db_connection.get_connection()
    conn.execute("UPDATE hospitals SET is_active = 0 WHERE id = ?", (hospital_id,))
    conn.commit()

    resp = client.post("/internal/top-up-slots", headers={"X-Internal-Secret": "internalsecret"})

    assert resp.status_code == 200
    assert "Default Hospital" not in resp.json()["by_hospital"]

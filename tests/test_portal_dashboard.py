# tests/test_portal_dashboard.py
"""
SPEC Section 12.8: the staff dashboard (/portal/dashboard) -- default landing
page after login, per hospital. Covers db/repository.py's dashboard query
functions directly against known, hand-inserted data (unit-level, same style
as tests/test_db.py -- create_appointment() doesn't let a caller control
created_at/updated_at, and these queries need to), a live HTTP round trip
for a hospital WITH data, cross-tenant isolation (hospital A's dashboard
must never surface hospital B's rows), and the empty-state case for a
brand-new hospital with nothing at all yet.
"""
import os
from datetime import datetime

import db.connection as db_connection
import db.repository as db

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")

from core.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from tests.test_portal import _login, _set_portal_password, client as portal_client  # noqa: E402

client = TestClient(app)


def _insert_appointment(
    hospital_id: int, phone: str, department_id: str, doctor_id: str,
    scheduled_at: datetime, created_at: datetime, status: str = "booked", updated_at: datetime | None = None,
) -> int:
    """Raw INSERT, bypassing db.create_appointment() -- that function always
    stamps created_at via Postgres's own now()::text default and has no way
    to backdate it, but these dashboard queries are specifically about
    dates/times, so tests need full control over created_at/updated_at too."""
    conn = db_connection.get_connection()
    cur = conn.execute(
        "INSERT INTO appointments (hospital_id, phone, department_id, doctor_id, scheduled_at, status, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (hospital_id, phone, department_id, doctor_id, scheduled_at.isoformat(), status,
         created_at.isoformat(), updated_at.isoformat() if updated_at else None),
    )
    conn.commit()
    return cur.fetchone()["id"]


# --- db.get_dashboard_stats(): counts + week-over-week deltas ---

def test_dashboard_stats_counts_match_known_seeded_data(hospital_id):
    now = datetime(2027, 6, 15, 14, 0, 0)  # a fixed "now" -- deterministic regardless of when the suite runs
    doctor_id = "doc_card_1"

    # Today: 2 booked (one already past `now`, one still upcoming) + 1 cancelled.
    _insert_appointment(hospital_id, "5490001111", "cardiology", doctor_id,
                         datetime(2027, 6, 15, 10, 0), datetime(2027, 6, 15, 9, 0))
    _insert_appointment(hospital_id, "5490002222", "cardiology", doctor_id,
                         datetime(2027, 6, 15, 16, 0), datetime(2027, 6, 15, 9, 30))
    _insert_appointment(hospital_id, "5490003333", "cardiology", doctor_id,
                         datetime(2027, 6, 15, 11, 0), datetime(2027, 6, 15, 9, 45),
                         status="cancelled", updated_at=datetime(2027, 6, 15, 12, 0))
    # A repeat patient: an appointment created today, but this phone's
    # EARLIEST appointment was created last week -- must NOT count as new.
    _insert_appointment(hospital_id, "5490004444", "cardiology", doctor_id,
                         datetime(2027, 6, 15, 13, 0), datetime(2027, 6, 8, 8, 0))
    _insert_appointment(hospital_id, "5490004444", "cardiology", doctor_id,
                         datetime(2027, 6, 16, 9, 0), datetime(2027, 6, 15, 9, 50))

    stats = db.get_dashboard_stats(hospital_id, now=now)

    # Scheduled on 2027-06-15: the 10:00 (booked), 16:00 (booked), 11:00
    # (cancelled), and 13:00 (booked, repeat patient's OLDER appointment)
    # rows -- the repeat patient's newer row is scheduled the 16th, not today.
    assert stats["today_appointments"] == 4
    assert stats["confirmed_today"] == 3  # booked (not cancelled) ones scheduled today: 10:00, 16:00, 13:00
    assert stats["no_shows_today"] == 2  # still-booked AND already past `now` (14:00): the 10:00 and 13:00 ones
    assert stats["new_patients_today"] == 3  # the 3 first-contact phones created today -- the repeat patient's phone is excluded (its earlier appointment predates today)


def test_dashboard_stats_week_over_week_delta_up_down_and_flat(hospital_id):
    now = datetime(2027, 6, 15, 14, 0, 0)
    last_week = datetime(2027, 6, 8, 14, 0, 0)
    doctor_id = "doc_card_1"

    # Today: 3 booked appointments.
    for i, phone in enumerate(["5490011111", "5490022222", "5490033333"]):
        _insert_appointment(hospital_id, phone, "cardiology", doctor_id,
                             datetime(2027, 6, 15, 9 + i, 0), datetime(2027, 6, 15, 8, 0))
    # Same weekday last week: 2 booked appointments (both already in the past).
    for i, phone in enumerate(["5490044444", "5490055555"]):
        _insert_appointment(hospital_id, phone, "cardiology", doctor_id,
                             datetime(2027, 6, 8, 9 + i, 0), datetime(2027, 6, 8, 8, 0))

    stats = db.get_dashboard_stats(hospital_id, now=now)
    assert stats["today_appointments"] == 3
    assert stats["today_appointments_delta_pct"] == 50.0  # (3-2)/2 * 100
    # confirmed_today == today_appointments here (nothing cancelled) -- same delta.
    assert stats["confirmed_today_delta_pct"] == 50.0


def test_dashboard_stats_delta_is_none_without_a_last_week_baseline(hospital_id):
    now = datetime(2027, 6, 15, 14, 0, 0)
    _insert_appointment(hospital_id, "5490099999", "cardiology", "doc_card_1",
                         datetime(2027, 6, 15, 9, 0), datetime(2027, 6, 15, 8, 0))
    stats = db.get_dashboard_stats(hospital_id, now=now)
    assert stats["today_appointments"] == 1
    assert stats["today_appointments_delta_pct"] is None  # zero appointments the same weekday last week -- no baseline


def test_dashboard_stats_empty_hospital_all_zero(hospital_id, second_hospital_id):
    """second_hospital_id has its own departments/doctors seeded but no
    appointments at all -- every stat must be 0, every delta None, no
    division-by-zero, no exception."""
    stats = db.get_dashboard_stats(second_hospital_id, now=datetime(2027, 6, 15, 14, 0, 0))
    assert stats == {
        "today_appointments": 0, "today_appointments_delta_pct": None,
        "confirmed_today": 0, "confirmed_today_delta_pct": None,
        "new_patients_today": 0, "new_patients_today_delta_pct": None,
        "no_shows_today": 0, "no_shows_today_delta_pct": None,
    }


# --- db.get_weekly_appointment_counts() ---

def test_weekly_appointment_counts_correct_per_day(hospital_id):
    now = datetime(2027, 6, 15, 12, 0, 0)  # Tuesday
    doctor_id = "doc_card_1"
    _insert_appointment(hospital_id, "5490011111", "cardiology", doctor_id,
                         datetime(2027, 6, 15, 9, 0), datetime(2027, 6, 15, 8, 0))
    _insert_appointment(hospital_id, "5490022222", "cardiology", doctor_id,
                         datetime(2027, 6, 15, 10, 0), datetime(2027, 6, 15, 8, 0))
    _insert_appointment(hospital_id, "5490033333", "cardiology", doctor_id,
                         datetime(2027, 6, 13, 9, 0), datetime(2027, 6, 13, 8, 0))
    # Outside the 7-day window (8 days before `now`) -- must not be counted.
    _insert_appointment(hospital_id, "5490044444", "cardiology", doctor_id,
                         datetime(2027, 6, 7, 9, 0), datetime(2027, 6, 7, 8, 0))

    counts = db.get_weekly_appointment_counts(hospital_id, now=now)
    assert len(counts) == 7
    assert counts[-1]["date"] == "2027-06-15"  # today is last (oldest-first ordering)
    assert counts[-1]["count"] == 2
    by_date = {c["date"]: c["count"] for c in counts}
    assert by_date["2027-06-13"] == 1
    assert "2027-06-07" not in by_date


def test_weekly_appointment_counts_empty_hospital_all_zero(second_hospital_id):
    counts = db.get_weekly_appointment_counts(second_hospital_id, now=datetime(2027, 6, 15, 12, 0, 0))
    assert len(counts) == 7
    assert all(c["count"] == 0 for c in counts)


# --- db.get_appointments_by_department() ---

def test_appointments_by_department_grouped_correctly(hospital_id):
    now = datetime(2027, 6, 15, 12, 0, 0)
    _insert_appointment(hospital_id, "5490011111", "cardiology", "doc_card_1",
                         datetime(2027, 6, 10, 9, 0), datetime(2027, 6, 10, 8, 0))
    _insert_appointment(hospital_id, "5490022222", "cardiology", "doc_card_1",
                         datetime(2027, 6, 11, 9, 0), datetime(2027, 6, 11, 8, 0))
    _insert_appointment(hospital_id, "5490033333", "orthopedics", "doc_ortho_1",
                         datetime(2027, 6, 12, 9, 0), datetime(2027, 6, 12, 8, 0))
    # Outside the 30-day window.
    _insert_appointment(hospital_id, "5490044444", "orthopedics", "doc_ortho_1",
                         datetime(2027, 4, 1, 9, 0), datetime(2027, 4, 1, 8, 0))

    breakdown = db.get_appointments_by_department(hospital_id, days=30, now=now)
    by_dept = {b["department_name"]: b["count"] for b in breakdown}
    assert by_dept == {"Cardiology": 2, "Orthopedics": 1}
    assert breakdown[0]["department_name"] == "Cardiology"  # descending by count


def test_appointments_by_department_empty_when_no_appointments(second_hospital_id):
    assert db.get_appointments_by_department(second_hospital_id) == []


# --- db.get_recent_activity_feed() ---

def test_recent_activity_feed_uses_updated_at_for_status_changes(hospital_id):
    # Both rows are backdated well into the past (real wall-clock time, not
    # `now=` parameters) -- db.cancel_appointment() stamps updated_at with the
    # REAL current time internally (it has no `now=` override), so the
    # cancelled row's event must always be more recent than these no matter
    # when this test actually runs.
    booked_created = datetime(2020, 1, 1, 8, 0)
    to_cancel_created = datetime(2020, 1, 1, 7, 0)  # created BEFORE the booked one, but cancelled AFTER both
    _insert_appointment(hospital_id, "5490011111", "cardiology", "doc_card_1",
                         datetime(2020, 1, 5, 9, 0), booked_created)
    to_cancel_id = _insert_appointment(hospital_id, "5490022222", "cardiology", "doc_card_1",
                                        datetime(2020, 1, 6, 9, 0), to_cancel_created)
    db.cancel_appointment(hospital_id, to_cancel_id)

    feed = db.get_recent_activity_feed(hospital_id, limit=10)
    labels_by_phone = {e["phone"]: e["label"] for e in feed}
    assert labels_by_phone["5490011111"] == "Booked appointment"
    assert labels_by_phone["5490022222"] == "Cancelled appointment"

    # The cancelled event sorts by ITS OWN updated_at (just now, real time),
    # not the original created_at (2020-01-01 07:00, earlier than the other
    # row's created_at) -- so it's more recent than the untouched booking
    # despite having been created first.
    assert feed[0]["phone"] == "5490022222"
    assert feed[0]["at"] > booked_created


def test_recent_activity_feed_empty_when_no_appointments(second_hospital_id):
    assert db.get_recent_activity_feed(second_hospital_id) == []


# --- HTTP layer: /portal/dashboard ---

def test_dashboard_requires_login(hospital_id):
    resp = portal_client.get("/portal/dashboard", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/portal/login"


def test_dashboard_renders_for_hospital_with_data(hospital_id):
    _insert_appointment(hospital_id, "5490011111", "cardiology", "doc_card_1",
                         datetime.now(), datetime.now())
    _login(hospital_id, "dash-data-pw")
    try:
        resp = portal_client.get("/portal/dashboard")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text
        assert "Today's Appointments" in resp.text
        assert "weekly-chart" in resp.text
        assert "5490011111" in resp.text  # shows up in the recent appointments table
        assert "chart.js" in resp.text.lower()  # CDN script actually included
    finally:
        portal_client.cookies.clear()


def test_dashboard_renders_empty_state_for_brand_new_hospital(hospital_id):
    """A hospital with zero departments/doctors/appointments at all -- every
    section must fall back to its empty-state message, not error out."""
    conn = db_connection.get_connection()
    cur = conn.execute(
        "INSERT INTO hospitals (name, whatsapp_phone_number_id, portal_password_hash) VALUES (?, ?, ?) RETURNING id",
        ("Brand New Hospital", "BRAND_NEW_PHONE_ID", db.hash_portal_password("brand-new-pw")),
    )
    conn.commit()
    new_hospital_id = cur.fetchone()["id"]

    resp = portal_client.post("/portal/login", data={"password": "brand-new-pw"}, follow_redirects=False)
    assert resp.status_code == 303
    try:
        resp = portal_client.get("/portal/dashboard")
        assert resp.status_code == 200
        assert "No appointments in the last 30 days" in resp.text
        assert "No appointments yet" in resp.text
        assert "No recent activity" in resp.text
        assert ">0<" in resp.text  # stat tiles render 0, not blank/broken
    finally:
        portal_client.cookies.clear()


def test_dashboard_cross_tenant_isolation(hospital_id, second_hospital_id):
    """Central requirement (SPEC Section 12.2): hospital A's dashboard must
    never surface hospital B's appointments, departments, or patient phones."""
    _insert_appointment(hospital_id, "5490011111", "cardiology", "doc_card_1",
                         datetime.now(), datetime.now())
    _insert_appointment(second_hospital_id, "5490099999", "t2_neurology", "t2_doc_neuro_1",
                         datetime.now(), datetime.now())

    _login(hospital_id, "isolation-a-pw")
    try:
        resp = portal_client.get("/portal/dashboard")
        assert resp.status_code == 200
        assert "5490011111" in resp.text
        assert "5490099999" not in resp.text
        assert "Neurology" not in resp.text
    finally:
        portal_client.cookies.clear()

    _login(second_hospital_id, "isolation-b-pw")
    try:
        resp = portal_client.get("/portal/dashboard")
        assert resp.status_code == 200
        assert "5490099999" in resp.text
        assert "5490011111" not in resp.text
        assert "Cardiology" not in resp.text
    finally:
        portal_client.cookies.clear()

    # And the underlying stats themselves are correctly scoped too, not just
    # incidentally absent from the rendered HTML.
    stats_a = db.get_dashboard_stats(hospital_id)
    stats_b = db.get_dashboard_stats(second_hospital_id)
    assert stats_a["today_appointments"] >= 1
    assert stats_b["today_appointments"] >= 1

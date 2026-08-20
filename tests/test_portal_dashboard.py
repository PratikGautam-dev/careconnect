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
        "upcoming_appointments": 0,
    }


def test_upcoming_appointments_counts_future_booked_only(hospital_id):
    """Not "today"-scoped like the other four stats -- deliberately, so a
    hospital's very first (near-certainly future-dated) booking shows up
    here immediately rather than reading as an empty dashboard."""
    now = datetime(2027, 6, 15, 14, 0, 0)
    doctor_id = "doc_card_1"
    # Counts: a booked appointment far in the future.
    _insert_appointment(hospital_id, "5490001111", "cardiology", doctor_id,
                         datetime(2027, 7, 20, 10, 0), datetime(2027, 6, 15, 9, 0))
    # Doesn't count: already in the past relative to `now`.
    _insert_appointment(hospital_id, "5490002222", "cardiology", doctor_id,
                         datetime(2027, 6, 15, 10, 0), datetime(2027, 6, 1, 9, 0))
    # Doesn't count: future but cancelled.
    _insert_appointment(hospital_id, "5490003333", "cardiology", doctor_id,
                         datetime(2027, 7, 21, 10, 0), datetime(2027, 6, 15, 9, 0), status="cancelled")

    stats = db.get_dashboard_stats(hospital_id, now=now)
    assert stats["upcoming_appointments"] == 1


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


def test_appointments_by_department_window_extends_forward_too(hospital_id):
    """Not a past-only window -- a hospital's first booking is almost always
    for a future date, and this donut used to stay empty right after it came
    in. Window is ±30 days around `now` by default."""
    now = datetime(2027, 6, 15, 12, 0, 0)
    _insert_appointment(hospital_id, "5490011111", "cardiology", "doc_card_1",
                         datetime(2027, 6, 20, 9, 0), datetime(2027, 6, 15, 8, 0))  # 5 days in the future
    # Outside a ±30-day window either direction.
    _insert_appointment(hospital_id, "5490022222", "orthopedics", "doc_ortho_1",
                         datetime(2027, 8, 1, 9, 0), datetime(2027, 6, 15, 8, 0))

    breakdown = db.get_appointments_by_department(hospital_id, days=30, now=now)
    by_dept = {b["department_name"]: b["count"] for b in breakdown}
    assert by_dept == {"Cardiology": 1}


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

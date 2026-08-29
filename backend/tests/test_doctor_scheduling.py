# tests/test_doctor_scheduling.py
"""
SPEC Section 14.7: richer doctor scheduling -- breaks, per-doctor
max_bookings_per_slot, daily_booking_limit, online/walk-in quotas,
followup_duration_minutes, effective_from, and doctor_leave (whole-day
unavailability). Covers db/repository.py's generate_slots_for_doctor()/
create_appointment()/get_slots()/doctor_leave CRUD changes directly
(unit-level, same style as tests/test_db.py), admin/onboarding.py's
_validate_doctor_fields() extension, and the wizard/portal HTTP paths that
wire all of it together end to end.
"""
import os
from datetime import date, datetime, timedelta

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
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")

from admin.validation import _validate_doctor_fields  # noqa: E402
from main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


# --- generate_slots_for_doctor(): breaks, leave, daily_booking_limit, effective_from ---

def test_break_window_excluded_from_generated_slots(hospital_id):
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Break Test",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
        working_hours=["09:00-11:00"],
        slot_duration_minutes=30,
        breaks=["10:00-10:30"],
    )
    slots = db.get_slots(hospital_id, doctor["id"])
    assert slots  # sanity: generation actually produced something
    times = {s["time"] for s in slots}
    assert "10:00" not in times  # the break window itself
    assert "09:00" in times and "10:30" in times  # before/after the break still offered


def test_break_partially_overlapping_a_candidate_slot_excludes_it(hospital_id):
    """A candidate slot only needs to overlap the break at all (not be fully
    contained) to be excluded -- e.g. a 30-minute slot starting at 09:45 with
    a break at 10:00-10:30 overlaps [09:45, 10:15) vs [10:00, 10:30)."""
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Overlap Test",
        working_days=["Mon"], working_hours=["09:00-11:00"],
        slot_duration_minutes=45, breaks=["10:00-10:30"],
    )
    slots = db.get_slots(hospital_id, doctor["id"])
    times = {s["time"] for s in slots if s["date"] == slots[0]["date"]}
    # 09:00-09:45 (fine), 09:45-10:30 (overlaps break, excluded), 10:30-11:15 (past shift end, not generated)
    assert "09:00" in times
    assert "09:45" not in times


def test_doctor_leave_date_skipped_entirely(hospital_id):
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Leave Test",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
        working_hours=["09:00-10:00"], slot_duration_minutes=30,
    )
    slots_before = db.get_slots(hospital_id, doctor["id"])
    leave_date = slots_before[0]["date"]

    db.create_doctor_leave(hospital_id, doctor["id"], leave_date, reason="Conference")

    slots_after = db.get_slots(hospital_id, doctor["id"])
    assert all(s["date"] != leave_date for s in slots_after)
    assert len(slots_after) < len(slots_before)


def test_doctor_leave_crud(hospital_id):
    doctor = db.create_doctor(hospital_id, "cardiology", "Dr. Leave CRUD")
    assert db.get_doctor_leave(hospital_id, doctor["id"]) == []

    created = db.create_doctor_leave(hospital_id, doctor["id"], "2027-01-15", "Holiday")
    assert created == {"date": "2027-01-15", "reason": "Holiday"}
    leave = db.get_doctor_leave(hospital_id, doctor["id"])
    assert len(leave) == 1
    assert leave[0]["date"] == "2027-01-15"
    assert leave[0]["reason"] == "Holiday"

    # Idempotent re-add of the same date.
    db.create_doctor_leave(hospital_id, doctor["id"], "2027-01-15", "Holiday (again)")
    assert len(db.get_doctor_leave(hospital_id, doctor["id"])) == 1

    assert db.delete_doctor_leave(hospital_id, doctor["id"], leave[0]["id"]) is True
    assert db.get_doctor_leave(hospital_id, doctor["id"]) == []
    assert db.delete_doctor_leave(hospital_id, doctor["id"], 999999) is False


def test_daily_booking_limit_caps_slot_generation_per_day(hospital_id):
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Daily Limit Test",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
        working_hours=["09:00-13:00"],  # 8 x 30-min slots/day without a cap
        slot_duration_minutes=30,
        daily_booking_limit=3,
    )
    slots = db.get_slots(hospital_id, doctor["id"])
    by_date: dict[str, list] = {}
    for s in slots:
        by_date.setdefault(s["date"], []).append(s)
    assert by_date  # sanity
    for day_slots in by_date.values():
        assert len(day_slots) <= 3
    # Soonest-first: the day's kept slots are the EARLIEST ones, not a random subset.
    first_day = sorted(by_date)[0]
    assert sorted(s["time"] for s in by_date[first_day]) == ["09:00", "09:30", "10:00"]


def test_effective_from_gates_slot_generation_to_future_dates(hospital_id):
    today = date.today()
    future = today + timedelta(days=10)
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Effective Future",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=30,
        effective_from=future.isoformat(),
    )
    slots = db.get_slots(hospital_id, doctor["id"])
    assert slots
    assert all(date.fromisoformat(s["date"]) >= future for s in slots)


def test_update_doctor_with_effective_from_preserves_earlier_unbooked_slots(hospital_id):
    """Section 14.7: a schedule change with a future effective_from must not
    retroactively touch already-offered slots dated before it -- only dates
    on/after effective_from get the new pattern (a db.update_doctor()-level
    regeneration-safety check; unrelated to the doctor-EDIT HTTP route,
    which no longer exists anywhere -- see Spec.md Section 0)."""
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Effective Update",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=30,
    )
    slots_before = db.get_slots(hospital_id, doctor["id"])
    assert slots_before
    old_pattern_dates = {s["date"] for s in slots_before}

    future = date.today() + timedelta(days=10)
    db.update_doctor(
        hospital_id, doctor["id"], "Dr. Effective Update",
        working_days=["Mon"], working_hours=["14:00-15:00"], slot_duration_minutes=60,
        effective_from=future.isoformat(),
    )

    slots_after = db.get_slots(hospital_id, doctor["id"])
    # Dates before `future` still carry the OLD pattern's times, untouched.
    pre_future = [s for s in slots_after if date.fromisoformat(s["date"]) < future]
    assert pre_future  # some of the old-pattern slots survived
    assert {s["time"] for s in pre_future} <= {"09:00", "09:30"}
    # Dates on/after `future` follow the NEW pattern only.
    post_future = [s for s in slots_after if date.fromisoformat(s["date"]) >= future]
    for s in post_future:
        assert s["time"] == "14:00"
        assert date.fromisoformat(s["date"]).strftime("%a") == "Mon"


def test_update_doctor_without_effective_from_still_wipes_whole_window(hospital_id):
    """effective_from=None (the default) keeps the pre-14.7 behavior exactly:
    the whole window is replaced, not just part of it."""
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Full Wipe",
        working_days=["Mon", "Tue"], working_hours=["09:00-10:00"], slot_duration_minutes=30,
    )
    db.update_doctor(
        hospital_id, doctor["id"], "Dr. Full Wipe",
        working_days=["Wed"], working_hours=["14:00-15:00"], slot_duration_minutes=60,
    )
    slots = db.get_slots(hospital_id, doctor["id"])
    assert slots
    for s in slots:
        assert s["time"] == "14:00"
        assert date.fromisoformat(s["date"]).strftime("%a") == "Wed"


# --- create_appointment()/get_slots(): max_bookings_per_slot ---

def test_max_bookings_per_slot_default_still_blocks_second_booking(hospital_id):
    """Parity check: the default (1) must behave byte-for-byte like the old
    single-column unique index did, pre-Section 14.7."""
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Default Cap",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=60,
    )
    slot = db.get_slots(hospital_id, doctor["id"])[0]
    scheduled_at = datetime.fromisoformat(f"{slot['date']}T{slot['time']}:00")
    db.create_appointment(hospital_id, "5490001111", "cardiology", doctor["id"], scheduled_at)
    with pytest.raises(IntegrityError):
        db.create_appointment(hospital_id, "5490002222", "cardiology", doctor["id"], scheduled_at)


def test_max_bookings_per_slot_above_one_allows_group_bookings(hospital_id):
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Group Slots",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=60,
        max_bookings_per_slot=3,
    )
    slot = db.get_slots(hospital_id, doctor["id"])[0]
    scheduled_at = datetime.fromisoformat(f"{slot['date']}T{slot['time']}:00")

    a = db.create_appointment(hospital_id, "5490001111", "cardiology", doctor["id"], scheduled_at)
    b = db.create_appointment(hospital_id, "5490002222", "cardiology", doctor["id"], scheduled_at)
    c = db.create_appointment(hospital_id, "5490003333", "cardiology", doctor["id"], scheduled_at)
    assert len({a.id, b.id, c.id}) == 3

    # get_slots() keeps offering the slot until the 3rd booking, then stops.
    assert slot["id"] not in {s["id"] for s in db.get_slots(hospital_id, doctor["id"])}

    with pytest.raises(IntegrityError):
        db.create_appointment(hospital_id, "5490004444", "cardiology", doctor["id"], scheduled_at)


def test_max_bookings_per_slot_two_still_offers_slot_after_one_booking(hospital_id):
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Two Seats",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=60,
        max_bookings_per_slot=2,
    )
    slot = db.get_slots(hospital_id, doctor["id"])[0]
    scheduled_at = datetime.fromisoformat(f"{slot['date']}T{slot['time']}:00")
    db.create_appointment(hospital_id, "5490001111", "cardiology", doctor["id"], scheduled_at)
    assert slot["id"] in {s["id"] for s in db.get_slots(hospital_id, doctor["id"])}


# --- get_slots(): past slots never offered ---

def test_get_slots_excludes_already_past_slots(hospital_id):
    """generate_slots_for_doctor() never deletes old rows once their date has
    passed -- get_slots() (the patient-facing date/time menu source) must
    filter them out itself, same `scheduled_at >= now` discipline
    get_doctor_slots_for_admin() already applies for its own "from now
    onward" mode."""
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Stale Slots",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=60,
    )
    conn = db_connection.get_connection()
    yesterday = (datetime.now() - timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    conn.execute(
        "INSERT INTO doctor_slots (hospital_id, doctor_id, scheduled_at) VALUES (?, ?, ?)",
        (hospital_id, doctor["id"], yesterday.isoformat()),
    )
    conn.commit()

    slots = db.get_slots(hospital_id, doctor["id"])

    assert yesterday.isoformat() not in {s["id"] for s in slots}
    assert all(datetime.fromisoformat(s["id"]) >= datetime.now() for s in slots)


# --- _validate_doctor_fields(): breaks/quota/daily-limit validation ---

def _base_args(**overrides):
    args = dict(
        index=0, name="Dr. Valid", specialization="", qualification="",
        years_raw="", days_raw="Mon,Tue", hours_raw="09:00-12:00", duration_raw="30",
    )
    args.update(overrides)
    return args


def test_break_outside_shift_rejected():
    doctor, errors, warnings = _validate_doctor_fields(**_base_args(breaks_raw="13:00-13:30"))
    assert doctor is None
    assert any("must fall entirely within a working-hours shift" in e for e in errors)


def test_overlapping_breaks_rejected():
    doctor, errors, warnings = _validate_doctor_fields(**_base_args(breaks_raw="09:30-10:00,09:45-10:15"))
    assert doctor is None
    assert any("must not overlap" in e for e in errors)


def test_break_consuming_entire_shift_rejected():
    doctor, errors, warnings = _validate_doctor_fields(
        **_base_args(hours_raw="09:00-09:30", duration_raw="30", breaks_raw="09:00-09:30")
    )
    assert doctor is None
    assert any("no bookable time" in e for e in errors)


def test_valid_break_inside_shift_accepted():
    doctor, errors, warnings = _validate_doctor_fields(**_base_args(breaks_raw="10:00-10:30"))
    assert errors == []
    assert doctor["breaks"] == ["10:00-10:30"]


def test_negative_daily_booking_limit_rejected():
    doctor, errors, warnings = _validate_doctor_fields(**_base_args(daily_limit_raw="-1"))
    assert doctor is None
    assert any("daily booking limit" in e for e in errors)


def test_zero_max_bookings_per_slot_rejected():
    doctor, errors, warnings = _validate_doctor_fields(**_base_args(max_bookings_raw="0"))
    assert doctor is None
    assert any("bookings per slot" in e for e in errors)


def test_negative_quota_rejected():
    doctor, errors, warnings = _validate_doctor_fields(**_base_args(online_quota_raw="-5"))
    assert doctor is None
    assert any("online quota" in e for e in errors)


def test_invalid_effective_from_date_rejected():
    doctor, errors, warnings = _validate_doctor_fields(**_base_args(effective_from_raw="not-a-date"))
    assert doctor is None
    assert any("effective from" in e for e in errors)


def test_quota_sum_exceeding_daily_limit_warns_but_does_not_block():
    doctor, errors, warnings = _validate_doctor_fields(**_base_args(
        daily_limit_raw="5", online_quota_raw="4", walkin_quota_raw="3",
    ))
    assert errors == []
    assert doctor is not None  # not blocked
    assert any("exceeds the daily booking limit" in w for w in warnings)


def test_quota_sum_within_daily_limit_no_warning():
    doctor, errors, warnings = _validate_doctor_fields(**_base_args(
        daily_limit_raw="10", online_quota_raw="4", walkin_quota_raw="3",
    ))
    assert errors == []
    assert warnings == []


def test_defaults_when_no_section_14_7_fields_given():
    """Every new field is optional -- omitting all of them (positional-only
    call, matching every pre-14.7 call site) must behave exactly like before:
    max_bookings_per_slot=1, everything else None/empty."""
    doctor, errors, warnings = _validate_doctor_fields(
        0, "Dr. Plain", "", "", "", "Mon", "09:00-10:00", "30",
    )
    assert errors == []
    assert doctor["breaks"] == []
    assert doctor["max_bookings_per_slot"] == 1
    assert doctor["daily_booking_limit"] is None
    assert doctor["online_quota"] is None
    assert doctor["walkin_quota"] is None
    assert doctor["followup_duration_minutes"] is None
    assert doctor["effective_from"] is None


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

from admin.onboarding import _validate_doctor_fields  # noqa: E402
from core.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
# test_portal's own module-level TestClient, reused (not a fresh instance) for
# every portal-cookie-based test below -- the signed session cookie
# _login() sets is only visible to requests made through THAT SAME client
# instance, so a separate TestClient() here would silently look logged out.
from tests.test_portal import _login, client as portal_client  # noqa: E402

client = TestClient(app)
ADMIN_SECRET = "test-admin-secret"


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
    on/after effective_from get the new pattern. Mirrors
    tests/test_portal.py's regeneration-safety test, but for the
    effective_from-scoped case rather than a full wipe."""
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


# --- Wizard/portal HTTP paths: end-to-end wiring, including "copy to other days" ---

def _doctor_form_fields(**overrides):
    """Mirrors tests/test_onboarding.py's _build_form() doctor-array shape,
    for a single doctor with every Section 14.7 field populated -- exercises
    the wizard's new Form() params end to end. "Copy to other days" is a pure
    JS form-population convenience (see admin/onboarding.py's copy-days-btn
    handler) -- there's no separate backend code path for it, so testing that
    the backend correctly accepts and stores a doctor with MANY working days
    (exactly what clicking it produces) is what actually proves that side of
    the feature works, per Section 14.7's own "not new backend logic" scope."""
    fields = {
        "admin_secret": ADMIN_SECRET,
        "name": "Scheduling Test Hospital",
        "whatsapp_phone_number_id": "SCHEDULING_TEST_PHONE_ID",
        "access_token": "tok", "app_secret": "secret",
        "enabled_features": ["booking"],
        "data_tier": "tier1",
        "department_name": ["Cardiology"],
        "doctor_department_index": ["0"],
        "doctor_name": ["Dr. Copy Days"],
        "doctor_specialization": [""], "doctor_qualification": [""], "doctor_years_experience": [""],
        "doctor_working_days": ["Mon,Tue,Wed,Thu,Fri,Sat,Sun"],  # "copy to other days" -> all 7 selected
        "doctor_working_hours": ["09:00-12:00"],
        "doctor_slot_duration_minutes": ["30"],
        "doctor_breaks": ["10:00-10:15"],
        "doctor_max_bookings_per_slot": ["2"],
        "doctor_daily_booking_limit": ["5"],
        "doctor_online_quota": [""],
        "doctor_walkin_quota": [""],
        "doctor_followup_duration_minutes": ["15"],
        "doctor_effective_from": [""],
    }
    fields.update(overrides)
    return fields


def test_wizard_creates_doctor_with_all_section_14_7_fields(hospital_id):
    resp = client.post("/admin/onboard-hospital", data=_doctor_form_fields())
    assert resp.status_code == 200

    hospital = db.find_hospital_by_phone_number_id("SCHEDULING_TEST_PHONE_ID")
    assert hospital is not None
    dept = db.get_departments(hospital.id)[0]
    doctor = db.get_doctors(hospital.id, dept["id"])[0]
    full = db.get_doctor_full(hospital.id, doctor["id"])

    assert full["working_days"] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert full["breaks"] == ["10:00-10:15"]
    assert full["max_bookings_per_slot"] == 2
    assert full["daily_booking_limit"] == 5
    assert full["followup_duration_minutes"] == 15


def test_wizard_rejects_invalid_break_without_creating_hospital(hospital_id):
    resp = client.post("/admin/onboard-hospital", data=_doctor_form_fields(doctor_breaks=["23:00-23:30"]))
    assert resp.status_code == 400
    assert db.find_hospital_by_phone_number_id("SCHEDULING_TEST_PHONE_ID") is None


def test_portal_add_doctor_with_break_and_quota_fields(hospital_id):
    _login(hospital_id, "sched-pw")
    try:
        dept = db.get_departments(hospital_id)[0]
        resp = portal_client.post("/portal/doctors", data={
            "department_id": dept["id"],
            "name": "Dr. Portal Schedule",
            "working_days": ["Mon", "Wed"],
            "shift1_start": "09:00", "shift1_end": "12:00",
            "slot_duration_minutes": "30",
            "break1_start": "10:00", "break1_end": "10:30",
            "max_bookings_per_slot": "1",
            "daily_booking_limit": "4",
        }, follow_redirects=False)
        assert resp.status_code == 303

        doctors = db.get_all_doctors_for_hospital(hospital_id)
        new_doctor = next(d for d in doctors if d["name"] == "Dr. Portal Schedule")
        full = db.get_doctor_full(hospital_id, new_doctor["id"])
        assert full["breaks"] == ["10:00-10:30"]
        assert full["daily_booking_limit"] == 4

        slots = db.get_slots(hospital_id, new_doctor["id"])
        assert all(s["time"] != "10:00" for s in slots)
    finally:
        portal_client.cookies.clear()


def test_portal_add_doctor_quota_warning_shown_but_doctor_still_created(hospital_id):
    _login(hospital_id, "sched-warn-pw")
    try:
        dept = db.get_departments(hospital_id)[0]
        resp = portal_client.post("/portal/doctors", data={
            "department_id": dept["id"],
            "name": "Dr. Quota Warning",
            "working_days": ["Mon"],
            "shift1_start": "09:00", "shift1_end": "12:00",
            "slot_duration_minutes": "30",
            "daily_booking_limit": "2",
            "online_quota": "2",
            "walkin_quota": "2",
        }, follow_redirects=False)
        assert resp.status_code == 200  # not a redirect -- warnings render inline, not blocking
        assert "worth double-checking" in resp.text.lower()

        doctors = db.get_all_doctors_for_hospital(hospital_id)
        assert any(d["name"] == "Dr. Quota Warning" for d in doctors)
    finally:
        portal_client.cookies.clear()


def test_portal_doctor_leave_add_and_remove(hospital_id):
    _login(hospital_id, "leave-pw")
    try:
        dept = db.get_departments(hospital_id)[0]
        doctor = db.get_doctors(hospital_id, dept["id"])[0]

        resp = portal_client.post(f"/portal/doctors/{doctor['id']}/leave", data={
            "date": "2027-03-01", "reason": "Vacation",
        }, follow_redirects=False)
        assert resp.status_code == 303

        leave = db.get_doctor_leave(hospital_id, doctor["id"])
        assert len(leave) == 1
        assert leave[0]["date"] == "2027-03-01"

        edit_page = portal_client.get(f"/portal/doctors/{doctor['id']}/edit")
        assert "2027-03-01" in edit_page.text

        resp2 = portal_client.post(f"/portal/doctors/{doctor['id']}/leave/{leave[0]['id']}/delete", follow_redirects=False)
        assert resp2.status_code == 303
        assert db.get_doctor_leave(hospital_id, doctor["id"]) == []
    finally:
        portal_client.cookies.clear()

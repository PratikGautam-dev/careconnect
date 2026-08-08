# tests/test_portal_new_booking.py
"""
SPEC Section 12.9: staff-created bookings (/portal/new-booking) -- walk-in or
phone patients a front-desk staff member books directly, through the exact
same connector.create_booking()/db.create_appointment() path a WhatsApp
booking uses, with source="staff" distinguishing the two afterward.

Covers: a staff booking succeeds and shows up identically to a WhatsApp one
in /portal/bookings and the dashboard (just with a different source pill);
staff-vs-WhatsApp bookings for the same doctor+slot correctly race-protect
each other (sequential, deterministic version of the live concurrency proof
-- see race_proof_staff_booking.py, run separately, for genuine concurrent
verification); online_quota/walkin_quota/daily_booking_limit enforcement,
including that a staff booking can be rejected purely on walk-in quota even
when online_quota has room; patient search (by name or phone) and inline
new-patient creation via the booking form; and cross-tenant isolation for
both the booking form itself and the patient-search endpoint.
"""
import os
from datetime import datetime

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

from core.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from tests.test_portal import _login, client as portal_client  # noqa: E402

client = TestClient(app)


def _first_slot(hospital_id, doctor_id):
    slot = db.get_slots(hospital_id, doctor_id)[0]
    return datetime.fromisoformat(f"{slot['date']}T{slot['time']}:00")


# --- db.is_valid_phone(): deliberately permissive, rejects only unambiguous garbage ---

@pytest.mark.parametrize("bad_phone", [None, "", "   ", "\t\n", "not-a-phone-number!!", "----"])
def test_is_valid_phone_rejects_garbage(bad_phone):
    assert db.is_valid_phone(bad_phone) is False


@pytest.mark.parametrize("ok_phone", [
    "5491112223333", "+54 9 11 1222-3333", "(011) 1222-3333", "1",  # short, but not "no digits" -- not enforced here
])
def test_is_valid_phone_stays_permissive_about_format(ok_phone):
    """Deliberately NOT enforcing length, country code, or separator rules --
    the goal is filtering "not-a-phone-number!!"-style garbage, not a strict
    international phone-number spec."""
    assert db.is_valid_phone(ok_phone) is True


def _same_day_slots(hospital_id, doctor_id, n):
    slots = db.get_slots(hospital_id, doctor_id)
    day = slots[0]["date"]
    same_day = [s for s in slots if s["date"] == day]
    assert len(same_day) >= n, f"doctor doesn't have {n} distinct same-day slots to test with"
    return [datetime.fromisoformat(f"{s['date']}T{s['time']}:00") for s in same_day[:n]]


# --- db.create_appointment(): source, patient upsert ---

def test_staff_booking_has_source_staff_and_upserts_patient_name(hospital_id):
    doctor_id = "doc_card_1"
    scheduled_at = _first_slot(hospital_id, doctor_id)
    appt = db.create_appointment(hospital_id, "5490011111", "cardiology", doctor_id, scheduled_at,
                                  source=db.SOURCE_STAFF, patient_name="Jane Walk-in")
    assert appt.source == "staff"

    matches = db.search_patients(hospital_id, "Jane")
    assert any(p["phone"] == "5490011111" and p["name"] == "Jane Walk-in" for p in matches)


def test_whatsapp_booking_defaults_to_source_whatsapp_unchanged(hospital_id):
    """Every pre-Section-12.9 call site (core/booking_flow.py) calls
    create_appointment() with no source= argument at all -- must keep
    defaulting to 'whatsapp', not require every caller to be updated."""
    doctor_id = "doc_card_1"
    scheduled_at = _first_slot(hospital_id, doctor_id)
    appt = db.create_appointment(hospital_id, "5490022222", "cardiology", doctor_id, scheduled_at)
    assert appt.source == "whatsapp"


def test_whatsapp_booking_never_clobbers_an_existing_patient_name(hospital_id):
    doctor_id = "doc_card_1"
    slot1, slot2 = _same_day_slots(hospital_id, doctor_id, 2)
    db.create_appointment(hospital_id, "5490033333", "cardiology", doctor_id, slot1,
                           source=db.SOURCE_STAFF, patient_name="Known Name")
    db.create_appointment(hospital_id, "5490033333", "cardiology", doctor_id, slot2)  # a later WhatsApp booking, no name

    matches = db.search_patients(hospital_id, "5490033333")
    assert matches[0]["name"] == "Known Name"


# --- Race protection: staff vs WhatsApp for the same doctor+slot ---

def test_staff_booking_blocks_a_later_whatsapp_booking_for_same_slot(hospital_id):
    doctor_id = "doc_card_1"
    scheduled_at = _first_slot(hospital_id, doctor_id)
    db.create_appointment(hospital_id, "5490044444", "cardiology", doctor_id, scheduled_at, source=db.SOURCE_STAFF)
    with pytest.raises(IntegrityError):
        db.create_appointment(hospital_id, "5490055555", "cardiology", doctor_id, scheduled_at)  # whatsapp


def test_whatsapp_booking_blocks_a_later_staff_booking_for_same_slot(hospital_id):
    doctor_id = "doc_card_1"
    scheduled_at = _first_slot(hospital_id, doctor_id)
    db.create_appointment(hospital_id, "5490066666", "cardiology", doctor_id, scheduled_at)  # whatsapp
    with pytest.raises(IntegrityError):
        db.create_appointment(hospital_id, "5490077777", "cardiology", doctor_id, scheduled_at, source=db.SOURCE_STAFF)


# --- Quota enforcement ---

def test_walkin_quota_rejects_staff_booking_even_with_online_room(hospital_id):
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Quota Test",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-13:00"], slot_duration_minutes=30,
        walkin_quota=1, online_quota=5,
    )
    slot1, slot2, slot3 = _same_day_slots(hospital_id, doctor["id"], 3)

    db.create_appointment(hospital_id, "5490088888", "cardiology", doctor["id"], slot1, source=db.SOURCE_STAFF)
    with pytest.raises(db.QuotaExceededError, match="Walk-in quota full"):
        db.create_appointment(hospital_id, "5490099999", "cardiology", doctor["id"], slot2, source=db.SOURCE_STAFF)
    # Online quota is untouched by the walk-in quota being full.
    appt = db.create_appointment(hospital_id, "5490011121", "cardiology", doctor["id"], slot3)
    assert appt.source == "whatsapp"


def test_online_quota_rejects_whatsapp_booking_even_with_walkin_room(hospital_id):
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Quota Test 2",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-13:00"], slot_duration_minutes=30,
        online_quota=1, walkin_quota=5,
    )
    slot1, slot2 = _same_day_slots(hospital_id, doctor["id"], 2)
    db.create_appointment(hospital_id, "5490022232", "cardiology", doctor["id"], slot1)
    with pytest.raises(db.QuotaExceededError, match="Online booking quota full"):
        db.create_appointment(hospital_id, "5490033343", "cardiology", doctor["id"], slot2)


def test_daily_booking_limit_blocks_regardless_of_source(hospital_id):
    """generate_slots_for_doctor() (Section 14.7) already caps slot GENERATION
    at daily_booking_limit, so a doctor with daily_booking_limit=1 only ever
    has 1 slot that day -- max_bookings_per_slot=2 creates real headroom at
    THAT one slot (the per-slot check alone would allow a 2nd booking there),
    proving daily_booking_limit is enforced as its own, independent check,
    not just an accidental side effect of there being few slots."""
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Daily Cap Test",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-13:00"], slot_duration_minutes=30,
        daily_booking_limit=1, max_bookings_per_slot=2,
    )
    slot = _first_slot(hospital_id, doctor["id"])
    db.create_appointment(hospital_id, "5490044454", "cardiology", doctor["id"], slot, source=db.SOURCE_STAFF)
    with pytest.raises(db.QuotaExceededError, match="booking limit"):
        db.create_appointment(hospital_id, "5490055565", "cardiology", doctor["id"], slot)  # whatsapp, same slot -- per-slot check alone would allow it


# --- db.search_patients() ---

def test_search_patients_matches_name_or_phone(hospital_id):
    doctor_id = "doc_card_1"
    slot = _first_slot(hospital_id, doctor_id)
    db.create_appointment(hospital_id, "5495551234", "cardiology", doctor_id, slot,
                           source=db.SOURCE_STAFF, patient_name="Alice Example")

    assert any(p["phone"] == "5495551234" for p in db.search_patients(hospital_id, "Alice"))
    assert any(p["phone"] == "5495551234" for p in db.search_patients(hospital_id, "555123"))
    assert db.search_patients(hospital_id, "nonexistent-query-xyz") == []
    assert db.search_patients(hospital_id, "") == []


def test_search_patients_scoped_to_hospital(hospital_id, second_hospital_id):
    doctor_id = "doc_card_1"
    slot = _first_slot(hospital_id, doctor_id)
    db.create_appointment(hospital_id, "5496661234", "cardiology", doctor_id, slot,
                           source=db.SOURCE_STAFF, patient_name="Hospital A Patient")

    assert any(p["phone"] == "5496661234" for p in db.search_patients(hospital_id, "Hospital A"))
    assert db.search_patients(second_hospital_id, "Hospital A") == []
    assert db.search_patients(second_hospital_id, "5496661234") == []


# --- HTTP layer: /portal/new-booking ---

def test_new_booking_requires_login(hospital_id):
    resp = portal_client.get("/portal/new-booking", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/portal/login"


def test_new_booking_form_renders_with_departments_and_doctors(hospital_id):
    _login(hospital_id, "newbook-pw")
    try:
        resp = portal_client.get("/portal/new-booking")
        assert resp.status_code == 200
        assert "New Booking" in resp.text
        assert "Cardiology" in resp.text
        assert "Main Branch" in resp.text  # the deliberate no-op branch dropdown
    finally:
        portal_client.cookies.clear()


def test_staff_booking_via_form_succeeds_and_appears_in_bookings_and_dashboard(hospital_id):
    doctor_id = "doc_card_1"
    slot = db.get_slots(hospital_id, doctor_id)[0]
    _login(hospital_id, "newbook-success-pw")
    try:
        resp = portal_client.post("/portal/new-booking", data={
            "patient_name": "Walk-in Patient",
            "patient_phone": "5497771234",
            "department_id": "cardiology",
            "doctor_id": doctor_id,
            "slot_id": slot["id"],
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/portal/bookings"

        bookings_page = portal_client.get("/portal/bookings")
        assert "5497771234" in bookings_page.text
        assert "Walk-in" in bookings_page.text

        dashboard_page = portal_client.get("/portal/dashboard")
        assert "5497771234" in dashboard_page.text
    finally:
        portal_client.cookies.clear()

    appt = next(a for a in db.get_all_appointments_for_hospital(hospital_id) if a.phone == "5497771234")
    assert appt.source == "staff"
    assert appt.department_id == "cardiology"


def test_staff_booking_rejected_when_slot_already_taken(hospital_id):
    doctor_id = "doc_card_1"
    scheduled_at = _first_slot(hospital_id, doctor_id)
    db.create_appointment(hospital_id, "5498881234", "cardiology", doctor_id, scheduled_at)  # takes the slot first

    _login(hospital_id, "newbook-taken-pw")
    try:
        resp = portal_client.post("/portal/new-booking", data={
            "patient_name": "Too Late",
            "patient_phone": "5498882345",
            "department_id": "cardiology",
            "doctor_id": doctor_id,
            "slot_id": scheduled_at.isoformat(),
        })
        assert resp.status_code == 400
        assert "just taken" in resp.text.lower()
    finally:
        portal_client.cookies.clear()


def test_staff_booking_rejected_when_walkin_quota_full_shows_clear_message(hospital_id):
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Portal Quota",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-13:00"], slot_duration_minutes=30, walkin_quota=1,
    )
    slot1, slot2 = _same_day_slots(hospital_id, doctor["id"], 2)
    db.create_appointment(hospital_id, "5499991234", "cardiology", doctor["id"], slot1, source=db.SOURCE_STAFF)

    _login(hospital_id, "newbook-quota-pw")
    try:
        resp = portal_client.post("/portal/new-booking", data={
            "patient_name": "Quota Blocked",
            "patient_phone": "5499992345",
            "department_id": "cardiology",
            "doctor_id": doctor["id"],
            "slot_id": slot2.isoformat(),
        })
        assert resp.status_code == 400
        assert "walk-in quota full" in resp.text.lower()
    finally:
        portal_client.cookies.clear()


@pytest.mark.parametrize("bad_phone", ["", "   ", "not-a-phone-number!!"])
def test_staff_booking_rejects_garbage_phone_before_creating_anything(hospital_id, bad_phone):
    """SPEC Section 12.9's phone-validation follow-up: empty, whitespace-only,
    and digit-free phone values must be rejected with a clear error --
    before any appointment or patients row is created, not after."""
    doctor_id = "doc_card_1"
    slot = db.get_slots(hospital_id, doctor_id)[0]
    _login(hospital_id, "newbook-badphone-pw")
    try:
        resp = portal_client.post("/portal/new-booking", data={
            "patient_name": "Bad Phone Patient",
            "patient_phone": bad_phone,
            "department_id": "cardiology",
            "doctor_id": doctor_id,
            "slot_id": slot["id"],
        })
        assert resp.status_code == 400
        assert "phone" in resp.text.lower()
    finally:
        portal_client.cookies.clear()

    assert db.search_patients(hospital_id, "Bad Phone Patient") == []
    assert not any(a.phone == bad_phone for a in db.get_all_appointments_for_hospital(hospital_id))


def test_staff_booking_accepts_a_normal_phone_unaffected(hospital_id):
    """Confirms the new validation doesn't accidentally reject real input --
    a normal phone number still creates the booking exactly as before."""
    doctor_id = "doc_card_1"
    slot = db.get_slots(hospital_id, doctor_id)[0]
    _login(hospital_id, "newbook-goodphone-pw")
    try:
        resp = portal_client.post("/portal/new-booking", data={
            "patient_name": "Good Phone Patient",
            "patient_phone": "5490001234",
            "department_id": "cardiology",
            "doctor_id": doctor_id,
            "slot_id": slot["id"],
        }, follow_redirects=False)
        assert resp.status_code == 303
    finally:
        portal_client.cookies.clear()


def test_new_booking_cannot_target_another_hospitals_department_or_doctor(hospital_id, second_hospital_id):
    """SPEC Section 12.2: staff logged into hospital A must not be able to
    book against hospital B's departments/doctors, even by crafting the
    request directly (not just because the UI wouldn't normally show them)."""
    other_doctor_id = "t2_doc_neuro_1"
    other_dept_id = "t2_neurology"
    _login(hospital_id, "newbook-crosstenant-pw")
    try:
        resp = portal_client.post("/portal/new-booking", data={
            "patient_name": "Cross Tenant Attempt",
            "patient_phone": "5490001111",
            "department_id": other_dept_id,
            "doctor_id": other_doctor_id,
            "slot_id": datetime(2099, 1, 1, 9, 0).isoformat(),
        })
        assert resp.status_code == 400
        assert "valid department" in resp.text.lower()
    finally:
        portal_client.cookies.clear()

    assert db.find_doctor(second_hospital_id, other_dept_id, other_doctor_id) is not None  # sanity: it really does exist, just not for hospital_id
    assert not any(a.phone == "5490001111" for a in db.get_all_appointments_for_hospital(hospital_id))
    assert not any(a.phone == "5490001111" for a in db.get_all_appointments_for_hospital(second_hospital_id))


def test_new_patient_created_inline_via_booking_form(hospital_id):
    doctor_id = "doc_card_1"
    slot = db.get_slots(hospital_id, doctor_id)[0]
    assert db.search_patients(hospital_id, "Brand New Patient") == []

    _login(hospital_id, "newbook-newpatient-pw")
    try:
        resp = portal_client.post("/portal/new-booking", data={
            "patient_name": "Brand New Patient",
            "patient_phone": "5495559999",
            "department_id": "cardiology",
            "doctor_id": doctor_id,
            "slot_id": slot["id"],
        }, follow_redirects=False)
        assert resp.status_code == 303
    finally:
        portal_client.cookies.clear()

    matches = db.search_patients(hospital_id, "Brand New Patient")
    assert len(matches) == 1
    assert matches[0]["phone"] == "5495559999"


# --- HTTP layer: /portal/patients/search ---

def test_patient_search_endpoint_requires_login(hospital_id):
    resp = portal_client.get("/portal/patients/search?q=test")
    assert resp.status_code == 401


def test_patient_search_endpoint_returns_matches(hospital_id):
    doctor_id = "doc_card_1"
    slot = _first_slot(hospital_id, doctor_id)
    db.create_appointment(hospital_id, "5493334444", "cardiology", doctor_id, slot,
                           source=db.SOURCE_STAFF, patient_name="Searchable Patient")

    _login(hospital_id, "search-pw")
    try:
        resp = portal_client.get("/portal/patients/search?q=Searchable")
        assert resp.status_code == 200
        results = resp.json()
        assert any(r["phone"] == "5493334444" for r in results)
    finally:
        portal_client.cookies.clear()


def test_patient_search_endpoint_cross_tenant_isolation(hospital_id, second_hospital_id):
    doctor_id = "t2_doc_neuro_1"
    slot = db.get_slots(second_hospital_id, doctor_id)[0]
    scheduled_at = datetime.fromisoformat(f"{slot['date']}T{slot['time']}:00")
    db.create_appointment(second_hospital_id, "5497778888", "t2_neurology", doctor_id, scheduled_at,
                           source=db.SOURCE_STAFF, patient_name="Hospital B Only Patient")

    _login(hospital_id, "search-crosstenant-pw")
    try:
        resp = portal_client.get("/portal/patients/search?q=Hospital B Only")
        assert resp.status_code == 200
        assert resp.json() == []
        resp2 = portal_client.get("/portal/patients/search?q=5497778888")
        assert resp2.json() == []
    finally:
        portal_client.cookies.clear()

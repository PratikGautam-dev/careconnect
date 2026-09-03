# tests/test_followup_validity.py
"""Follow-up validity override (migration 0024): a patient's attended visit
stops being follow-up-eligible followup_validity_days after its own
scheduled_at (db/repositories/hospital_settings.py's DEFAULT_FOLLOWUP_
VALIDITY_DAYS=30 when unset). Covers the repository-level eligibility/
extension logic and the two admin/receptionist-only portal routes that let
staff either widen that window for a specific visit (extend) or book a
follow-up directly against it, bypassing the window entirely (book-now)."""
from datetime import datetime, timedelta

import pytest

import db.repository as db
from auth.jwt_session import issue_access_token

import os

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")

from main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


def _staff_auth(hospital_id: int, role: str, email: str) -> dict:
    staff = db.create_staff_user(hospital_id, role, email, "x", "Test Staff")
    token = issue_access_token(staff["id"], hospital_id, role, staff["token_version"])
    return {"Authorization": f"Bearer {token}"}


def _attended_appointment(hospital_id: int, doctor_id: str, department_id: str, days_ago: int, phone: str):
    scheduled_at = datetime.now() - timedelta(days=days_ago)
    appt = db.create_appointment(hospital_id, phone, department_id, doctor_id, scheduled_at)
    db.mark_attendance(hospital_id, appt.id, True)
    return db.get_appointment(hospital_id, appt.id)


# --- Repository-level eligibility + extension ---

def test_visit_outside_default_window_is_not_eligible(hospital_id):
    appt = _attended_appointment(hospital_id, "doc_card_1", "cardiology", days_ago=60, phone="5490002001")
    eligible = db.get_followup_eligible_appointments(
        hospital_id, appt.patient_id, db.get_followup_validity_days(hospital_id),
    )
    assert appt.id not in {a.id for a in eligible}


def test_grant_followup_extension_makes_an_expired_visit_eligible_again(hospital_id):
    appt = _attended_appointment(hospital_id, "doc_card_1", "cardiology", days_ago=60, phone="5490002002")
    validity_days = db.get_followup_validity_days(hospital_id)
    assert appt.id not in {a.id for a in db.get_followup_eligible_appointments(hospital_id, appt.patient_id, validity_days)}

    updated = db.grant_followup_extension(hospital_id, appt.id, extra_days=5)
    assert updated is not None
    assert updated.followup_override_until == (datetime.now().date() + timedelta(days=5)).isoformat()

    eligible = db.get_followup_eligible_appointments(hospital_id, appt.patient_id, validity_days)
    assert appt.id in {a.id for a in eligible}


def test_grant_followup_extension_returns_none_for_a_non_attended_appointment(hospital_id):
    slot = db.get_slots(hospital_id, "doc_card_1")[0]
    appt = db.create_appointment(
        hospital_id, "5490002003", "cardiology", "doc_card_1", datetime.fromisoformat(slot["id"]),
    )  # still status='booked', never marked attended
    assert db.grant_followup_extension(hospital_id, appt.id, extra_days=5) is None


def test_grant_followup_extension_cannot_target_other_hospitals_appointment(hospital_id, second_hospital_id):
    appt = _attended_appointment(hospital_id, "doc_card_1", "cardiology", days_ago=60, phone="5490002004")
    assert db.grant_followup_extension(second_hospital_id, appt.id, extra_days=5) is None


# --- Portal routes ---

def test_extend_followup_validity_requires_staff_auth(hospital_id):
    appt = _attended_appointment(hospital_id, "doc_card_1", "cardiology", days_ago=60, phone="5490002005")
    resp = client.post(f"/api/portal/bookings/{appt.id}/followup/extend", json={"extra_days": 5})
    assert resp.status_code == 401


def test_extend_followup_validity_as_admin_widens_the_window(hospital_id):
    appt = _attended_appointment(hospital_id, "doc_card_1", "cardiology", days_ago=60, phone="5490002006")
    headers = _staff_auth(hospital_id, "admin", "admin-followup-test@example.com")

    resp = client.post(f"/api/portal/bookings/{appt.id}/followup/extend", json={"extra_days": 3}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()["appointment"]
    assert body["followup_override_until"] == (datetime.now().date() + timedelta(days=3)).isoformat()

    validity_days = db.get_followup_validity_days(hospital_id)
    eligible = db.get_followup_eligible_appointments(hospital_id, appt.patient_id, validity_days)
    assert appt.id in {a.id for a in eligible}


def test_extend_followup_validity_rejects_non_positive_extra_days(hospital_id):
    appt = _attended_appointment(hospital_id, "doc_card_1", "cardiology", days_ago=60, phone="5490002007")
    headers = _staff_auth(hospital_id, "receptionist", "recept-followup-test@example.com")
    resp = client.post(f"/api/portal/bookings/{appt.id}/followup/extend", json={"extra_days": 0}, headers=headers)
    assert resp.status_code == 400


def test_extend_followup_validity_404s_for_a_still_booked_appointment(hospital_id):
    slot = db.get_slots(hospital_id, "doc_card_1")[0]
    appt = db.create_appointment(hospital_id, "5490002008", "cardiology", "doc_card_1", datetime.fromisoformat(slot["id"]))
    headers = _staff_auth(hospital_id, "admin", "admin-followup-test2@example.com")
    resp = client.post(f"/api/portal/bookings/{appt.id}/followup/extend", json={"extra_days": 5}, headers=headers)
    assert resp.status_code == 404


def test_book_followup_now_bypasses_the_window_entirely(hospital_id):
    appt = _attended_appointment(hospital_id, "doc_card_1", "cardiology", days_ago=90, phone="5490002009")
    headers = _staff_auth(hospital_id, "receptionist", "recept-followup-test2@example.com")

    slot = db.get_slots(hospital_id, "doc_card_1")[0]
    resp = client.post(
        f"/api/portal/bookings/{appt.id}/followup/book", json={"scheduled_at": slot["id"]}, headers=headers,
    )
    assert resp.status_code == 200, resp.text
    created = resp.json()["appointment"]
    assert created["appointment_type_id"] == "followup"
    assert created["department_name"] == "Cardiology"
    assert created["patient_display_id"] == appt.patient_display_id


def test_book_followup_now_404s_for_an_appointment_that_was_never_attended(hospital_id):
    slot = db.get_slots(hospital_id, "doc_card_1")[0]
    appt = db.create_appointment(hospital_id, "5490002010", "cardiology", "doc_card_1", datetime.fromisoformat(slot["id"]))
    headers = _staff_auth(hospital_id, "admin", "admin-followup-test3@example.com")
    resp = client.post(
        f"/api/portal/bookings/{appt.id}/followup/book", json={"scheduled_at": slot["id"]}, headers=headers,
    )
    assert resp.status_code == 404


def test_followup_valid_until_reflects_override_on_the_bookings_list(hospital_id):
    appt = _attended_appointment(hospital_id, "doc_card_1", "cardiology", days_ago=60, phone="5490002011")
    headers = _staff_auth(hospital_id, "admin", "admin-followup-test4@example.com")
    resp = client.post(f"/api/portal/bookings/{appt.id}/followup/extend", json={"extra_days": 10}, headers=headers)
    assert resp.status_code == 200, resp.text

    listing = client.get("/api/portal/bookings", headers={"Authorization": headers["Authorization"]})
    # /api/portal/bookings only accepts the legacy hospital-password/staff-JWT
    # dual auth (_authenticate), which a staff JWT satisfies too.
    assert listing.status_code == 200, listing.text
    row = next(a for a in listing.json()["appointments"] if a["id"] == appt.id)
    assert row["followup_valid_until"] == (datetime.now().date() + timedelta(days=10)).isoformat()

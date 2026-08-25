# tests/test_onboarding_api.py
"""
JSON API equivalent of the old tests/test_onboarding.py + test_faq_onboarding.py
(deleted) -- those tested admin/onboarding.py's server-rendered HTML wizard,
which was removed once the Next.js frontend (posting to POST /api/onboarding,
this module's actual subject) became the real onboarding UI. Ported rather
than dropped: admin/onboarding_api.py's submit_onboarding() shares its
validation logic (_validate_doctor_fields, _build_departments equivalent,
_parse_offsets) with the code the old HTML route used, so this is coverage
of currently-live, currently-used logic, not dead code.

Section 15 addition since the old tests were written: submit_onboarding()
now requires BOTH a signed-in user (Authorization: Bearer, via the
user_auth_header fixture) AND the correct admin_secret -- two independent
gates (see admin/onboarding_api.py's own comment on why). Every test here
carries a real user_auth_header unless specifically testing that gate.
"""
import os

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")

import db.repository as db  # noqa: E402
from app import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


def _valid_departments():
    return [{
        "name": "Pediatrics",
        "doctors": [
            {"name": "Dr. Meera Nair", "specialization": "Pediatrician", "qualification": "MBBS, MD",
             "years_experience": "10", "working_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
             "working_hours": ["09:00-13:00"], "slot_duration_minutes": "20"},
            {"name": "Dr. Arjun Singh", "specialization": "Pediatrician", "qualification": "MBBS",
             "years_experience": "5", "working_days": ["Mon", "Wed", "Fri"],
             "working_hours": ["14:00-17:00"], "slot_duration_minutes": "30"},
        ],
    }]


def _payload(**overrides):
    data = {
        "admin_secret": "test-admin-secret",
        "name": "St. Jude Community Hospital",
        "whatsapp_phone_number_id": "NEW_HOSPITAL_PHONE_ID",
        "access_token": "new-hospital-token",
        "app_secret": "new-hospital-secret",
        "welcome_message_text": "Welcome to St. Jude!",
        "reminder_offsets_hours": "24,1",
        "portal_password": "bookings-pw",
        "enabled_features": ["booking"],
        "data_tier": "tier1",
        "departments": _valid_departments(),
        "topics": [],
    }
    data.update(overrides)
    return data


def test_successful_onboarding_creates_real_rows_and_links_owner(hospital_id, user_auth_header):
    resp = client.post("/api/onboarding", json=_payload(), headers=user_auth_header)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["hospital_name"] == "St. Jude Community Hospital"
    assert body["portal_password_set"] is True

    hospital = db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID")
    assert hospital is not None
    assert hospital.access_token == "new-hospital-token"
    assert sorted(hospital.reminder_offsets_hours) == [1, 24]

    departments = db.get_departments(hospital.id)
    assert len(departments) == 1
    doctors = db.get_doctors(hospital.id, departments[0]["id"])
    assert sorted(d["name"] for d in doctors) == ["Dr. Arjun Singh", "Dr. Meera Nair"]

    # Section 15: the signed-in user must actually be linked as the owner.
    owners = db.get_owners_for_hospital(hospital.id)
    assert len(owners) == 1
    assert owners[0].email == "test-owner@example.com"


def test_requires_signed_in_user(hospital_id):
    resp = client.post("/api/onboarding", json=_payload())  # no Authorization header
    assert resp.status_code == 401
    assert db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID") is None


def test_wrong_admin_secret_rejected_even_when_signed_in(hospital_id, user_auth_header):
    resp = client.post("/api/onboarding", json=_payload(admin_secret="wrong"), headers=user_auth_header)
    assert resp.status_code == 403
    assert db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID") is None


def test_duplicate_phone_number_id_rejected(hospital_id, user_auth_header):
    before = db.find_hospital_by_phone_number_id("123")  # the already-seeded hospital's number
    resp = client.post("/api/onboarding", json=_payload(whatsapp_phone_number_id="123"), headers=user_auth_header)
    assert resp.status_code == 400
    assert "already exists" in resp.json()["errors"][0]
    after = db.find_hospital_by_phone_number_id("123")
    assert before.id == after.id


def test_missing_departments_rejected_when_booking_enabled(hospital_id, user_auth_header):
    resp = client.post("/api/onboarding", json=_payload(departments=[]), headers=user_auth_header)
    assert resp.status_code == 400
    assert any("department" in e.lower() for e in resp.json()["errors"])
    assert db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID") is None


def test_doctor_with_invalid_working_day_rejected(hospital_id, user_auth_header):
    departments = [{"name": "Pediatrics", "doctors": [
        {"name": "Dr. Bad Day", "working_days": ["Mon", "Funday"], "working_hours": ["09:00-13:00"], "slot_duration_minutes": "20"},
    ]}]
    resp = client.post("/api/onboarding", json=_payload(departments=departments), headers=user_auth_header)
    assert resp.status_code == 400
    assert any("invalid working day" in e.lower() for e in resp.json()["errors"])


def test_no_features_selected_rejected(hospital_id, user_auth_header):
    resp = client.post("/api/onboarding", json=_payload(enabled_features=[], departments=[]), headers=user_auth_header)
    assert resp.status_code == 400
    assert any("patient-experience" in e.lower() for e in resp.json()["errors"])


def test_unrecognized_feature_rejected(hospital_id, user_auth_header):
    resp = client.post("/api/onboarding", json=_payload(enabled_features=["booking", "teleporting"]), headers=user_auth_header)
    assert resp.status_code == 400


def test_tier2_requires_api_fields(hospital_id, user_auth_header):
    resp = client.post("/api/onboarding", json=_payload(data_tier="tier2", api_base_url="", api_key=""), headers=user_auth_header)
    assert resp.status_code == 400
    assert db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID") is None


def test_tier2_fields_save_correctly(hospital_id, user_auth_header):
    resp = client.post(
        "/api/onboarding",
        json=_payload(data_tier="tier2", api_base_url="https://erp.stjude.example/api", api_key="tier2-secret-key"),
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text
    hospital = db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID")
    assert hospital.data_tier == "tier2"
    assert hospital.external_api_base_url == "https://erp.stjude.example/api"


def test_faq_only_hospital_created_with_topics_not_departments(hospital_id, user_auth_header):
    resp = client.post(
        "/api/onboarding",
        json=_payload(
            enabled_features=["faq"], departments=[], portal_password="",
            whatsapp_phone_number_id="FAQ_HOSPITAL_PHONE_ID",
            topics=[{"topic_label": "Hours", "answer_text": "Mon-Sat, 9-6."},
                    {"topic_label": "Location", "answer_text": "123 Main St."}],
        ),
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text
    hospital = db.find_hospital_by_phone_number_id("FAQ_HOSPITAL_PHONE_ID")
    assert hospital.enabled_features == ["faq"]
    topics = db.get_faq_topics(hospital.id)
    assert {(t["topic_label"], t["answer_text"]) for t in topics} == {
        ("Hours", "Mon-Sat, 9-6."), ("Location", "123 Main St."),
    }
    assert db.get_departments(hospital.id) == []


def test_faq_missing_topics_rejected(hospital_id, user_auth_header):
    resp = client.post(
        "/api/onboarding",
        json=_payload(enabled_features=["faq"], departments=[], portal_password="", topics=[],
                       whatsapp_phone_number_id="FAQ_HOSPITAL_PHONE_ID"),
        headers=user_auth_header,
    )
    assert resp.status_code == 400
    assert any("topic" in e.lower() for e in resp.json()["errors"])


def test_booking_and_faq_both_enabled_creates_both(hospital_id, user_auth_header):
    resp = client.post(
        "/api/onboarding",
        json=_payload(
            enabled_features=["booking", "faq"], whatsapp_phone_number_id="BOTH_PHONE_ID",
            topics=[{"topic_label": "Hours", "answer_text": "Mon-Sat, 9-6."}],
        ),
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text
    hospital = db.find_hospital_by_phone_number_id("BOTH_PHONE_ID")
    assert set(hospital.enabled_features) == {"booking", "faq"}
    assert len(db.get_departments(hospital.id)) == 1
    assert len(db.get_faq_topics(hospital.id)) == 1

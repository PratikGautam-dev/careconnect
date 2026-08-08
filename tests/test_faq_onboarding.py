# tests/test_faq_onboarding.py
"""
SPEC Section 14.5: the onboarding wizard's "faq"-only enabled_features path --
POST /admin/onboard-hospital with enabled_features=["faq"] creates a hospital
with real faq_topics rows instead of departments/doctors, and the existing
booking-flow submission path (tests/test_onboarding.py) is confirmed
unaffected by this file's existence (both paths share the same route/backend
function). Also covers a hospital with BOTH "booking" and "faq" enabled at
once, since the two are no longer mutually exclusive (Section 14.5 replaced
the old single flow_type fork).
"""
import os

import db.repository as db

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")

from core.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


def _faq_form(topics=None, enabled_features=None, **overrides):
    if topics is None:
        topics = [("Hours", "Mon-Sat, 9-6."), ("Location", "123 Main St.")]
    if enabled_features is None:
        enabled_features = ["faq"]
    data = {
        "admin_secret": "test-admin-secret",
        "name": "Riverside Info Desk",
        "whatsapp_phone_number_id": "FAQ_HOSPITAL_PHONE_ID",
        "access_token": "faq-hospital-token",
        "app_secret": "faq-hospital-secret",
        "welcome_message_text": "Hi! Ask me anything about Riverside.",
        "enabled_features": enabled_features,
        "data_tier": "tier1",
        "topic_label": [t[0] for t in topics],
        "topic_answer": [t[1] for t in topics],
    }
    data.update(overrides)
    return data


def test_faq_only_hospital_created_with_topics_not_departments(hospital_id):
    resp = client.post("/admin/onboard-hospital", data=_faq_form())
    assert resp.status_code == 200
    assert "Hospital created" in resp.text

    hospital = db.find_hospital_by_phone_number_id("FAQ_HOSPITAL_PHONE_ID")
    assert hospital is not None
    assert hospital.enabled_features == ["faq"]

    topics = db.get_faq_topics(hospital.id)
    assert {(t["topic_label"], t["answer_text"]) for t in topics} == {
        ("Hours", "Mon-Sat, 9-6."), ("Location", "123 Main St."),
    }
    assert db.get_departments(hospital.id) == []


def test_faq_hospital_review_page_shows_topics(hospital_id):
    resp = client.post("/admin/onboard-hospital", data=_faq_form())
    assert resp.status_code == 200
    assert "Topics" in resp.text
    assert "Hours" in resp.text
    assert "Mon-Sat, 9-6." in resp.text
    assert "Departments" not in resp.text


def test_faq_missing_topics_rejected(hospital_id):
    resp = client.post("/admin/onboard-hospital", data=_faq_form(topics=[]))
    assert resp.status_code == 400
    assert "at least one topic" in resp.text.lower()
    assert db.find_hospital_by_phone_number_id("FAQ_HOSPITAL_PHONE_ID") is None


def test_faq_topic_with_label_but_no_answer_rejected(hospital_id):
    data = _faq_form()
    data["topic_label"] = ["Hours", "Location"]
    data["topic_answer"] = ["Mon-Sat, 9-6.", ""]  # second topic half-filled
    resp = client.post("/admin/onboard-hospital", data=data)
    assert resp.status_code == 400
    assert "answer text is required" in resp.text.lower()
    assert db.find_hospital_by_phone_number_id("FAQ_HOSPITAL_PHONE_ID") is None


def test_no_features_selected_rejected(hospital_id):
    resp = client.post("/admin/onboard-hospital", data=_faq_form(enabled_features=[]))
    assert resp.status_code == 400
    assert "at least one patient-experience option" in resp.text.lower()
    assert db.find_hospital_by_phone_number_id("FAQ_HOSPITAL_PHONE_ID") is None


def test_unrecognized_feature_rejected(hospital_id):
    resp = client.post("/admin/onboard-hospital", data=_faq_form(enabled_features=["faq", "teleporting"]))
    assert resp.status_code == 400
    assert db.find_hospital_by_phone_number_id("FAQ_HOSPITAL_PHONE_ID") is None


def test_booking_and_faq_both_enabled_creates_departments_and_topics(hospital_id):
    """Section 14.5: booking and faq are no longer mutually exclusive -- a
    hospital can enable both at once and gets both sets of child rows."""
    from tests.test_onboarding import _valid_departments

    departments = _valid_departments()
    data = _faq_form(enabled_features=["booking", "faq"])
    data["department_name"] = [d["name"] for d in departments]
    doctor_fields = [
        "department_index", "name", "specialization", "qualification",
        "years_experience", "working_days", "working_hours", "slot_duration_minutes",
    ]
    doctor_columns = {f"doctor_{f}": [] for f in doctor_fields}
    for dept_idx, dept in enumerate(departments):
        for doc in dept["doctors"]:
            doctor_columns["doctor_department_index"].append(str(dept_idx))
            for f in doctor_fields[1:]:
                doctor_columns[f"doctor_{f}"].append(str(doc.get(f, "")))
    data.update(doctor_columns)

    resp = client.post("/admin/onboard-hospital", data=data)
    assert resp.status_code == 200

    hospital = db.find_hospital_by_phone_number_id("FAQ_HOSPITAL_PHONE_ID")
    assert hospital is not None
    assert set(hospital.enabled_features) == {"booking", "faq"}
    assert len(db.get_departments(hospital.id)) == 1
    assert len(db.get_faq_topics(hospital.id)) == 2
    # Both sections show up on the confirmation page since both are enabled.
    assert "Topics" in resp.text
    assert "Departments" in resp.text


def test_faq_wizard_form_renders_feature_and_topic_markup(hospital_id):
    resp = client.get("/admin/onboard-hospital")
    assert resp.status_code == 200
    assert 'class="feature-checkbox" name="enabled_features" value="booking"' in resp.text
    assert 'class="feature-checkbox" name="enabled_features" value="faq"' in resp.text
    assert 'name="topic_label"' in resp.text
    assert 'name="topic_answer"' in resp.text


def test_booking_submission_unaffected_by_enabled_features_model(hospital_id):
    """A plain booking-only submission (enabled_features=["booking"], matching
    db.create_hospital()'s intent) must produce identical behavior to before
    Section 14.5 existed -- confirms the fork point in the backend route
    doesn't leak into the booking path even though both now share one handler
    function."""
    from tests.test_onboarding import _build_form

    resp = client.post("/admin/onboard-hospital", data=_build_form())
    assert resp.status_code == 200
    hospital = db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID")
    assert hospital.enabled_features == ["booking"]
    assert db.get_faq_topics(hospital.id) == []

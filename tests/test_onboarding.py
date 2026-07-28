# tests/test_onboarding.py
"""
SPEC Section 12.1 / Phase 10: the guided onboarding wizard. Proves a new
hospital can be added end-to-end through the plain HTML form (POST /admin/
onboard-hospital) without touching the database or code directly, and that
the newly created hospital immediately works with Phase 9's per-message
routing (a webhook for its own phone_number_id, signed with its own
app_secret, is accepted and processed).
"""
import hashlib
import hmac
import json
import os
from datetime import date, datetime

import pytest

import db.repository as db
from db.connection import IntegrityError

# Same defensive env-var setup as tests/test_main.py and tests/test_multi_tenant.py
# -- core.main (and admin.onboarding, which it imports) is only actually
# imported -- and its module-level os.environ[...] reads executed -- the first
# time any test file does so, so this must be safe regardless of which test
# module pytest happens to collect/import first.
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
# ADMIN_SECRET itself is set in tests/conftest.py, before any test module (this
# one included) gets a chance to trigger core.main's first import -- see the
# comment there for why it can't safely be set here instead.
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")
# DATABASE_URL is already pointed at the test Postgres instance by
# tests/conftest.py (loaded before this module).

from core.main import app  # noqa: E402  (must follow the env var setdefaults above)
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

VALID_DEPARTMENTS_TEXT = (
    "# Pediatrics\n"
    "Dr. Meera Nair | Pediatrician | MBBS, MD | 10 | Mon,Tue,Wed,Thu,Fri | 09:00-13:00 | 20\n"
    "Dr. Arjun Singh | Pediatrician | MBBS | 5 | Mon,Wed,Fri | 14:00-17:00 | 30\n"
)

VALID_FORM = {
    "admin_secret": "test-admin-secret",
    "name": "St. Jude Community Hospital",
    "whatsapp_phone_number_id": "NEW_HOSPITAL_PHONE_ID",
    "access_token": "new-hospital-token",
    "app_secret": "new-hospital-secret",
    "welcome_message_text": "Welcome to St. Jude!",
    "reminder_offsets_hours": "24,1",
    "reminder_template_name": "appointment_reminder",
    "data_tier": "tier1",
    "departments_text": VALID_DEPARTMENTS_TEXT,
}


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _webhook_body(phone_number_id: str, from_phone: str, text: str) -> bytes:
    return json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": phone_number_id},
            "messages": [{"from": from_phone, "type": "text", "text": {"body": text}}],
        }}]}]
    }).encode()


def test_get_form_renders(hospital_id):
    resp = client.get("/admin/onboard-hospital")
    assert resp.status_code == 200
    assert "Onboard a new hospital" in resp.text
    assert "departments_text" in resp.text


def test_successful_onboarding_creates_real_rows_and_routing_works(hospital_id, httpx_mock):
    resp = client.post("/admin/onboard-hospital", data=VALID_FORM)
    assert resp.status_code == 200
    assert "Hospital created" in resp.text
    assert "St. Jude Community Hospital" in resp.text

    hospital = db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID")
    assert hospital is not None
    assert hospital.name == "St. Jude Community Hospital"
    assert hospital.access_token == "new-hospital-token"
    assert hospital.app_secret == "new-hospital-secret"
    assert sorted(hospital.reminder_offsets_hours) == [1, 24]
    assert str(hospital.id) in resp.text

    departments = db.get_departments(hospital.id)
    assert len(departments) == 1
    assert departments[0]["name"] == "Pediatrics"
    doctors = db.get_doctors(hospital.id, departments[0]["id"])
    doctor_names = sorted(d["name"] for d in doctors)
    assert doctor_names == ["Dr. Arjun Singh", "Dr. Meera Nair"]

    # Section 12.1.1: onboarding must generate REAL slots from the doctor's
    # working pattern, not leave them empty/mock. Dr. Meera Nair works
    # Mon/Tue/Wed/Thu/Fri 09:00-13:00 in 20-minute increments -- every
    # generated slot must fall on one of those weekdays at one of those times.
    meera = next(d for d in doctors if d["name"] == "Dr. Meera Nair")
    slots = db.get_slots(hospital.id, meera["id"])
    assert slots
    for s in slots:
        assert date.fromisoformat(s["date"]).strftime("%a") in ("Mon", "Tue", "Wed", "Thu", "Fri")
    times_on_a_working_day = {s["time"] for s in slots if s["date"] == slots[0]["date"]}
    assert times_on_a_working_day == {"09:00", "09:20", "09:40", "10:00", "10:20", "10:40",
                                       "11:00", "11:20", "11:40", "12:00", "12:20", "12:40"}

    # Phase 8 double-booking guard must apply unchanged to these newly
    # generated slots: booking one excludes it from get_slots(), and a second
    # booking attempt for the exact same doctor/time still raises IntegrityError.
    target = slots[0]
    scheduled_at = datetime.fromisoformat(f"{target['date']}T{target['time']}:00")
    db.create_appointment(hospital.id, "5490001111", departments[0]["id"], meera["id"], scheduled_at)
    remaining = db.get_slots(hospital.id, meera["id"])
    assert target["id"] not in {s["id"] for s in remaining}
    with pytest.raises(IntegrityError):
        db.create_appointment(hospital.id, "5490002222", departments[0]["id"], meera["id"], scheduled_at)

    # Prove Phase 9's per-message routing actually works for this brand-new
    # hospital: a webhook signed with ITS OWN app_secret, for ITS OWN
    # phone_number_id, must be accepted and processed (not silently ignored).
    httpx_mock.add_response(
        url=f"https://graph.facebook.com/v22.0/NEW_HOSPITAL_PHONE_ID/messages",
        json={"messages": [{"id": "wamid.new"}]},
    )
    body = _webhook_body("NEW_HOSPITAL_PHONE_ID", "5490009999", "hi")
    resp2 = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body, "new-hospital-secret"), "Content-Type": "application/json"},
    )
    assert resp2.status_code == 200
    assert len(httpx_mock.get_requests()) == 1  # the new hospital's own token/number were actually used


def test_duplicate_phone_number_id_rejected(hospital_id):
    form = dict(VALID_FORM, whatsapp_phone_number_id="123")  # "123" is the already-seeded hospital's number
    before = db.find_hospital_by_phone_number_id("123")
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 400
    assert "already exists" in resp.text

    after = db.find_hospital_by_phone_number_id("123")
    assert before.id == after.id  # untouched, no duplicate/overwrite


def test_missing_departments_rejected(hospital_id):
    form = dict(VALID_FORM, departments_text="")
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 400
    assert "at least one department" in resp.text.lower()
    assert db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID") is None


def test_department_with_no_doctors_rejected(hospital_id):
    form = dict(VALID_FORM, departments_text="# Pediatrics\n")  # header only, no doctor lines
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 400
    assert "at least one department" in resp.text.lower()
    assert db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID") is None


def test_doctor_line_with_invalid_working_day_rejected(hospital_id):
    form = dict(VALID_FORM, departments_text=(
        "# Pediatrics\n"
        "Dr. Bad Day |||| Mon,Funday | 09:00-13:00 | 20\n"
    ))
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 400
    assert "invalid working day" in resp.text.lower()
    assert db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID") is None


def test_doctor_line_with_invalid_hour_range_rejected(hospital_id):
    form = dict(VALID_FORM, departments_text=(
        "# Pediatrics\n"
        "Dr. Bad Hours |||| Mon | not-a-range | 20\n"
    ))
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 400
    assert "invalid working hour" in resp.text.lower()


def test_doctor_line_missing_fields_rejected(hospital_id):
    form = dict(VALID_FORM, departments_text="# Pediatrics\nDr. Too Few Fields | only two\n")
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 400
    assert "7" in resp.text


def test_tier2_fields_save_correctly(hospital_id):
    form = dict(VALID_FORM, data_tier="tier2", api_base_url="https://erp.stjude.example/api", api_key="tier2-secret-key")
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 200
    assert "Tier 2" in resp.text or "tier2" in resp.text.lower()

    hospital = db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID")
    assert hospital.data_tier == "tier2"
    assert hospital.external_api_base_url == "https://erp.stjude.example/api"
    assert hospital.external_api_key == "tier2-secret-key"


def test_tier2_without_api_fields_rejected(hospital_id):
    form = dict(VALID_FORM, data_tier="tier2", api_base_url="", api_key="")
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 400
    assert db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID") is None


def test_tier3_shows_contact_us_message_with_no_fields_required(hospital_id):
    """Tier 3 (direct DB connection) is explicitly not self-serve -- selecting
    it must succeed with zero API fields submitted, and the confirmation page
    must make clear this is a manually-assisted follow-up, not something the
    wizard itself completed."""
    form = dict(VALID_FORM, data_tier="tier3", api_base_url="", api_key="")
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 200
    assert "manually-assisted" in resp.text.lower() or "contact" in resp.text.lower() or "we'll be in touch" in resp.text.lower()

    hospital = db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID")
    assert hospital.data_tier == "tier3"
    assert hospital.external_api_base_url is None
    assert hospital.external_api_key is None


def test_missing_hospital_name_rejected(hospital_id):
    form = dict(VALID_FORM, name="")
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 400
    assert "name is required" in resp.text.lower()


def test_wrong_admin_secret_rejected(hospital_id):
    form = dict(VALID_FORM, admin_secret="wrong-secret")
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 403
    assert db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID") is None


def test_missing_admin_secret_rejected(hospital_id):
    form = dict(VALID_FORM)
    del form["admin_secret"]
    resp = client.post("/admin/onboard-hospital", data=form)
    assert resp.status_code == 403

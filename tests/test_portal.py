# tests/test_portal.py
"""
Section 12.7: the hospital-staff bookings portal (portal.py) -- a self-serve
login (separate from admin/onboarding.py's platform-wide ADMIN_SECRET) that
lets a hospital's own staff see only their own WhatsApp bookings. Covers:
login success/failure, the signed-cookie session actually gating
/portal/bookings, hospital-scoped data isolation (the same discipline every
other query in db/repository.py already has), and that the portal password
can be set through both onboarding and the tenant edit form.
"""
import os
from datetime import datetime, timedelta

import pytest

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

client = TestClient(app)

ADMIN_SECRET = "test-admin-secret"


@pytest.fixture(autouse=True)
def _clear_portal_cookie():
    """The module-level TestClient's cookie jar persists across tests (same
    client instance reused throughout this file) -- without this, a
    portal_session cookie set by an earlier login test leaks into a later
    test that expects to be logged OUT, e.g. test_bookings_page_requires_login
    would otherwise inherit a still-valid cookie from whichever login test
    ran before it."""
    client.cookies.clear()
    yield
    client.cookies.clear()


def _set_portal_password(hospital_id: int, password: str) -> None:
    h = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id,
        name=h.name,
        whatsapp_phone_number_id=h.whatsapp_phone_number_id,
        access_token=h.access_token,
        app_secret=h.app_secret,
        timezone=h.timezone,
        welcome_message_text=h.welcome_message_text,
        reminder_offsets_hours=h.reminder_offsets_hours,
        reminder_template_name=h.reminder_template_name,
        data_tier=h.data_tier,
        external_api_base_url=h.external_api_base_url,
        external_api_key=h.external_api_key,
        portal_password_hash=db.hash_portal_password(password),
    )


def test_login_page_renders(hospital_id):
    resp = client.get("/portal/login")
    assert resp.status_code == 200
    assert 'name="password"' in resp.text


def test_login_success_sets_cookie_and_redirects(hospital_id):
    _set_portal_password(hospital_id, "hospital-portal-pw")
    resp = client.post("/portal/login", data={"password": "hospital-portal-pw"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/portal/bookings"
    assert "portal_session" in resp.cookies


def test_login_wrong_password_rejected(hospital_id):
    _set_portal_password(hospital_id, "hospital-portal-pw")
    resp = client.post("/portal/login", data={"password": "wrong-password"})
    assert resp.status_code == 403
    assert "portal_session" not in resp.cookies


def test_login_with_no_password_set_anywhere_rejected(hospital_id, second_hospital_id):
    # Neither seeded hospital has a portal password set by default.
    resp = client.post("/portal/login", data={"password": "anything"})
    assert resp.status_code == 403


def test_bookings_page_requires_login(hospital_id):
    resp = client.get("/portal/bookings", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/portal/login"


def test_bookings_page_rejects_tampered_cookie(hospital_id):
    _set_portal_password(hospital_id, "hospital-portal-pw")
    client.cookies.set("portal_session", "1.9999999999.deadbeef" + "0" * 58)
    try:
        resp = client.get("/portal/bookings", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/portal/login"
    finally:
        client.cookies.clear()


def test_bookings_page_shows_only_this_hospitals_appointments(hospital_id, second_hospital_id):
    _set_portal_password(hospital_id, "hospital-a-pw")
    _set_portal_password(second_hospital_id, "hospital-b-pw")

    dept_a = db.get_departments(hospital_id)[0]
    doctor_a = db.get_doctors(hospital_id, dept_a["id"])[0]
    db.create_appointment(hospital_id, "5490001111", dept_a["id"], doctor_a["id"], datetime.now() + timedelta(days=1))

    dept_b = db.get_departments(second_hospital_id)[0]
    doctor_b = db.get_doctors(second_hospital_id, dept_b["id"])[0]
    db.create_appointment(second_hospital_id, "5490002222", dept_b["id"], doctor_b["id"], datetime.now() + timedelta(days=1))

    login_resp = client.post("/portal/login", data={"password": "hospital-a-pw"}, follow_redirects=False)
    assert login_resp.status_code == 303

    try:
        resp = client.get("/portal/bookings")
        assert resp.status_code == 200
        assert "5490001111" in resp.text
        assert "5490002222" not in resp.text
    finally:
        client.cookies.clear()


def test_logout_clears_cookie_and_redirects(hospital_id):
    _set_portal_password(hospital_id, "hospital-portal-pw")
    client.post("/portal/login", data={"password": "hospital-portal-pw"})
    try:
        resp = client.get("/portal/logout", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/portal/login"

        bookings_resp = client.get("/portal/bookings", follow_redirects=False)
        assert bookings_resp.status_code == 303
        assert bookings_resp.headers["location"] == "/portal/login"
    finally:
        client.cookies.clear()


def test_wizard_onboarding_can_set_portal_password():
    from tests.test_onboarding import _build_form

    resp = client.post("/admin/onboard-hospital", data=_build_form(scalars={"portal_password": "new-tenant-pw"}))
    assert resp.status_code == 200

    hospital = db.find_hospital_by_phone_number_id("NEW_HOSPITAL_PHONE_ID")
    assert hospital.portal_password_hash is not None

    login_resp = client.post("/portal/login", data={"password": "new-tenant-pw"}, follow_redirects=False)
    assert login_resp.status_code == 303
    client.cookies.clear()


def test_edit_tenant_can_set_portal_password(hospital_id):
    resp = client.post(f"/admin/edit-tenant/{hospital_id}", data={
        "admin_secret": ADMIN_SECRET,
        "name": "Portal Test Hospital",
        "whatsapp_phone_number_id": "123",
        "access_token": "",
        "app_secret": "",
        "welcome_message_text": "",
        "reminder_offsets_hours": "24",
        "reminder_template_name": "",
        "portal_password": "edited-in-pw",
        "data_tier": "tier1",
        "api_base_url": "",
        "api_key": "",
    })
    assert resp.status_code == 200

    login_resp = client.post("/portal/login", data={"password": "edited-in-pw"}, follow_redirects=False)
    assert login_resp.status_code == 303
    client.cookies.clear()


def test_edit_tenant_blank_portal_password_keeps_existing(hospital_id):
    _set_portal_password(hospital_id, "keep-me-pw")
    resp = client.post(f"/admin/edit-tenant/{hospital_id}", data={
        "admin_secret": ADMIN_SECRET,
        "name": "Portal Test Hospital 2",
        "whatsapp_phone_number_id": "123",
        "access_token": "",
        "app_secret": "",
        "welcome_message_text": "",
        "reminder_offsets_hours": "24",
        "reminder_template_name": "",
        "portal_password": "",
        "data_tier": "tier1",
        "api_base_url": "",
        "api_key": "",
    })
    assert resp.status_code == 200

    login_resp = client.post("/portal/login", data={"password": "keep-me-pw"}, follow_redirects=False)
    assert login_resp.status_code == 303
    client.cookies.clear()

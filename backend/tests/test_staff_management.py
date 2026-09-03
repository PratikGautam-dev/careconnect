# tests/test_staff_management.py
"""portal/routes/staff.py's admin-facing staff CRUD (create/list/patch) --
no dedicated test file existed for this route before, despite it being the
actual, current way a hospital creates a doctor's login (Staff -> Add staff
member -> role Doctor -> pick an existing doctor record), superseding the
older per-doctor "login credentials" flow in portal/routes/doctors.py.

Covers the bug fixed alongside this file: create_staff()'s validation/
duplicate-email error responses used to return {"errors": [...]} (a plural
array) while every consumer of this route (staffFetch, the staff settings
page's setFormError()) only ever reads {"error": "..."} (a singular
string) -- so a real validation failure silently displayed a generic
"Something went wrong." instead of the actual reason. Fixed to match the
singular shape; these tests pin that shape so it can't silently regress."""
import os

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SUPER_ADMIN_JWT_SECRET", "test-super-admin-jwt-secret")

import db.repository as db  # noqa: E402
from db.repositories.hospitals import hash_portal_password  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _staff_login(email: str, password: str) -> dict:
    resp = client.post("/api/portal/staff/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _make_admin(hospital_id: int, email: str = "admin.staffmgmt@example.com", password: str = "hunter22") -> str:
    db.create_staff_user(hospital_id, "admin", email, hash_portal_password(password), "Test Admin")
    return _staff_login(email, password)["access_token"]


def test_create_doctor_staff_links_to_an_existing_doctor(hospital_id):
    admin_token = _make_admin(hospital_id)
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Staff Create",
        working_days=["Mon", "Tue"], working_hours=["09:00-12:00"],
    )

    resp = client.post(
        "/api/portal/staff",
        json={
            "name": "Dr. Staff Create", "email": "staff.create.doctor@example.com",
            "password": "a-real-password", "role": "doctor", "doctor_id": doctor["id"],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "doctor"
    assert body["doctor_id"] == doctor["id"]

    # The new login actually works.
    login = _staff_login("staff.create.doctor@example.com", "a-real-password")
    assert login["staff"]["role"] == "doctor"


def test_create_staff_validation_error_uses_the_singular_error_shape(hospital_id):
    """Regression: this used to be {"errors": [...]} -- a shape no consumer
    of this route (staffFetch, the staff settings page) actually reads,
    so the real reason was silently swallowed into a generic frontend
    message. Every field missing at once, to also confirm the messages are
    joined into one string rather than just the first one being reachable."""
    admin_token = _make_admin(hospital_id)

    resp = client.post(
        "/api/portal/staff",
        json={"name": "", "email": "", "password": "", "role": ""},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert "errors" not in body
    assert isinstance(body["error"], str)
    assert "name" in body["error"].lower()
    assert "email" in body["error"].lower()
    assert "password" in body["error"].lower()
    assert "role" in body["error"].lower()


def test_create_staff_doctor_role_without_a_doctor_selected_is_a_clean_error(hospital_id):
    admin_token = _make_admin(hospital_id)

    resp = client.post(
        "/api/portal/staff",
        json={"name": "Dr. No Doctor", "email": "no.doctor@example.com", "password": "a-real-password", "role": "doctor"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400, resp.text
    assert "doctor" in resp.json()["error"].lower()


def test_create_staff_duplicate_email_uses_the_singular_error_shape(hospital_id):
    admin_token = _make_admin(hospital_id)
    db.create_staff_user(hospital_id, "receptionist", "dupe@example.com", hash_portal_password("x"), "Existing")

    resp = client.post(
        "/api/portal/staff",
        json={"name": "New Person", "email": "dupe@example.com", "password": "a-real-password", "role": "receptionist"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert "errors" not in body
    assert "already in use" in body["error"].lower()


def test_create_staff_requires_write_permission(hospital_id):
    db.create_staff_user(hospital_id, "receptionist", "recep.nowrite@example.com", hash_portal_password("x"), "Recep")
    token = _staff_login("recep.nowrite@example.com", "x")["access_token"]

    resp = client.post(
        "/api/portal/staff",
        json={"name": "Someone", "email": "someone@example.com", "password": "a-real-password", "role": "receptionist"},
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text

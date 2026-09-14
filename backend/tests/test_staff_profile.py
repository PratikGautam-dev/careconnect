# tests/test_staff_profile.py
"""portal/routes/staff_auth.py's GET /api/portal/staff/me -- the Profile
page's own data source. Backed by db.get_own_profile() (staff_users.py),
which coalesces a doctor-role login's profile fields (phone/employee_id/
department/schedule/specialization/qualification/years_experience/
location) from its linked doctors row rather than this login's own
separate, usually-blank staff_details copies -- these tests pin that
coalescing so it can't silently regress back to reading the blank columns."""
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


def _role_id(hospital_id: int, name: str) -> int:
    return next(r["id"] for r in db.list_roles(hospital_id) if r["name"].lower() == name.lower())


def test_staff_me_returns_own_profile_fields_for_a_plain_staff_login(hospital_id):
    db.create_staff_user(
        hospital_id, _role_id(hospital_id, "receptionist"), "profile.recep@example.com", hash_portal_password("x"),
        "Recep Profile",
        phone="9876543210", address="221B Baker Street", department_id="cardiology",
        working_days=["Mon", "Tue"], working_hours=["09:00-13:00"], breaks=["11:00-11:15"],
    )
    token = _staff_login("profile.recep@example.com", "x")["access_token"]

    resp = client.get("/api/portal/staff/me", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Recep Profile"
    assert body["is_doctor_role"] is False
    assert body["phone"] == "9876543210"
    assert body["address"] == "221B Baker Street"
    assert body["department_name"] == "Cardiology"
    assert body["working_days"] == ["Mon", "Tue"]
    assert body["working_hours"] == ["09:00-13:00"]
    assert body["breaks"] == ["11:00-11:15"]
    assert body["employee_id"].startswith("EMP-ST-")
    assert body["specialization"] is None
    assert body["qualification"] is None
    assert body["years_experience"] is None
    assert body["location"] is None


def test_staff_me_sources_doctor_fields_from_the_linked_doctor_row(hospital_id):
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Profile Test",
        specialization="Cardiology", qualification="MD", years_experience=12,
        working_days=["Mon", "Wed"], working_hours=["10:00-14:00"],
    )
    doctor_full = db.get_doctor_full(hospital_id, doctor["id"])
    db.create_staff_user(
        hospital_id, _role_id(hospital_id, "doctor"), "profile.doctor@example.com", hash_portal_password("x"),
        "Dr. Profile Test",
        doctor_id=doctor["id"],
        # This login's OWN staff_details copies are deliberately different/
        # blank from the doctor's real profile -- proves the route reads
        # the doctors row, not these.
        phone="", working_days=[], working_hours=[],
    )
    token = _staff_login("profile.doctor@example.com", "x")["access_token"]

    resp = client.get("/api/portal/staff/me", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_doctor_role"] is True
    assert body["doctor_id"] == doctor["id"]
    assert body["specialization"] == "Cardiology"
    assert body["qualification"] == "MD"
    assert body["years_experience"] == 12
    assert body["department_name"] == "Cardiology"
    assert body["working_days"] == ["Mon", "Wed"]
    assert body["working_hours"] == ["10:00-14:00"]
    assert body["employee_id"] == doctor_full["employee_id"]
    assert body["phone"] == doctor_full["phone"]

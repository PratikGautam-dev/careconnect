# tests/test_portal_doctor_scoping.py
"""
Doctor/portal consolidation follow-up: /api/portal/bookings and
/api/portal/patients (+ its {id} detail route) used to be hospital-wide and
unscoped regardless of caller role, which was only safe because doctors
were blocked from /portal/* entirely. Now that a doctor logs in through the
same shared portal, portal/routes/bookings.py and portal/routes/patients.py
scope themselves to the caller's own data when role=="doctor" (via the new
_authenticate_with_role() in portal/deps.py). This file proves that
scoping actually holds -- the same cross-doctor isolation guarantee
tests/test_doctor_unified_login.py proves for the dedicated /api/doctor/*
routes, now proven for the shared /api/portal/* routes those doctors use
too.
"""
import os
from datetime import datetime, timedelta

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

_book_call_count = 0


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _staff_login(email: str, password: str) -> dict:
    resp = client.post("/api/portal/staff/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _make_doctor(hospital_id: int, name: str, email: str, password: str = "hunter22") -> tuple[str, str]:
    """Returns (doctor_id, access_token). Same cardiology department_id every
    test hospital seeds, same pattern test_doctor_unified_login.py uses."""
    doctor = db.create_doctor(
        hospital_id, "cardiology", name,
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-12:00"],
    )
    db.create_staff_user(hospital_id, "doctor", email, hash_portal_password(password), name, doctor_id=doctor["id"])
    token = _staff_login(email, password)["access_token"]
    return doctor["id"], token


def _make_staff(hospital_id: int, role: str, name: str, email: str, password: str = "hunter22") -> str:
    """Returns an access_token for a non-doctor staff role (admin/receptionist)."""
    db.create_staff_user(hospital_id, role, email, hash_portal_password(password), name)
    return _staff_login(email, password)["access_token"]


def _book(hospital_id: int, doctor_id: str, phone: str, patient_name: str | None = None):
    global _book_call_count
    _book_call_count += 1
    scheduled_at = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=30 + _book_call_count)
    return db.create_appointment(hospital_id, phone, "cardiology", doctor_id, scheduled_at, patient_name=patient_name)


def test_portal_bookings_scoped_to_caller_when_role_is_doctor(hospital_id):
    doctor_a, token_a = _make_doctor(hospital_id, "Dr. Scope A", "scope.a@example.com")
    doctor_b, _ = _make_doctor(hospital_id, "Dr. Scope B", "scope.b@example.com")
    appt_a = _book(hospital_id, doctor_a, "5491110001")
    _book(hospital_id, doctor_b, "5491110002")

    resp = client.get("/api/portal/bookings", headers=_auth(token_a))
    assert resp.status_code == 200, resp.text
    ids = [a["id"] for a in resp.json()["appointments"]]
    assert ids == [appt_a.id]


def test_portal_patients_scoped_to_caller_when_role_is_doctor(hospital_id):
    doctor_a, token_a = _make_doctor(hospital_id, "Dr. Scope C", "scope.c@example.com")
    doctor_b, _ = _make_doctor(hospital_id, "Dr. Scope D", "scope.d@example.com")
    _book(hospital_id, doctor_a, "5491110003", patient_name="Patient Of A")
    _book(hospital_id, doctor_b, "5491110004", patient_name="Patient Of B")

    resp = client.get("/api/portal/patients", headers=_auth(token_a))
    assert resp.status_code == 200, resp.text
    names = [p["name"] for p in resp.json()["patients"]]
    assert names == ["Patient Of A"]


def test_portal_patient_detail_404s_for_a_patient_the_doctor_has_not_treated(hospital_id):
    doctor_a, token_a = _make_doctor(hospital_id, "Dr. Scope E", "scope.e@example.com")
    doctor_b, _ = _make_doctor(hospital_id, "Dr. Scope F", "scope.f@example.com")
    _book(hospital_id, doctor_a, "5491110005", patient_name="Patient Of A2")
    appt_b = _book(hospital_id, doctor_b, "5491110006", patient_name="Patient Of B2")

    resp = client.get("/api/portal/patients", headers=_auth(token_a))
    own_patient_id = resp.json()["patients"][0]["id"]

    ok = client.get(f"/api/portal/patients/{own_patient_id}", headers=_auth(token_a))
    assert ok.status_code == 200, ok.text

    forbidden = client.get(f"/api/portal/patients/{appt_b.patient_id}", headers=_auth(token_a))
    assert forbidden.status_code == 404, forbidden.text


def test_portal_bookings_and_patients_remain_hospital_wide_for_admin(hospital_id):
    doctor_a, _ = _make_doctor(hospital_id, "Dr. Scope G", "scope.g@example.com")
    doctor_b, _ = _make_doctor(hospital_id, "Dr. Scope H", "scope.h@example.com")
    _book(hospital_id, doctor_a, "5491110007", patient_name="Patient Of A3")
    _book(hospital_id, doctor_b, "5491110008", patient_name="Patient Of B3")
    admin_token = _make_staff(hospital_id, "admin", "Admin Scope", "admin.scope@example.com")

    bookings = client.get("/api/portal/bookings", headers=_auth(admin_token))
    assert bookings.status_code == 200, bookings.text
    assert len(bookings.json()["appointments"]) == 2

    patients = client.get("/api/portal/patients", headers=_auth(admin_token))
    assert patients.status_code == 200, patients.text
    assert len(patients.json()["patients"]) == 2


def test_schedule_page_key_defaults_view_true_for_doctor_false_for_receptionist(hospital_id):
    admin_token = _make_staff(hospital_id, "admin", "Admin Roles", "admin.roles@example.com")
    resp = client.get("/api/portal/roles/permissions", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    matrix = resp.json()["permissions"]
    assert matrix["doctor"]["schedule"]["view"] is True
    assert matrix["doctor"]["schedule"]["write"] is True
    assert matrix["receptionist"]["schedule"]["view"] is False
    assert matrix["admin"]["schedule"]["view"] is True

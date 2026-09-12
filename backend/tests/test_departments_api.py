"""Settings -> Departments tab's backend (migration 20260912141027,
portal/routes/departments.py). Covers: the new profile/status/visibility
fields round-tripping through create/update/toggle, doctor/support-staff
counts, and -- most importantly -- that a hidden/inactive department is
excluded from the WhatsApp booking flow's department picker
(db.get_departments) while still showing up in every staff-facing list
(get_all_departments_for_hospital, and GET /api/portal/doctors' own bundled
list). Same self-contained hospital_id/_make_admin() pattern
test_leave_requests.py already uses, rather than test_portal_api.py's own
file-local two_hospitals fixture."""
import db.repository as db
from db.repositories.hospitals import hash_portal_password
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _staff_login(email: str, password: str) -> dict:
    resp = client.post("/api/portal/staff/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _make_admin(hospital_id: int, email: str, password: str = "hunter22") -> str:
    db.create_staff_user(hospital_id, "admin", email, hash_portal_password(password), "Test Admin")
    return _staff_login(email, password)["access_token"]


def _find(departments, department_id):
    return next(d for d in departments if d["id"] == department_id)


def test_create_department_with_profile_fields(hospital_id):
    token = _make_admin(hospital_id, "admin.dept.create@example.com")
    resp = client.post(
        "/api/portal/departments",
        json={
            "name": "Radiology Test",
            "floor_wing": "Basement, Diagnostic Wing",
            "consultation_hours": "8:00 AM - 8:00 PM",
            "description": "Imaging and diagnostics.",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    department_id = resp.json()["department"]["id"]

    listing = client.get("/api/portal/departments", headers=_auth(token)).json()["departments"]
    created = _find(listing, department_id)
    assert created["floor_wing"] == "Basement, Diagnostic Wing"
    assert created["consultation_hours"] == "8:00 AM - 8:00 PM"
    assert created["description"] == "Imaging and diagnostics."
    assert created["is_active"] is True
    assert created["show_on_frontend"] is True
    assert created["online_booking_enabled"] is True
    assert created["whatsapp_booking_enabled"] is True
    assert created["head_doctor"] is None
    assert created["doctor_count"] == 0
    assert created["support_staff_count"] == 0


def test_update_department_sets_head_doctor_and_counts_doctors(hospital_id):
    token = _make_admin(hospital_id, "admin.dept.update@example.com")
    doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Head Test",
        working_days=["Mon", "Tue"], working_hours=["09:00-12:00"],
    )
    resp = client.patch(
        "/api/portal/departments/cardiology",
        json={"name": "Cardiology", "head_doctor_id": doctor["id"], "floor_wing": "2nd Floor"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    listing = client.get("/api/portal/departments", headers=_auth(token)).json()["departments"]
    dept = _find(listing, "cardiology")
    assert dept["head_doctor"]["id"] == doctor["id"]
    assert dept["head_doctor"]["name"] == "Dr. Head Test"
    assert dept["floor_wing"] == "2nd Floor"
    assert dept["doctor_count"] >= 1


def test_update_department_rejects_unknown_doctor_as_head(hospital_id):
    token = _make_admin(hospital_id, "admin.dept.badhead@example.com")
    resp = client.patch(
        "/api/portal/departments/cardiology",
        json={"name": "Cardiology", "head_doctor_id": "no-such-doctor"},
        headers=_auth(token),
    )
    assert resp.status_code == 400, resp.text


def test_deactivate_hides_department_from_whatsapp_but_not_from_staff_views(hospital_id):
    token = _make_admin(hospital_id, "admin.dept.deactivate@example.com")
    resp = client.post(
        "/api/portal/departments/cardiology/active", json={"is_active": False}, headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    # The one real patient channel (WhatsApp department picker) excludes it.
    patient_facing = db.get_departments(hospital_id)
    assert "cardiology" not in [d["id"] for d in patient_facing]

    # The portal's own management list still shows it (so staff can turn it
    # back on) -- and so does /api/portal/doctors' bundled list, which feeds
    # the Doctors page's own department list/picker.
    admin_listing = client.get("/api/portal/departments", headers=_auth(token)).json()["departments"]
    assert "cardiology" in [d["id"] for d in admin_listing]
    doctors_page = client.get("/api/portal/doctors", headers=_auth(token)).json()
    assert "cardiology" in [d["id"] for d in doctors_page["departments"]]

    # Re-activating restores it.
    resp = client.post(
        "/api/portal/departments/cardiology/active", json={"is_active": True}, headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    patient_facing_after = db.get_departments(hospital_id)
    assert "cardiology" in [d["id"] for d in patient_facing_after]


def test_visibility_toggle_hides_from_whatsapp_without_deactivating(hospital_id):
    token = _make_admin(hospital_id, "admin.dept.visibility@example.com")
    resp = client.post(
        "/api/portal/departments/cardiology/visibility",
        json={"show_on_frontend": True, "online_booking_enabled": True, "whatsapp_booking_enabled": False},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    patient_facing = db.get_departments(hospital_id)
    assert "cardiology" not in [d["id"] for d in patient_facing]

    # Still shows up as "active" in the admin list -- only WhatsApp booking
    # was turned off, not the whole department.
    admin_listing = client.get("/api/portal/departments", headers=_auth(token)).json()["departments"]
    dept = _find(admin_listing, "cardiology")
    assert dept["is_active"] is True
    assert dept["whatsapp_booking_enabled"] is False


def test_support_staff_count_reflects_staff_details_department_id(hospital_id):
    token = _make_admin(hospital_id, "admin.dept.staffcount@example.com")
    resp = client.post(
        "/api/portal/staff",
        json={
            "name": "Test Receptionist", "email": "test.receptionist.dept@example.com",
            "password": "supersecret1", "role": "receptionist", "department_id": "cardiology",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text

    listing = client.get("/api/portal/departments", headers=_auth(token)).json()["departments"]
    dept = _find(listing, "cardiology")
    assert dept["support_staff_count"] >= 1


def test_departments_are_hospital_scoped(hospital_id, second_hospital_id):
    b_token = _make_admin(second_hospital_id, "admin.dept.scopecheck@example.com")
    resp = client.patch(
        "/api/portal/departments/cardiology",
        json={"name": "Should not work"},
        headers=_auth(b_token),
    )
    assert resp.status_code == 404, resp.text

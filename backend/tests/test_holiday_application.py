# tests/test_holiday_application.py
"""Self-service leave submission (migration 6eda12041ecf) -- the doctor/
staff-facing side of the already-shipped Leave Requests admin review queue
(tests/test_leave_requests.py covers that side). Any staff member, not just
a doctor, can submit; approving a full-day request auto-blocks the doctor's
booking calendar via doctor_leave."""
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


def _role_id(hospital_id: int, name: str) -> int:
    return next(r["id"] for r in db.list_roles(hospital_id) if r["name"].lower() == name.lower())


def _login(email: str, password: str = "hunter22") -> dict:
    resp = client.post("/api/portal/staff/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _make_admin(hospital_id: int) -> str:
    db.create_staff_user(hospital_id, _role_id(hospital_id, "admin"), "hol.admin@example.com", hash_portal_password("hunter22"), "Hol Admin")
    return _login("hol.admin@example.com")["access_token"]


def _make_doctor(hospital_id: int, name: str, email: str) -> tuple[str, str]:
    doctor = db.create_doctor(hospital_id, "cardiology", name, working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-17:00"])
    db.create_staff_user(hospital_id, _role_id(hospital_id, "doctor"), email, hash_portal_password("hunter22"), name, doctor_id=doctor["id"])
    token = _login(email)["access_token"]
    return token, doctor["id"]


def _make_receptionist(hospital_id: int, name: str, email: str) -> str:
    db.create_staff_user(hospital_id, _role_id(hospital_id, "receptionist"), email, hash_portal_password("hunter22"), name)
    return _login(email)["access_token"]


def test_doctor_can_submit_and_see_their_own_leave_request(hospital_id):
    token, _doctor_id = _make_doctor(hospital_id, "Dr. Holiday", "dr.holiday@example.com")
    resp = client.post(
        "/api/portal/leave-requests/mine",
        json={"leave_type": "annual", "from_date": "2026-11-10", "to_date": "2026-11-12", "reason": "Family trip"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["request"]
    assert body["status"] == "pending"
    assert body["duration_days"] == 3
    assert body["is_half_day"] is False

    resp = client.get("/api/portal/leave-requests/mine", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["requests"]) == 1
    assert data["balance"]["quota_days"] == 20  # default doctor_annual_leave_days
    assert data["balance"]["used_days"] == 0  # not yet approved


def test_receptionist_can_also_submit_a_leave_request(hospital_id):
    """Explicit product requirement: Holiday Application is not doctor-only."""
    token = _make_receptionist(hospital_id, "Rita Reception", "rita.reception@example.com")
    resp = client.post(
        "/api/portal/leave-requests/mine",
        json={"leave_type": "casual", "from_date": "2026-11-20", "to_date": "2026-11-20", "reason": "Personal errand"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    resp = client.get("/api/portal/leave-requests/mine", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["balance"]["quota_days"] == 30  # default staff_annual_leave_days


def test_half_day_must_be_a_single_day(hospital_id):
    token, _ = _make_doctor(hospital_id, "Dr. HalfDay", "dr.halfday@example.com")
    resp = client.post(
        "/api/portal/leave-requests/mine",
        json={"leave_type": "sick", "from_date": "2026-11-10", "to_date": "2026-11-11", "is_half_day": True, "reason": "Appointment"},
        headers=_auth(token),
    )
    assert resp.status_code == 400, resp.text


def test_reason_is_required(hospital_id):
    token, _ = _make_doctor(hospital_id, "Dr. NoReason", "dr.noreason@example.com")
    resp = client.post(
        "/api/portal/leave-requests/mine",
        json={"leave_type": "sick", "from_date": "2026-11-10", "to_date": "2026-11-10", "reason": "   "},
        headers=_auth(token),
    )
    assert resp.status_code == 400, resp.text


def test_approving_a_full_day_request_blocks_the_doctor_calendar(hospital_id):
    admin_token = _make_admin(hospital_id)
    doc_token, doctor_id = _make_doctor(hospital_id, "Dr. Blocked", "dr.blocked@example.com")

    resp = client.post(
        "/api/portal/leave-requests/mine",
        json={"leave_type": "annual", "from_date": "2026-12-01", "to_date": "2026-12-02", "reason": "Vacation"},
        headers=_auth(doc_token),
    )
    request_id = resp.json()["request"]["id"]

    assert db.get_doctor_leave(hospital_id, doctor_id) == []

    resp = client.post(f"/api/portal/leave-requests/{request_id}/approve", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text

    leave_dates = {row["date"] for row in db.get_doctor_leave(hospital_id, doctor_id)}
    assert leave_dates == {"2026-12-01", "2026-12-02"}

    # Balance now reflects the approved days.
    resp = client.get("/api/portal/leave-requests/mine", headers=_auth(doc_token))
    assert resp.json()["balance"]["used_days"] == 2


def test_approving_a_half_day_request_does_not_block_the_calendar(hospital_id):
    admin_token = _make_admin(hospital_id)
    doc_token, doctor_id = _make_doctor(hospital_id, "Dr. HalfBlock", "dr.halfblock@example.com")

    resp = client.post(
        "/api/portal/leave-requests/mine",
        json={"leave_type": "sick", "from_date": "2026-12-05", "to_date": "2026-12-05", "is_half_day": True, "reason": "Clinic visit"},
        headers=_auth(doc_token),
    )
    request_id = resp.json()["request"]["id"]

    resp = client.post(f"/api/portal/leave-requests/{request_id}/approve", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text

    assert db.get_doctor_leave(hospital_id, doctor_id) == []

    resp = client.get("/api/portal/leave-requests/mine", headers=_auth(doc_token))
    assert resp.json()["balance"]["used_days"] == 0.5


def test_receptionists_own_leave_is_not_gated_by_the_admin_review_permission(hospital_id):
    """holiday_application (submit) and leave_requests (review) are two
    separate permissions -- a receptionist has no access to the admin
    review queue by default, but must still be able to submit their own."""
    token = _make_receptionist(hospital_id, "Rita NoReview", "rita.noreview@example.com")
    resp = client.get("/api/portal/leave-requests", headers=_auth(token))
    assert resp.status_code == 403, resp.text

    resp = client.get("/api/portal/leave-requests/mine", headers=_auth(token))
    assert resp.status_code == 200, resp.text

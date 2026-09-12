# tests/test_leave_requests.py
"""Leave Requests admin page's backend (migration 20260912065049) --
portal/routes/leave_requests.py's list/approve/reject + the doctor/
receptionist annual leave policy, and the real leave_balance_total/used
fields this migration adds to GET /api/portal/staff and GET
/api/portal/doctors.

No POST /api/portal/leave-requests (create) route exists yet -- doctor/
staff self-service is a later page (confirmed with the user) -- so every
request here is seeded directly via db.create_leave_request(), the same
way the real self-service page will eventually call it."""
import os
from datetime import date, timedelta

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SUPER_ADMIN_JWT_SECRET", "test-super-admin-jwt-secret")

import pytest  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

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


def _make_admin(hospital_id: int, email: str = "admin.leave@example.com", password: str = "hunter22") -> str:
    db.create_staff_user(hospital_id, "admin", email, hash_portal_password(password), "Test Admin")
    return _staff_login(email, password)["access_token"]


def _make_receptionist(hospital_id: int, email: str, name: str = "Recep", password: str = "hunter22") -> dict:
    staff = db.create_staff_user(hospital_id, "receptionist", email, hash_portal_password(password), name)
    return {"identity_id": staff["id"], "token": _staff_login(email, password)["access_token"]}


def _make_doctor_with_login(hospital_id: int, email: str, name: str = "Dr. Leave", password: str = "hunter22") -> dict:
    doctor = db.create_doctor(
        hospital_id, "cardiology", name,
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-12:00"],
    )
    staff = db.create_staff_user(hospital_id, "doctor", email, hash_portal_password(password), name, doctor_id=doctor["id"])
    return {"doctor_id": doctor["id"], "identity_id": staff["id"]}


def test_leave_policy_defaults_to_twenty_and_thirty(hospital_id):
    admin_token = _make_admin(hospital_id)
    resp = client.get("/api/portal/leave-requests/policy", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["doctor_annual_leave_days"] == 20
    assert body["staff_annual_leave_days"] == 30


def test_admin_can_update_leave_policy(hospital_id):
    admin_token = _make_admin(hospital_id)
    resp = client.post(
        "/api/portal/leave-requests/policy",
        json={"doctor_annual_leave_days": 18, "staff_annual_leave_days": 24},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"doctor_annual_leave_days": 18, "staff_annual_leave_days": 24}

    resp2 = client.get("/api/portal/leave-requests/policy", headers=_auth(admin_token))
    assert resp2.json() == {"doctor_annual_leave_days": 18, "staff_annual_leave_days": 24}


def test_leave_policy_rejects_negative_values(hospital_id):
    admin_token = _make_admin(hospital_id)
    resp = client.post(
        "/api/portal/leave-requests/policy",
        json={"doctor_annual_leave_days": -1, "staff_annual_leave_days": 10},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400, resp.text


def test_list_leave_requests_is_empty_for_a_fresh_hospital(hospital_id):
    admin_token = _make_admin(hospital_id)
    resp = client.get("/api/portal/leave-requests", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requests"] == []
    assert body["summary"] == {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "on_leave_today": 0}


def test_seeded_leave_request_appears_pending_with_correct_shape(hospital_id):
    admin_token = _make_admin(hospital_id)
    recep = _make_receptionist(hospital_id, "recep.pending@example.com")
    db.create_leave_request(hospital_id, recep["identity_id"], "casual", "2027-01-10", "2027-01-12", "Family event")

    resp = client.get("/api/portal/leave-requests", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["requests"]) == 1
    row = body["requests"][0]
    assert row["applicant_name"] == "Recep"
    assert row["role"] == "receptionist"
    assert row["leave_type"] == "casual"
    assert row["duration_days"] == 3  # 10th, 11th, 12th inclusive
    assert row["status"] == "pending"
    assert row["reason"] == "Family event"
    assert body["summary"]["pending"] == 1
    assert body["summary"]["total"] == 1


def test_admin_can_approve_a_pending_request(hospital_id):
    admin_token = _make_admin(hospital_id)
    recep = _make_receptionist(hospital_id, "recep.approve@example.com")
    created = db.create_leave_request(hospital_id, recep["identity_id"], "sick", "2027-02-01", "2027-02-02")

    resp = client.post(f"/api/portal/leave-requests/{created['id']}/approve", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    row = resp.json()["request"]
    assert row["status"] == "approved"
    assert row["decided_by_name"] == "Test Admin"


def test_admin_can_reject_a_pending_request(hospital_id):
    admin_token = _make_admin(hospital_id)
    recep = _make_receptionist(hospital_id, "recep.reject@example.com")
    created = db.create_leave_request(hospital_id, recep["identity_id"], "sick", "2027-02-01", "2027-02-02")

    resp = client.post(f"/api/portal/leave-requests/{created['id']}/reject", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["request"]["status"] == "rejected"


def test_deciding_an_already_decided_request_is_a_clean_404(hospital_id):
    """Approving/rejecting is only ever valid on a pending request -- a
    stale UI or a double-click retrying the same decision must not
    silently re-approve or flip an already-rejected request."""
    admin_token = _make_admin(hospital_id)
    recep = _make_receptionist(hospital_id, "recep.double@example.com")
    created = db.create_leave_request(hospital_id, recep["identity_id"], "sick", "2027-02-01", "2027-02-02")

    first = client.post(f"/api/portal/leave-requests/{created['id']}/approve", headers=_auth(admin_token))
    assert first.status_code == 200, first.text

    second = client.post(f"/api/portal/leave-requests/{created['id']}/reject", headers=_auth(admin_token))
    assert second.status_code == 404, second.text

    # Still approved, not flipped to rejected.
    resp = client.get("/api/portal/leave-requests", headers=_auth(admin_token))
    assert resp.json()["requests"][0]["status"] == "approved"


def test_receptionist_without_leave_requests_permission_is_forbidden(hospital_id):
    recep = _make_receptionist(hospital_id, "recep.noperm@example.com")
    resp = client.get("/api/portal/leave-requests", headers=_auth(recep["token"]))
    assert resp.status_code == 403, resp.text


def test_staff_list_shows_real_leave_balance_after_approval(hospital_id):
    admin_token = _make_admin(hospital_id)
    client.post(
        "/api/portal/leave-requests/policy",
        json={"doctor_annual_leave_days": 20, "staff_annual_leave_days": 30},
        headers=_auth(admin_token),
    )
    recep = _make_receptionist(hospital_id, "recep.balance@example.com")
    today = date.today()
    from_date = today.isoformat()
    to_date = (today + timedelta(days=3)).isoformat()  # 4 days inclusive
    created = db.create_leave_request(hospital_id, recep["identity_id"], "annual", from_date, to_date)
    client.post(f"/api/portal/leave-requests/{created['id']}/approve", headers=_auth(admin_token))

    resp = client.get("/api/portal/staff", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    row = next(s for s in resp.json() if s["id"] == recep["identity_id"])
    assert row["leave_balance_total"] == 30
    assert row["leave_balance_used"] == 4

    # "On leave today" reflects this approved, currently-active request.
    summary = client.get("/api/portal/leave-requests", headers=_auth(admin_token)).json()["summary"]
    assert summary["on_leave_today"] == 1


def test_admin_row_has_no_leave_balance_tracked(hospital_id):
    """Confirmed with the user: the leave policy is doctor/receptionist
    only -- an admin row must show None/None, not a fabricated number."""
    admin_token = _make_admin(hospital_id)
    resp = client.get("/api/portal/staff", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    admin_row = next(s for s in resp.json() if s["role"] == "admin")
    assert admin_row["leave_balance_total"] is None
    assert admin_row["leave_balance_used"] is None


def test_doctor_with_login_shows_real_leave_balance_after_approval(hospital_id):
    admin_token = _make_admin(hospital_id)
    doc = _make_doctor_with_login(hospital_id, "dr.leave.balance@example.com")
    today = date.today()
    from_date = today.isoformat()
    to_date = (today + timedelta(days=4)).isoformat()  # 5 days inclusive, and inside THIS year
    created = db.create_leave_request(hospital_id, doc["identity_id"], "conference", from_date, to_date)
    client.post(f"/api/portal/leave-requests/{created['id']}/approve", headers=_auth(admin_token))

    resp = client.get("/api/portal/doctors", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    row = next(d for d in resp.json()["doctors"] if d["id"] == doc["doctor_id"])
    assert row["leave_balance_total"] == 20
    assert row["leave_balance_used"] == 5


def test_doctor_without_login_has_no_leave_balance(hospital_id):
    admin_token = _make_admin(hospital_id)
    doctor = db.create_doctor(hospital_id, "cardiology", "Dr. No Login Balance")

    resp = client.get("/api/portal/doctors", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    row = next(d for d in resp.json()["doctors"] if d["id"] == doctor["id"])
    assert row["leave_balance_total"] is None
    assert row["leave_balance_used"] is None


def test_leave_usage_is_clipped_to_the_current_calendar_year(hospital_id):
    """A request spanning Dec 31 -> Jan 2 of the NEXT year must only count
    the one day (Dec 31) that falls in the current computation year -- the
    policy resets annually (confirmed with the user), so the far side of a
    boundary-crossing request must never inflate either year's usage."""
    recep = _make_receptionist(hospital_id, "recep.yearclip@example.com")
    created = db.create_leave_request(hospital_id, recep["identity_id"], "annual", "2027-12-31", "2028-01-02")
    db.decide_leave_request(hospital_id, created["id"], recep["identity_id"], "approved")

    usage_2027 = db.get_leave_usage_by_identity(hospital_id, year=2027)
    usage_2028 = db.get_leave_usage_by_identity(hospital_id, year=2028)
    assert usage_2027.get(recep["identity_id"], 0) == 1  # only Dec 31
    assert usage_2028.get(recep["identity_id"], 0) == 2  # only Jan 1 + Jan 2


def test_leave_request_status_and_type_are_validated_at_the_db_layer(hospital_id):
    """Not exercised through the API (no create route yet) -- confirms the
    CHECK constraints this migration added actually reject bad data at
    the repository layer, the same guard the future self-service page
    will rely on."""
    recep = _make_receptionist(hospital_id, "recep.checkconstraint@example.com")
    with pytest.raises(IntegrityError):
        db.create_leave_request(hospital_id, recep["identity_id"], "not-a-real-type", "2027-01-01", "2027-01-02")

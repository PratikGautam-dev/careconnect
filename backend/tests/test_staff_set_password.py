# tests/test_staff_set_password.py
"""portal/routes/staff.py's admin-initiated POST /api/portal/staff/{id}/
password -- unlike staff_auth.py's self-service change-password, there's no
current-password check (the caller is an admin resetting someone ELSE's
password) and the admin's own tokens aren't touched. Covers permission
gating, hospital scoping, and that the reset actually takes effect."""
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


def _make_admin(hospital_id: int, email: str, password: str = "hunter22") -> str:
    db.create_staff_user(hospital_id, "admin", email, hash_portal_password(password), "Test Admin")
    return _staff_login(email, password)["access_token"]


def test_admin_can_reset_staff_password(hospital_id):
    admin_token = _make_admin(hospital_id, "sp.admin@example.com")
    staff = db.create_staff_user(hospital_id, "receptionist", "sp.target@example.com", hash_portal_password("old-password-1"), "Target Staff")

    resp = client.post(
        f"/api/portal/staff/{staff['id']}/password",
        json={"new_password": "new-password-1"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text

    old_login = client.post("/api/portal/staff/login", json={"email": "sp.target@example.com", "password": "old-password-1"})
    assert old_login.status_code == 401, old_login.text

    new_login = client.post("/api/portal/staff/login", json={"email": "sp.target@example.com", "password": "new-password-1"})
    assert new_login.status_code == 200, new_login.text


def test_reset_password_rejects_short_password(hospital_id):
    admin_token = _make_admin(hospital_id, "sp.short@example.com")
    staff = db.create_staff_user(hospital_id, "receptionist", "sp.short.target@example.com", hash_portal_password("old-password-1"), "Target Staff")

    resp = client.post(
        f"/api/portal/staff/{staff['id']}/password",
        json={"new_password": "short"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400, resp.text


def test_reset_password_requires_authentication(hospital_id):
    staff = db.create_staff_user(hospital_id, "receptionist", "sp.noauth@example.com", hash_portal_password("old-password-1"), "Target Staff")
    resp = client.post(f"/api/portal/staff/{staff['id']}/password", json={"new_password": "new-password-1"})
    assert resp.status_code == 401, resp.text


def test_reset_password_requires_staff_write_permission(hospital_id):
    # Receptionists get no "staff" permission by default (DEFAULT_PERMISSIONS_BY_ROLE).
    db.create_staff_user(hospital_id, "receptionist", "sp.rec@example.com", hash_portal_password("hunter22"), "Plain Receptionist")
    rec_login = _staff_login("sp.rec@example.com", "hunter22")

    target = db.create_staff_user(hospital_id, "receptionist", "sp.rectarget@example.com", hash_portal_password("old-password-1"), "Target Staff")
    resp = client.post(
        f"/api/portal/staff/{target['id']}/password",
        json={"new_password": "new-password-1"},
        headers=_auth(rec_login["access_token"]),
    )
    assert resp.status_code == 403, resp.text


def test_reset_password_is_scoped_to_own_hospital(hospital_id, second_hospital_id):
    admin_token = _make_admin(hospital_id, "sp.crosshosp.admin@example.com")
    other_staff = db.create_staff_user(
        second_hospital_id, "receptionist", "sp.otherhospital@example.com",
        hash_portal_password("old-password-1"), "Other Hospital Staff",
    )

    resp = client.post(
        f"/api/portal/staff/{other_staff['id']}/password",
        json={"new_password": "new-password-1"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404, resp.text

    still_old = client.post("/api/portal/staff/login", json={"email": "sp.otherhospital@example.com", "password": "old-password-1"})
    assert still_old.status_code == 200, still_old.text

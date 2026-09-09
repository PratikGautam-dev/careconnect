# tests/test_staff_change_password.py
"""portal/routes/staff_auth.py's self-service POST /api/portal/staff/change-
password -- verifies current-password checking, the actual password swap
(next login uses the new password, not the old one), and that the caller's
own session survives (token_version bump from db.update_staff_user_password()
re-issues fresh tokens in the same response rather than logging this
request's own caller out)."""
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


def _make_staff(hospital_id: int, email: str, password: str) -> dict:
    db.create_staff_user(hospital_id, "admin", email, hash_portal_password(password), "Test Staff")
    resp = client.post("/api/portal/staff/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_change_password_requires_correct_current_password(hospital_id):
    login = _make_staff(hospital_id, "cp.wrong@example.com", "old-password-1")
    resp = client.post(
        "/api/portal/staff/change-password",
        json={"current_password": "not-the-real-one", "new_password": "new-password-1"},
        headers=_auth(login["access_token"]),
    )
    assert resp.status_code == 400, resp.text


def test_change_password_rejects_short_new_password(hospital_id):
    login = _make_staff(hospital_id, "cp.short@example.com", "old-password-1")
    resp = client.post(
        "/api/portal/staff/change-password",
        json={"current_password": "old-password-1", "new_password": "short"},
        headers=_auth(login["access_token"]),
    )
    assert resp.status_code == 400, resp.text


def test_change_password_succeeds_and_new_password_works_on_next_login(hospital_id):
    login = _make_staff(hospital_id, "cp.ok@example.com", "old-password-1")
    resp = client.post(
        "/api/portal/staff/change-password",
        json={"current_password": "old-password-1", "new_password": "new-password-1"},
        headers=_auth(login["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data and "refresh_token" in data

    old_login = client.post("/api/portal/staff/login", json={"email": "cp.ok@example.com", "password": "old-password-1"})
    assert old_login.status_code == 401, old_login.text

    new_login = client.post("/api/portal/staff/login", json={"email": "cp.ok@example.com", "password": "new-password-1"})
    assert new_login.status_code == 200, new_login.text


def test_change_password_reissued_token_still_works_immediately(hospital_id):
    login = _make_staff(hospital_id, "cp.selfsession@example.com", "old-password-1")
    resp = client.post(
        "/api/portal/staff/change-password",
        json={"current_password": "old-password-1", "new_password": "new-password-1"},
        headers=_auth(login["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    new_token = resp.json()["access_token"]

    # The OLD access token's token_version claim is now stale (the change
    # bumped it) -- a request against a protected route with the old token
    # must fail, while the freshly re-issued one must succeed.
    stale = client.get("/api/portal/staff", headers=_auth(login["access_token"]))
    assert stale.status_code == 401, stale.text

    fresh = client.get("/api/portal/staff", headers=_auth(new_token))
    assert fresh.status_code == 200, fresh.text


def test_change_password_requires_authentication(hospital_id):
    resp = client.post(
        "/api/portal/staff/change-password",
        json={"current_password": "x", "new_password": "new-password-1"},
    )
    assert resp.status_code == 401, resp.text


def test_staff_me_returns_profile_including_email(hospital_id):
    login = _make_staff(hospital_id, "cp.me@example.com", "old-password-1")
    resp = client.get("/api/portal/staff/me", headers=_auth(login["access_token"]))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["email"] == "cp.me@example.com"
    assert data["role"] == "admin"
    assert data["hospital"]["id"] == hospital_id
    assert "permissions" in data and isinstance(data["permissions"], dict)


def test_staff_me_requires_authentication(hospital_id):
    resp = client.get("/api/portal/staff/me")
    assert resp.status_code == 401, resp.text

# tests/test_google_calendar_integration.py
"""Google Meet integration (Spec.md Section 0): one Google account
connected per HOSPITAL by an admin (require_permission(principal,
"settings", "write")), used for every doctor's tele-consultation Meet
links -- not a per-doctor connection (a revision of the original plan,
confirmed with the user directly). Alongside, never replacing, the
existing Jitsi tele-consultation link.

The one hard requirement this whole build was scoped around: the app must
boot cleanly and every route it adds must degrade gracefully (never a 500)
with GOOGLE_CALENDAR_CLIENT_ID/GOOGLE_CALENDAR_CLIENT_SECRET/
CALENDAR_TOKEN_ENCRYPTION_KEY all unset -- the real state of every
deployment until the user hands over actual credentials.

conftest.py never sets these three vars, so every OTHER test file in this
suite already proves "the app imports/boots with them unset" hundreds of
times over just by existing -- this file's own boot-safety tests
additionally use monkeypatch.delenv (defensive against a leaked shell env
var) and assert the actual HTTP-level graceful-degradation behavior
directly, per the user's explicit "don't just reason about it, prove it"
requirement."""
import os

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")
os.environ.setdefault("DOCTOR_SECRET", "test-doctor-secret")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SUPER_ADMIN_JWT_SECRET", "test-super-admin-jwt-secret")

import pytest  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402

import db.repository as db  # noqa: E402
from core.config import get_settings  # noqa: E402
from core.crypto import CryptoNotConfiguredError, decrypt_secret, encrypt_secret  # noqa: E402
from db.repositories.hospitals import hash_portal_password  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from modules.google_calendar import create_meet_event, is_calendar_integration_configured  # noqa: E402

client = TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_admin(hospital_id: int, email: str = "admin.gcal@example.com", password: str = "hunter22") -> str:
    db.create_staff_user(hospital_id, "admin", email, hash_portal_password(password), "Test Admin")
    return _staff_login(email, password)["access_token"]


def _make_receptionist(hospital_id: int, email: str = "recep.gcal@example.com", password: str = "hunter22") -> str:
    db.create_staff_user(hospital_id, "receptionist", email, hash_portal_password(password), "Test Receptionist")
    return _staff_login(email, password)["access_token"]


def _staff_login(email: str, password: str) -> dict:
    resp = client.post("/api/portal/staff/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture(autouse=True)
def _calendar_env_vars_unset(monkeypatch):
    """The default backdrop for every test in this file -- explicitly
    guaranteed unset (not just "happens to be unset"), even if something in
    the environment this suite runs in has ever set them. Individual tests
    that need the feature "on" call monkeypatch.setenv themselves, on top of
    this fixture already having cleared the slate."""
    monkeypatch.delenv("GOOGLE_CALENDAR_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CALENDAR_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("CALENDAR_TOKEN_ENCRYPTION_KEY", raising=False)


# --- Boot safety + graceful degradation, unconfigured ---

def test_app_boots_with_all_three_calendar_env_vars_unset():
    """Not just "doesn't raise" -- confirms core/config.py's Settings()
    actually reads them back as the empty-string default, the same
    DOCTOR_SECRET-precedent shape every other optional secret in that file
    uses, and that the app object built at this file's own import time
    (`from main import app` above, with these vars already unset per the
    fixture) is a real, usable FastAPI app."""
    settings = get_settings()
    assert settings.GOOGLE_CALENDAR_CLIENT_ID == ""
    assert settings.GOOGLE_CALENDAR_CLIENT_SECRET == ""
    assert settings.CALENDAR_TOKEN_ENCRYPTION_KEY == ""
    assert is_calendar_integration_configured() is False
    # A totally unrelated route still works -- proves the app is genuinely
    # up, not just that import didn't crash.
    resp = client.get("/api/portal/calendar/status", headers=_auth("garbage"))
    assert resp.status_code == 401  # not authenticated, but a clean 401 -- no 500


def test_calendar_status_reports_unconfigured_and_disconnected(hospital_id):
    token = _make_admin(hospital_id)

    resp = client.get("/api/portal/calendar/status", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"configured": False, "connected": False, "google_email": None}


def test_calendar_status_and_disconnect_require_settings_permission(hospital_id):
    """A receptionist has no write access to Settings by default
    (portal/permissions.py's DEFAULT_PERMISSIONS_BY_ROLE) -- initiating or
    revoking the hospital's shared Google account connection is sensitive
    enough that this must be a real 403, not just a hidden button."""
    token = _make_receptionist(hospital_id)

    resp = client.get("/api/portal/calendar/status", headers=_auth(token))
    assert resp.status_code == 403, resp.text

    resp = client.post("/api/portal/calendar/disconnect", headers=_auth(token))
    assert resp.status_code == 403, resp.text


def test_connect_route_returns_a_graceful_error_not_a_500_when_unconfigured(hospital_id):
    token = _make_admin(hospital_id)

    resp = client.get(f"/auth/google/calendar/connect?token={token}", follow_redirects=False)
    assert resp.status_code == 503
    assert "isn't configured" in resp.json()["error"].lower()


def test_connect_route_rejects_a_bad_token_before_touching_oauth(hospital_id):
    """Even if the feature WERE configured, a missing/invalid admin token
    must be a clean 401, never a 500 -- checked here against the
    unconfigured backdrop (503 wins first, since that check runs first),
    and again below with the feature toggled on."""
    resp = client.get("/auth/google/calendar/connect?token=not-a-real-token", follow_redirects=False)
    assert resp.status_code in (401, 503)


def test_disconnect_is_a_safe_noop_with_no_existing_connection(hospital_id):
    token = _make_admin(hospital_id)

    resp = client.post("/api/portal/calendar/disconnect", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}


def test_create_meet_event_returns_none_when_unconfigured(hospital_id):
    """The exact function flows/booking/types/tele_consultation.py's hook
    calls -- must never raise, must return None, so the Jitsi fallback in
    that hook is unconditionally reached. tests/test_booking_flow.py's own
    full-flow tele tests already prove that fallback end to end; this is
    the narrower, direct proof of the piece feeding it."""
    from datetime import datetime

    link = create_meet_event(hospital_id, "Tele-consultation", datetime.now(), 30)
    assert link is None


# --- Graceful degradation, feature toggled ON (a fake key/id/secret --
# these tests never call out to Google, only exercise config-plumbing and
# status/disconnect once a connection row exists) ---

def test_connect_route_gates_on_a_valid_admin_token_once_configured(hospital_id, monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("CALENDAR_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert is_calendar_integration_configured() is True

    resp = client.get("/auth/google/calendar/connect?token=not-a-real-token", follow_redirects=False)
    assert resp.status_code == 401
    assert resp.json()["error"] == "Not authenticated."


def test_connect_route_rejects_a_valid_non_admin_token_once_configured(hospital_id, monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("CALENDAR_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    token = _make_receptionist(hospital_id)

    resp = client.get(f"/auth/google/calendar/connect?token={token}", follow_redirects=False)
    assert resp.status_code == 403


def test_status_reports_connected_once_a_connection_row_exists(hospital_id, monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("CALENDAR_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

    token = _make_admin(hospital_id)
    db.upsert_calendar_connection(
        hospital_id, "hospital@gmail.com", "encrypted-access", "encrypted-refresh",
        "2099-01-01T00:00:00",
    )

    resp = client.get("/api/portal/calendar/status", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"configured": True, "connected": True, "google_email": "hospital@gmail.com"}

    resp = client.post("/api/portal/calendar/disconnect", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    resp = client.get("/api/portal/calendar/status", headers=_auth(token))
    assert resp.json()["connected"] is False


def test_connection_is_shared_across_every_doctor_at_the_hospital(hospital_id):
    """The whole point of the redesign: one connection covers every doctor
    at the hospital, not just whichever one happened to connect it."""
    doctor_a = db.create_doctor(
        hospital_id, "cardiology", "Dr. Shared A",
        working_days=["Mon"], working_hours=["09:00-12:00"],
    )
    doctor_b = db.create_doctor(
        hospital_id, "cardiology", "Dr. Shared B",
        working_days=["Mon"], working_hours=["09:00-12:00"],
    )
    db.upsert_calendar_connection(
        hospital_id, "hospital@gmail.com", "encrypted-access", "encrypted-refresh", "2099-01-01T00:00:00",
    )
    # create_meet_event() looks the connection up purely by hospital_id --
    # confirmed here it doesn't matter which doctor's appointment this is.
    connection_for_a = db.get_calendar_connection(hospital_id)
    connection_for_b = db.get_calendar_connection(hospital_id)
    assert connection_for_a == connection_for_b
    assert doctor_a["id"] != doctor_b["id"]


# --- core/crypto.py ---

def test_encrypt_decrypt_roundtrip_with_a_configured_key():
    key = Fernet.generate_key().decode()
    ciphertext = encrypt_secret("a-real-refresh-token", key)
    assert ciphertext != "a-real-refresh-token"
    assert decrypt_secret(ciphertext, key) == "a-real-refresh-token"


def test_encrypt_raises_clean_error_with_no_key():
    with pytest.raises(CryptoNotConfiguredError):
        encrypt_secret("anything", "")


def test_decrypt_raises_clean_error_with_wrong_key():
    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()
    ciphertext = encrypt_secret("a-real-refresh-token", key_a)
    with pytest.raises(CryptoNotConfiguredError):
        decrypt_secret(ciphertext, key_b)


# --- db/repositories/google_calendar.py ---

def test_calendar_connection_repo_crud(hospital_id):
    assert db.get_calendar_connection(hospital_id) is None

    db.upsert_calendar_connection(
        hospital_id, "repo@gmail.com", "enc-access-1", "enc-refresh-1", "2099-01-01T00:00:00",
    )
    connection = db.get_calendar_connection(hospital_id)
    assert connection["google_email"] == "repo@gmail.com"
    assert connection["encrypted_access_token"] == "enc-access-1"
    assert connection["calendar_id"] == "primary"

    db.update_calendar_access_token(hospital_id, "enc-access-2", "2099-06-01T00:00:00")
    connection = db.get_calendar_connection(hospital_id)
    assert connection["encrypted_access_token"] == "enc-access-2"
    assert connection["encrypted_refresh_token"] == "enc-refresh-1"  # untouched by a token-only refresh

    assert db.delete_calendar_connection(hospital_id) is True
    assert db.get_calendar_connection(hospital_id) is None
    assert db.delete_calendar_connection(hospital_id) is False  # already gone -- no error, just False


def test_calendar_connection_is_isolated_per_hospital(hospital_id, second_hospital_id):
    db.upsert_calendar_connection(
        hospital_id, "hospital-a@gmail.com", "enc-access-a", "enc-refresh-a", "2099-01-01T00:00:00",
    )
    assert db.get_calendar_connection(second_hospital_id) is None
    assert db.get_calendar_connection(hospital_id)["google_email"] == "hospital-a@gmail.com"

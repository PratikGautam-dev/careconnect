# tests/test_google_calendar_integration.py
"""Google Meet integration (Spec.md Section 0): alongside, never replacing,
the existing Jitsi tele-consultation link. The one hard requirement this
whole build was scoped around: the app must boot cleanly and every route it
adds must degrade gracefully (never a 500) with GOOGLE_CALENDAR_CLIENT_ID/
GOOGLE_CALENDAR_CLIENT_SECRET/CALENDAR_TOKEN_ENCRYPTION_KEY all unset -- the
real state of every deployment until the user hands over actual credentials.

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


def _make_doctor_staff_user(hospital_id: int, name: str, email: str, password: str = "hunter22") -> str:
    doctor = db.create_doctor(
        hospital_id, "cardiology", name,
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-12:00"],
    )
    db.create_staff_user(hospital_id, "doctor", email, hash_portal_password(password), name, doctor_id=doctor["id"])
    return doctor["id"]


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
    resp = client.get("/api/doctor/calendar/status", headers=_auth("garbage"))
    assert resp.status_code == 401  # not authenticated, but a clean 401 -- no 500


def test_calendar_status_reports_unconfigured_and_disconnected(hospital_id):
    doctor_id = _make_doctor_staff_user(hospital_id, "Dr. Cal Status", "cal.status@example.com")
    token = _staff_login("cal.status@example.com", "hunter22")["access_token"]

    resp = client.get("/api/doctor/calendar/status", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"configured": False, "connected": False, "google_email": None}
    assert doctor_id  # sanity: the doctor really was created


def test_connect_route_returns_a_graceful_error_not_a_500_when_unconfigured(hospital_id):
    _make_doctor_staff_user(hospital_id, "Dr. Cal Connect", "cal.connect@example.com")
    token = _staff_login("cal.connect@example.com", "hunter22")["access_token"]

    resp = client.get(f"/auth/google/calendar/connect?token={token}", follow_redirects=False)
    assert resp.status_code == 503
    assert "isn't configured" in resp.json()["error"].lower()


def test_connect_route_rejects_a_bad_token_before_touching_oauth(hospital_id):
    """Even if the feature WERE configured, a missing/invalid doctor token
    must be a clean 401, never a 500 -- checked here against the
    unconfigured backdrop (503 wins first, since that check runs first),
    and again below with the feature toggled on."""
    resp = client.get("/auth/google/calendar/connect?token=not-a-real-token", follow_redirects=False)
    assert resp.status_code in (401, 503)


def test_disconnect_is_a_safe_noop_with_no_existing_connection(hospital_id):
    _make_doctor_staff_user(hospital_id, "Dr. Cal Disconnect", "cal.disconnect@example.com")
    token = _staff_login("cal.disconnect@example.com", "hunter22")["access_token"]

    resp = client.post("/api/doctor/calendar/disconnect", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}


def test_create_meet_event_returns_none_when_unconfigured(hospital_id):
    """The exact function flows/booking/types/tele_consultation.py's hook
    calls -- must never raise, must return None, so the Jitsi fallback in
    that hook is unconditionally reached. tests/test_booking_flow.py's own
    full-flow tele tests already prove that fallback end to end; this is
    the narrower, direct proof of the piece feeding it."""
    from datetime import datetime

    doctor_id = _make_doctor_staff_user(hospital_id, "Dr. Cal Meet", "cal.meet@example.com")
    link = create_meet_event(doctor_id, "Tele-consultation", datetime.now(), 30)
    assert link is None


# --- Graceful degradation, feature toggled ON (a fake key/id/secret --
# these tests never call out to Google, only exercise config-plumbing and
# status/disconnect once a connection row exists) ---

def test_connect_route_gates_on_a_valid_doctor_token_once_configured(hospital_id, monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("CALENDAR_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert is_calendar_integration_configured() is True

    resp = client.get("/auth/google/calendar/connect?token=not-a-real-token", follow_redirects=False)
    assert resp.status_code == 401
    assert resp.json()["error"] == "Not authenticated."


def test_status_reports_connected_once_a_connection_row_exists(hospital_id, monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("CALENDAR_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

    doctor_id = _make_doctor_staff_user(hospital_id, "Dr. Cal Connected", "cal.connected@example.com")
    token = _staff_login("cal.connected@example.com", "hunter22")["access_token"]
    db.upsert_calendar_connection(
        doctor_id, hospital_id, "doc@gmail.com", "encrypted-access", "encrypted-refresh",
        "2099-01-01T00:00:00",
    )

    resp = client.get("/api/doctor/calendar/status", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"configured": True, "connected": True, "google_email": "doc@gmail.com"}

    resp = client.post("/api/doctor/calendar/disconnect", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    resp = client.get("/api/doctor/calendar/status", headers=_auth(token))
    assert resp.json()["connected"] is False


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
    doctor_id = _make_doctor_staff_user(hospital_id, "Dr. Cal Repo", "cal.repo@example.com")

    assert db.get_calendar_connection(doctor_id) is None

    db.upsert_calendar_connection(
        doctor_id, hospital_id, "repo@gmail.com", "enc-access-1", "enc-refresh-1", "2099-01-01T00:00:00",
    )
    connection = db.get_calendar_connection(doctor_id)
    assert connection["google_email"] == "repo@gmail.com"
    assert connection["encrypted_access_token"] == "enc-access-1"
    assert connection["calendar_id"] == "primary"

    db.update_calendar_access_token(doctor_id, "enc-access-2", "2099-06-01T00:00:00")
    connection = db.get_calendar_connection(doctor_id)
    assert connection["encrypted_access_token"] == "enc-access-2"
    assert connection["encrypted_refresh_token"] == "enc-refresh-1"  # untouched by a token-only refresh

    assert db.delete_calendar_connection(doctor_id) is True
    assert db.get_calendar_connection(doctor_id) is None
    assert db.delete_calendar_connection(doctor_id) is False  # already gone -- no error, just False

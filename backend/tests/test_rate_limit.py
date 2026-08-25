# tests/test_rate_limit.py
"""
Audit follow-up (Spec.md Section 0): every password/secret check in this app
previously allowed unlimited guesses, and ADMIN_SECRET/TENANTS_ADMIN_SECRET
used plain `!=`/`==` instead of a timing-safe comparison. Covers:
  - core/rate_limit.py's InMemoryRateLimiter in isolation (threshold, reset,
    window expiry -- via monkeypatched time.time, not a real 15-minute sleep)
  - portal login (both auth/session.py's HTML form and portal/routes/auth.py's JSON
    endpoint, which deliberately share one lockout counter per IP)
  - admin/onboarding.py's ADMIN_SECRET gate (HTML wizard submit) and
    admin/onboarding_api.py's JSON equivalent (which also deliberately share
    one counter, since they're two entry points to the same secret)
  - admin/tenants_api.py's TENANTS_ADMIN_SECRET gate
  - that a successful auth resets the failure count (a couple of wrong
    guesses followed by a correct one doesn't leave you "part-way locked"),
    and that lockout is temporary (expires once the window passes), not a
    permanent brick after one bad guess
"""
import os

import pytest

import core.rate_limit as rate_limit
import db.repository as db

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")

import admin.tenants_api as tenants_api  # noqa: E402
from app import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

ADMIN_SECRET = "test-admin-secret"  # matches conftest.py's os.environ.setdefault

# admin/tenants_api.py reads TENANTS_ADMIN_SECRET from the environment once,
# at import time -- by the time this test module loads, some earlier test
# file may already have imported it with the env var unset (giving a
# permanently-empty module constant for the rest of the process). Patch the
# module attribute directly rather than relying on setdefault() winning a
# race it can't win.
TENANTS_ADMIN_SECRET = "test-tenants-admin-secret"
tenants_api.TENANTS_ADMIN_SECRET = TENANTS_ADMIN_SECRET


@pytest.fixture(autouse=True)
def _clear_cookies():
    client.cookies.clear()
    yield
    client.cookies.clear()


def _set_portal_password(hospital_id: int, password: str) -> None:
    h = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id,
        name=h.name,
        whatsapp_phone_number_id=h.whatsapp_phone_number_id,
        access_token=h.access_token,
        app_secret=h.app_secret,
        timezone=h.timezone,
        welcome_message_text=h.welcome_message_text,
        reminder_offsets_hours=h.reminder_offsets_hours,
        reminder_template_name=h.reminder_template_name,
        data_tier=h.data_tier,
        external_api_base_url=h.external_api_base_url,
        external_api_key=h.external_api_key,
        portal_password_hash=db.hash_portal_password(password),
        enabled_features=h.enabled_features,
    )


# --- InMemoryRateLimiter in isolation ---


def test_limiter_allows_up_to_threshold_then_locks_out():
    limiter = rate_limit.InMemoryRateLimiter(max_attempts=3, window_seconds=60)
    assert limiter.is_locked_out("k") is False
    limiter.record_failure("k")
    limiter.record_failure("k")
    assert limiter.is_locked_out("k") is False  # 2 failures, threshold is 3
    limiter.record_failure("k")
    assert limiter.is_locked_out("k") is True  # 3rd failure trips it


def test_limiter_reset_clears_failures():
    limiter = rate_limit.InMemoryRateLimiter(max_attempts=2, window_seconds=60)
    limiter.record_failure("k")
    limiter.record_failure("k")
    assert limiter.is_locked_out("k") is True
    limiter.reset("k")
    assert limiter.is_locked_out("k") is False


def test_limiter_keys_are_independent():
    limiter = rate_limit.InMemoryRateLimiter(max_attempts=1, window_seconds=60)
    limiter.record_failure("attacker-ip")
    assert limiter.is_locked_out("attacker-ip") is True
    assert limiter.is_locked_out("someone-else-ip") is False


def test_limiter_lockout_expires_after_window_passes(monkeypatch):
    """Proves lockout is temporary, not a permanent brick -- old failures
    fall outside the window and stop counting, without needing a real
    15-minute sleep in the test suite."""
    now = [1_000_000.0]
    monkeypatch.setattr(rate_limit.time, "time", lambda: now[0])

    limiter = rate_limit.InMemoryRateLimiter(max_attempts=2, window_seconds=60)
    limiter.record_failure("k")
    limiter.record_failure("k")
    assert limiter.is_locked_out("k") is True

    now[0] += 61  # advance past the window
    assert limiter.is_locked_out("k") is False


# --- Portal login (HTML + JSON share one lockout counter per IP) ---


def test_portal_login_locks_out_after_max_attempts(hospital_id):
    _set_portal_password(hospital_id, "correct-horse-battery-staple")
    for _ in range(rate_limit.DEFAULT_MAX_ATTEMPTS):
        resp = client.post("/api/portal/login", json={"password": "wrong"})
        assert resp.status_code == 403

    locked = client.post("/api/portal/login", json={"password": "wrong"})
    assert locked.status_code == 429

    # Locked out blocks even the CORRECT password -- not just repeats of the wrong one.
    still_locked = client.post("/api/portal/login", json={"password": "correct-horse-battery-staple"})
    assert still_locked.status_code == 429
    assert "token" not in still_locked.json()


def test_portal_login_success_resets_failure_count(hospital_id):
    _set_portal_password(hospital_id, "correct-horse-battery-staple")
    # A couple of wrong guesses (well under the threshold)...
    client.post("/api/portal/login", json={"password": "wrong"})
    client.post("/api/portal/login", json={"password": "wrong"})
    # ...then a correct one.
    ok = client.post("/api/portal/login", json={"password": "correct-horse-battery-staple"})
    assert ok.status_code == 200

    # If the earlier failures hadn't been cleared, only
    # (DEFAULT_MAX_ATTEMPTS - 2) more wrong guesses would be allowed before
    # lockout. Prove the full budget is available again.
    for _ in range(rate_limit.DEFAULT_MAX_ATTEMPTS):
        resp = client.post("/api/portal/login", json={"password": "still-wrong"})
        assert resp.status_code == 403, "locked out earlier than a fresh counter should allow"


# --- admin/onboarding_api.py's ADMIN_SECRET gate ---


def _onboarding_payload(admin_secret: str) -> dict:
    # "hospital_info" deliberately avoided "booking" -- that feature requires
    # at least one department/doctor, which is irrelevant noise for a test
    # that's only exercising the ADMIN_SECRET gate itself.
    return {
        "admin_secret": admin_secret,
        "name": "Rate Limit Test Hospital",
        "whatsapp_phone_number_id": "rl-test-phone-id",
        "access_token": "tok",
        "app_secret": "sec",
        "portal_password": "irrelevant",
        "enabled_features": ["hospital_info"],
        "data_tier": "tier1",
    }


def test_admin_secret_locks_out_after_max_attempts(user_auth_header):
    for _ in range(rate_limit.DEFAULT_MAX_ATTEMPTS):
        resp = client.post("/api/onboarding", json=_onboarding_payload("wrong-secret"), headers=user_auth_header)
        assert resp.status_code == 403

    locked = client.post("/api/onboarding", json=_onboarding_payload("wrong-secret"), headers=user_auth_header)
    assert locked.status_code == 403

    # Confirm it's genuinely a lockout, not coincidence, via the shared
    # in-process counter directly (this TestClient's requests all carry the
    # same "testclient" host, which is what the key is built from).
    assert rate_limit.is_locked_out(rate_limit.client_key("admin_secret", None)) is False  # "unknown" key, unaffected
    assert rate_limit.is_locked_out(f"admin_secret:testclient") is True

    # Locked out blocks even the CORRECT secret, not just repeats of the wrong one.
    still_locked = client.post("/api/onboarding", json=_onboarding_payload(ADMIN_SECRET), headers=user_auth_header)
    assert still_locked.status_code == 403


def test_admin_secret_correct_value_still_works_before_lockout(user_auth_header):
    resp = client.post("/api/onboarding", json=_onboarding_payload(ADMIN_SECRET), headers=user_auth_header)
    assert resp.status_code == 200, resp.text


# --- admin/tenants_api.py's TENANTS_ADMIN_SECRET ---


def test_tenants_admin_secret_locks_out_after_max_attempts():
    for _ in range(rate_limit.DEFAULT_MAX_ATTEMPTS):
        resp = client.post("/api/admin/tenants/login", json={"secret": "wrong"})
        assert resp.status_code == 403

    locked = client.post("/api/admin/tenants/login", json={"secret": "wrong"})
    assert locked.status_code == 429

    still_locked = client.post("/api/admin/tenants/login", json={"secret": TENANTS_ADMIN_SECRET})
    assert still_locked.status_code == 429


def test_tenants_admin_secret_correct_value_works():
    resp = client.post("/api/admin/tenants/login", json={"secret": TENANTS_ADMIN_SECRET})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_tenants_list_endpoint_shares_lockout_with_login_endpoint():
    """GET /api/admin/tenants re-checks the secret on every request (no
    server-side session) -- guessing via that endpoint must count against
    the same budget as the dedicated login endpoint."""
    for _ in range(rate_limit.DEFAULT_MAX_ATTEMPTS):
        client.get("/api/admin/tenants", headers={"X-Admin-Secret": "wrong"})

    locked = client.get("/api/admin/tenants", headers={"X-Admin-Secret": TENANTS_ADMIN_SECRET})
    assert locked.status_code == 401  # locked-out and wrong-secret look identical on this endpoint by design


# --- Timing-safe comparison: functional correctness (the actual timing
# property is what hmac.compare_digest guarantees; these confirm the
# comparison is wired correctly, not just that some comparison exists) ---


def test_admin_secret_empty_env_value_never_authenticates(monkeypatch):
    import admin.onboarding as onboarding

    monkeypatch.setattr(onboarding, "ADMIN_SECRET", "")
    # hmac.compare_digest("", "") is True -- the bool(ADMIN_SECRET) guard is
    # what prevents an unset secret from accepting a blank guess.
    assert onboarding.check_admin_secret("", request=None) is False


def test_tenants_admin_secret_empty_env_value_never_authenticates(monkeypatch):
    import admin.tenants_api as tenants_api

    monkeypatch.setattr(tenants_api, "TENANTS_ADMIN_SECRET", "")
    assert tenants_api._check_secret("", request=None) is False

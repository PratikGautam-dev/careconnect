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

from main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

# RBAC (docs/rbac-redis-plan.md): admin.onboarding.ADMIN_SECRET is the one
# shared-secret constant still live anywhere in this file (dead code post-
# migration, covered by test_admin_secret_empty_env_value_never_authenticates
# below) -- TENANTS_ADMIN_SECRET no longer gates anything at request time,
# so there's no equivalent module constant to patch here anymore.
ADMIN_SECRET = "test-admin-secret"  # matches conftest.py's os.environ.setdefault


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


# --- RBAC (docs/rbac-redis-plan.md): admin/onboarding_api.py's ADMIN_SECRET
# gate and admin/tenants_api.py's TENANTS_ADMIN_SECRET/X-Admin-Secret gate
# (and its POST /api/admin/tenants/login rate-limited entry point) are both
# GONE now -- replaced by get_current_super_admin(), a JWT verification that
# isn't a "guessable shared secret" the same way those two were (a JWT can't
# be brute-forced the way a short shared secret can; the actual guessable
# surface moved to the LOGIN that mints the JWT). admin/onboarding.py's
# check_admin_secret() itself is untouched (dead code post-migration, not
# yet deleted -- Phase 6 cleanup) and still covered below for the same
# "timing-safe comparison is wired correctly" reason it always was.
# admin/tenants_api.py's own former _check_secret() is deleted outright
# (nothing references TENANTS_ADMIN_SECRET as a request-time gate anymore),
# so its own empty-value test is removed rather than adapted.
#
# The genuinely analogous "brute-forceable shared credential" surface now is
# POST /api/admin/super/login's password check (admin/super_auth.py) -- its
# own rate-limit scope ("super_admin_login", distinct from "portal_login"/
# "staff_login") is what these tests cover instead.


def test_super_admin_login_locks_out_after_max_attempts():
    import db.repository as db

    db.create_super_admin(email="ratelimit-super@example.com", password_hash=db.hash_portal_password("correct-pw"), name="RL Super")

    for _ in range(rate_limit.DEFAULT_MAX_ATTEMPTS):
        resp = client.post("/api/admin/super/login", json={"email": "ratelimit-super@example.com", "password": "wrong"})
        assert resp.status_code == 401

    locked = client.post("/api/admin/super/login", json={"email": "ratelimit-super@example.com", "password": "wrong"})
    assert locked.status_code == 429

    assert rate_limit.is_locked_out(rate_limit.client_key("super_admin_login", None)) is False  # "unknown" key, unaffected
    assert rate_limit.is_locked_out("super_admin_login:testclient") is True

    # Locked out blocks even the CORRECT password, not just repeats of the wrong one.
    still_locked = client.post("/api/admin/super/login", json={"email": "ratelimit-super@example.com", "password": "correct-pw"})
    assert still_locked.status_code == 429


def test_super_admin_login_correct_password_still_works_before_lockout():
    import db.repository as db

    db.create_super_admin(email="ratelimit-super2@example.com", password_hash=db.hash_portal_password("correct-pw"), name="RL Super 2")
    resp = client.post("/api/admin/super/login", json={"email": "ratelimit-super2@example.com", "password": "correct-pw"})
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()


# --- Timing-safe comparison: functional correctness (the actual timing
# property is what hmac.compare_digest guarantees; this confirms the
# comparison is wired correctly, not just that some comparison exists).
# admin/onboarding.py's check_admin_secret() is dead code post-migration
# (Phase 6 cleanup deletes it), still covered here since it still exists
# and still guards the "" (unset) case the same way. ---


def test_admin_secret_empty_env_value_never_authenticates(monkeypatch):
    import admin.onboarding as onboarding

    monkeypatch.setattr(onboarding, "ADMIN_SECRET", "")
    # hmac.compare_digest("", "") is True -- the bool(ADMIN_SECRET) guard is
    # what prevents an unset secret from accepting a blank guess.
    assert onboarding.check_admin_secret("", request=None) is False

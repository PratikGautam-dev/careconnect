import atexit
import os

import pytest

# Must be set before any test module's first `from core.main import app` (which
# transitively imports admin/onboarding.py) -- that module reads ADMIN_SECRET
# from the environment once, at import time, and Python only executes a module
# once per process. conftest.py is guaranteed to load before every test module
# in this directory, so this is the one place that setting can't lose a race
# against which test file pytest happens to collect first.
os.environ.setdefault("ADMIN_SECRET", "test-admin-secret")
# Section 15: same reasoning as ADMIN_SECRET above -- user_auth.py reads this
# at import time (core.main imports it), so it must be set before that
# first import too.
os.environ.setdefault("AUTH_SECRET", "test-auth-secret")
# Deliberately a different value from ADMIN_SECRET (admin/tenants_api.py's
# own module docstring: a leaked onboarding secret must not also gate the
# platform-admin tenant pages) -- same "must be set before core.main's
# first import" reasoning.
os.environ.setdefault("TENANTS_ADMIN_SECRET", "test-tenants-admin-secret")
# RBAC (docs/rbac-redis-plan.md): unlike REDIS_URL/DATABASE_URL, JWT_SECRET/
# SUPER_ADMIN_JWT_SECRET ARE read live per call (auth/jwt_session.py's
# _secret_for(), never cached at import time) -- set here anyway, same place
# as every other secret above, purely for consistency; nothing actually
# depends on these being set before first import the way ADMIN_SECRET does.
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SUPER_ADMIN_JWT_SECRET", "test-super-admin-jwt-secret")

# SPEC Section 6/12.6: the app moved off SQLite onto Postgres (Neon), so tests
# need a real Postgres to run against -- an in-memory swap-in-a-connection
# trick (the old sqlite3.connect(":memory:") fixture) has no Postgres
# equivalent. Two ways to provide that Postgres, both supported here:
#
#   1. testcontainers (default, no setup required) -- provisions a throwaway
#      Postgres container automatically via the local Docker daemon. Chosen
#      as the default because it reproduces what the old in-memory fixture
#      gave every contributor for free: `pytest` just works on a fresh clone,
#      with no manual "go install/configure Postgres yourself" step, on any
#      machine or CI runner that already has Docker (which this project's
#      Docker-based deploy path assumes anyway).
#   2. TEST_DATABASE_URL env var -- if set, tests connect directly to that
#      Postgres instead (a free-tier Neon branch, a local install, or a CI
#      "services:" container) and testcontainers is never imported/started.
#      Use this where Docker-in-Docker isn't available/wanted, or to test
#      against the exact same Postgres version/provider (Neon) production uses.
#
# This has to happen at module level (not inside a fixture) and set the real
# DATABASE_URL env var: core/main.py calls db.init_db.init_db() at *import*
# time (before any pytest fixture runs), and that reads DATABASE_URL via
# db.connection.get_database_url() -- so it must already be set the moment
# the first test file does `from core.main import app`, which can happen
# during collection, before any fixture below has had a chance to run.
_test_database_url = os.environ.get("TEST_DATABASE_URL")
if not _test_database_url:
    from testcontainers.community.postgres import PostgresContainer

    _pg_container = PostgresContainer("postgres:16-alpine")
    _pg_container.start()
    atexit.register(_pg_container.stop)
    _test_database_url = _pg_container.get_connection_url(driver=None)

os.environ["DATABASE_URL"] = _test_database_url

import db.connection as db_connection
from db.init_db import init_db_on_connection
from db.seed import seed_test_hospital


@pytest.fixture(autouse=True)
def _fresh_rate_limiter():
    """Login/secret-check rate limiting (core/rate_limit.py) is a module-level
    singleton, same reason core/session_store.py's session store is -- real request
    handling needs failure counts to persist across requests. Tests need the
    opposite: a clean slate per test, same role this file's _fresh_test_db
    fixture plays for the database, so one test's lockout never bleeds into
    the next."""
    import core.rate_limit as rate_limit

    rate_limit.reset_all_for_tests()
    yield
    rate_limit.reset_all_for_tests()


@pytest.fixture(autouse=True)
def _fresh_rbac_caches():
    """RBAC (docs/rbac-redis-plan.md): portal/permission_cache.py's
    _LOCAL_CACHE and auth/refresh_tokens.py's in-memory fallback store are
    both module-level singletons keyed by hospital_id/staff_id -- and
    _fresh_test_db below recreates the schema (so hospital ids like 1/2
    get REUSED across tests) without touching either of these process-wide
    caches. Left alone, a permission matrix or refresh token cached/issued
    by one test would leak into the next test that happens to get the same
    id, the same class of cross-test bleed core/rate_limit.py's own
    _fresh_rate_limiter fixture already exists to prevent for that module."""
    import auth.refresh_tokens as refresh_tokens
    import portal.permission_cache as permission_cache

    permission_cache.reset_for_tests()
    refresh_tokens.reset_for_tests()
    yield
    permission_cache.reset_for_tests()
    refresh_tokens.reset_for_tests()


@pytest.fixture(autouse=True)
def _fresh_test_db():
    """
    Fresh Postgres schema per test (SPEC Section 12.6 Tier 1, now Postgres/Neon
    per Section 6) -- DROP/CREATE SCHEMA public gives every test the same
    "nothing pre-exists" starting point the old sqlite3.connect(":memory:")
    fixture gave for free, since a real Postgres instance can't be recreated
    from scratch anywhere near as cheaply as an in-memory SQLite file could.

    Also seeds a second, entirely fake hospital (SPEC Section 12.2/Phase 9) —
    present in every test's DB so multi-tenant isolation tests don't each need
    to seed it themselves, but never seeded in a real deployment (only this
    fixture calls seed_test_hospital(), not db/init_db.py's production path).
    """
    conn = db_connection._connect(_test_database_url)
    conn.execute("DROP SCHEMA public CASCADE")
    conn.execute("CREATE SCHEMA public")
    seeded_hospital_id = init_db_on_connection(conn)
    second_hospital_id = seed_test_hospital(conn)
    db_connection.set_connection(conn)
    # Groundwork for the SQLAlchemy ORM migration (no repository reads
    # through get_session() yet): discards any session left over from a
    # previous test so the next get_session() call lazily creates one bound
    # to THIS test's just-recreated schema, not a stale one referencing
    # tables that no longer exist after the DROP SCHEMA above.
    db_connection.reset_session()
    yield seeded_hospital_id, second_hospital_id
    db_connection.reset_connection()
    db_connection.reset_session()


@pytest.fixture
def hospital_id(_fresh_test_db):
    """The id of the one 'real' hospital seeded into this test's fresh database."""
    return _fresh_test_db[0]


@pytest.fixture
def second_hospital_id(_fresh_test_db):
    """The id of the second, fake hospital seeded purely for isolation tests."""
    return _fresh_test_db[1]


@pytest.fixture
def user_auth_header(_fresh_test_db):
    """Section 15: a real signed-in Google-account user, for tests hitting
    endpoints that require one (POST /api/onboarding, /api/auth/*) --
    creates a real users row (not a mock) and signs a real user-session
    token the exact way user_auth.py's OAuth callback does, so these tests
    exercise the same _verify_user_session() path a real request would."""
    import time

    import db.repository as db
    from auth.google_oauth import _sign_user_session

    user = db.create_user(email="test-owner@example.com", google_id="google-test-id", name="Test Owner")
    token = _sign_user_session(user.id, int(time.time()) + 3600)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def super_admin_token(_fresh_test_db):
    """RBAC (docs/rbac-redis-plan.md): a real super_admins row + a real
    typ='super_admin' JWT, the get_current_super_admin() replacement for
    every test that used to send a bare X-Admin-Secret/TENANTS_ADMIN_SECRET
    header. Returns the raw token string (not a headers dict) since
    admin/onboarding_api.py's submit_onboarding() needs it as a PLAIN
    payload field (payload.super_admin_token), not an Authorization header
    -- see that endpoint's own docstring for why; every other super-admin-
    gated route uses super_admin_headers below instead."""
    import db.repository as db
    from auth.jwt_session import issue_access_token

    super_admin = db.create_super_admin(
        email="super-admin@example.com", password_hash=db.hash_portal_password("irrelevant"), name="Test Super Admin",
    )
    return issue_access_token(
        super_admin["id"], hospital_id=None, role="super_admin",
        token_version=super_admin["token_version"], typ="super_admin",
    )


@pytest.fixture
def super_admin_headers(super_admin_token):
    """The Authorization-header form of super_admin_token above, for every
    get_current_super_admin()-gated route EXCEPT /api/onboarding (which
    needs the bare token in the request body -- see super_admin_token's own
    docstring)."""
    return {"Authorization": f"Bearer {super_admin_token}"}

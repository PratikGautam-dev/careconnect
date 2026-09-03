# core/config.py
"""
ARCHITECTURE_PLAN.md Phase 0: one centralized place for process-level env
vars (secrets, tokens, S3/R2 creds, WhatsApp API base identifiers), instead
of each module doing its own `os.environ.get(...)` at import time. Per-tenant
config (menu labels, feature toggles, credentials-per-hospital) lives in the
`hospitals` DB table and is untouched by this file -- see `db/repository.py`.

Deliberately does NOT cover DATABASE_URL, or REDIS_URL for any of the SIX
existing hand-rolled call sites (core/chat_history.py's get_history(),
core/session_store.py's get_session_store(), core/rate_limit.py's
_build_limiter(), webhook/dispatch.py's _get_redis(), modules/booking/calendar.py's
_get_redis(), auth/refresh_tokens.py's _build_store(), db/connection.py's
get_database_url() -- that's seven, including DATABASE_URL). Each already
has a "read live, connect, fall back if unreachable" pattern re-checked on
every call, and several tests exercise that via `monkeypatch.delenv` --
freezing either into a singleton at import time would silently break that
live re-check. Leave those exactly as direct os.environ reads where they are.
main.py is NOT one of these -- its own Redis usage already goes through
core/redis_client.py's get_redis(), not a hand-rolled copy.

REDIS_URL below is the ONE exception, added for core/redis_client.py's
get_redis() specifically -- that function calls get_settings().REDIS_URL
fresh on every invocation (never caches the value at import time the way
PORTAL_SECRET/DOCTOR_SECRET below do), so it preserves the exact same live-
read-per-call semantics os.environ.get() would have given it, without
actually reintroducing the frozen-singleton risk this docstring warns about.
Not retrofitted onto the six sites above -- this is scoped to redis_client.py
alone, by request, not a signal to migrate the others.

No cached module-level `settings` singleton, deliberately: several of the
values below (WHATSAPP_VERIFY_TOKEN especially) were previously read at each
CONSUMING module's own import time (`core/main.py`'s `os.environ[...]`),
and this project's test suite already has undocumented ordering dependencies
on exactly that -- e.g. tests/test_create_appointment_transaction_safety.py
sets WHATSAPP_VERIFY_TOKEN via os.environ.setdefault() at its own module top,
relying on alphabetical pytest collection order to run before other test
files import core.main. A single shared Settings() instance built once at
THIS module's first import (which could be triggered earlier, by any of the
several other modules that import this file) would freeze that value before
such a setdefault() runs, silently breaking that ordering. get_settings()
below re-reads env on every call instead, so each consumer still effectively
gets a "read live at my own import time" value, exactly like before.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Optional here even though core/main.py requires it -- db/init_db.py
    # also imports this module (for HOSPITAL_NAME etc. below) but never
    # touches WHATSAPP_VERIFY_TOKEN, including its standalone `python -m
    # db.init_db` entry point, which must keep working without this set.
    # core/main.py enforces "required" itself, same place the old
    # `os.environ["WHATSAPP_VERIFY_TOKEN"]` KeyError used to fire.
    WHATSAPP_VERIFY_TOKEN: str | None = None

    INTERNAL_SECRET: str = ""
    ADMIN_SECRET: str = ""
    TENANTS_ADMIN_SECRET: str = ""
    PORTAL_SECRET: str = ""
    AUTH_SECRET: str = ""
    # Dedicated doctor-login session token (auth/doctor_session.py) -- its own
    # secret, not PORTAL_SECRET/AUTH_SECRET, same "a leaked secret should only
    # forge the one thing it's for" reasoning ADMIN_SECRET vs
    # TENANTS_ADMIN_SECRET and PORTAL_SECRET vs AUTH_SECRET already apply: a
    # leaked PORTAL_SECRET must not also forge a doctor-scoped token, and vice
    # versa.
    DOCTOR_SECRET: str = ""
    # RBAC (docs/rbac-redis-plan.md): staff JWT access tokens (auth/jwt_session.py)
    # and super-admin JWT access tokens are signed with SEPARATE secrets, same
    # "a leaked secret should only forge the one thing it's for" precedent
    # DOCTOR_SECRET vs PORTAL_SECRET already established -- a leaked JWT_SECRET
    # must never be usable to forge a super-admin token (full platform access),
    # and vice versa.
    JWT_SECRET: str = ""
    SUPER_ADMIN_JWT_SECRET: str = ""
    # See this module's own docstring above -- the one exception to "REDIS_URL
    # isn't covered here", scoped to core/redis_client.py's get_redis() alone.
    REDIS_URL: str | None = None
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    # Google Meet integration (alongside the existing Jitsi tele-consultation
    # link, not replacing it) -- a SEPARATE OAuth client from GOOGLE_CLIENT_ID/
    # SECRET above (confirmed with the user), since that one resolves hospital-
    # owner sign-in identity and must never carry the Calendar scope. All three
    # default to "" like every other optional secret in this file: the app
    # boots cleanly with them unset (core/crypto.py, auth/google_calendar_oauth.py,
    # modules/google_calendar.py all check for empty/missing explicitly at the
    # point of use and degrade to a clean error/fallback, never a crash).
    GOOGLE_CALENDAR_CLIENT_ID: str = ""
    GOOGLE_CALENDAR_CLIENT_SECRET: str = ""
    # Fernet key (44-char urlsafe-base64, e.g. Fernet.generate_key()) encrypting
    # google_calendar_connections' stored access/refresh tokens at rest -- see
    # core/crypto.py. Unset means the feature is simply unconfigured, not a
    # crash: nothing decrypts anything until a doctor actually connects, which
    # itself is blocked with a clean error until this is set.
    CALENDAR_TOKEN_ENCRYPTION_KEY: str = ""

    # core/storage.py -- omit S3_BUCKET and uploads fall back to local disk.
    S3_BUCKET: str | None = None
    S3_REGION: str | None = None
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    LOCAL_STORAGE_DIR: str = "local_storage"

    # db/init_db.py -- seeds the one real hospital's row from these on first
    # startup only; every later change goes through the portal, not .env.
    HOSPITAL_NAME: str = "Default Hospital"
    WHATSAPP_PHONE_NUMBER_ID: str | None = None
    WHATSAPP_ACCESS_TOKEN: str | None = None
    WHATSAPP_APP_SECRET: str | None = None


def get_settings() -> Settings:
    """Uncached -- see the module docstring for why. Cheap enough (env-var
    lookups + pydantic validation) that each consuming module calling this
    once, at its own import time, has no meaningful cost."""
    return Settings()

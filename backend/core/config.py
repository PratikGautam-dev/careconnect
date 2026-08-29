# core/config.py
"""
ARCHITECTURE_PLAN.md Phase 0: one centralized place for process-level env
vars (secrets, tokens, S3/R2 creds, WhatsApp API base identifiers), instead
of each module doing its own `os.environ.get(...)` at import time. Per-tenant
config (menu labels, feature toggles, credentials-per-hospital) lives in the
`hospitals` DB table and is untouched by this file -- see `db/repository.py`.

Deliberately does NOT cover REDIS_URL or DATABASE_URL. Both already have a
"read live, connect, fall back if unreachable" pattern re-checked on every
call (core/chat_history.py's get_history(), core/session_store.py's get_session_store(), core/rate_limit.py's
_build_limiter(), core/main.py's _get_redis(), db/connection.py's
get_database_url()) that several tests exercise via `monkeypatch.delenv` --
freezing either into a singleton at import time would silently break that
live re-check. Leave those exactly as direct os.environ reads where they are.

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
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    FRONTEND_ORIGIN: str = "http://localhost:3000"

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

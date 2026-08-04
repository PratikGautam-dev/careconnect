# db/init_db.py
"""
Creates the schema (db/schema.sql, SPEC Section 4) and seeds the default
hospital (db/seed.py). Safe to re-run — every CREATE is IF NOT EXISTS and
seed_default_hospital() no-ops if that hospital already exists.

Run directly to set up (or update) the on-disk database:
    python -m db.init_db
core/main.py also calls init_db() once at startup, so a fresh clone works
without a manual step.
"""
import os
import re
from pathlib import Path

from db import seed
from db.connection import get_connection, get_database_url

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _backfill_enabled_features(conn) -> None:
    """SPEC Section 14.5: one-time, idempotent backfill for any hospital row
    with enabled_features still NULL (created before this column existed, or
    seeded by seed.py's explicit column lists, which don't set it directly).
    Only ever touches NULL rows, so re-running this on every startup is safe
    and never overwrites a real tenant's own later choices. 'booking' rows
    get EXACTLY the old flow_type='booking' main menu, item for item: Book
    Appointment, Reschedule, Cancel, and the static "FAQ" button (which just
    sent hospital-info text -- now the "hospital_info" feature) -- true
    behavior parity, no new capability silently switched on for an existing
    tenant. 'faq' rows get just ["faq"]; anything else (a flow_type this
    migration doesn't recognize) gets an empty set rather than guessing."""
    conn.execute(
        "UPDATE hospitals SET enabled_features = ? "
        "WHERE enabled_features IS NULL AND flow_type = 'booking'",
        ('["booking","reschedule","cancel","hospital_info"]',),
    )
    conn.execute(
        "UPDATE hospitals SET enabled_features = ? WHERE enabled_features IS NULL AND flow_type = 'faq'",
        ('["faq"]',),
    )
    conn.execute("UPDATE hospitals SET enabled_features = '[]' WHERE enabled_features IS NULL")
    conn.commit()


def init_db_on_connection(conn) -> int:
    """Apply schema + seed data to an already-open connection. Used directly by
    tests (against an in-memory DB) and internally by init_db() below."""
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    hospital_name = os.environ.get("HOSPITAL_NAME", "Default Hospital")
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    # Populating these from .env keeps the one real hospital's row usable for
    # per-message routing (SPEC Section 12.2/Phase 9) without requiring a manual
    # DB edit — core/main.py no longer reads WHATSAPP_ACCESS_TOKEN directly.
    access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    app_secret = os.environ.get("WHATSAPP_APP_SECRET")
    hospital_id = seed.seed_default_hospital(
        conn, hospital_name=hospital_name, whatsapp_phone_number_id=phone_number_id,
        access_token=access_token, app_secret=app_secret,
    )
    conn.commit()
    _backfill_enabled_features(conn)
    return hospital_id


def init_db() -> int:
    """
    Initializes whichever connection db.connection.get_connection() resolves to
    — the Postgres database at DATABASE_URL. Deliberately reuses that same
    shared connection (rather than opening + closing its own) so init_db() and
    every db/repository.py call afterward operate against the exact same
    connection object.
    Returns the seeded hospital's id.
    """
    conn = get_connection()
    return init_db_on_connection(conn)


def _redact_credentials(database_url: str) -> str:
    """Never print a password to stdout, even in a diagnostic CLI message --
    someone pasting this output into a bug report/Slack thread is the
    realistic leak vector, not an attacker with a debugger."""
    return re.sub(r"//([^:/@]+):[^@]*@", r"//\1:***@", database_url)


if __name__ == "__main__":
    seeded_hospital_id = init_db()
    print(f"Database initialized at {_redact_credentials(get_database_url())} (hospital_id={seeded_hospital_id})")

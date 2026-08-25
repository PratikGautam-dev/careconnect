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
import re
from pathlib import Path

from core.config import get_settings
from db import seed
from db.connection import get_connection, get_database_url
from db.repository import _generate_patient_display_id

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


def _backfill_patients(conn) -> None:
    """SPEC Section 12.9: patients was always in Section 4's original data
    model but never actually built until staff-side patient SEARCH (by name,
    not just phone) needed somewhere to store one. Every distinct
    (hospital_id, phone) pair already sitting in appointments gets a row here
    (name NULL -- WhatsApp bookings never collected one) so existing patients
    are searchable by phone immediately, without waiting for their next
    booking to (re-)upsert them.

    Patient identity SEPARATION (Spec.md Section 0) dropped patients'
    UNIQUE(hospital_id, phone) constraint (multiple profiles per phone are
    now allowed), so the ON CONFLICT (hospital_id, phone) DO NOTHING this
    used to rely on no longer has a matching unique index to target --
    switched to the same WHERE NOT EXISTS idiom every other backfill in this
    file already uses. Behaviorally identical: still only ever ADDS a row
    for a (hospital_id, phone) with zero existing patients rows, never
    touches one that already exists (so it can never clobber a name staff
    already filled in, and never creates a 2nd row for a phone this backfill
    already covered on an earlier startup)."""
    conn.execute(
        "INSERT INTO patients (hospital_id, phone) "
        "SELECT DISTINCT a.hospital_id, a.phone FROM appointments a "
        "WHERE NOT EXISTS (SELECT 1 FROM patients p WHERE p.hospital_id = a.hospital_id AND p.phone = a.phone)"
    )
    conn.commit()


def _backfill_appointment_patient_denorm(conn) -> None:
    """Item 8 (Spec.md Section 0): appointments.patient_id/patient_name/
    patient_phone are populated going forward by create_appointment() itself
    -- this is the one-time catch-up for every row that predates those
    columns. Only ever touches rows where patient_id IS NULL, so re-running
    on every startup is a safe no-op once caught up, and it can never
    overwrite a value create_appointment() already set correctly."""
    conn.execute(
        "UPDATE appointments a SET patient_id = p.id, patient_name = p.name, patient_phone = a.phone "
        "FROM patients p WHERE p.hospital_id = a.hospital_id AND p.phone = a.phone AND a.patient_id IS NULL"
    )
    conn.commit()


def _backfill_appointment_patient_age(conn) -> None:
    """Family/multi-person-booking follow-up (Spec.md Section 0):
    appointments.patient_age is populated going forward by
    create_appointment() itself -- catches up every row that predates that
    column, from the (single, mutable) patients.age value, same
    best-effort approximation the column's own docstring already flags.
    Gated on a.patient_age IS NULL specifically (not reusing the patient_id
    gate above) since a row can already have patient_id/patient_name set
    from an earlier startup's run of the backfill above, before this
    column existed -- that gate alone would skip it here."""
    conn.execute(
        "UPDATE appointments a SET patient_age = p.age "
        "FROM patients p WHERE p.hospital_id = a.hospital_id AND p.phone = a.phone AND a.patient_age IS NULL"
    )
    conn.commit()


def _backfill_patient_display_ids(conn) -> None:
    """Patient identity system (Spec.md Section 0): every patient created
    before this feature existed has patient_display_id still NULL --
    assigned here, in CREATION ORDER per hospital (created_at, then id as a
    tiebreak for same-instant rows), via the exact same
    _generate_patient_display_id() (short-code derivation + the
    patient_id_counters atomic sequence) that create_appointment()'s
    _upsert_patient() uses for every NEW patient going forward -- so the
    counter this backfill leaves behind is exactly where the next real
    patient's id continues from, no gap or collision. Only ever touches
    patient_display_id IS NULL rows, so re-running this on every startup is
    a safe no-op once every hospital is caught up (each hospital's counter
    only advances while there's still a NULL row left for it)."""
    hospital_ids = [
        row["hospital_id"] for row in conn.execute(
            "SELECT DISTINCT hospital_id FROM patients WHERE patient_display_id IS NULL ORDER BY hospital_id"
        ).fetchall()
    ]
    for hospital_id in hospital_ids:
        patient_ids = [
            row["id"] for row in conn.execute(
                "SELECT id FROM patients WHERE hospital_id = ? AND patient_display_id IS NULL "
                "ORDER BY created_at, id",
                (hospital_id,),
            ).fetchall()
        ]
        for patient_id in patient_ids:
            display_id = _generate_patient_display_id(conn, hospital_id)
            conn.execute("UPDATE patients SET patient_display_id = ? WHERE id = ?", (display_id, patient_id))
    conn.commit()


def _backfill_patient_links(conn) -> None:
    """Patient identity SEPARATION (Spec.md Section 0): every `patients` row
    that predates this feature (i.e. every one that currently exists, since
    this migration ships alongside the feature itself) gets exactly one
    patient_links row, relationship_label='Self' -- the implicit "this is the
    phone's own profile" link every pre-existing patient already had, just
    never modeled explicitly. `linked_at` is backdated to the patient's own
    `created_at` rather than "now" -- preserves the real historical ordering
    get_active_patients_for_phone() sorts by, in case a phone somehow already
    had more than one `patients` row before this ran (shouldn't happen given
    the old UNIQUE(hospital_id, phone) constraint, but this keeps the
    backfill correct even in that edge case rather than assuming it away).

    Gated on NOT EXISTS (one link per patient, not per phone -- a patient
    with two links from a bad prior run would break this gate, but nothing
    in this codebase ever creates more than one link per patient), so
    re-running this on every startup is a safe no-op once every existing
    patient is linked. Does not touch `patients` or `appointments` at all --
    purely additive rows in the new table, zero risk to existing booking
    history or Patient IDs."""
    conn.execute(
        "INSERT INTO patient_links (hospital_id, whatsapp_phone, patient_id, relationship_label, linked_at) "
        "SELECT p.hospital_id, p.phone, p.id, 'Self', p.created_at FROM patients p "
        "WHERE NOT EXISTS (SELECT 1 FROM patient_links pl WHERE pl.patient_id = p.id)"
    )
    conn.commit()


def _backfill_reports_prescriptions_feature(conn) -> None:
    """CareConnect architecture doc alignment (Spec.md Section 0): "my_details"
    renamed to "reports_prescriptions" (Section 20's exact menu item) --
    the underlying implementation is unchanged, just the feature KEY.
    Plain string REPLACE on the raw JSON-encoded TEXT columns (both
    enabled_features, a JSON array member, and feature_labels, a JSON
    object key) is correct here specifically because "my_details" only
    ever appears as a full quoted JSON string/key, never as a substring of
    anything else -- and is naturally idempotent, since the WHERE clause
    finds nothing left to touch on a second run once every hospital's
    already been converted."""
    # %% (not %) -- db/connection.py's execute() always passes a params
    # tuple to psycopg2, which treats a bare % in the query as the start of
    # its own substitution syntax even with nothing to substitute.
    conn.execute(
        "UPDATE hospitals SET enabled_features = REPLACE(enabled_features, '\"my_details\"', '\"reports_prescriptions\"') "
        "WHERE enabled_features LIKE '%%my_details%%'"
    )
    conn.execute(
        "UPDATE hospitals SET feature_labels = REPLACE(feature_labels, '\"my_details\"', '\"reports_prescriptions\"') "
        "WHERE feature_labels LIKE '%%my_details%%'"
    )
    conn.commit()


def _backfill_handoff_messages(conn) -> None:
    """Handoff two-way threading follow-up (Spec.md Section 0): every
    pre-existing handoff_requests row's own message_text becomes that
    thread's first inbound handoff_messages row, so get_handoff_messages()
    (the portal's single source of truth for the chat thread) isn't empty
    for a handoff that predates this table. Only ever touches a
    handoff_requests row with zero handoff_messages rows yet, so this is a
    safe no-op to re-run on every startup once caught up."""
    conn.execute(
        "INSERT INTO handoff_messages (hospital_id, handoff_request_id, direction, message_text, created_at) "
        "SELECT hr.hospital_id, hr.id, 'inbound', hr.message_text, hr.created_at "
        "FROM handoff_requests hr "
        "WHERE hr.message_text IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM handoff_messages hm WHERE hm.handoff_request_id = hr.id)"
    )
    conn.commit()


def init_db_on_connection(conn) -> int:
    """Apply schema + seed data to an already-open connection. Used directly by
    tests (against an in-memory DB) and internally by init_db() below."""
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    _settings = get_settings()
    hospital_name = _settings.HOSPITAL_NAME
    phone_number_id = _settings.WHATSAPP_PHONE_NUMBER_ID
    # Populating these from .env keeps the one real hospital's row usable for
    # per-message routing (SPEC Section 12.2/Phase 9) without requiring a manual
    # DB edit — core/main.py no longer reads WHATSAPP_ACCESS_TOKEN directly.
    access_token = _settings.WHATSAPP_ACCESS_TOKEN
    app_secret = _settings.WHATSAPP_APP_SECRET
    hospital_id = seed.seed_default_hospital(
        conn, hospital_name=hospital_name, whatsapp_phone_number_id=phone_number_id,
        access_token=access_token, app_secret=app_secret,
    )
    conn.commit()
    _backfill_enabled_features(conn)
    _backfill_patients(conn)
    _backfill_appointment_patient_denorm(conn)
    _backfill_appointment_patient_age(conn)
    _backfill_patient_display_ids(conn)
    _backfill_patient_links(conn)
    _backfill_reports_prescriptions_feature(conn)
    _backfill_handoff_messages(conn)
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

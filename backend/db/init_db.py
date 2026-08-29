# db/init_db.py
"""
Creates the schema (SPEC Section 4 -- see db/migrations/versions/
0001_baseline_schema.py's frozen SQL, or db/schema.sql for the same content
kept as a human-readable, no-longer-executed reference) and seeds the default
hospital (db/seed.py). Safe to re-run — every CREATE is IF NOT EXISTS and
seed_default_hospital() no-ops if that hospital already exists.

Run directly to set up (or update) the on-disk database:
    python -m db.init_db
core/main.py also calls init_db() once at startup, so a fresh clone works
without a manual step.
"""
import importlib
import re
from pathlib import Path

from alembic import command
from alembic.config import Config

from core.config import get_settings
from db import seed
from db.connection import get_connection, get_database_url
from db.display_ids import CARE_CONNECT_ACCOUNT_PREFIX, GLOBAL_SCOPE_KEY, generate_yearly_display_id_conn
from db.repositories.accounts import _get_or_create_account_in_conn
from db.repositories.appointment_types import DEFAULT_APPOINTMENT_TYPES, default_is_active
from db.repositories.daycare_duration_options import DEFAULT_DAYCARE_DURATION_OPTIONS
from db.models import DEFAULT_MAX_ACTIVE_PATIENT_LINKS
from db.repository import _generate_patient_identifiers, _get_or_create_hospital_short_code

# SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
_ALEMBIC_INI_PATH = Path(__file__).resolve().parent.parent / "alembic.ini"

# db/schema.sql is retired as a runtime dependency -- kept on disk purely as
# a human-readable reference (SPEC Section 4's own schema documentation).
# db/migrations/versions/0001_baseline_schema.py's _BASELINE_SQL is a frozen,
# byte-for-byte snapshot of it taken at the moment Alembic was adopted, and is
# now the actual source this module applies -- importlib, not a normal
# `import`, because "0001_baseline_schema" isn't a valid Python identifier.
_baseline_schema = importlib.import_module("db.migrations.versions.0001_baseline_schema")


def run_alembic_migrations() -> None:
    """Establishes schema version tracking (alembic_version table) going
    forward -- production/dev only, deliberately NOT called by
    init_db_on_connection() below, so the per-test fixture in
    tests/conftest.py (which calls init_db_on_connection() directly, hundreds
    of times per run) is completely unaffected by this addition.

    Safe to run every time this process starts, including against a database
    the baseline schema is already fully applied to: migration 0001
    (db/migrations/versions/0001_baseline_schema.py) is entirely IF NOT
    EXISTS/IF EXISTS-guarded, so replaying it is a verified no-op.
    init_db_on_connection() below still separately applies that same frozen
    baseline SQL too, for the same reason -- redundant but harmless."""
    alembic_cfg = Config(str(_ALEMBIC_INI_PATH))
    # alembic.ini's script_location is the relative path "db/migrations",
    # which Alembic resolves against the process's CWD, not the ini file's
    # own directory -- overridden here to an absolute path so this works
    # regardless of where this process was started from (e.g. Docker's
    # CMD/WORKDIR, or `python -m db.init_db` run from an unexpected cwd).
    alembic_cfg.set_main_option("script_location", str(_ALEMBIC_INI_PATH.parent / "db" / "migrations"))
    command.upgrade(alembic_cfg, "head")


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
    before this feature existed has patient_display_id (and mrn) still
    NULL -- assigned here, in CREATION ORDER per hospital (created_at, then
    id as a tiebreak for same-instant rows), via the exact same
    _generate_patient_identifiers() (short-code derivation + the
    patient_id_counters atomic sequence) that create_appointment()'s
    _upsert_patient() uses for every NEW patient going forward -- so the
    counter this backfill leaves behind is exactly where the next real
    patient's id continues from, no gap or collision. Only ever touches
    patient_display_id IS NULL rows, so re-running this on every startup is
    a safe no-op once every hospital is caught up (each hospital's counter
    only advances while there's still a NULL row left for it). See
    _backfill_patient_mrns() below for the separate case of a patient that
    already has a patient_display_id but predates the mrn column."""
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
            display_id, mrn = _generate_patient_identifiers(conn, hospital_id)
            conn.execute(
                "UPDATE patients SET patient_display_id = ?, mrn = ? WHERE id = ?", (display_id, mrn, patient_id),
            )
    conn.commit()


def _backfill_patient_link_accounts(conn) -> None:
    """CareConnect account/identity layer (db/schema.sql's own comment on
    care_connect_accounts/whatsapp_identities): catches any patient_links
    row still missing a care_connect_account_id -- either a genuinely
    legacy row (from before this layer existed) or one from a startup that
    ran between this feature's rollout and this backfill catching up.
    _link_patient_under_cap() (db/repositories/patients.py) stamps every
    NEW row inline now, so this is a safety net, not the main write path --
    but it MUST run before the ALTER ... SET NOT NULL below, or that
    statement fails outright on any database with a row this hasn't caught
    yet (see migration 0002's own docstring for how that broke in prod).

    Deliberately collapses onto ONE shared account per distinct
    whatsapp_phone across ALL hospitals (not one per hospital) -- the
    account layer is global by design. provider_user_id is set to the
    phone itself -- the practical fallback since historical rows never
    captured a real WhatsApp wa_id distinct from the phone string. Gated on
    care_connect_account_id IS NULL, so re-running this on every startup is
    a safe no-op once every phone is caught up."""
    phones = [
        row["whatsapp_phone"] for row in conn.execute(
            "SELECT DISTINCT whatsapp_phone FROM patient_links WHERE care_connect_account_id IS NULL"
        ).fetchall()
    ]
    for phone in phones:
        account_row = conn.execute(
            "SELECT care_connect_account_id FROM whatsapp_identities WHERE provider_user_id = ?", (phone,),
        ).fetchone()
        if account_row is not None:
            account_id = account_row["care_connect_account_id"]
        else:
            new_account = conn.execute("INSERT INTO care_connect_accounts DEFAULT VALUES RETURNING id").fetchone()
            account_id = new_account["id"]
            conn.execute(
                "UPDATE care_connect_accounts SET display_id = ? WHERE id = ?",
                (generate_yearly_display_id_conn(conn, CARE_CONNECT_ACCOUNT_PREFIX, GLOBAL_SCOPE_KEY), account_id),
            )
            conn.execute(
                "INSERT INTO whatsapp_identities (care_connect_account_id, provider_user_id, phone_number) "
                "VALUES (?, ?, ?)",
                (account_id, phone, phone),
            )
        conn.execute(
            "UPDATE patient_links SET care_connect_account_id = ? "
            "WHERE whatsapp_phone = ? AND care_connect_account_id IS NULL",
            (account_id, phone),
        )
    conn.commit()


def _backfill_patient_mrns(conn) -> None:
    """mrn is a NEWER column than patient_display_id -- a patient that
    already got a patient_display_id before mrn existed needs an mrn too,
    but WITHOUT consuming a fresh patient_id_counters number (that would
    break the "same sequence number" pairing _generate_patient_identifiers()
    guarantees for every patient created after this column existed).
    Instead, reuses the number already embedded in that patient's own
    patient_display_id suffix (e.g. ...-0007 -> MRN-<code>-0007). Only
    touches mrn IS NULL rows, so re-running this on every startup is a
    no-op once every hospital is caught up."""
    rows = conn.execute(
        "SELECT id, hospital_id, patient_display_id FROM patients "
        "WHERE mrn IS NULL AND patient_display_id IS NOT NULL"
    ).fetchall()
    for row in rows:
        code = _get_or_create_hospital_short_code(conn, row["hospital_id"])
        seq_part = row["patient_display_id"].rsplit("-", 1)[1]
        mrn = f"MRN-{code}-{seq_part}"
        conn.execute("UPDATE patients SET mrn = ? WHERE id = ?", (mrn, row["id"]))
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

    care_connect_account_id is resolved/created inline via the same raw-conn
    helper _link_patient_under_cap() uses (patients.py) -- patient_links.
    care_connect_account_id is NOT NULL, so the row has to be stamped with a
    real account at INSERT time; there's no later pass that goes back and
    fills it in. Deliberately collapses onto ONE shared account per distinct
    whatsapp_phone across ALL hospitals (not one per hospital), matching
    get_or_create_account()'s own global-identity resolution.

    Gated on NOT EXISTS (one link per patient, not per phone -- a patient
    with two links from a bad prior run would break this gate, but nothing
    in this codebase ever creates more than one link per patient), so
    re-running this on every startup is a safe no-op once every existing
    patient is linked. Does not touch `patients` or `appointments` at all --
    purely additive rows in the new table, zero risk to existing booking
    history or Patient IDs."""
    rows = conn.execute(
        "SELECT p.hospital_id, p.phone, p.id AS patient_id, p.created_at FROM patients p "
        "WHERE NOT EXISTS (SELECT 1 FROM patient_links pl WHERE pl.patient_id = p.id)"
    ).fetchall()
    for row in rows:
        account = _get_or_create_account_in_conn(conn, row["phone"], phone_number=row["phone"])
        conn.execute(
            "INSERT INTO patient_links "
            "(hospital_id, whatsapp_phone, patient_id, relationship_label, linked_at, care_connect_account_id) "
            "VALUES (?, ?, ?, 'Self', ?, ?)",
            (row["hospital_id"], row["phone"], row["patient_id"], row["created_at"], account["id"]),
        )
    conn.commit()


def _backfill_appointment_types(conn) -> None:
    """Appointment type step (WhatsApp flow alignment): seeds
    DEFAULT_APPOINTMENT_TYPES (db/repositories/appointment_types.py, the
    single source of truth this mirrors) for every hospital that doesn't
    already have a row for a given type id -- so a hospital created before
    this feature, and a hospital onboarded after it, both end up with the
    same fixed catalog, ready to relabel/deactivate via the portal without
    a second migration. Gated per (hospital_id, type id), so re-running this
    on every startup is a safe no-op once every hospital is caught up, and a
    hospital that's already relabeled/deactivated a type is never touched
    again. is_active for a newly-inserted row is resolved from the hospital's
    own tenant_type (default_is_active(), appointment_types.py's single
    source of truth), so a pre-existing hospital gets the same
    tenant-appropriate default a freshly-onboarded one would."""
    hospitals = conn.execute("SELECT id, tenant_type FROM hospitals").fetchall()
    for hospital in hospitals:
        hospital_id, tenant_type = hospital["id"], hospital["tenant_type"]
        for sort_order, appt_type in enumerate(DEFAULT_APPOINTMENT_TYPES):
            conn.execute(
                "INSERT INTO appointment_types "
                "(id, hospital_id, label, requires_consent, requires_doctor_selection, is_active, sort_order) "
                "SELECT ?, ?, ?, ?, ?, ?, ? WHERE NOT EXISTS "
                "(SELECT 1 FROM appointment_types WHERE hospital_id = ? AND id = ?)",
                (
                    appt_type["id"], hospital_id, appt_type["label"], appt_type["requires_consent"],
                    appt_type["requires_doctor_selection"], default_is_active(tenant_type, appt_type["id"]),
                    sort_order, hospital_id, appt_type["id"],
                ),
            )
    conn.commit()


def _backfill_daycare_duration_options(conn) -> None:
    """Daycare Phase 2 (docs/per-appointment-type-flow-plan.md): seeds
    DEFAULT_DAYCARE_DURATION_OPTIONS (db/repositories/daycare_duration_
    options.py) for every hospital that doesn't already have ANY row --
    unlike _backfill_appointment_types above, a hospital that's already
    added/removed/relabeled its own options (a genuinely open catalog, not a
    fixed one re-keyed by id) is left alone entirely rather than gated per
    option, since there's no stable id to gate on until a row already
    exists. Every hospital gets these regardless of tenant_type, same as
    appointment_types rows -- daycare being hospital-only is enforced by
    that type's own is_active, not by withholding its duration options."""
    hospitals = conn.execute("SELECT id FROM hospitals").fetchall()
    for hospital in hospitals:
        hospital_id = hospital["id"]
        has_any = conn.execute(
            "SELECT 1 FROM daycare_duration_options WHERE hospital_id = ? LIMIT 1", (hospital_id,),
        ).fetchone()
        if has_any:
            continue
        for sort_order, option in enumerate(DEFAULT_DAYCARE_DURATION_OPTIONS):
            conn.execute(
                "INSERT INTO daycare_duration_options (hospital_id, label, hours, is_active, sort_order) "
                "VALUES (?, ?, ?, TRUE, ?)",
                (hospital_id, option["label"], option["hours"], sort_order),
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


def _backfill_admin_capabilities(conn) -> None:
    """Tenant-type-driven capability gating (tenant-capability-gating-plan.md):
    every existing hospital row gets an EXPLICIT admin_capabilities value
    (rather than leaving it NULL and relying on
    backend/portal/capabilities.py's get_capabilities() runtime fallback) so
    nothing silently depends on "default = full access" -- same "backfill
    explicitly, don't just infer at read time" precedent
    _backfill_enabled_features() above already established. Only touches
    rows where admin_capabilities IS NULL, so re-running this on every
    startup is a safe no-op once every hospital is caught up, and it can
    never overwrite a value a tenant admin already edited via
    admin/tenants_api.py. The literal JSON arrays here are a snapshot
    matching backend/portal/capabilities.py's DEFAULT_CAPABILITIES_BY_TYPE
    at the time this migration was written -- that module (not this
    function) is the single source of truth application code actually
    reads through; this only needs to match at backfill time, same as
    every other one-time JSON-literal backfill in this file.

    The final catch-all (admin_capabilities = '[]' for anything still NULL
    after the two typed UPDATEs above) covers a tenant_type value other than
    'hospital'/'clinic' -- shouldn't happen given the column's own CHECK
    constraint, but a zero-capability default is the safe failure mode if it
    ever does, rather than leaving the column NULL (which would fall back to
    the full hospital capability set via get_capabilities())."""
    conn.execute(
        "UPDATE hospitals SET admin_capabilities = ? "
        "WHERE admin_capabilities IS NULL AND tenant_type = 'hospital'",
        ('["manage_doctors","manage_departments","manage_appointment_types",'
         '"manage_bookings","manage_settings","manage_staff"]',),
    )
    conn.execute(
        "UPDATE hospitals SET admin_capabilities = ? "
        "WHERE admin_capabilities IS NULL AND tenant_type = 'clinic'",
        ('["manage_bookings","manage_settings"]',),
    )
    conn.execute("UPDATE hospitals SET admin_capabilities = '[]' WHERE admin_capabilities IS NULL")
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
    tests (against an in-memory DB) and internally by init_db() below.

    run_alembic_migrations() is deliberately NOT called here (see its own
    docstring) -- the per-test fixture in tests/conftest.py calls this
    function directly, hundreds of times per run, and never runs Alembic at
    all. So every schema DELTA added after the 0001 baseline (migrations
    0002+) needs its own idempotent statement here too, same
    "ALTER TABLE ... ADD COLUMN IF NOT EXISTS" pattern schema.sql used for
    years before Alembic adoption -- redundant against a DB that already
    got there via `alembic upgrade head` (prod), but the only way it
    reaches a test's freshly-recreated schema at all."""
    # schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    # conn.executescript(schema_sql)
    conn.executescript(_baseline_schema._BASELINE_SQL)
    # Migration 0002: patient_links.care_connect_account_id NOT NULL. Must
    # backfill any legacy NULL row FIRST -- this ALTER runs unconditionally
    # on every startup (prod included), and Postgres refuses to add a NOT
    # NULL constraint while a NULL value still exists, which would crash
    # init_db() (and the whole app, since main.py calls it at import time)
    # on any database old enough to have a row that predates the
    # CareConnect account layer.
    _backfill_patient_link_accounts(conn)
    conn.execute("ALTER TABLE patient_links ALTER COLUMN care_connect_account_id SET NOT NULL")
    # Migration 0003: patients.mrn.
    conn.execute("ALTER TABLE patients ADD COLUMN IF NOT EXISTS mrn TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_patients_hospital_mrn "
        "ON patients(hospital_id, mrn) WHERE mrn IS NOT NULL"
    )
    # Migration 0004: appointments.video_link (tele-consultation Jitsi URL --
    # was in schema.sql but never made it into the frozen 0001 baseline or
    # any numbered migration, so it silently didn't exist anywhere that
    # only ever ran `alembic upgrade head`).
    conn.execute("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS video_link TEXT")
    # Migration 0005: partial index supporting _link_patient_under_cap()'s
    # (db/repositories/patients.py) account-scoped active-link count.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_patient_links_active_account "
        "ON patient_links(hospital_id, care_connect_account_id) WHERE unlinked_at IS NULL"
    )
    # Migration 0006: care_connect_accounts.display_id / hospitals.display_id
    # (db/display_ids.py). Must run BEFORE seed_default_hospital() below --
    # that function now stamps display_id on the row it creates.
    conn.execute("ALTER TABLE care_connect_accounts ADD COLUMN IF NOT EXISTS display_id TEXT")
    conn.execute("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS display_id TEXT")
    conn.execute("UPDATE care_connect_accounts SET display_id = 'DCC-ACC-' || lpad(id::text, 6, '0') WHERE display_id IS NULL")
    conn.execute("UPDATE hospitals SET display_id = 'DCC-HOS-' || lpad(id::text, 4, '0') WHERE display_id IS NULL")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_care_connect_accounts_display_id "
        "ON care_connect_accounts(display_id) WHERE display_id IS NOT NULL"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_hospitals_display_id "
        "ON hospitals(display_id) WHERE display_id IS NOT NULL"
    )
    # Migration 0007: audit_logs (two-level audit trail, tenant-capability-
    # gating-plan.md's follow-up).
    conn.execute(
        "CREATE TABLE IF NOT EXISTS audit_logs ("
        "id BIGSERIAL PRIMARY KEY, "
        "actor_level TEXT NOT NULL CHECK (actor_level IN ('platform_admin', 'portal')), "
        "hospital_id INTEGER REFERENCES hospitals(id), "
        "actor_label TEXT NOT NULL, "
        "action TEXT NOT NULL, "
        "entity_type TEXT, "
        "entity_id TEXT, "
        "before_value TEXT, "
        "after_value TEXT, "
        "created_at TEXT NOT NULL DEFAULT (now()::text)"
        ")"
    )
    # Self-healing: an environment that ran an interim draft of this
    # migration (created_at as a native timestamp type, before it was
    # corrected to TEXT to match this schema's own "every timestamp is
    # ISO-8601 TEXT" convention) already has the table, so the CREATE TABLE
    # IF NOT EXISTS above is a no-op there and never picks up the fix --
    # this ALTER converges it on every startup regardless of which shape it
    # currently has (a column already TEXT casts to itself, a no-op).
    conn.execute("ALTER TABLE audit_logs ALTER COLUMN created_at TYPE TEXT USING created_at::text")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_hospital_created ON audit_logs (hospital_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_level_created ON audit_logs (actor_level, created_at)")
    # Migration 0008: daycare_duration_options table + appointments.duration_hours
    # (Daycare Phase 2, docs/per-appointment-type-flow-plan.md).
    conn.execute(
        "CREATE TABLE IF NOT EXISTS daycare_duration_options ("
        "id SERIAL PRIMARY KEY, "
        "hospital_id INTEGER NOT NULL REFERENCES hospitals(id), "
        "label TEXT NOT NULL, "
        "hours INTEGER NOT NULL CHECK (hours > 0), "
        "is_active BOOLEAN NOT NULL DEFAULT TRUE, "
        "sort_order INTEGER NOT NULL DEFAULT 0"
        ")"
    )
    conn.execute("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS duration_hours INTEGER")
    # Migration 0010: code_sequences (db/display_ids.py's shared, yearly-
    # resetting counter table for DCCG/DCCH/DCCC/DCCP -- see that module's
    # own docstring). Must run before seed_default_hospital()/
    # _backfill_patient_link_accounts() below, both of which now mint a
    # display_id through this table.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS code_sequences ("
        "id SERIAL PRIMARY KEY, "
        "prefix TEXT NOT NULL, "
        "scope_key TEXT NOT NULL, "
        "period_key TEXT NOT NULL, "
        "last_value INTEGER NOT NULL DEFAULT 0, "
        "UNIQUE (prefix, scope_key, period_key)"
        ")"
    )
    # Migration 0011: platform_settings (db/repositories/platform_settings.py)
    # -- a SINGLETON row (id=1, CHECK-enforced) for cross-tenant values only a
    # platform/super admin can change, starting with max_active_patient_links.
    # Seeded from db/models.py's DEFAULT_MAX_ACTIVE_PATIENT_LINKS exactly
    # once; ON CONFLICT DO NOTHING makes re-running this on every startup a
    # no-op once the row exists, so a later admin edit (admin/
    # platform_settings_api.py) is never silently reset back to the default.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS platform_settings ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), "
        "max_active_patient_links INTEGER NOT NULL DEFAULT 5"
        ")"
    )
    conn.execute(
        "INSERT INTO platform_settings (id, max_active_patient_links) VALUES (1, ?) "
        "ON CONFLICT (id) DO NOTHING",
        (DEFAULT_MAX_ACTIVE_PATIENT_LINKS,),
    )
    conn.commit()
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
    _backfill_patient_mrns(conn)
    _backfill_patient_links(conn)
    _backfill_appointment_types(conn)
    _backfill_daycare_duration_options(conn)
    _backfill_reports_prescriptions_feature(conn)
    _backfill_admin_capabilities(conn)
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
    run_alembic_migrations()
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

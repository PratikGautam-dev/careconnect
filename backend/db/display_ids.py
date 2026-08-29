# db/display_ids.py
"""Single source of truth for every human-readable display ID CareConnect
generates, and the prefix each one uses -- add a new entity's prefix here
even if (like patient_display_id/mrn) its actual generation stays in its own
repository file for a mechanism-specific reason, so every prefix in use is
still visible in one place.

GLOBAL_SCOPE_KEY-scoped codes (CareConnect account, hospital, clinic) and
per-hospital codes (patient/mrn) now ALL route through the shared
`code_sequences` table (see CodeSequence in db/orm_models.py) via
_next_sequence_conn()/_next_sequence_session() below, keyed on
(prefix, scope_key, period_key) -- one row per distinct combination, atomic
INSERT ... ON CONFLICT DO UPDATE increment, same race-safety precedent
_next_daily_reference_sequence() below already established for APT ids.
period_key is the current calendar year (str(now.year)) for every one of
these four, so each prefix's own numbering restarts at 1 every January 1st
-- this is why the OLD id-derived scheme (a display id computed straight off
the row's own permanent, never-resetting SERIAL id) had to be retired for
these: resetting a counter only means something once the period is embedded
in the visible code itself, otherwise DCCG-000001 minted in 2025 and
DCCG-000001 minted in 2026 would be visually indistinguishable despite
belonging to different accounts.

Already-issued display ids (minted before this reset-yearly scheme shipped)
are NEVER rewritten -- they keep their old, un-dated format
(e.g. DCC-PAT-0007) permanently. Only a NEW id, minted after this shipped,
uses the new "PREFIX-YYYY-NNNNN" shape. This mirrors the same
"assigned once, never regenerated" rule patient_display_id/mrn already
followed even before this change.

APT (appointment reference id) is explicitly OUT of scope for the shared
table/yearly-reset scheme -- it already resets on its own (daily, not
yearly) via its own dedicated reference_id_counters table, which predates
code_sequences and is left exactly as it was."""
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.orm_models import CodeSequence

# CareConnect account (db/repositories/accounts.py) -- global (GLOBAL_SCOPE_KEY),
# yearly-resetting. Not surfaced in any UI yet; stored for later use.
CARE_CONNECT_ACCOUNT_PREFIX = "DCCG"

# Hospital tenant (db/repositories/hospitals.py, tenant_type == "hospital") --
# global, yearly-resetting. Shown to hospital users as their own identifier.
HOSPITAL_PREFIX = "DCCH"

# Clinic tenant (db/repositories/hospitals.py, tenant_type == "clinic") --
# same shape/scope as HOSPITAL_PREFIX, distinct prefix so a hospital's and a
# clinic's own numbering never share one sequence (see hospital_display_prefix()
# below for which one a given tenant_type resolves to).
CLINIC_PREFIX = "DCCC"

# Patient (db/models.py's _generate_patient_identifiers) -- per-hospital
# (scope_key = str(hospital_id)), yearly-resetting.
PATIENT_DISPLAY_ID_PREFIX = "DCCP"
PATIENT_MRN_PREFIX = "MRN"  # followed by the hospital's own short code, not this prefix alone -- a
# real clinical/legal record number, not a CareConnect-namespaced id, so it deliberately doesn't
# take the DCC- form the others do. Still shares patient_display_id's own (hospital, year) sequence
# number -- see _generate_patient_identifiers()'s own docstring.

# Appointment reference id (generate_reference_id() below) -- APT-<DDMMYY>-<NNN>,
# e.g. APT-130826-001 (Item 8, Spec.md Section 0). Predates the DCC- naming
# convention and is shown directly to patients/staff on confirmations
# (tests assert this exact "APT-" prefix) -- deliberately NOT renamed, and
# deliberately NOT moved onto code_sequences (see module docstring).
APPOINTMENT_REFERENCE_ID_PREFIX = "APT"

# scope_key for every global (not per-hospital) prefix above.
GLOBAL_SCOPE_KEY = "global"

# Zero-padding width shared by every code_sequences-backed prefix.
_SEQUENCE_WIDTH = 5


# Summary table:

# Prefix   Sequence source           Scope           Resets?
# DCCG     code_sequences            global           yearly
# DCCH     code_sequences            global           yearly
# DCCC     code_sequences            global           yearly
# DCCP / MRN   code_sequences        per-hospital     yearly
# APT      reference_id_counters.counter   per-hospital, per-day   daily


def hospital_display_prefix(tenant_type: str) -> str:
    """CLINIC_PREFIX for tenant_type == "clinic", HOSPITAL_PREFIX for every
    other tenant_type (including the default "hospital") -- same fallback
    discipline db/repositories/appointment_types.py's
    DEFAULT_ACTIVE_TYPES_BY_TENANT_TYPE already uses for an unrecognized
    tenant_type."""
    return CLINIC_PREFIX if tenant_type == "clinic" else HOSPITAL_PREFIX


def _next_sequence_conn(conn, prefix: str, scope_key: str, period_key: str) -> int:
    """Raw-connection counterpart to _next_sequence_session() below -- same
    atomic INSERT ... ON CONFLICT DO UPDATE increment, for callers still on
    the raw psycopg2-style connection (db/repositories/accounts.py's
    _get_or_create_account_in_conn(), db/seed.py, db/models.py's
    _generate_patient_identifiers())."""
    row = conn.execute(
        "INSERT INTO code_sequences (prefix, scope_key, period_key, last_value) VALUES (?, ?, ?, 1) "
        "ON CONFLICT (prefix, scope_key, period_key) DO UPDATE SET last_value = code_sequences.last_value + 1 "
        "RETURNING last_value",
        (prefix, scope_key, period_key),
    ).fetchone()
    return row["last_value"]


def _next_sequence_session(session, prefix: str, scope_key: str, period_key: str) -> int:
    """ORM-session counterpart to _next_sequence_conn() above, for callers
    already on get_session() (db/repositories/accounts.py's
    _get_or_create_account_in_session(), db/repositories/hospitals.py's
    create_hospital())."""
    result = session.execute(
        pg_insert(CodeSequence)
        .values(prefix=prefix, scope_key=scope_key, period_key=period_key, last_value=1)
        .on_conflict_do_update(
            index_elements=["prefix", "scope_key", "period_key"],
            set_={"last_value": CodeSequence.last_value + 1},
        )
        .returning(CodeSequence.last_value)
    )
    return result.scalar_one()


def generate_yearly_display_id_conn(conn, prefix: str, scope_key: str, now: datetime | None = None) -> str:
    """DCCG/DCCH/DCCC's own generator (raw-connection callers) -- see module
    docstring for why the year is embedded directly in the returned string,
    not just used to key the underlying counter."""
    now = now or datetime.now()
    seq = _next_sequence_conn(conn, prefix, scope_key, str(now.year))
    return f"{prefix}-{now.year}-{seq:0{_SEQUENCE_WIDTH}d}"


def generate_yearly_display_id_session(session, prefix: str, scope_key: str, now: datetime | None = None) -> str:
    """Same as generate_yearly_display_id_conn() above, for ORM-session callers."""
    now = now or datetime.now()
    seq = _next_sequence_session(session, prefix, scope_key, str(now.year))
    return f"{prefix}-{now.year}-{seq:0{_SEQUENCE_WIDTH}d}"


def _next_daily_reference_sequence(conn, hospital_id: int, day: str) -> int:
    """Atomic per-(hospital, day) increment -- INSERT...ON CONFLICT DO UPDATE
    is a single statement, so this is race-safe under real concurrent
    bookings (unlike a read-then-increment-then-write pair). Deliberately
    its own reference_id_counters table, not code_sequences -- see module
    docstring for why APT stays out of the shared/yearly-reset scheme."""
    row = conn.execute(
        "INSERT INTO reference_id_counters (hospital_id, day, counter) VALUES (?, ?, 1) "
        "ON CONFLICT (hospital_id, day) DO UPDATE SET counter = reference_id_counters.counter + 1 "
        "RETURNING counter",
        (hospital_id, day),
    ).fetchone()
    return row["counter"]


def _generate_reference_id(conn, hospital_id: int, now: datetime | None = None) -> str:
    """Item 8 (Spec.md Section 0): structured, human-readable format --
    APT-<DDMMYY>-<NNN>, e.g. APT-130826-001 -- replacing the old
    apt_<millisecond-epoch> format (Section 12.12). A later Item 2 follow-up
    (Spec.md Section 0) switched the date part from a month-ABBREVIATION
    (DDMMMYY, e.g. 13AUG26) to fully numeric DDMMYY (e.g. 130826), confirmed
    with the user directly rather than assumed. Sequence is PER HOSPITAL PER
    DAY (reference_id_counters' composite PK), not globally sequential across
    tenants, and resets to 001 each new calendar day. Based on the booking's
    CREATION time (when create_appointment() runs), not the appointment's
    scheduled visit date -- same convention a receipt/invoice number uses
    (the transaction date), and matches the OLD format's own basis
    (time.time() at creation, not scheduled_at)."""
    now = now or datetime.now()
    day_key = now.strftime("%Y-%m-%d")
    seq = _next_daily_reference_sequence(conn, hospital_id, day_key)
    date_part = now.strftime("%d%m%y")
    return f"{APPOINTMENT_REFERENCE_ID_PREFIX}-{date_part}-{seq:03d}"

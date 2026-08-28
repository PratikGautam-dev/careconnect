# db/display_ids.py
"""Single source of truth for every human-readable display ID CareConnect
generates, and the prefix each one uses -- add a new entity's prefix here
even if (like patient_display_id/mrn) its actual generation stays in its own
repository file for a mechanism-specific reason, so every prefix in use is
still visible in one place."""
from datetime import datetime

# CareConnect account (db/repositories/accounts.py) -- global, id-derived.
# Not surfaced in any UI yet; stored for later use.
CARE_CONNECT_ACCOUNT_PREFIX = "DCC-ACC"

# Hospital (db/repositories/hospitals.py) -- global, id-derived.
# Shown to hospital users as their own hospital's identifier.
HOSPITAL_PREFIX = "DCC-HOS"

# Patient (db/models.py's _generate_patient_identifiers) -- per-hospital
# counter, NOT id-derived (needs a small hospital-scoped sequence, distinct
# from the global patients.id) -- generation stays in db/models.py, prefix
# documented here only. See that function's own docstring for why it can't
# use generate_id_derived_display_id() below.
PATIENT_DISPLAY_ID_PREFIX = "DCC-PAT"
PATIENT_MRN_PREFIX = "MRN"  # followed by the hospital's own short code, not this prefix alone -- a
# real clinical/legal record number, not a CareConnect-namespaced id, so it deliberately doesn't
# take the DCC- form the others do.

# Appointment reference id (generate_reference_id() below) -- APT-<DDMMYY>-<NNN>,
# e.g. APT-130826-001 (Item 8, Spec.md Section 0). Predates the DCC- naming
# convention and is shown directly to patients/staff on confirmations
# (tests assert this exact "APT-" prefix) -- deliberately NOT renamed to a
# DCC- form, unlike the two new prefixes above.
APPOINTMENT_REFERENCE_ID_PREFIX = "APT"


# Summary table:

# Prefix	Sequence source	                Scope	       Resets?
# DCC-ACC	own care_connect_accounts.id	global	        never
# DCC-HOS	own hospitals.id	            global	        never
# DCC-PAT / MRN	patient_id_counters.counter	per-hospital	never
# APT	reference_id_counters.counter	   per-hospital, per-day	daily


def generate_id_derived_display_id(prefix: str, row_id: int, width: int) -> str:
    """For any entity whose display id can be safely derived from its own
    already-atomic integer PK (Postgres SERIAL) -- no separate counter table
    or advisory lock needed, since there's nothing to race on. NOT for
    entities needing a per-tenant-scoped sequence distinct from their own id
    (e.g. patients -- see PATIENT_DISPLAY_ID_PREFIX above)."""
    return f"{prefix}-{row_id:0{width}d}"


def _next_daily_reference_sequence(conn, hospital_id: int, day: str) -> int:
    """Atomic per-(hospital, day) increment -- INSERT...ON CONFLICT DO UPDATE
    is a single statement, so this is race-safe under real concurrent
    bookings (unlike a read-then-increment-then-write pair)."""
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

# db/repositories/patients.py
"""Patient search/directory, profiles, and the patient-identity-separation
linking/consent model (Spec.md Section 0). Split out of db/repository.py --
see ARCHITECTURE_PLAN.md Phase 1."""
from datetime import datetime

from db.connection import get_connection
from db.models import MAX_ACTIVE_PATIENT_LINKS, TooManyLinkedPatientsError, _generate_patient_display_id
from db.repositories.accounts import _get_or_create_account_in_conn

# --- Patients (Section 12.9 -- staff-created bookings need to search by name,
# not just phone; see db/schema.sql's comment on the patients table and
# create_appointment()'s _upsert_patient() for how rows get here) ---

def is_valid_phone(phone: str | None) -> bool:
    """Deliberately permissive (SPEC Section 12.9's phone-validation follow-up)
    -- rejects only the unambiguous garbage cases (empty, whitespace-only, or
    containing no digits at all, e.g. "not-a-phone-number!!"), not a strict
    phone-number format spec: no length requirement, no country-code check,
    no separator/whitespace-shape rules. International phone formats vary too
    much to validate meaningfully without a dedicated library this project
    doesn't otherwise need -- filtering garbage, not enforcing a spec, is the
    actual goal here. Called at every point a phone number is first captured:
    core/main.py's webhook intake (WhatsApp) and portal.py's new-booking form
    (staff) -- not re-checked here in create_appointment() itself, since both
    of those are the only real entry points and re-validating a third time
    at the shared data-access layer would just be the same rule maintained
    in three places instead of two."""
    if not phone:
        return False
    phone = phone.strip()
    if not phone:
        return False
    return any(c.isdigit() for c in phone)


def search_patients(hospital_id: int, query: str, limit: int = 10) -> list[dict]:
    """Case-insensitive partial match on name OR phone, hospital-scoped.
    Powers portal.py's /portal/patients/search (staff typing into the new-
    booking form's patient search box)."""
    query = query.strip()
    if not query:
        return []
    conn = get_connection()
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT phone, name FROM patients WHERE hospital_id = ? "
        "AND (phone ILIKE ? OR name ILIKE ?) ORDER BY name NULLS LAST, phone LIMIT ?",
        (hospital_id, like, like, limit),
    ).fetchall()
    return [{"phone": r["phone"], "name": r["name"]} for r in rows]


def _patients_with_visit_stats_sql(where_extra: str = "") -> str:
    """Shared by list_patients()/get_recent_patients() -- last_visit is the
    most recent scheduled_at across every appointment (any status, same
    "staff want to see the full history" reasoning as
    get_all_appointments_for_hospital()), visit_count counts every
    appointment row ever created for that phone, not just kept ones."""
    return (
        "SELECT p.id, p.phone, p.name, p.patient_display_id, MAX(a.scheduled_at) AS last_visit, "
        "COUNT(a.id) AS visit_count "
        "FROM patients p LEFT JOIN appointments a ON a.hospital_id = p.hospital_id AND a.phone = p.phone "
        f"WHERE p.hospital_id = ? {where_extra} "
        "GROUP BY p.id, p.phone, p.name, p.patient_display_id "
        "ORDER BY last_visit DESC NULLS LAST, p.name NULLS LAST, p.phone "
    )


def list_patients(hospital_id: int, search: str | None = None, limit: int = 200) -> list[dict]:
    """Full patient directory for /portal/patients -- unlike search_patients()
    (name/phone only, built for the new-booking form's autocomplete), this
    also surfaces last_visit/visit_count so staff can see engagement at a
    glance, and returns every patient (not just search hits) when no query
    is given."""
    conn = get_connection()
    search = (search or "").strip()
    if search:
        like = f"%{search}%"
        rows = conn.execute(
            _patients_with_visit_stats_sql("AND (p.phone ILIKE ? OR p.name ILIKE ?)") + "LIMIT ?",
            (hospital_id, like, like, limit),
        ).fetchall()
    else:
        rows = conn.execute(_patients_with_visit_stats_sql() + "LIMIT ?", (hospital_id, limit)).fetchall()
    return [
        {
            "id": r["id"], "phone": r["phone"], "name": r["name"], "patient_display_id": r["patient_display_id"],
            "last_visit": r["last_visit"], "visit_count": r["visit_count"],
        }
        for r in rows
    ]


def get_recent_patients(hospital_id: int, limit: int = 5) -> list[dict]:
    """The dashboard's small "Patients" widget -- same shape as list_patients()
    but capped short and always unfiltered (most-recently-seen patients),
    since it's a glance-and-click-through widget, not a search surface."""
    return list_patients(hospital_id, search=None, limit=limit)


# --- Patient records (Section 12.10: visit history, notes, documents) ---

def get_patient(hospital_id: int, patient_id: int) -> dict | None:
    """The single ownership check every patient-detail/notes/documents route
    uses before doing anything else -- returns None for a patient_id that
    doesn't exist OR belongs to a different hospital, so callers can't tell
    the two cases apart from the response (same 404-not-403 discipline as
    get_doctor_full())."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, hospital_id, phone, name, date_of_birth, gender, address, age, patient_display_id, "
        "status, created_at "
        "FROM patients WHERE hospital_id = ? AND id = ?",
        (hospital_id, patient_id),
    ).fetchone()
    return dict(row) if row else None


def get_patient_by_phone(hospital_id: int, phone: str) -> dict | None:
    """Section 12.11: the WhatsApp booking flow's "have we met this patient
    before" check -- unlike get_patient() (looked up by the portal's own
    numeric id), the bot only ever knows a phone number. Exact match, not
    search_patients()'s partial ILIKE -- this is an identity lookup, not a
    staff-typed search box.

    Patient identity SEPARATION (Spec.md Section 0): kept as-is for callers
    that still want "the one patient this phone has" (e.g. "My Details",
    which predates multi-patient linking and is out of scope for this
    round) -- returns the FIRST matching row if a phone somehow has more
    than one `patients` row, not an error, but is no longer the right
    lookup for anything booking-related. Use get_active_patients_for_phone()
    for that."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, hospital_id, phone, name, date_of_birth, gender, address, age, patient_display_id, "
        "status, created_at "
        "FROM patients WHERE hospital_id = ? AND phone = ?",
        (hospital_id, phone),
    ).fetchone()
    return dict(row) if row else None


# --- Patient identity SEPARATION (Spec.md Section 0): one WhatsApp phone can
# link up to MAX_ACTIVE_PATIENT_LINKS patient profiles (a shared family phone).
# patient_links is the source of truth for phone<->patient associations;
# `patients` itself no longer implies "one row per phone" (db/schema.sql's own
# comment on the dropped UNIQUE(hospital_id, phone) constraint explains why). ---

# CareConnect architecture doc alignment (Spec.md Section 0), Section 17's
# fixed relationship enum -- single source of truth the WhatsApp picker and
# db/schema.sql's own patient_links_relationship_label_check CHECK
# constraint both mirror. Stored/displayed as Title Case, matching the
# migration backfill's own pre-existing 'Self' value -- not the doc's
# literal uppercase SELF/MOTHER/... strings, which would need a data
# migration for no functional gain (confirmed with the user).
RELATIONSHIP_OPTIONS = ("Self", "Mother", "Father", "Son", "Daughter", "Spouse", "Guardian", "Other")

# CareConnect architecture doc alignment, Section 18's Patient Master state
# model (CREATED collapsed into ACTIVE, confirmed with the user -- see
# db/schema.sql's own comment on patients.status for why).
PATIENT_STATUS_ACTIVE = "active"
PATIENT_STATUS_BLOCKED = "blocked"
PATIENT_STATUS_INACTIVE = "inactive"
PATIENT_STATUSES = (PATIENT_STATUS_ACTIVE, PATIENT_STATUS_BLOCKED, PATIENT_STATUS_INACTIVE)


def get_active_patients_for_phone(hospital_id: int, phone: str) -> list[dict]:
    """The real "which patients does this phone see" lookup, replacing
    get_patient_by_phone() for every WhatsApp-facing use -- returns every
    ACTIVE (unlinked_at IS NULL) linked patient, soonest-linked first (so the
    original/"Self" profile from before this feature existed, or the first
    family member added, is always first -- the natural single-result case
    for a still-single-patient phone stays first without any extra logic).

    CareConnect architecture doc alignment (Spec.md Section 0), Section 18:
    also filters to patients.status = 'active' -- a hospital-blocked or
    inactive patient is excluded from selection/auto-continue entirely,
    without touching their patient_links row at all (their link stays
    active; they just can't be chosen while the PATIENT record itself is
    blocked/inactive). This is the one enforcement point every WhatsApp-
    facing patient list goes through, same "filter at the one real read
    path" precedent doctors.is_active already established."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT p.id, p.name, p.age, p.patient_display_id, pl.relationship_label, pl.id AS link_id "
        "FROM patient_links pl JOIN patients p ON p.id = pl.patient_id "
        "WHERE pl.hospital_id = ? AND pl.whatsapp_phone = ? AND pl.unlinked_at IS NULL "
        "AND p.status = 'active' "
        "ORDER BY pl.linked_at, pl.id",
        (hospital_id, phone),
    ).fetchall()
    return [dict(r) for r in rows]


def validate_active_patient_link(hospital_id: int, phone: str, patient_id: int) -> bool:
    """CareConnect architecture doc alignment (Spec.md Section 0), Section
    14's patient-context validation: re-checked at the point of an actual
    patient-specific WRITE (booking/cancel/reschedule confirm), not just at
    selection time -- a link resolved several messages ago in a multi-step
    flow (department -> doctor -> date -> time -> confirm) could have been
    unlinked, or the patient blocked, in between. True only if the link is
    still active AND the patient itself is still 'active'."""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM patient_links pl JOIN patients p ON p.id = pl.patient_id "
        "WHERE pl.hospital_id = ? AND pl.whatsapp_phone = ? AND pl.patient_id = ? "
        "AND pl.unlinked_at IS NULL AND p.status = 'active'",
        (hospital_id, phone, patient_id),
    ).fetchone()
    return row is not None


def count_active_links_for_phone(hospital_id: int, phone: str) -> int:
    conn = get_connection()
    return conn.execute(
        "SELECT COUNT(*) AS c FROM patient_links WHERE hospital_id = ? AND whatsapp_phone = ? AND unlinked_at IS NULL",
        (hospital_id, phone),
    ).fetchone()["c"]


def _check_relationship_label(relationship_label: str | None) -> None:
    if relationship_label is not None and relationship_label not in RELATIONSHIP_OPTIONS:
        raise ValueError(f"relationship_label must be one of {RELATIONSHIP_OPTIONS} or None, got {relationship_label!r}")


def _link_patient_under_cap(conn, hospital_id: int, phone: str, patient_id: int, relationship_label: str | None) -> None:
    """Shared by create_patient_profile()/link_existing_patient(): the
    advisory-locked "count active links, raise if at cap, else INSERT the
    link row" sequence -- must run under `conn`'s already-open transaction
    (both callers wrap this in BEGIN/COMMIT/ROLLBACK) so the count-then-
    insert is atomic against a genuine concurrent "add/link a patient" tap
    from the same phone."""
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (f"patient_links|{hospital_id}|{phone}",))
    active_count = conn.execute(
        "SELECT COUNT(*) AS c FROM patient_links WHERE hospital_id = ? AND whatsapp_phone = ? AND unlinked_at IS NULL",
        (hospital_id, phone),
    ).fetchone()["c"]
    if active_count >= MAX_ACTIVE_PATIENT_LINKS:
        raise TooManyLinkedPatientsError(
            f"This phone number already has {MAX_ACTIVE_PATIENT_LINKS} linked patients -- unlink one first."
        )
    # CareConnect account/identity layer (db/schema.sql's own comment on
    # care_connect_accounts): stamps every new link with the GLOBAL account
    # this phone resolves to. Uses the transaction-agnostic helper (not
    # get_or_create_account()) since this already runs inside the caller's
    # own BEGIN/COMMIT -- idempotent either way, so this is a cheap lookup on
    # the common path where webhook/dispatch.py's own per-message
    # identify_contact() call already created the account earlier in this
    # same conversation.
    account = _get_or_create_account_in_conn(conn, phone, phone_number=phone)
    conn.execute(
        "INSERT INTO patient_links (hospital_id, whatsapp_phone, patient_id, relationship_label, care_connect_account_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (hospital_id, phone, patient_id, relationship_label, account["id"]),
    )


def find_potential_duplicate_patient(hospital_id: int, phone: str, name: str, age: int | None) -> dict | None:
    """CareConnect architecture doc alignment (Spec.md Section 0), Sections
    8-10: searched BEFORE create_patient_profile() creates a brand-new
    `patients` row/MRN, so a family member who already has a hospital
    record (e.g. from a staff-created booking, or a different WhatsApp
    number) isn't silently duplicated. Matching criteria confirmed with the
    user, deliberately simple and conservative -- no fuzzy matching: exact
    name (case/whitespace-insensitive) AND exact age, among this hospital's
    ACTIVE patients. Excludes any patient already actively linked to THIS
    phone -- if they're already linked, they'd show up in the family list
    directly, not through this duplicate-detection path at all. Returns the
    first match (deterministic: lowest patient id) or None."""
    conn = get_connection()
    if age is None:
        return None
    row = conn.execute(
        "SELECT p.id, p.name, p.age, p.patient_display_id FROM patients p "
        "WHERE p.hospital_id = ? AND p.status = 'active' "
        "AND LOWER(TRIM(p.name)) = LOWER(TRIM(?)) AND p.age = ? "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM patient_links pl WHERE pl.patient_id = p.id AND pl.hospital_id = ? "
        "  AND pl.whatsapp_phone = ? AND pl.unlinked_at IS NULL"
        ") "
        "ORDER BY p.id LIMIT 1",
        (hospital_id, name, age, hospital_id, phone),
    ).fetchone()
    return dict(row) if row else None


def create_patient_profile(
    hospital_id: int, phone: str, name: str, age: int | None, relationship_label: str | None = None,
) -> dict:
    """Creates a brand-new `patients` row (NEVER an upsert-by-phone -- multiple
    profiles are the whole point now) and links it to `phone` via a new
    patient_links row. Raises TooManyLinkedPatientsError if this phone already
    has MAX_ACTIVE_PATIENT_LINKS active links, or ValueError if
    relationship_label isn't one of RELATIONSHIP_OPTIONS (or None).

    Callers are expected to have already checked
    find_potential_duplicate_patient() and confirmed with the patient that
    this is genuinely a NEW patient, not an existing one to link instead
    (link_existing_patient(), below) -- this function itself does not
    re-check for a duplicate, so it can also serve any future caller (e.g.
    a staff-side "register new patient" form) that has already resolved
    identity its own way.

    Wrapped in a real BEGIN/COMMIT/ROLLBACK block -- see
    _link_patient_under_cap()'s own docstring for the advisory-lock
    reasoning, unchanged from before this was extracted into a shared
    helper."""
    _check_relationship_label(relationship_label)
    conn = get_connection()
    conn.execute("BEGIN")
    try:
        patient_row = conn.execute(
            "INSERT INTO patients (hospital_id, phone, name, age) VALUES (?, ?, ?, ?) RETURNING id",
            (hospital_id, phone, name, age),
        ).fetchone()
        patient_id = patient_row["id"]
        display_id = _generate_patient_display_id(conn, hospital_id)
        conn.execute("UPDATE patients SET patient_display_id = ? WHERE id = ?", (display_id, patient_id))
        _link_patient_under_cap(conn, hospital_id, phone, patient_id, relationship_label)
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    return {
        "id": patient_id, "name": name, "age": age, "patient_display_id": display_id,
        "relationship_label": relationship_label,
    }


def link_existing_patient(
    hospital_id: int, phone: str, patient_id: int, relationship_label: str | None = None,
) -> dict:
    """CareConnect architecture doc alignment (Spec.md Section 0), Section
    9: the "Link Existing Patient" choice after find_potential_duplicate_patient()
    surfaces a plausible match -- creates a new patient_links row pointing
    at the EXISTING `patients` row (no new patient/MRN, matching Section 9's
    explicit "should not create a second MRN merely because..." rule)
    rather than create_patient_profile()'s "always a fresh row." Subject to
    the exact same 5-active-link cap as a new profile. Raises ValueError if
    patient_id doesn't belong to hospital_id, or isn't 'active'."""
    _check_relationship_label(relationship_label)
    conn = get_connection()
    conn.execute("BEGIN")
    try:
        patient_row = conn.execute(
            "SELECT id, name, age, patient_display_id FROM patients WHERE hospital_id = ? AND id = ? AND status = ?",
            (hospital_id, patient_id, PATIENT_STATUS_ACTIVE),
        ).fetchone()
        if patient_row is None:
            raise ValueError(f"patient_id {patient_id} not found (or not active) for hospital {hospital_id}")
        _link_patient_under_cap(conn, hospital_id, phone, patient_id, relationship_label)
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    return {
        "id": patient_row["id"], "name": patient_row["name"], "age": patient_row["age"],
        "patient_display_id": patient_row["patient_display_id"], "relationship_label": relationship_label,
    }


def set_patient_status(hospital_id: int, patient_id: int, status: str) -> dict | None:
    """Staff-side action (the portal's patient detail page) for Section 18's
    BLOCKED/INACTIVE states -- a hospital-level fact about the PATIENT
    record, deliberately independent of patient_links (blocking a patient
    doesn't touch or require touching any phone's link to them; see
    get_active_patients_for_phone()'s own docstring). Returns None if
    patient_id doesn't belong to this hospital, or raises ValueError for an
    unrecognized status."""
    if status not in PATIENT_STATUSES:
        raise ValueError(f"status must be one of {PATIENT_STATUSES}, got {status!r}")
    conn = get_connection()
    cur = conn.execute(
        "UPDATE patients SET status = ? WHERE hospital_id = ? AND id = ?",
        (status, hospital_id, patient_id),
    )
    if cur.rowcount == 0:
        return None
    conn.commit()
    return get_patient(hospital_id, patient_id)


def unlink_patient(hospital_id: int, phone: str, patient_id: int) -> bool:
    """Soft-unlink only -- sets unlinked_at on the matching ACTIVE link row.
    Never touches `patients` or `appointments`: a soft-unlink is purely a
    patient_links row update, so this patient's appointment history and
    Patient ID are completely unaffected (confirmed by design, not just by
    accident of implementation -- there is no code path here that could
    touch either table). Returns False if no such active link exists (stale
    tap, already unlinked, or a patient_id belonging to a different phone)."""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE patient_links SET unlinked_at = ? "
        "WHERE hospital_id = ? AND whatsapp_phone = ? AND patient_id = ? AND unlinked_at IS NULL",
        (datetime.now().isoformat(), hospital_id, phone, patient_id),
    )
    if cur.rowcount == 0:
        return False
    conn.commit()
    return True


def get_patient_link_consent(hospital_id: int, phone: str, patient_id: int) -> dict | None:
    """CareConnect architecture doc alignment (Spec.md Section 0), Section
    20's Consent & Privacy menu item -- reads the active link's own
    service_consent/marketing_consent columns. Returns None if there's no
    active link for this (hospital_id, phone, patient_id) triple."""
    conn = get_connection()
    row = conn.execute(
        "SELECT service_consent, marketing_consent FROM patient_links "
        "WHERE hospital_id = ? AND whatsapp_phone = ? AND patient_id = ? AND unlinked_at IS NULL",
        (hospital_id, phone, patient_id),
    ).fetchone()
    return dict(row) if row else None


def set_marketing_consent(hospital_id: int, phone: str, patient_id: int, consented: bool) -> bool:
    """The one genuinely user-togglable consent flag (Section 20) --
    service_consent is implicit in having an active link at all (see
    db/schema.sql's own comment on why it's not a separate WhatsApp-facing
    toggle); marketing_consent is independent, opt-in, and freely
    reversible either direction. Returns False if there's no active link to
    update."""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE patient_links SET marketing_consent = ? "
        "WHERE hospital_id = ? AND whatsapp_phone = ? AND patient_id = ? AND unlinked_at IS NULL",
        (consented, hospital_id, phone, patient_id),
    )
    if cur.rowcount == 0:
        return False
    conn.commit()
    return True


def update_patient_profile(hospital_id: int, patient_id: int, name: str, age: int | None) -> dict | None:
    """Not exposed in the v1 WhatsApp flow (which only ever creates new
    profiles, never edits one) -- kept available for a future "edit a linked
    patient" step without needing a second migration. Returns None if
    patient_id doesn't belong to this hospital."""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE patients SET name = ?, age = ? WHERE hospital_id = ? AND id = ?",
        (name, age, hospital_id, patient_id),
    )
    if cur.rowcount == 0:
        return None
    conn.commit()
    return get_patient(hospital_id, patient_id)


def update_patient_demographics(
    hospital_id: int, patient_id: int, date_of_birth: str | None, gender: str | None, address: str | None,
) -> dict | None:
    """All three fields optional -- an empty-string/None value clears that
    field rather than being rejected, since none of this was ever required
    at patient creation and staff filling it in gradually is the expected
    path, not an all-at-once form."""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE patients SET date_of_birth = ?, gender = ?, address = ? WHERE hospital_id = ? AND id = ?",
        (date_of_birth or None, gender or None, address or None, hospital_id, patient_id),
    )
    if cur.rowcount == 0:
        return None
    conn.commit()
    return get_patient(hospital_id, patient_id)



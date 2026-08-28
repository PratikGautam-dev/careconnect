# db/models.py
"""
ARCHITECTURE_PLAN.md Phase 1: shared dataclasses, row-mapping helpers,
exceptions, and cross-domain constants extracted out of db/repository.py's
former god-file. Anything here is used by more than one file under
db/repositories/, or is a typed return shape crossing the Connector/portal
JSON boundary -- domain-specific logic stays in db/repositories/*.py.
"""
import re
from dataclasses import dataclass
from datetime import datetime

from db.connection import IntegrityError

STATUS_BOOKED = "booked"
STATUS_CANCELLED = "cancelled"
STATUS_RESCHEDULED = "rescheduled"
# Item 9 (Spec.md Section 0): real, staff-confirmed statuses -- closes the
# previously-flagged "no-shows are a heuristic, not a real status" gap
# (get_dashboard_stats()' "no_shows_today" below is UNCHANGED, still the
# same time-passed-and-still-booked heuristic -- these two new values don't
# retroactively reclassify it, they give staff a way to record the real
# outcome going forward once they confirm it).
STATUS_ATTENDED = "attended"
STATUS_NO_SHOW = "no_show"

SOURCE_WHATSAPP = "whatsapp"
SOURCE_STAFF = "staff"

# Patient identity SEPARATION (Spec.md Section 0): max ACTIVE (not unlinked)
# patient_links rows one WhatsApp phone number may have per hospital at once --
# confirmed with the user before building. Enforced in create_patient_profile(),
# not a DB constraint (a COUNT-based cap can't be expressed as a plain CHECK).
MAX_ACTIVE_PATIENT_LINKS = 5




class QuotaExceededError(IntegrityError):
    """Section 12.9: raised by create_appointment() specifically when a
    booking is rejected because the doctor's online_quota/walkin_quota/
    daily_booking_limit (Section 14.7) is exhausted, as opposed to the exact
    requested slot being full. Subclasses IntegrityError so every EXISTING
    `except IntegrityError:` call site (core/booking_flow.py's double-booking
    handling) keeps working unchanged with its generic "that slot was just
    taken" message; portal.py's staff-booking route catches THIS specifically
    first, to show str(e) (a purpose-written message) instead."""


class DuplicateBookingError(IntegrityError):
    """Item 5 (Spec.md Section 0): raised by create_appointment() when this
    phone already has an ACTIVE (status='booked') appointment with the SAME
    doctor and the same patient age on file. Scoped to same-doctor
    specifically -- a patient legitimately booking two different doctors is
    never blocked. Subclasses IntegrityError for the same reason
    QuotaExceededError does (existing `except IntegrityError:` call sites
    keep working); carries the existing appointment's id so a caller can
    offer direct Cancel/Reschedule actions for THAT appointment instead of a
    generic error message."""
    def __init__(self, message: str, existing_appointment_id: int):
        super().__init__(message)
        self.existing_appointment_id = existing_appointment_id


class TooManyLinkedPatientsError(Exception):
    """Patient identity SEPARATION (Spec.md Section 0): raised by
    create_patient_profile() when a phone number already has
    MAX_ACTIVE_PATIENT_LINKS active (not unlinked) patient_links rows for
    this hospital. Deliberately NOT an IntegrityError subclass -- this isn't
    a booking race to recover from, it's a validation rule flows.py's own
    "Add Patient" handler catches specifically to show a clear message
    ("unlink someone first")."""



_APPOINTMENT_SELECT = """
    SELECT a.id, a.hospital_id, a.phone, a.department_id, d.name AS department_name,
           a.doctor_id, doc.name AS doctor_name, a.scheduled_at, a.status, a.source, a.reference_id,
           a.patient_id, p.patient_display_id, a.appointment_type_id, a.consent_given_at, a.video_link
    FROM appointments a
    JOIN departments d ON d.id = a.department_id
    JOIN doctors doc ON doc.id = a.doctor_id
    LEFT JOIN patients p ON p.id = a.patient_id
    WHERE a.deleted_at IS NULL
"""
# Item 3 (Spec.md Section 0): every normal read of an appointment excludes a
# soft-deleted one (deleted_at IS NOT NULL) -- baked into the base SELECT's
# own WHERE clause so every call site below appends "AND ..." instead of a
# fresh "WHERE ...", and none of them can forget this filter individually.
# The one deliberate exception is get_total_bookings_count() (Section 0,
# platform-admin lifetime usage stat) -- a soft-deleted row still represents
# a real historical booking event, so that one query is NOT built on this
# constant.



def _derive_hospital_short_code(name: str) -> str:
    """Patient identity system (Spec.md Section 0), confirmed with the user:
    auto-derived from the hospital's own `name`, not a new onboarding field.
    Two rules, chosen for a short, deterministic, always->=3-character code:
    - 3+ words: first letter of each of the first 4 words, uppercased (e.g.
      "Metro Lifeline Hospital" -> "MLH").
    - 1-2 words: first 3 letters of the name with spaces removed, uppercased
      (e.g. "Default Hospital" -> "DEF", "DaaPrime" -> "DAA") -- initials
      alone would be only 1-2 characters here, too short to be useful.
    Deliberately NOT enforced globally unique across hospitals (confirmed
    with the user) -- see db/schema.sql's patient_id_prefix column comment."""
    words = re.findall(r"[A-Za-z0-9]+", name)
    if not words:
        return "HSP"
    if len(words) >= 3:
        return "".join(w[0] for w in words[:4]).upper()
    return "".join(words).upper()[:3]


def _get_or_create_hospital_short_code(conn, hospital_id: int) -> str:
    """Computed once, the first time a hospital's first patient is ever
    created, and stored permanently -- never recomputed even if the hospital
    is later renamed, so existing patients' ids stay stable."""
    row = conn.execute(
        "SELECT patient_id_prefix, name FROM hospitals WHERE id = ?", (hospital_id,),
    ).fetchone()
    if row["patient_id_prefix"]:
        return row["patient_id_prefix"]
    code = _derive_hospital_short_code(row["name"])
    conn.execute("UPDATE hospitals SET patient_id_prefix = ? WHERE id = ?", (code, hospital_id))
    return code


def _next_patient_display_sequence(conn, hospital_id: int) -> int:
    """Same atomic INSERT ... ON CONFLICT DO UPDATE pattern as
    _next_daily_reference_sequence above, one row per hospital (no `day`
    dimension -- a lifetime count, not a daily-resetting one)."""
    row = conn.execute(
        "INSERT INTO patient_id_counters (hospital_id, counter) VALUES (?, 1) "
        "ON CONFLICT (hospital_id) DO UPDATE SET counter = patient_id_counters.counter + 1 "
        "RETURNING counter",
        (hospital_id,),
    ).fetchone()
    return row["counter"]


def _generate_patient_identifiers(conn, hospital_id: int) -> tuple[str, str]:
    """Returns (patient_display_id, mrn), generated together and sharing the
    SAME per-hospital sequence number (patient_id_counters) -- zero-padded
    to 4 digits, sequential PER HOSPITAL, not global.

    patient_display_id (DCC-PAT-<seq>, e.g. DCC-PAT-0001) is the portal-
    facing internal id -- hospital-agnostic-looking on purpose, since the
    portal is always scoped to one hospital's own session anyway.

    mrn (MRN-<hospital short code>-<seq>, e.g. MRN-MLH-0001) is the
    hospital-specific clinical/legal record number -- same short-code
    derivation as before.

    Called exactly once per patient, by _upsert_patient()
    (db/repositories/appointments.py) / create_patient_profile()
    (db/repositories/patients.py) the moment a `patients` row is first
    created, and by db/init_db.py's one-time backfill for patients created
    before this feature existed."""
    code = _get_or_create_hospital_short_code(conn, hospital_id)
    seq = _next_patient_display_sequence(conn, hospital_id)
    return f"DCC-PAT-{seq:04d}", f"MRN-{code}-{seq:04d}"


@dataclass
class Appointment:
    id: int
    hospital_id: int
    phone: str
    department_id: str
    department_name: str
    doctor_id: str
    doctor_name: str
    scheduled_at: datetime
    status: str = STATUS_BOOKED
    # Section 12.9: 'whatsapp' (patient self-booking) or 'staff' (portal.py's
    # /portal/new-booking) -- descriptive only, never branched on by booking
    # logic itself (both go through the exact same create_appointment()).
    source: str = "whatsapp"
    # Section 12.12: the patient-facing reference shown in the WhatsApp
    # confirmation message. None only for rows booked before this column
    # existed (never backfilled -- see db/schema.sql's column comment).
    reference_id: str | None = None
    # Patient identity system (Spec.md Section 0): the owning patient's
    # PERMANENT display id (patients.patient_display_id, via a.patient_id --
    # not appointments.reference_id, which is per-booking). None for a row
    # whose patient_id FK is unset (predates Item 8's denormalization and
    # hasn't been backfilled) or whose patient hasn't been backfilled yet.
    patient_display_id: str | None = None
    # Patient identity SEPARATION (Spec.md Section 0): appointments.patient_id
    # itself (was denormalized since Item 8 but never read back onto this
    # dataclass) -- needed to filter "my appointments" down to one linked
    # patient, and to carry the SAME patient through a reschedule.
    patient_id: int | None = None
    # Appointment type step (WhatsApp flow alignment): which of the
    # hospital's appointment_types this booking is, and (only when that
    # type's requires_consent was true) when consent was given -- see
    # db/schema.sql's own comment on appointment_types. None for any
    # appointment predating this feature (never backfilled -- there's no
    # correct type to guess for a historical row).
    appointment_type_id: str | None = None
    consent_given_at: str | None = None
    # Tele-consultation Phase 2 (docs/per-appointment-type-flow-plan.md): the
    # Jitsi Meet URL generated at confirmation time (flows/booking/types/
    # tele_consultation.py's on_booking_confirmed hook). None for every
    # other appointment type, and for any tele booking that predates this
    # column.
    video_link: str | None = None


def _row_to_appointment(row) -> Appointment:
    return Appointment(
        id=row["id"],
        hospital_id=row["hospital_id"],
        phone=row["phone"],
        department_id=row["department_id"],
        department_name=row["department_name"],
        doctor_id=row["doctor_id"],
        doctor_name=row["doctor_name"],
        scheduled_at=datetime.fromisoformat(row["scheduled_at"]),
        status=row["status"],
        source=row["source"],
        reference_id=row["reference_id"],
        patient_display_id=row["patient_display_id"],
        patient_id=row["patient_id"],
        appointment_type_id=row["appointment_type_id"],
        consent_given_at=row["consent_given_at"],
        video_link=row["video_link"],
    )




@dataclass
class Hospital:
    id: int
    name: str
    whatsapp_phone_number_id: str | None
    access_token: str | None  # DB column: meta_access_token_ref
    app_secret: str | None  # DB column: app_secret_ref
    timezone: str
    welcome_message_text: str | None
    reminder_offsets_hours: list[float]
    reminder_template_name: str | None
    is_active: bool
    data_tier: str
    external_api_base_url: str | None
    external_api_key: str | None
    portal_password_hash: str | None
    enabled_features: list[str]
    # Section 12.13: self-serve bot customization -- see db/schema.sql's
    # column comments for what each controls and its "unset" default.
    feature_labels: dict[str, str]
    closing_message_text: str | None
    business_hours_text: str | None
    default_language: str
    language_prompt_enabled: bool
    session_timeout_minutes: int | None
    # CareConnect architecture doc alignment (Spec.md Section 0): see
    # db/schema.sql's own column comments for what each controls.
    require_patient_confirmation: bool
    privacy_notice_text: str | None
    # Tenant-type-driven capability gating (tenant-capability-gating-plan.md):
    # tenant_type is descriptive/default-seeding metadata only, never read
    # directly by feature routes; admin_capabilities (parsed JSON list, via
    # backend/portal/capabilities.py's get_capabilities() -- never read as a
    # raw string outside that module) is what routes actually check.
    tenant_type: str
    admin_capabilities: list[str] | None
    # DPDP Act consent gate (db/schema.sql's own comment on
    # hospitals.dpdp_consent_required/dpdp_consents): default off, same
    # self-serve opt-in convention as require_patient_confirmation above.
    # Kept last among these three (not interleaved) since it's the only one
    # of the three with a default value -- a dataclass field with a default
    # can't precede one without.
    dpdp_consent_required: bool = False
    # migration 0006 -- global, id-derived (db/display_ids.py); shown to
    # hospital users the same way patients.patient_display_id is shown to
    # patients. Nullable at the DB level only for the "INSERT can't know its
    # own id yet" reason that migration's docstring explains -- always set
    # in practice. Defaulted here (not a real "unset" state) only because
    # it's declared after dpdp_consent_required above, which itself needs one.
    display_id: str | None = None


@dataclass
class User:
    id: int
    google_id: str | None
    email: str
    name: str | None
    created_at: str

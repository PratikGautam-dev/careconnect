# db/orm_models.py
"""SQLAlchemy ORM model classes, added one domain at a time as each
db/repositories/*.py file migrates off raw SQL (see the SQLAlchemy ORM +
Alembic migration plan). These map onto tables that already exist --
created/versioned by db/schema.sql + db/migrations/ -- never by
Base.metadata.create_all(); a new column still needs its own Alembic
revision, adding it here alone changes nothing in the database.

Datetime columns are mapped as String, not DateTime: every timestamp in this
schema is stored as ISO-8601 TEXT (db/schema.sql's own header comment
explains why), not a native Postgres TIMESTAMP -- mapping them as DateTime
here would silently change how SQLAlchemy binds/reads these columns from
what every existing raw-SQL repository function already does.

ForeignKey() below mirrors constraints db/schema.sql already enforces in
Postgres -- it's metadata only (documents cardinality/relations so they're
visible by reading this file), not a behavior change: no relationship()
pairs, no cascade, no lazy-loading. A column only gets ForeignKey() here if
the table actually has that REFERENCES clause in schema.sql; a few TEXT
columns that look like foreign keys (e.g. appointments.appointment_type_id)
aren't DB-enforced and are deliberately left plain to match."""
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CareConnectAccount(Base):
    """db/schema.sql's care_connect_accounts table -- see that file's own
    comment for the "why global, not hospital-scoped" identity-layer
    reasoning. status/created_at are Postgres-side defaults ('active',
    now()::text) -- always created via a Core `insert(CareConnectAccount)
    .values()` with NO columns set (never the ORM's own instance-persistence
    path), matching the original `INSERT ... DEFAULT VALUES` exactly; the
    ORM's own new-instance INSERT path sends an explicit NULL for any unset
    column instead of omitting it, which would violate this table's NOT NULL
    constraints -- verified empirically before relying on it."""
    __tablename__ = "care_connect_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str]
    created_at: Mapped[str]
    updated_at: Mapped[str | None]


class WhatsappIdentity(Base):
    """db/schema.sql's whatsapp_identities table. Same Core-insert-only
    caveat as CareConnectAccount above applies to created_at.
    care_connect_account_id is UNIQUE in the DB -- genuinely 1:1 with
    CareConnectAccount today, not 1:M (modeled as a separate table anyway to
    leave room for a future second channel identity per account)."""
    __tablename__ = "whatsapp_identities"

    id: Mapped[int] = mapped_column(primary_key=True)
    care_connect_account_id: Mapped[int] = mapped_column(ForeignKey("care_connect_accounts.id"), unique=True)
    provider_user_id: Mapped[str]
    username: Mapped[str | None]
    phone_number: Mapped[str | None]
    created_at: Mapped[str]
    updated_at: Mapped[str | None]


class AppointmentType(Base):
    """db/schema.sql's appointment_types table -- one row per (hospital, type
    id), PRIMARY KEY (hospital_id, id) matching the table's own composite
    key. is_active/requires_consent/requires_doctor_selection all have
    Postgres-side defaults, but every write path today (db/init_db.py,
    db/seed.py, db/repositories/hospitals.py) always sets every column
    explicitly, so unlike CareConnectAccount above there's no unset-column-
    vs-server-default pitfall to worry about here -- nothing currently
    inserts a row via this model regardless (see appointment_types.py, read-
    only so far)."""
    __tablename__ = "appointment_types"

    id: Mapped[str] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), primary_key=True)
    label: Mapped[str]
    requires_consent: Mapped[bool]
    requires_doctor_selection: Mapped[bool]
    is_active: Mapped[bool]
    sort_order: Mapped[int]


class FaqTopic(Base):
    """db/schema.sql's faq_topics table -- the faq_flow_type's entire data
    model (SPEC Section 14.2)."""
    __tablename__ = "faq_topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    topic_label: Mapped[str]
    answer_text: Mapped[str]
    display_order: Mapped[int]


class DoctorLeave(Base):
    """db/schema.sql's doctor_leave table -- one row per date a doctor is
    unavailable for the whole day (Section 14.7)."""
    __tablename__ = "doctor_leave"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    date: Mapped[str]
    reason: Mapped[str | None]


class DoctorSlot(Base):
    """db/schema.sql's doctor_slots table -- real, persisted bookable slots
    (Section 12.1.1). created_at isn't mapped -- nothing ORM-migrated so far
    (leave.py's DELETE, slots.py's own reads/writes) reads or writes it."""
    __tablename__ = "doctor_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    scheduled_at: Mapped[str]
    blocked: Mapped[bool]
    block_reason: Mapped[str | None]


class Department(Base):
    """db/schema.sql's departments table. id is a caller-generated opaque
    string (h{hospital_id}_{uuid}), not a DB-assigned SERIAL -- see
    create_department()'s own docstring."""
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    name: Mapped[str]


class DoctorRow(Base):
    """db/schema.sql's doctors table -- the FULL, authoritative mapping, per
    doctors.py's own migration (slots.py originally added this as a partial
    model with just max_bookings_per_slot; extended here to every column,
    per that model's own "doctors.py's own migration should define the
    complete model" instruction). Named DoctorRow, not Doctor, to leave that
    name free for a future dataclass -- see UserAccount's docstring for the
    same naming precedent."""
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"))
    name: Mapped[str]
    specialization: Mapped[str | None]
    qualification: Mapped[str | None]
    years_experience: Mapped[int | None]
    working_days: Mapped[str]
    working_hours: Mapped[str]
    slot_duration_minutes: Mapped[int]
    breaks: Mapped[str]
    max_bookings_per_slot: Mapped[int]
    daily_booking_limit: Mapped[int | None]
    online_quota: Mapped[int | None]
    walkin_quota: Mapped[int | None]
    followup_duration_minutes: Mapped[int | None]
    effective_from: Mapped[str | None]
    is_active: Mapped[bool]


class AppointmentRow(Base):
    """db/schema.sql's appointments table -- the FULL, authoritative mapping,
    per appointments.py's own migration (closing the "partial, extend later"
    deferrals slots.py and patients.py both left on this model). Named
    AppointmentRow, not Appointment, since db/models.py already has an
    Appointment dataclass with a different (fuller, JOINED-with-department/
    doctor/patient) shape -- _row_to_appointment() in that module still maps
    the JOIN result (raw or ORM) onto that dataclass unchanged.

    _upsert_patient()/create_appointment() (db/repositories/appointments.py)
    do NOT use this model for their writes -- see those functions' own
    docstrings (advisory-lock + multi-statement-transaction code stays raw
    SQL permanently, same reasoning as patients.py's create_patient_profile()
    trio). appointment_type_id is deliberately plain (no ForeignKey()) --
    schema.sql adds that column with no REFERENCES clause, so it isn't
    DB-enforced against appointment_types' composite (hospital_id, id) key."""
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    phone: Mapped[str]
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"))
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    scheduled_at: Mapped[str]
    status: Mapped[str]
    source: Mapped[str]
    booking_ordinal: Mapped[int]
    reference_id: Mapped[str | None]
    created_at: Mapped[str]
    updated_at: Mapped[str | None]
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"))
    patient_name: Mapped[str | None]
    patient_phone: Mapped[str | None]
    patient_age: Mapped[int | None]
    deleted_at: Mapped[str | None]
    appointment_type_id: Mapped[str | None]
    consent_given_at: Mapped[str | None]
    video_link: Mapped[str | None]


class AppointmentReminder(Base):
    """db/schema.sql's appointment_reminders table."""
    __tablename__ = "appointment_reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"))
    offset_hours: Mapped[float]
    sent_at: Mapped[str]


class UserAccount(Base):
    """db/schema.sql's users table -- Google-OAuth accounts (Section 15).
    Named UserAccount, not User, to avoid colliding with db/models.py's
    User dataclass (db/repositories/users.py's _row_to_user() still maps a
    query result -- ORM or raw -- onto that dataclass; this class is only
    the table mapping used to build the query itself)."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    google_id: Mapped[str | None]
    email: Mapped[str]
    name: Mapped[str | None]
    created_at: Mapped[str]


class HospitalUser(Base):
    """db/schema.sql's hospital_users table -- hospital-ownership join
    table (Section 15)."""
    __tablename__ = "hospital_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str]
    created_at: Mapped[str]


class HandoffRequest(Base):
    """db/schema.sql's handoff_requests table -- the human-handoff queue
    (see that file's own comment for the two unrelated triggers that share
    this one table)."""
    __tablename__ = "handoff_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    phone: Mapped[str]
    reason: Mapped[str]
    message_text: Mapped[str | None]
    status: Mapped[str]
    created_at: Mapped[str]
    resolved_at: Mapped[str | None]
    deleted_at: Mapped[str | None]


class HandoffMessage(Base):
    """db/schema.sql's handoff_messages table -- real two-way conversation
    threading for an active handoff."""
    __tablename__ = "handoff_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    handoff_request_id: Mapped[int] = mapped_column(ForeignKey("handoff_requests.id"))
    direction: Mapped[str]
    message_text: Mapped[str]
    created_at: Mapped[str]


class HospitalRow(Base):
    """db/schema.sql's hospitals table -- the FULL, authoritative mapping
    (every column the table has), named HospitalRow (not Hospital, which is
    db/models.py's dataclass _row_to_hospital() below maps onto). This is
    the model db/repositories/users.py's get_hospitals_for_user() deferred
    to, per that function's own docstring -- update that deferral note if
    this model's shape ever changes in a way that affects it.

    is_active/language_prompt_enabled are genuinely INTEGER columns in
    Postgres (not BOOLEAN) -- db/schema.sql's own column definitions --
    mapped as int here to match; require_patient_confirmation/
    dpdp_consent_required ARE real BOOLEAN columns. Mixed on purpose,
    matching the schema exactly rather than normalizing them to look
    consistent."""
    __tablename__ = "hospitals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    whatsapp_phone_number_id: Mapped[str | None]
    meta_access_token_ref: Mapped[str | None]
    app_secret_ref: Mapped[str | None]
    timezone: Mapped[str]
    welcome_message_text: Mapped[str | None]
    reminder_offsets_hours: Mapped[str]
    reminder_template_name: Mapped[str | None]
    data_tier: Mapped[str]
    external_api_base_url: Mapped[str | None]
    external_api_key: Mapped[str | None]
    portal_password_hash: Mapped[str | None]
    flow_type: Mapped[str]
    enabled_features: Mapped[str | None]
    feature_labels: Mapped[str | None]
    closing_message_text: Mapped[str | None]
    business_hours_text: Mapped[str | None]
    default_language: Mapped[str | None]
    language_prompt_enabled: Mapped[int | None]
    session_timeout_minutes: Mapped[int | None]
    is_active: Mapped[int]
    created_at: Mapped[str]
    patient_id_prefix: Mapped[str | None]
    require_patient_confirmation: Mapped[bool]
    privacy_notice_text: Mapped[str | None]
    dpdp_consent_required: Mapped[bool]
    tenant_type: Mapped[str]
    admin_capabilities: Mapped[str | None]


class PatientVisitNote(Base):
    """db/schema.sql's patient_visit_notes table (Section 12.10)."""
    __tablename__ = "patient_visit_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))
    doctor_id: Mapped[str | None] = mapped_column(ForeignKey("doctors.id"))
    note_text: Mapped[str]
    created_at: Mapped[str]
    created_by_session_id: Mapped[str | None]


class PatientDocument(Base):
    """db/schema.sql's patient_documents table (Section 12.10)."""
    __tablename__ = "patient_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))
    file_name: Mapped[str]
    file_url: Mapped[str]
    uploaded_at: Mapped[str]
    uploaded_by_session_id: Mapped[str | None]
    sent_to_whatsapp_at: Mapped[str | None]


class PatientRow(Base):
    """db/schema.sql's patients table -- the full mapping (12 columns, matches
    the table exactly). Named PatientRow, not Patient, to leave that name
    free for a future dataclass -- see UserAccount's docstring for the same
    naming precedent. create_patient_profile()/link_existing_patient()/
    _link_patient_under_cap() (db/repositories/patients.py) do NOT use this
    model -- see those functions' own docstrings for why (advisory-lock +
    multi-statement-transaction code stays raw SQL permanently).
    patient_display_id (DCC-PAT-<seq>) and mrn (MRN-<hospital short code>
    -<seq>) are generated together, same sequence number, by
    db/models.py's _generate_patient_identifiers() -- see migration 0003."""
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    phone: Mapped[str]
    name: Mapped[str | None]
    date_of_birth: Mapped[str | None]
    gender: Mapped[str | None]
    address: Mapped[str | None]
    age: Mapped[int | None]
    created_at: Mapped[str]
    status: Mapped[str]
    patient_display_id: Mapped[str | None]
    mrn: Mapped[str | None]


class PatientLink(Base):
    """db/schema.sql's patient_links table -- the full mapping. See
    PatientRow's docstring for the same "advisory-lock code stays raw"
    caveat on the write path (_link_patient_under_cap). patient_id has no
    unique constraint here (unlike WhatsappIdentity.care_connect_account_id
    above) -- this is the genuine M:M join between whatsapp_phone and
    patients: one phone can hold up to MAX_ACTIVE_PATIENT_LINKS active
    links, and nothing stops the same patient being linked from a second
    phone. care_connect_account_id is NOT NULL (migration 0002) -- every
    write path (patients.py's _link_patient_under_cap(), init_db.py's
    _backfill_patient_links()) stamps it via _get_or_create_account_in_conn()
    at INSERT time; whatsapp_phone remains the actual join key, this column
    is not yet read by any lookup."""
    __tablename__ = "patient_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    whatsapp_phone: Mapped[str]
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    relationship_label: Mapped[str | None]
    linked_at: Mapped[str]
    unlinked_at: Mapped[str | None]
    service_consent: Mapped[bool]
    marketing_consent: Mapped[bool]
    care_connect_account_id: Mapped[int] = mapped_column(ForeignKey("care_connect_accounts.id"))


class DpdpConsent(Base):
    """db/schema.sql's dpdp_consents table -- one row per (hospital,
    whatsapp_phone) that has an on-file AGREED DPDP consent decision. See
    db/repositories/consent.py for the read/write logic; only the read side
    (has_agreed_to_dpdp_consent) is ORM-based so far -- record_dpdp_consent()
    is still raw SQL, see that function's own docstring for why."""
    __tablename__ = "dpdp_consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    whatsapp_phone: Mapped[str]
    care_connect_account_id: Mapped[int | None] = mapped_column(ForeignKey("care_connect_accounts.id"))
    consented_at: Mapped[str]

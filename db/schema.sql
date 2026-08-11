-- db/schema.sql
-- SPEC Section 4 data model. Postgres (Neon), per Section 6/12.6 -- migrated
-- off SQLite before real production load; db/repository.py is the only module
-- that knows this is Postgres (via db/connection.py), and even it barely
-- changed: datetimes are still stored as ISO-8601 TEXT (written by Python's
-- .isoformat(), read back with datetime.fromisoformat()) exactly as they were
-- under SQLite, since Postgres's TEXT type and lexical ISO-8601 string
-- ordering behave identically for our purposes -- there was no need to
-- retype those columns as TIMESTAMP to get a correct migration. hospital_id
-- is on every table from day one per Section 4/12.2, even now that only one
-- real hospital exists — the point is to never have to retrofit this column
-- onto live data later.
--
-- Safe to re-run: every statement is IF NOT EXISTS (Postgres supports this
-- for CREATE TABLE/CREATE INDEX the same as SQLite did).

CREATE TABLE IF NOT EXISTS hospitals (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    -- UNIQUE (Phase 10, Section 12.1): the onboarding wizard relies on this
    -- constraint, not application logic, to reject a duplicate phone_number_id
    -- that would otherwise break Phase 9's per-message routing (two hospitals
    -- can't both claim the same incoming number). CREATE TABLE IF NOT EXISTS
    -- won't retroactively add this to a database created before this change.
    whatsapp_phone_number_id TEXT UNIQUE,
    meta_access_token_ref TEXT,
    app_secret_ref TEXT,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    welcome_message_text TEXT,
    reminder_offsets_hours TEXT NOT NULL DEFAULT '[24]',
    reminder_template_name TEXT,
    -- Section 12.6 data connection tier, chosen per-hospital during onboarding
    -- (Section 12.1 Step 6). Tier 2's api_base_url/api_key are only ever stored
    -- here, not acted on -- no connector logic exists yet (built only once a
    -- real Tier 2 hospital exists). Tier 3 stores neither; it's a manually
    -- assisted, non-self-serve case (Section 12.6).
    data_tier TEXT NOT NULL DEFAULT 'tier1' CHECK (data_tier IN ('tier1', 'tier2', 'tier3')),
    external_api_base_url TEXT,
    external_api_key TEXT,
    -- Section 12.7: the hospital-staff bookings portal's login credential --
    -- salted PBKDF2-SHA256 (db/repository.py:hash_portal_password()), never
    -- the plaintext password. NULL means the hospital hasn't set one yet
    -- (portal login is simply unavailable until it does, via onboarding or
    -- the edit-tenant form) -- not enforced UNIQUE, since two hospitals can
    -- legitimately pick the same password and get different hashes (each
    -- has its own random salt); portal.py finds the right hospital by
    -- hashing the login attempt against every stored hash, not by lookup.
    portal_password_hash TEXT,
    -- Section 14.1 (superseded by 14.5): originally "which single conversation
    -- shape this tenant runs" -- kept as a historical/unread column (never
    -- dropped, per this file's existing no-destructive-migrations convention)
    -- now that Section 14.5 replaced it with enabled_features below. Nothing
    -- in the app reads this column anymore except the one-time backfill in
    -- db/init_db.py that seeds enabled_features for rows from before that change.
    flow_type TEXT NOT NULL DEFAULT 'booking',
    -- Section 14.5: which capabilities this tenant's WhatsApp number offers
    -- patients, as a JSON array of feature keys (e.g. ["booking","reschedule",
    -- "cancel","faq"]) -- a hospital enables a SET of features simultaneously
    -- rather than picking one exclusive flow_type (the model above). The IDLE
    -- main menu (flows.py) shows only the enabled ones; tapping one hands the
    -- conversation to that feature's own handler/state machine. NULL means
    -- "not yet migrated from flow_type" -- db/init_db.py backfills every NULL
    -- row once, at startup; every hospital created after Section 14.5 always
    -- gets a real value at creation time, never NULL.
    enabled_features TEXT,
    -- Section 12.13: self-serve bot customization beyond enabled_features'
    -- on/off toggles -- everything below is optional (NULL = use the fixed
    -- default already hardcoded in flows.py/core/booking_flow.py/
    -- core/translations.py), so an existing hospital that's never touched
    -- these fields keeps behaving byte-for-byte as before this section.
    --
    -- feature_labels: JSON object, feature key -> custom display label (e.g.
    -- {"booking": "Schedule a consultation"}), overriding the fixed
    -- translations.py label for that one row in the main menu. Only covers
    -- REAL_FEATURES keys; an unrecognized key is simply never read.
    feature_labels TEXT,
    -- closing_message_text: APPENDED (not replacing) after the standard
    -- booking/cancel/reschedule confirmation text -- e.g. "Thank you for
    -- choosing City Hospital. For emergencies, call 102."
    closing_message_text TEXT,
    -- business_hours_text: shown as an extra line in the "hospital_info"
    -- feature's reply if set -- purely informational, never enforced against
    -- real slot availability (which already comes from each doctor's own
    -- working_days/working_hours).
    business_hours_text TEXT,
    -- default_language: which language the language-picker highlights/
    -- defaults to (still just "en"/"hi", core/translations.py's
    -- SUPPORTED_LANGUAGES) -- NULL means "en", same as today.
    default_language TEXT,
    -- language_prompt_enabled: FALSE lets a single-language hospital (e.g.
    -- English-only) skip the language picker step entirely and go straight
    -- to the main menu in default_language every fresh conversation, instead
    -- of offering a language nobody at that hospital ever uses. NULL/TRUE
    -- (the default) keeps today's picker-shown-first behavior.
    language_prompt_enabled INTEGER,
    -- session_timeout_minutes: replaces core/history.py's fixed 30-minute
    -- SESSION_TIMEOUT_SECONDS constant for this hospital specifically.
    -- CHECK bounds (5-120) match the portal settings form's own validation --
    -- enforced at the DB level too so a direct/future write path can't set
    -- something nonsensical. NULL means "use the 30-minute default."
    session_timeout_minutes INTEGER CHECK (session_timeout_minutes IS NULL OR (session_timeout_minutes BETWEEN 5 AND 120)),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (now()::text)
);

-- CREATE TABLE IF NOT EXISTS above won't retroactively add these columns to a
-- database created before each was added (same limitation already noted for
-- whatsapp_phone_number_id's UNIQUE constraint) -- this makes them idempotent
-- and self-healing on the next app startup against the live database too.
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS portal_password_hash TEXT;
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS flow_type TEXT NOT NULL DEFAULT 'booking';
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS enabled_features TEXT;
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS feature_labels TEXT;
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS closing_message_text TEXT;
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS business_hours_text TEXT;
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS default_language TEXT;
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS language_prompt_enabled INTEGER;
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS session_timeout_minutes INTEGER CHECK (session_timeout_minutes IS NULL OR (session_timeout_minutes BETWEEN 5 AND 120));

-- id is a human-readable slug (e.g. "cardiology") rather than a surrogate integer,
-- so it can be used directly as a WhatsApp list-reply id, same as before this
-- migration. Known limitation: id is globally unique, not (hospital_id, id)
-- composite-unique, so two hospitals can't both have an id="cardiology" row yet.
-- Fine for the single hospital Tier 1 actually runs today; revisit before a
-- second hospital is onboarded (Phase 9, Section 12.4).
CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    name TEXT NOT NULL
);

-- specialization/qualification/years_experience are display-only. working_days
-- (comma-separated "Mon".."Sun"), working_hours (comma-separated "HH:MM-HH:MM"
-- ranges) and slot_duration_minutes are the doctor's working pattern that
-- db/repository.py:generate_slots_for_doctor() reads to produce real rows in
-- doctor_slots below (Section 12.1.1) -- a doctor with no working_days/
-- working_hours simply generates zero slots, rather than erroring.
--
-- Section 14.7 (richer scheduling) additions below -- deliberately kept flat
-- on this table rather than a separate doctor_schedule_settings table, same
-- reasoning as working_days/working_hours already being flat columns here:
-- one doctor has exactly one active schedule pattern at a time, so a 1:1
-- side table would just be this table with extra JOINs, no real normalization
-- benefit. breaks mirrors working_hours' own shape/convention deliberately
-- (comma-separated "HH:MM-HH:MM" ranges, applied uniformly across every
-- working day, not a per-day structure) -- working_hours already applies the
-- same shift pattern to every working day, so per-day breaks would be an
-- inconsistent one-off; a break must fall inside some shift on any day that
-- shift runs, which is what "per working-day" means in practice here.
CREATE TABLE IF NOT EXISTS doctors (
    id TEXT PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    department_id TEXT NOT NULL REFERENCES departments(id),
    name TEXT NOT NULL,
    specialization TEXT,
    qualification TEXT,
    years_experience INTEGER,
    working_days TEXT NOT NULL DEFAULT '',
    working_hours TEXT NOT NULL DEFAULT '',
    slot_duration_minutes INTEGER NOT NULL DEFAULT 30,
    -- Comma-separated "HH:MM-HH:MM" ranges excluded from slot generation
    -- within whichever shift each one falls inside (e.g. a lunch break).
    breaks TEXT NOT NULL DEFAULT '',
    -- How many separate BOOKED appointments this doctor can hold at the exact
    -- same scheduled_at (default 1 = today's existing behavior, one patient
    -- per slot). >1 is enforced via appointments.booking_ordinal below, not
    -- by relaxing the old single-booking unique index.
    max_bookings_per_slot INTEGER NOT NULL DEFAULT 1,
    -- NULL = uncapped. Enforced at slot-generation time (generate_slots_for_doctor
    -- stops generating more slots for a given date once this many would exist),
    -- not at booking time -- once a day's slots are generated, patients can
    -- book any of them same as always.
    daily_booking_limit INTEGER,
    -- Reserved split of daily_booking_limit between WhatsApp-booked (online)
    -- and front-desk-created (walk-in) patients. Stored and validated now but
    -- NOT enforced anywhere yet -- the staff portal has no walk-in booking
    -- creation path yet (upcoming work), so there's nothing on the walk-in
    -- side to actually split capacity against.
    online_quota INTEGER,
    walkin_quota INTEGER,
    -- A separate, typically shorter duration for follow-up visits. NULL means
    -- "no distinct follow-up duration configured" -- the booking flow falls
    -- back to slot_duration_minutes for a follow-up in that case.
    followup_duration_minutes INTEGER,
    -- The date this doctor's CURRENT working_days/working_hours/breaks/etc.
    -- pattern takes effect. NULL means "effective immediately / no
    -- restriction" (matches every doctor's behavior before this column
    -- existed). update_doctor()'s slot regeneration only replaces slots dated
    -- on/after this date, leaving any earlier still-unbooked slots (generated
    -- under the doctor's previous pattern) untouched -- a schedule change
    -- applies going forward, not retroactively.
    effective_from TEXT,
    -- Staff-controlled on/off switch, independent of leave dates/working
    -- hours: a hospital may want a doctor to simply stop appearing as
    -- bookable (resigned, long-term unavailable, etc.) without deleting
    -- their record or editing their schedule. FALSE excludes them from
    -- get_doctors() (the connector interface both the WhatsApp bot and the
    -- staff new-booking flow read from) entirely -- same enforcement point,
    -- so "off" means off everywhere a patient or staff member could book
    -- them, not just the bot. Portal's own doctor MANAGEMENT list
    -- (get_all_doctors_for_hospital) still shows inactive doctors, so staff
    -- can toggle them back on.
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS breaks TEXT NOT NULL DEFAULT '';
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS max_bookings_per_slot INTEGER NOT NULL DEFAULT 1;
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS daily_booking_limit INTEGER;
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS online_quota INTEGER;
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS walkin_quota INTEGER;
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS followup_duration_minutes INTEGER;
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS effective_from TEXT;
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- Section 14.7: one row per date a doctor is unavailable for the whole day
-- (leave/holiday/on-call elsewhere). generate_slots_for_doctor() skips any
-- date present here entirely for that doctor, rather than generating slots
-- and hoping nobody books them. UNIQUE(doctor_id, date) makes re-adding the
-- same leave date harmlessly idempotent instead of a duplicate row.
CREATE TABLE IF NOT EXISTS doctor_leave (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    doctor_id TEXT NOT NULL REFERENCES doctors(id),
    date TEXT NOT NULL,
    reason TEXT,
    UNIQUE(doctor_id, date)
);

-- Real, persisted bookable slots (Section 12.1.1) generated from a doctor's
-- working pattern above -- replaces the earlier synthetic/computed approach
-- (db/repository.py's old get_slots() built a fixed 3-day/10:00+15:00 list on
-- the fly for every doctor regardless of their actual hours). Generated for a
-- rolling window (e.g. next 14 days) at onboarding time and extended by a
-- periodic top-up job as days pass (same pattern as reminders/scheduler.py).
-- UNIQUE(doctor_id, scheduled_at) is what makes the top-up job idempotent --
-- re-running generate_slots_for_doctor() for a window that's already partly
-- populated is a safe ON CONFLICT DO NOTHING, not a duplicate-row risk.
CREATE TABLE IF NOT EXISTS doctor_slots (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    doctor_id TEXT NOT NULL REFERENCES doctors(id),
    scheduled_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (now()::text),
    UNIQUE(doctor_id, scheduled_at)
);

-- No "patients" table (Section 4 has one, but nothing in this build normalizes
-- patients out of appointments.phone yet). Available slots ARE now persisted
-- (doctor_slots above, Section 12.1.1, Phase 10 extension) rather than computed
-- on the fly -- db/repository.py:get_slots() reads real rows there, filtering
-- out ones with a booked appointment below, same as before this change.
--
-- Section 12.9 (staff-created bookings): Section 4's original data model
-- always planned a `patients` table ("phone_number (unique, WhatsApp-linked),
-- name, hospital_id") but nothing before this normalized patients out of
-- appointments.phone -- there was simply no need to until staff-side patient
-- SEARCH (by name, not just phone) required somewhere to actually store a
-- name. Deliberately minimal -- exactly what Section 4 originally specified,
-- nothing more. UNIQUE(hospital_id, phone), not phone alone: two different
-- hospitals' patients can share a phone number (Section 12.2's own tenant-
-- isolation discipline applies here too). db/init_db.py backfills a row (name
-- NULL) for every distinct (hospital_id, phone) pair already in appointments
-- so existing WhatsApp-only patients are searchable by phone immediately.
CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    phone TEXT NOT NULL,
    name TEXT,
    -- Section 12.10: basic demographics for the patient-record feature, all
    -- nullable -- none required at creation (WhatsApp self-bookings still
    -- never collect any of this; only ever filled in later by staff via the
    -- patient detail page). Deliberately no medical/clinical fields yet
    -- (allergies, conditions, diagnosis codes) -- out of scope for this
    -- first version, see Section 12.10.
    date_of_birth TEXT,
    gender TEXT,
    address TEXT,
    -- Section 12.11 (language selection + patient name/age during booking):
    -- deliberately separate from date_of_birth above, not a second way to
    -- express the same fact -- a WhatsApp patient typing "34" is a much
    -- lower-friction ask than collecting a full birthdate over chat, and the
    -- staff portal's date_of_birth field (Section 12.10) stays the source of
    -- truth when a hospital does have it. The two are never reconciled
    -- against each other.
    age INTEGER,
    created_at TEXT NOT NULL DEFAULT (now()::text),
    UNIQUE(hospital_id, phone)
);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS date_of_birth TEXT;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS gender TEXT;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS age INTEGER;

-- No reminder_sent_at column (an earlier version had one) — reminder status is
-- now tracked per-offset in appointment_reminders below, not as a single flag
-- here. Note CREATE TABLE IF NOT EXISTS won't retroactively drop that column
-- from a database created before this change; it's just a harmless unused
-- leftover there, nothing reads or writes it anymore.
CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    phone TEXT NOT NULL,
    department_id TEXT NOT NULL REFERENCES departments(id),
    doctor_id TEXT NOT NULL REFERENCES doctors(id),
    scheduled_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'booked' CHECK (status IN ('booked', 'cancelled', 'rescheduled')),
    -- Section 12.9: 'whatsapp' (patient self-booking, core/booking_flow.py) or
    -- 'staff' (portal.py's /portal/new-booking, front-desk/phone bookings) --
    -- both go through the exact same db.create_appointment()/get_slots()
    -- availability and double-booking logic, this column is purely
    -- descriptive/for later reporting, never branched on for booking logic
    -- itself. CHECK constraint only applies to freshly created tables (same
    -- caveat as the status CHECK above) -- not retroactively added to an
    -- already-existing database.
    source TEXT NOT NULL DEFAULT 'whatsapp' CHECK (source IN ('whatsapp', 'staff')),
    -- Section 14.7: which "seat" within a doctor's max_bookings_per_slot this
    -- booking occupies at its scheduled_at (0-indexed, 0 for every doctor
    -- whose max_bookings_per_slot is the default 1 -- identical to how the
    -- old doctor_id+scheduled_at-only uniqueness behaved). Assigned by
    -- db/repository.py:create_appointment()'s count-then-insert-with-retry
    -- loop, never chosen by a caller.
    booking_ordinal INTEGER NOT NULL DEFAULT 0,
    -- Section 12.12: a patient-facing booking reference shown in the WhatsApp
    -- confirmation message ("Reference ID: apt_..."), generated once at
    -- create_appointment() time from a millisecond-precision epoch (not
    -- second-precision -- two different patients booking in the same second
    -- is realistic at any real hospital's traffic, same millisecond isn't).
    -- Deliberately no UNIQUE constraint: a same-millisecond collision would
    -- raise IntegrityError, which core/booking_flow.py already treats as
    -- "the exact slot was just taken" and reroutes to slot selection -- a
    -- confusing wrong message for what would actually be a reference_id
    -- collision, not a real double-booking. Nullable/no backfill for rows
    -- booked before this column existed -- there's no natural value to
    -- backfill them with.
    reference_id TEXT,
    created_at TEXT NOT NULL DEFAULT (now()::text),
    -- Section 12.8 (staff dashboard): when this row's status last changed
    -- (cancel/reschedule), set by db/repository.py's cancel_appointment()/
    -- mark_rescheduled(). NULL for a still-'booked' row that's never changed
    -- status -- read as COALESCE(updated_at, created_at) everywhere, so a
    -- never-changed row's "event time" is just its booking time. Added
    -- specifically so the dashboard's recent-activity feed can show a
    -- cancellation/reschedule at the time it actually happened, not
    -- mislabeled with the original booking's created_at.
    updated_at TEXT
);
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS booking_ordinal INTEGER NOT NULL DEFAULT 0;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS updated_at TEXT;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS reference_id TEXT;

-- Which reminder offset(s) (SPEC Section 4's hospitals.reminder_offsets_hours,
-- e.g. a hospital configured for both 24h-before AND 1h-before) have already
-- fired for a given appointment. A single reminder_sent_at timestamp on
-- appointments (this table's predecessor) can only represent "reminded or not",
-- which silently prevented a second, differently-timed reminder from ever
-- firing for the same appointment — this table tracks each offset independently.
-- UNIQUE + ON CONFLICT DO NOTHING (see db/repository.py:mark_reminded) is what
-- actually prevents a duplicate send for the same offset, not application logic.
CREATE TABLE IF NOT EXISTS appointment_reminders (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    appointment_id INTEGER NOT NULL REFERENCES appointments(id),
    offset_hours REAL NOT NULL,
    sent_at TEXT NOT NULL DEFAULT (now()::text),
    UNIQUE(appointment_id, offset_hours)
);

-- Double-booking prevention at the DB level (ties into Phase 8's race-condition
-- handling), extended by Section 14.7 to allow more than one BOOKED
-- appointment per doctor per exact scheduled_at when max_bookings_per_slot > 1:
-- uniqueness is now on (doctor_id, scheduled_at, booking_ordinal), not just
-- (doctor_id, scheduled_at). For the default max_bookings_per_slot = 1 case
-- every booking_ordinal is 0, so this is byte-for-byte the same guarantee as
-- before for every doctor that hasn't opted into >1. db/repository.py's
-- create_appointment() assigns booking_ordinal by counting existing bookings
-- at that scheduled_at and retrying on a losing race (an IntegrityError from
-- this exact index, same exception core/booking_flow.py already catches and
-- turns into a friendly "that slot was just taken" message -- Phase 8), never
-- by the caller. The old two-column version of this index is dropped, not
-- kept alongside -- it would incorrectly block the 2nd..Nth booking for any
-- doctor with max_bookings_per_slot > 1, so keeping it would silently break
-- the feature it's dropped to enable; this is a constraint, not stored data,
-- so it's exempt from this file's normal no-destructive-migrations convention.
DROP INDEX IF EXISTS ux_appointments_doctor_slot_booked;
CREATE UNIQUE INDEX IF NOT EXISTS ux_appointments_doctor_slot_ordinal_booked
    ON appointments(doctor_id, scheduled_at, booking_ordinal)
    WHERE status = 'booked';

-- Present per Section 4's schema, but NOT wired up in this build — core/history.py's
-- Redis/in-memory session store (get_session_store()) remains the actual mechanism
-- booking_flow.py uses for conversation state. Migrating session storage onto this
-- table was not part of this task's scope (only mock_data.py/mock_appointments.py
-- were asked to move onto the real DB) and would be a separate change.
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id SERIAL PRIMARY KEY,
    patient_phone TEXT NOT NULL,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    current_state TEXT NOT NULL DEFAULT 'IDLE',
    context TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (now()::text),
    UNIQUE(patient_phone, hospital_id)
);

-- SPEC Section 14.2: the FAQ flow_type's entire data model -- deliberately
-- just this one table. A pure FAQ-flow tenant needs no departments, doctors,
-- doctor_slots, or appointments at all, which is exactly why forcing a
-- non-booking tenant (DaaPrime) through booking's placeholder department/
-- doctor data was the wrong fit (Section 14.0) that this flow type replaces.
-- display_order is a plain sort key (not a UNIQUE constraint) -- faq_flow.py
-- orders by it, then by id as a tiebreaker; ties are harmless, not an error.
CREATE TABLE IF NOT EXISTS faq_topics (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    topic_label TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0
);

-- Human-handoff queue: a "needs a person" inbox for the staff portal, fed by
-- two different triggers that otherwise have nothing to do with each other --
-- a patient deliberately tapping "Talk to Reception" (reception_handoff,
-- promoted from a PLACEHOLDER_FEATURE to real, flows.py), and the webhook
-- handler catching a genuine unexpected exception while processing a message
-- (core/main.py's _process_message, previously only caught
-- ConnectorNotImplementedError specifically and let anything else propagate
-- uncaught with no patient-facing reply and no record of what happened).
-- Both funnel into this one table/queue rather than two separate mechanisms,
-- since a staff member reviewing "what needs my attention" doesn't care which
-- trigger fired -- reason is kept only so the portal can label the two cases
-- differently, not to branch behavior anywhere.
CREATE TABLE IF NOT EXISTS handoff_requests (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    phone TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('patient_requested', 'system_error')),
    -- What the patient sent (patient_requested) or a short description of
    -- what failed (system_error) -- context for the staff member, not
    -- parsed/branched on by any code.
    message_text TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    created_at TEXT NOT NULL DEFAULT (now()::text),
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_handoff_requests_hospital_status ON handoff_requests(hospital_id, status);

-- Section 12.10: patient records, first version -- visit history (existing
-- `appointments` rows already give this, nothing new needed there), free-text
-- notes, and document upload/WhatsApp-send. Deliberately NOT full clinical
-- records: no diagnosis coding, no allergy/condition tracking -- see
-- Spec.md Section 12.10 for the explicit scope line and the audit-logging
-- follow-up this table's `created_by_session_id`/`uploaded_by_session_id`
-- columns are a deliberate stand-in for (real per-staff accounts don't exist
-- yet -- portal auth is still one shared password per hospital, Section 12.7
-- -- so a note/document can only be traced back to a *login session*, not a
-- named person; flagged as a priority follow-up given this is more sensitive
-- data than appointment scheduling).
CREATE TABLE IF NOT EXISTS patient_visit_notes (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    -- Nullable: a note can exist without a formal appointment (e.g. a
    -- walk-in the front desk never logged as a booking).
    appointment_id INTEGER REFERENCES appointments(id),
    doctor_id TEXT REFERENCES doctors(id),
    note_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (now()::text),
    created_by_session_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_patient_visit_notes_hospital_patient ON patient_visit_notes(hospital_id, patient_id);

CREATE TABLE IF NOT EXISTS patient_documents (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    appointment_id INTEGER REFERENCES appointments(id),
    file_name TEXT NOT NULL,
    -- The object-storage KEY (core/storage.py), not a public URL -- files are
    -- private, never a public bucket; every read goes through
    -- storage.get_signed_url(), which mints a short-lived expiring URL on
    -- demand rather than this column ever storing something directly
    -- browsable.
    file_url TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (now()::text),
    uploaded_by_session_id TEXT,
    sent_to_whatsapp_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_patient_documents_hospital_patient ON patient_documents(hospital_id, patient_id);

-- Section 15 (Google OAuth + per-user identity): one row per Google account
-- that's ever signed in. google_id is nullable -- a platform admin can
-- pre-create a placeholder row by email alone via /admin/edit-tenant's
-- owner-assignment field (the migration path for hospital #1/DaaPrime,
-- onboarded before this section existed and still using portal_password_hash
-- login); the OAuth callback matches an incoming Google sign-in by google_id
-- first, then by email, backfilling google_id onto that same placeholder row
-- rather than creating a second, disconnected one for the same person.
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    google_id TEXT UNIQUE,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    created_at TEXT NOT NULL DEFAULT (now()::text)
);

-- Join table, not a single owner_user_id column on hospitals -- deliberately
-- future-proofs for real per-staff accounts (Section 12.10's flagged
-- follow-up: patient notes/documents can currently only be traced to a
-- login session, not a named person) without a later migration off a
-- single-owner column onto a join table. role is stored but not yet
-- enforced differently (every row created today is 'owner') -- same
-- "store now, enforce later" pattern as doctors.online_quota/walkin_quota
-- (Section 14.7).
CREATE TABLE IF NOT EXISTS hospital_users (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    role TEXT NOT NULL DEFAULT 'owner',
    created_at TEXT NOT NULL DEFAULT (now()::text),
    UNIQUE(hospital_id, user_id)
);

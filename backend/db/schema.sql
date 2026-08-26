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
    -- CHECK bounds (2-120 -- widened from 5-120, see the ALTER CONSTRAINT
    -- migration below) match the portal settings form's own validation --
    -- enforced at the DB level too so a direct/future write path can't set
    -- something nonsensical. NULL means "use the 30-minute default."
    session_timeout_minutes INTEGER CHECK (session_timeout_minutes IS NULL OR (session_timeout_minutes BETWEEN 2 AND 120)),
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
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS session_timeout_minutes INTEGER CHECK (session_timeout_minutes IS NULL OR (session_timeout_minutes BETWEEN 2 AND 120));
-- Patient identity system (Spec.md Section 0): the "<hospital-short-code>" in
-- a patient_display_id (patients table below, e.g. PAT-MLH-0001). NULL means
-- "not derived yet" -- db/repository.py's _get_or_create_hospital_short_code()
-- derives one from the hospital's own `name` (first letter of each word,
-- e.g. "Metro Lifeline Hospital" -> "MLH") the first time it's needed and
-- stores it here permanently, so it's computed once and never drifts even if
-- the hospital is later renamed. Deliberately NOT enforced UNIQUE across
-- hospitals (confirmed with the user) -- two differently-onboarded hospitals
-- can derive the same code (e.g. two "City Hospital"s), which only makes
-- PAT-CH-0001 cosmetically ambiguous if compared side by side; every real
-- lookup is already hospital_id-scoped, so this can never cause a wrong
-- patient to be found. Same accepted-limitation precedent departments.id's
-- own comment already documents for a similar global-uniqueness gap.
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS patient_id_prefix TEXT;
-- CareConnect architecture doc alignment (Spec.md Section 0): Section 11 --
-- "depending on the hospital's security requirements" -- a single linked
-- patient's zero-friction auto-continue is the DEFAULT (matches every
-- phone's behavior before this column existed), but a hospital can opt
-- into an explicit "You are accessing services for: {name} -- Continue?"
-- confirmation even for exactly one linked patient.
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS require_patient_confirmation BOOLEAN NOT NULL DEFAULT FALSE;
-- Section 20 (Consent & Privacy menu item): static, hospital-configurable
-- privacy notice text shown on that screen. NULL means "not configured yet"
-- -- the Consent & Privacy screen falls back to a fixed generic notice
-- rather than showing nothing.
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS privacy_notice_text TEXT;
-- DPDP Act consent gate (default off, same "self-serve, opt-in" convention
-- as require_patient_confirmation above): when TRUE, a fresh conversation
-- must tap "I Agree" on a fixed DPDP notice (core/translations.py's
-- dpdp_consent_body) right after language selection, BEFORE any patient
-- identity is resolved -- see dpdp_consents below for where the decision
-- is recorded. A hospital that doesn't need this (or handles consent
-- outside the bot) leaves it off and the flow is unchanged.
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS dpdp_consent_required BOOLEAN NOT NULL DEFAULT FALSE;

-- [tenant-capability-gating] (docs/tenant-capability-gating-plan.md, SQL
-- step -- DONE): hospital vs. clinic tenant gating, WITHOUT any
-- if tenant_type == 'clinic' branches in feature code. tenant_type is purely
-- descriptive/default-seeding metadata; 'hospital' default preserves today's
-- behavior (full admin capability) for every existing row.
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS tenant_type TEXT NOT NULL DEFAULT 'hospital';
ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS hospitals_tenant_type_check;
ALTER TABLE hospitals ADD CONSTRAINT hospitals_tenant_type_check
    CHECK (tenant_type IN ('hospital', 'clinic'));
-- admin_capabilities: JSON array of staff-portal capability keys this tenant
-- has (e.g. ["manage_doctors","manage_departments","manage_appointment_types",
-- "manage_bookings","manage_settings","manage_staff"] -- see
-- backend/portal/capabilities.py once added, next step of the plan above).
-- Distinct from enabled_features above (patient-facing WhatsApp menu) -- this
-- one gates staff/admin PORTAL routes instead; every route delegates to the
-- same has_capability() check rather than branching on tenant_type directly,
-- so adding/removing a capability per tenant never requires new backend
-- logic. NULL means "not yet backfilled from tenant_type" -- db/init_db.py's
-- _backfill_admin_capabilities() (added alongside this column) fills every
-- NULL row once, at startup, same convention as
-- _backfill_enabled_features() above; every hospital created after this
-- section always gets a real value at creation time, never NULL.
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS admin_capabilities TEXT;

-- Widens the CHECK bound below from 5-120 to 2-120 (a 2-minute idle-timeout
-- option, for testing/demoing the flow without a real 5+ minute wait) --
-- the ADD COLUMN IF NOT EXISTS above only fires on a database created
-- before this column existed at all, so on the real, already-migrated
-- database it's a no-op and this explicit ALTER is the only thing that
-- actually widens the constraint. DROP+ADD (not ALTER CHECK, which
-- Postgres doesn't support) is safe to re-run on every startup: same end
-- state every time, a fast metadata-only operation, no data movement.
ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS hospitals_session_timeout_minutes_check;
ALTER TABLE hospitals ADD CONSTRAINT hospitals_session_timeout_minutes_check
    CHECK (session_timeout_minutes IS NULL OR (session_timeout_minutes BETWEEN 2 AND 120));

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
-- Item 1 (Spec.md Section 0): a manual per-slot override on top of the
-- normal generated availability -- distinct from doctor_leave (blocks a
-- whole day) and doctors.is_active (blocks the whole doctor). db.get_slots()
-- (the one function both the WhatsApp bot and staff new-booking read
-- through) excludes any blocked=TRUE row, same enforcement-at-one-point
-- pattern is_active already established.
ALTER TABLE doctor_slots ADD COLUMN IF NOT EXISTS blocked BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE doctor_slots ADD COLUMN IF NOT EXISTS block_reason TEXT;

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
-- CareConnect architecture doc alignment (Spec.md Section 0), Section 18's
-- recommended Patient Master state model: CREATED -> ACTIVE -> {BLOCKED,
-- INACTIVE}. Collapsed CREATED into ACTIVE deliberately (confirmed with the
-- user) -- nothing in this system has a distinct "pending hospital
-- approval" step between creating a patient record and it being usable, so
-- a literal CREATED dwell-state would never be observably different from
-- ACTIVE; every new patient starts directly at 'active'. 'blocked'/
-- 'inactive' are real, staff-settable states (db.set_patient_status(),
-- the portal's patient detail page) -- a blocked/inactive patient is
-- excluded from get_active_patients_for_phone() (so they can't be selected
-- or auto-continued to) without touching patient_links at all, keeping
-- "this patient can't be used right now" (a hospital-side fact about the
-- PATIENT) separate from "this phone doesn't have them linked" (a
-- CHANNEL-side fact about the LINK) -- exactly the distinction Section 18
-- itself calls out ("A patient can remain ACTIVE in the hospital system
-- while their WhatsApp link is UNLINKED").
ALTER TABLE patients ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE patients DROP CONSTRAINT IF EXISTS patients_status_check;
ALTER TABLE patients ADD CONSTRAINT patients_status_check
    CHECK (status IN ('active', 'blocked', 'inactive'));
-- Patient identity system (Spec.md Section 0): a permanent, human-readable
-- id (PAT-<hospital short code>-<sequential number>, e.g. PAT-MLH-0001) --
-- distinct from this row's own internal SERIAL `id` (never patient-facing)
-- and from appointments.reference_id (per-BOOKING, regenerated every visit;
-- this is per-PATIENT, generated exactly ONCE and never regenerated).
-- Generated by db/repository.py's _upsert_patient() the moment a `patients`
-- row is FIRST created for a (hospital_id, phone) pair -- detected via
-- Postgres's `xmax = 0` trick on the same INSERT ... ON CONFLICT statement
-- that upsert already runs, so no separate "is this new" query is needed and
-- a second/third booking by the same phone never touches this column again
-- (ON CONFLICT DO UPDATE's SET list deliberately never mentions it). NULL
-- only for a patient created before this column existed -- see
-- db/init_db.py's one-time backfill, which assigns these in creation order
-- per hospital so nobody already on file is left without one.
ALTER TABLE patients ADD COLUMN IF NOT EXISTS patient_display_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS ux_patients_hospital_display_id
    ON patients(hospital_id, patient_display_id) WHERE patient_display_id IS NOT NULL;

-- Patient identity SEPARATION (Spec.md Section 0, confirmed with the user via a
-- reviewed plan before this touched production data): one WhatsApp number can
-- now link up to 5 patient profiles (a shared family phone), so `patients` is no
-- longer "one row per (hospital_id, phone)" -- the UNIQUE constraint above that
-- enforced that is dropped. `phone` stays as a column (still populated at
-- profile-creation time) but is now INFORMATIONAL ONLY, not authoritative --
-- "the phone this profile was originally created under." patient_links below is
-- the real source of truth for phone<->patient associations going forward; every
-- WhatsApp-facing lookup goes through it (db.get_active_patients_for_phone()),
-- not patients.phone directly. Existing single-profile-per-phone reads (portal
-- search, visit-history joins) are left as-is -- still correct for any phone that
-- only ever has one linked profile, which is every phone that predates this
-- section (see the patient_links backfill below).
ALTER TABLE patients DROP CONSTRAINT IF EXISTS patients_hospital_id_phone_key;

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
    status TEXT NOT NULL DEFAULT 'booked' CHECK (status IN ('booked', 'cancelled', 'rescheduled', 'attended', 'no_show')),
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
-- Item 8 (Spec.md Section 0): denormalized copies of the owning patient's
-- id/name/phone, same convention appointment_reminders already established
-- by carrying hospital_id alongside its own appointment_id FK -- directly
-- supports item 5's duplicate-booking check (same doctor + same phone +
-- same age on file, without a join to patients for every booking attempt)
-- and makes this table more directly queryable/exportable by staff without
-- one. patient_phone duplicates the existing `phone` column's value
-- (there's only ever one phone per patient per hospital, UNIQUE(hospital_id,
-- phone) on patients) -- kept as its own explicitly-named column anyway for
-- a consistent "every patient_* column lives together" shape when exporting,
-- not because the value itself ever differs from `phone`. All nullable,
-- backfilled below for rows that predate these columns -- never required at
-- INSERT time by any CHECK, so a hypothetical future caller that doesn't set
-- them still works.
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS patient_id INTEGER REFERENCES patients(id);
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS patient_name TEXT;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS patient_phone TEXT;
-- Family/multi-person-booking follow-up (Spec.md Section 0): patient_age
-- joins patient_name/patient_id/patient_phone above -- added so the
-- duplicate-booking check (create_appointment()) can compare a NEW
-- booking's name+age against each of THIS PHONE's own existing active
-- appointments directly, instead of the single mutable `patients.age`
-- value (which can't tell two different family members on one phone
-- apart once a 2nd booking's age has overwritten the first's). Same
-- nullable/no-CHECK/backfilled convention as the columns above.
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS patient_age INTEGER;
-- Item 3 (Spec.md Section 0, this session's 2nd follow-up): soft-delete only
-- -- this project's standing convention is every appointment status change
-- (cancel/reschedule/attendance) status-flags, never physically removes the
-- row, and "delete" here preserves that: hidden from normal reads (baked
-- into _APPOINTMENT_SELECT's own WHERE clause, db/repository.py) but never
-- actually removed. Restricted to non-'booked' rows only (db.soft_delete_
-- appointment()'s own guard) -- deleting a still-active appointment without
-- cancelling it first isn't offered.
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS deleted_at TEXT;

-- Appointment type step (WhatsApp flow alignment): hospital-configurable
-- (like enabled_features/feature_labels), not hardcoded -- each hospital's
-- onboarding picks its own subset/labels from the fixed id set db/init_db.py
-- seeds (new, followup, tele, second_opinion, diagnostic, lab, daycare).
-- requires_doctor_selection is carried for a future per-type booking-path
-- branch (e.g. a lab/diagnostic type skipping straight to a resource picker
-- instead of doctor selection) -- not yet acted on by the booking flow in
-- this pass, every type goes through department/doctor selection today
-- regardless of this flag's value.
CREATE TABLE IF NOT EXISTS appointment_types (
    id TEXT NOT NULL,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    label TEXT NOT NULL,
    requires_consent BOOLEAN NOT NULL DEFAULT FALSE,
    requires_doctor_selection BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (hospital_id, id)
);

ALTER TABLE appointments ADD COLUMN IF NOT EXISTS appointment_type_id TEXT;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS consent_given_at TEXT;
-- Tele-consultation Phase 2 (docs/per-appointment-type-flow-plan.md): a
-- per-booking Jitsi Meet URL (https://meet.jit.si/CareConnect-<random-token>),
-- generated at confirmation time by flows/booking/types/tele_consultation.py
-- via TypeFlow.on_booking_confirmed -- the room name IS the access control
-- (Jitsi has no auth of its own), so the token must stay high-entropy
-- (secrets.token_urlsafe, never a predictable/sequential value) and this
-- column is the only place it's persisted. NULL for every appointment type
-- other than tele, and for any tele booking that predates this column.
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS video_link TEXT;
-- Item 9: the inline CHECK above only applies to a freshly-created table --
-- same idempotency gap Section 12.13's session_timeout_minutes CHECK hit,
-- same fix (explicit DROP + re-ADD, safe to re-run every startup). Real
-- constraint name confirmed against a live Postgres instance before writing
-- this (Postgres's own default naming for an inline column CHECK).
ALTER TABLE appointments DROP CONSTRAINT IF EXISTS appointments_status_check;
ALTER TABLE appointments ADD CONSTRAINT appointments_status_check
    CHECK (status IN ('booked', 'cancelled', 'rescheduled', 'attended', 'no_show'));

-- Item 8 (Spec.md Section 0): backs the new structured reference_id format
-- (APT-<DDMMYY>-<NNN>, numeric date part per the later Item 2 follow-up;
-- sequence resets per day PER HOSPITAL -- the PRIMARY
-- KEY is (hospital_id, day), not day alone, exactly because it must not be
-- globally sequential across tenants). One row per hospital per calendar day
-- that's had at least one booking; INSERT ... ON CONFLICT DO UPDATE SET
-- counter = counter + 1 RETURNING counter (db/repository.py's
-- _next_daily_reference_sequence()) is what makes incrementing it atomic
-- under real concurrent bookings, not a read-then-write race.
CREATE TABLE IF NOT EXISTS reference_id_counters (
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    day TEXT NOT NULL,
    counter INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (hospital_id, day)
);

-- Patient identity system (Spec.md Section 0): same atomic-counter pattern as
-- reference_id_counters above, one row per hospital (no `day` dimension --
-- this is a lifetime sequential count per hospital, not a daily-resetting
-- one) so patient_display_id's numeric suffix is assigned via a single
-- INSERT ... ON CONFLICT DO UPDATE SET counter = counter + 1 RETURNING
-- counter (db/repository.py's _next_patient_display_sequence()), race-safe
-- under real concurrent first-time bookings the same way the reference-id
-- counter already is.
CREATE TABLE IF NOT EXISTS patient_id_counters (
    hospital_id INTEGER PRIMARY KEY REFERENCES hospitals(id),
    counter INTEGER NOT NULL DEFAULT 0
);

-- Patient identity SEPARATION (Spec.md Section 0): links a WhatsApp phone number
-- to 1-5 patient profiles (a shared family phone booking for a spouse/kids, each
-- with their own real `patients` row/Patient ID) -- the source of truth for
-- phone<->patient associations, since `patients.phone` above is now informational
-- only. Soft-unlink only (unlinked_at set, row never deleted) -- matches this
-- project's standing no-hard-delete convention (cancel_appointment()'s own
-- docstring, appointments/handoff_requests' own deleted_at columns) -- unlinking
-- a patient never touches `patients` or `appointments`, only this row, so
-- appointment history and the Patient ID are completely unaffected. The 5-active-
-- link cap is enforced at the application level (db.create_patient_profile(),
-- pg_advisory_xact_lock-scoped to (hospital_id, whatsapp_phone), the same pattern
-- create_appointment() already uses for quota enforcement) rather than a DB
-- trigger -- this project has none anywhere else, confirmed with the user before
-- choosing this over introducing one.
CREATE TABLE IF NOT EXISTS patient_links (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    whatsapp_phone TEXT NOT NULL,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    relationship_label TEXT,
    linked_at TEXT NOT NULL DEFAULT (now()::text),
    unlinked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_patient_links_active_phone
    ON patient_links(hospital_id, whatsapp_phone) WHERE unlinked_at IS NULL;
-- A given patient can't be double-linked to the same phone while both links are
-- active (defensive -- application code never attempts this, but worth the DB
-- itself refusing it outright).
CREATE UNIQUE INDEX IF NOT EXISTS ux_patient_links_active_pair
    ON patient_links(hospital_id, whatsapp_phone, patient_id) WHERE unlinked_at IS NULL;
-- CareConnect architecture doc alignment (Spec.md Section 0), Section 17's
-- fixed relationship enum -- stored as this codebase's own Title Case
-- values (matching the migration backfill's pre-existing 'Self' value
-- exactly, rather than switching to the doc's literal SELF/MOTHER/...
-- uppercase strings and needing a data migration for no functional gain)
-- rather than the doc's literal uppercase strings. RELATIONSHIP_OPTIONS in
-- db/repository.py is the single source of truth this constraint mirrors.
ALTER TABLE patient_links DROP CONSTRAINT IF EXISTS patient_links_relationship_label_check;
ALTER TABLE patient_links ADD CONSTRAINT patient_links_relationship_label_check
    CHECK (relationship_label IS NULL OR relationship_label IN
        ('Self', 'Mother', 'Father', 'Son', 'Daughter', 'Spouse', 'Guardian', 'Other'));
-- Consent & Privacy (Section 20's menu item): service consent is implicit
-- in having an active link at all (using CareConnect for this patient IS
-- the service) -- modeled as a plain boolean rather than a second
-- active/inactive flag redundant with unlinked_at, and "withdrawing" it in
-- the WhatsApp UI maps to unlinking (Manage Patients), not a separate
-- toggle. marketing_consent is a GENUINE, independently-togglable opt-in
-- (defaults FALSE -- opt-in, not opt-out), kept deliberately separate per
-- the doc's own explicit instruction not to bundle service and marketing
-- consent together.
ALTER TABLE patient_links ADD COLUMN IF NOT EXISTS service_consent BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE patient_links ADD COLUMN IF NOT EXISTS marketing_consent BOOLEAN NOT NULL DEFAULT FALSE;

-- CareConnect account/identity layer: separates "who is messaging us" (a
-- durable, GLOBAL identity) from "which hospital's patient record does this
-- resolve to" (patient_links above, which stays hospital-scoped -- medical
-- records are). Deliberately NO hospital_id on either table below: a
-- person's WhatsApp identity is the same no matter which hospital's
-- WhatsApp Business number they message (each hospital has its own
-- phone_number_id, but the sender's own wa_id doesn't change), so they're
-- recognized instantly on their FIRST message to a second/third hospital --
-- they just still land in patient_links' 0-links -> registration branch
-- there, since that hospital has no patient record for them yet. This is
-- also what makes a future patient portal (one login across every hospital)
-- and ERP integration tractable without a later identity-unification
-- migration.
CREATE TABLE IF NOT EXISTS care_connect_accounts (
    id SERIAL PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'blocked')),
    created_at TEXT NOT NULL DEFAULT (now()::text),
    updated_at TEXT
);

-- One row per WhatsApp identity. provider_user_id is WhatsApp's own stable
-- per-sender id (today, the Cloud API webhook's `message.from`, which is
-- also the phone number -- but named/modeled distinctly from phone_number
-- so a future identifier that isn't the phone number itself, e.g. a
-- username-first contact, is additive here, not a rework). Globally UNIQUE,
-- same reasoning as the account table having no hospital_id.
CREATE TABLE IF NOT EXISTS whatsapp_identities (
    id SERIAL PRIMARY KEY,
    care_connect_account_id INTEGER NOT NULL UNIQUE REFERENCES care_connect_accounts(id),
    provider_user_id TEXT NOT NULL UNIQUE,
    username TEXT,
    phone_number TEXT,
    created_at TEXT NOT NULL DEFAULT (now()::text),
    updated_at TEXT
);

-- Informational link from a patient_links row back to the account that
-- created/owns it -- NULLable and populated going forward by
-- create_patient_profile()/link_existing_patient() (db/repositories/patients.py),
-- with a one-time backfill (db/init_db.py) for pre-existing rows. Not yet the
-- join key any hospital-scoped lookup relies on (whatsapp_phone still is,
-- exactly as before) -- this column exists so the account/identity layer is
-- fully wired up and ready for a future portal/ERP read to use, without
-- rewriting every existing phone-keyed query in this pass.
ALTER TABLE patient_links ADD COLUMN IF NOT EXISTS care_connect_account_id INTEGER REFERENCES care_connect_accounts(id);

-- DPDP Act consent gate (hospitals.dpdp_consent_required above): recorded
-- once per (hospital, phone), right after language selection and BEFORE
-- any patient identity is resolved. Deliberately hospital-scoped (unlike
-- care_connect_accounts/whatsapp_identities, which are global) -- consent
-- is inherently about what THIS hospital does with the data, not a fact
-- about the person's identity overall. Only an AGREED decision is ever
-- written here -- declining doesn't insert a row at all, so a person who
-- taps "I Do Not Agree" is simply asked again on their next fresh
-- conversation (they may have misread the prompt, or changed their mind)
-- rather than being permanently flagged as refused.
CREATE TABLE IF NOT EXISTS dpdp_consents (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    whatsapp_phone TEXT NOT NULL,
    care_connect_account_id INTEGER REFERENCES care_connect_accounts(id),
    consented_at TEXT NOT NULL DEFAULT (now()::text),
    UNIQUE(hospital_id, whatsapp_phone)
);

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
-- Item 3: same soft-delete convention as appointments above.
ALTER TABLE handoff_requests ADD COLUMN IF NOT EXISTS deleted_at TEXT;

-- Real two-way conversation threading for an active handoff (Spec.md
-- Section 0 follow-up) -- handoff_requests.message_text alone only ever
-- captured the ONE trigger message, and the reply endpoint persisted
-- nothing at all, so staff had no way to see a patient's follow-up
-- messages sent after triggering a handoff, or a record of what was
-- already replied. Every message in a handoff's thread (the original
-- trigger included, backfilled below for rows that predate this table)
-- lives here now -- single source of truth for the portal's chat-thread UI,
-- not a mix of this table plus handoff_requests.message_text.
CREATE TABLE IF NOT EXISTS handoff_messages (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    handoff_request_id INTEGER NOT NULL REFERENCES handoff_requests(id),
    -- 'inbound' = patient -> staff (captured while the handoff is open,
    -- flows.py's has_open_handoff() gate routes here instead of the bot);
    -- 'outbound' = staff -> patient (portal_reply_handoff(), after the real
    -- WhatsApp send succeeds).
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    message_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (now()::text)
);
CREATE INDEX IF NOT EXISTS idx_handoff_messages_request ON handoff_messages(handoff_request_id, created_at);

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

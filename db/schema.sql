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
    effective_from TEXT
);
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS breaks TEXT NOT NULL DEFAULT '';
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS max_bookings_per_slot INTEGER NOT NULL DEFAULT 1;
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS daily_booking_limit INTEGER;
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS online_quota INTEGER;
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS walkin_quota INTEGER;
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS followup_duration_minutes INTEGER;
ALTER TABLE doctors ADD COLUMN IF NOT EXISTS effective_from TEXT;

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
    source TEXT NOT NULL DEFAULT 'whatsapp',
    -- Section 14.7: which "seat" within a doctor's max_bookings_per_slot this
    -- booking occupies at its scheduled_at (0-indexed, 0 for every doctor
    -- whose max_bookings_per_slot is the default 1 -- identical to how the
    -- old doctor_id+scheduled_at-only uniqueness behaved). Assigned by
    -- db/repository.py:create_appointment()'s count-then-insert-with-retry
    -- loop, never chosen by a caller.
    booking_ordinal INTEGER NOT NULL DEFAULT 0,
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

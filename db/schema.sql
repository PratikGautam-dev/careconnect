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
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (now()::text)
);

-- CREATE TABLE IF NOT EXISTS above won't retroactively add this column to a
-- database created before this change (same limitation already noted for
-- whatsapp_phone_number_id's UNIQUE constraint) -- this makes it idempotent
-- and self-healing on the next app startup against the live database too.
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS portal_password_hash TEXT;

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
    slot_duration_minutes INTEGER NOT NULL DEFAULT 30
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
    created_at TEXT NOT NULL DEFAULT (now()::text)
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
-- handling): only one BOOKED appointment per doctor per exact scheduled_at can
-- exist, no matter how many requests race to insert it. A conflicting
-- create_appointment() call raises db.connection.IntegrityError (psycopg2's
-- IntegrityError, re-exported from db/connection.py) -- core/booking_flow.py
-- catches that and shows a friendly "that slot was just taken" message
-- (Phase 8), not Tier 1's job.
CREATE UNIQUE INDEX IF NOT EXISTS ux_appointments_doctor_slot_booked
    ON appointments(doctor_id, scheduled_at)
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

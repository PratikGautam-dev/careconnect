# WhatsApp Hospital Appointment System — Build Spec

**Purpose of this doc:** Hand this to Claude Code (or any dev agent) as the source of truth for building this feature. It covers architecture, phases, data model, and file structure so implementation can proceed without re-deriving decisions already made.

---

## 0. Progress Log (update as you go)

**Status as of last update:**
- ✅ Phase 0 — AI stripped from fork (`core/ai.py`, `core/transcribe.py`, `modules/payments/`, `knowledge/` deleted; `openai` dependency removed; broken AI/payment tests deleted)
- ✅ Phase 1 — Live Meta webhook connection confirmed working end-to-end (test number, ngrok tunnel, real message round-trip)
- ✅ Phase 2 — Menu state machine built (`core/booking_flow.py`) — department → doctor → slot → confirm flow. Originally built against `mock_data.py`; now against the real database (see Section 12.6 Tier 1 entry below — `mock_data.py` no longer exists).
- ⏳ Phase 3 — ERP data wiring — **on hold, waiting on client to confirm ERP schema/details**
- ✅ Phase 5 — Cancel/reschedule. New states: `AWAITING_CANCEL_SELECTION`/`AWAITING_CANCEL_CONFIRM` and `AWAITING_RESCHEDULE_SELECTION`/`AWAITING_RESCHEDULE_SLOT`/`AWAITING_RESCHEDULE_CONFIRM`. Cancel and reschedule both look up the patient's upcoming appointments by phone (excludes past/cancelled/rescheduled ones); reschedule reuses the existing slot-menu logic scoped to the appointment's current doctor, so the patient only re-picks a time, not department/doctor. Appointments have a `status` field (booked/cancelled/rescheduled) — records are marked, never deleted, preserving history. Originally built against `mock_appointments.py`; now against the real database (Section 12.6 Tier 1 below). Tests cover cancel with none/one/multiple appointments, reschedule happy path, past/already-cancelled filtering, and decline-at-confirm for both flows.
- ✅ Phase 6 — Reminder scheduler (`reminders/scheduler.py`, `/internal/send-reminders` endpoint protected by `INTERNAL_SECRET`). Sends plain text, not a template, since no Meta template is approved yet — flagged in code as a placeholder to swap before production. Originally built against `mock_appointments.py`; now against the real database (Section 12.6 Tier 1 below). Tests cover in-window, out-of-window, and already-reminded (no double-send) cases.
- ✅ Section 12.6 Tier 1 — Real persistence layer (SQLite) replacing `mock_data.py`/`mock_appointments.py`. New `db/` package: `schema.sql` (hospitals/departments/doctors/appointments/conversation_sessions per Section 4, `hospital_id` on every table per Section 12.2), `repository.py` (the only module with raw SQL — `core/booking_flow.py` and `reminders/scheduler.py` call this, never touch SQL directly), `seed.py` (the old mock department/doctor data, now seeded as real rows), `connection.py` (single swappable connection, injectable for tests), `init_db.py` (idempotent — safe to call on every startup, which `core/main.py` does). Added a DB-level partial unique index on `(doctor_id, scheduled_at) WHERE status='booked'` — the actual double-booking guard, not just application logic (the graceful catch was added in Phase 8). `conversation_sessions` table exists per the Section 4 schema but is **still not** wired up — `core/history.py`'s Redis/in-memory session store remains the active mechanism (now itself keyed by `(hospital_id, phone)` as of Phase 9 below), migrating it onto this table wasn't in scope for either phase. *(hospital_id was resolved once at startup in this phase — Phase 9 below replaced that with real per-message routing.)*
- ✅ Phase 9 (Section 12.2) — Multi-tenant routing. `hospital_id` is now resolved **per message**, not once at startup: `core/main.py`'s webhook handler reads `value.metadata.phone_number_id` from the incoming payload (`core/whatsapp.py:extract_phone_number_id`, distinct from `message["from"]`, which is the *patient's* number) and looks it up via `db.find_hospital_by_phone_number_id()` *before* any session/state/booking logic runs; an unrecognized or `is_active=0` phone_number_id is logged and acked with 200, never processed, never assumed to default to some hospital. Threaded hospital_id through everywhere it wasn't already: `core/history.py`'s session store is now keyed by `(hospital_id, phone)` (so the same phone messaging two hospitals never resumes one's conversation inside the other's), and the per-phone message lock in `core/main.py` likewise. `core/whatsapp.py` needed no changes — `WhatsAppClient` already took `phone_number_id`/`access_token` per-instance; what changed is `core/main.py` now builds one cached client per hospital (`_get_whatsapp_client`) from that hospital's own DB-stored credentials instead of one global client from `.env`. `reminders/scheduler.py` loops over each hospital's own `reminder_offsets_hours`; `/internal/send-reminders` loops `db.get_active_hospitals()`, sending each with its own client. Seeded a second, fully fake "Test Hospital 2" (`db/seed.py:seed_test_hospital`, distinct `t2_`-prefixed departments/doctors, never wired to a real number) — seeded only by `tests/conftest.py`, never in production. Tests: new `tests/test_multi_tenant.py` (departments/appointments/sessions never leak across hospitals, unrecognized and deactivated phone_number_id both safely ignored, reminders sent separately per hospital with correct credentials) plus updates everywhere the session-store signature changed. Verified live: same patient phone messaging two different (real, differently-numbered) hospitals gets fully independent menus/appointments/conversations, and an unrecognized number is silently ignored with zero sends. Two gaps flagged at the time (per-hospital signature validation; multiple reminder offsets per hospital) were fixed immediately after — see the next entry. The department/doctor globally-unique-slug limitation from Tier 1 is still unchanged (worked around for the two seeded test hospitals via distinct slug prefixes, not fixed). `config.yaml`/`config/loader.py` are now fully unused by the running app (superseded by the DB) — left in place rather than deleted, since removing them wasn't asked for.
- ✅ Phase 9 follow-up — Two gaps from the Phase 9 entry above, fixed:
  1. **Per-hospital webhook signature validation.** `core/main.py`'s `/webhook` handler now parses just enough of the payload to read `metadata.phone_number_id` and resolve the hospital *before* validating anything — signature verification then uses that specific hospital's own `app_secret_ref`, not one global `WHATSAPP_APP_SECRET` (which is now gone from `core/main.py` entirely). Ordering is: parse structure → resolve hospital (unrecognized/inactive → log + 200, same as before) → verify signature against that hospital's secret (invalid → log + 403) → *then* branch on status-updates/message content — nothing from the message body is read or acted on before signature verification passes. `core/whatsapp.py:validate_webhook_signature` was hardened to fail closed (return `False`) rather than raise when a hospital's `app_secret` is `None` (e.g. mid-onboarding, or the seeded test hospital), since `hmac.new(None, ...)` would otherwise crash the request. New tests in `tests/test_multi_tenant.py` prove hospital A's secret cannot validate a payload claiming to be hospital B's (and the reverse), that each hospital's own secret still correctly validates its own payloads, and that a hospital with no secret configured rejects cleanly (403, not 500) rather than crashing.
  2. **Multiple reminder offsets per hospital.** New `appointment_reminders` table (`db/schema.sql`) — `(hospital_id, appointment_id, offset_hours, sent_at)` with `UNIQUE(appointment_id, offset_hours)` — replaces the single `appointments.reminder_sent_at` timestamp, which could only represent "reminded or not" and silently blocked every offset after the first configured one from ever firing. `db.get_upcoming_appointments(hospital_id, offset_hours, ...)` now checks per-offset via `NOT EXISTS` against that table; `db.mark_reminded(hospital_id, appointment_id, offset_hours)` uses `INSERT OR IGNORE` against the `UNIQUE` constraint as the actual no-double-send guarantee (same DB-constraint-as-source-of-truth pattern as the Phase 8 double-booking index), not application logic. `reminders/scheduler.py:send_reminders` now takes `offsets_hours: list[float]` and loops one full pass per offset. Added `db.get_reminded_offsets()`; removed the now-redundant `Appointment.reminded` boolean field (reminded-ness isn't binary anymore) — existing tests/callers updated accordingly. Tests cover: both offsets firing for a near appointment, only the due offset firing for a farther one, a second cron pass not re-sending an already-fired offset, and a single-offset hospital behaving exactly as before. Verified live: a hospital configured for `[24, 1]` gets both reminders with no duplicates on a repeat run, while a `[24]`-only hospital is unaffected.
- ✅ Phase 8 — Edge case hardening. Went through all 6 items; found and fixed real gaps in 4 of them, confirmed 2 were already correct:
  1. **Double-booking races**: `db/repository.py`'s `get_slots()` didn't check the `appointments` table at all — an already-booked slot stayed visible and pickable forever, with only the DB unique index (Tier 1) silently blocking the second `create_appointment()` with an uncaught `IntegrityError` → 500. Fixed: `get_slots()`/`find_slot()` now exclude booked slots (scoped by hospital_id), and `core/booking_flow.py` catches the race at both the booking-confirm and reschedule-confirm steps — the loser gets "sorry, that slot was just taken" and a freshly-queried slot list for the *same* doctor (no re-asking department/doctor), or a "no other slots left" message if that doctor is now fully booked. Also caught and fixed a related bug while doing this: the reschedule-confirm path called `mark_rescheduled()` on the old appointment *before* attempting the new booking, so a losing race left the patient with neither appointment — reordered so the old one is only marked rescheduled after the new booking actually succeeds.
  2. **Stale session resumption**: audited every session read in the codebase — `sessions.get(phone)` is called in exactly one place (`booking_flow.handle_incoming`), and `core/history.py`'s store already resets to IDLE there on timeout. No bypass existed. Added a parametrized test asserting this across all 9 non-IDLE states (previously only `AWAITING_SLOT` had explicit coverage) to make that guarantee explicit rather than assumed.
  3. **Malformed webhook payloads**: found a real gap — `data = await request.json()` sat *outside* the try/except in `core/main.py`, so an invalid JSON body raised `json.JSONDecodeError` uncaught → 500; non-dict JSON (a list/string/number) similarly raised uncaught `TypeError` when subscripted. Fixed by moving the JSON parse inside the try and broadening the catch to `(KeyError, IndexError, TypeError, ValueError)`, plus a warning log. Message types we don't specifically parse (reactions, etc.) were already safe via `parse_incoming_message`'s `"unsupported"` fallback.
  4. **Concurrent messages, same patient**: confirmed already correct — `_acquire_message_lock` has no `await` inside it, so it's atomic with respect to the event loop regardless of Redis vs. in-memory backend. Proved deterministically (a real `asyncio.gather` test turned out to be inherently flaky — nothing guarantees genuine interleaving — so replaced with pre-acquiring the lock and confirming the second request is skipped, plus a direct unit test of the lock itself).
  5. **Empty doctor/slot lists**: real gap — sending a WhatsApp interactive list with zero rows is invalid and Meta rejects it, but nothing checked for this; a department with no doctors or a doctor with no slots (increasingly likely now that (1)'s fix excludes booked slots) would silently dead-end the patient. Fixed with graceful "no doctors/slots available" messages at every transition into a doctor or slot list, including the free-text re-prompt path (since slots are dynamic mid-conversation) and the double-booking retry path.
  6. **Delivery failures**: confirmed already correct from earlier debugging (see lessons learned) — `send_text`/`send_list`/`send_buttons` already catch `httpx.HTTPError` and log non-2xx responses without raising, so a webhook always returns 200 regardless of Meta API failures.

  Tests: `tests/test_phase8_edge_cases.py` (new, covers 1/2/5), plus additions to `tests/test_main.py` (3/4/6) and `tests/test_whatsapp.py` (6). 116 tests passing total (up from 88). Verified live via a script simulating two patients racing for the same slot, plus a fully-booked-out doctor.
- ✅ Phase 10 (Section 12.1) — Guided onboarding wizard, **v1 only** (the plain-form guided wizard, not the later Embedded Signup flow in Section 12.5). New `admin/` package (`admin/onboarding.py`): a server-rendered HTML form (no Jinja2/JS framework — plain f-string templates, `html.escape()` on every echoed value) at `GET/POST /admin/onboard-hospital`, wired into `core/main.py` via `app.include_router(...)`. Fields: hospital name, `phone_number_id`, access token, app secret, welcome message, comma-separated reminder offsets, reminder template name, and a single textarea for departments using a line-based DSL (`"Department Name: Doctor One, Doctor Two"` per line) — deliberately not a JS-driven repeatable form section, per "minimal maintenance." Submitting calls new `db/repository.py` functions (`create_hospital`, `get_hospital`, `create_department`, `create_doctor` — no raw SQL added outside `repository.py`); `create_department`/`create_doctor` generate their own opaque `h{hospital_id}_{uuid4}` ids, sidestepping the Tier 1 globally-unique-slug limitation without fixing the schema itself. Fixed a real latent gap while building this: `hospitals.whatsapp_phone_number_id` had no `UNIQUE` constraint despite Phase 9's routing depending on it being unique — added to `db/schema.sql` (same DB-constraint-as-source-of-truth pattern as the Phase 8 double-booking index and the Phase 9 follow-up's reminder-offset dedup), and `admin/onboarding.py` catches the resulting `sqlite3.IntegrityError` to show a friendly re-rendered form error instead of a 500. Validation: hospital name and `phone_number_id` required, at least one department with at least one doctor required (each malformed DSL line reported individually), duplicate `phone_number_id` rejected. Basic protection (not full auth): a shared-secret `ADMIN_SECRET` env var gate on the POST route, same convention as `INTERNAL_SECRET`. On success, shows the new hospital's id plus an explicit reminder that the hospital's own Meta Business/number setup (verification, System User token — Section 12.3) must already be done, since this form doesn't do that part. Added `python-multipart` to `requirements.txt` (required by FastAPI's `Form(...)` parsing; was already transitively installed but not declared). Tests: new `tests/test_onboarding.py` (successful end-to-end creation with real DB rows *and* proof that the new hospital's webhook routing/signature validation from Phase 9 works immediately; duplicate `phone_number_id` rejected; missing department/no-doctors rejected; wrong/missing admin secret rejected; GET form renders). 144 tests passing total (up from 136). Verified live by onboarding a genuine second hospital ("Riverside General Hospital," two departments, three doctors) through the form itself — not the seeded test hospital — confirming its webhook signature validation and message routing worked without any code written specifically for it.
- ✅ Phase 10 extension (Section 12.1 full spec) — Extended the wizard above to match the fully-specified Section 12.1: (1) **Meta setup instructional copy** (Steps 1-4) is now static HTML above the credential fields, linking `business.facebook.com`/`developers.facebook.com` and steering toward a System User token, so the hospital admin isn't left to go find that themselves. (2) **Data connection tier choice** (Step 6, Section 12.6): a radio group — Tier 1 "use this platform" (default), Tier 2 "connect my existing system's API" (collects `api_base_url`/`api_key`, stored on the hospital row only — no connector logic reads them yet), Tier 3 "connect my database directly" (no fields; static copy explaining it's a manually-assisted, non-self-serve engagement). New `hospitals.data_tier`/`external_api_base_url`/`external_api_key` columns; `db.create_hospital()` takes all three; `admin/onboarding.py` only persists the API fields when `data_tier == "tier2"`, discarding stray values for the other two tiers regardless of what was typed. (3) **Real per-doctor working patterns and slot generation** (Section 12.1.1) — replaced the last of the mock-style slot logic: `doctors` gained `specialization`, `qualification`, `years_experience`, `working_days`, `working_hours`, `slot_duration_minutes` columns, and a new `doctor_slots` table stores real, generated bookable rows instead of `db/repository.py`'s old fixed 3-day/10:00+15:00-on-the-fly computation. New `db.generate_slots_for_doctor()` builds a rolling window (default 14 days) from a doctor's working pattern, called automatically inside `db.create_doctor()` (satisfies "run at onboarding submission time" without the wizard needing a separate step) and reused by `db/seed.py` for the existing seeded doctors (given the exact old 10:00/15:00-every-day pattern so `get_slots()` keeps returning what existing tests already expected, just from real rows now). `db.get_slots()`/`find_slot()` now read `doctor_slots` directly, filtering out already-booked ones exactly as before — **no changes were needed to the Phase 8 double-booking guard itself**, confirmed by both a unit test (`tests/test_onboarding.py`) and a live smoke test that books a freshly-generated slot and proves a second identical booking still raises `sqlite3.IntegrityError` (now `db.connection.IntegrityError` post-Postgres-migration below — see that entry). New `slots/scheduler.py` + `/internal/top-up-slots` endpoint (`INTERNAL_SECRET`-gated, loops `db.get_active_hospitals()`) — same pattern as `reminders/scheduler.py`/`/internal/send-reminders` — extends every doctor's window forward as days pass; idempotent via `doctor_slots`' `UNIQUE(doctor_id, scheduled_at)` + `INSERT OR IGNORE` (now `ON CONFLICT DO NOTHING`, same note), so a repeat run only adds newly-in-range days, never duplicates. The onboarding wizard's doctor DSL (Step 7) changed from the old one-line-per-department format to a `"# Department"` header line followed by one pipe-delimited line per doctor (`Name | Specialization | Qualification | Years | WorkingDays | WorkingHours | SlotMinutes`), validated field-by-field (working days must be `Mon`-`Sun`, hours must be `HH:MM-HH:MM`, slot minutes a positive integer) with per-line errors reported back on the re-rendered form. Tests: `tests/test_db.py` (working-pattern-driven generation, no-op/idempotent regeneration, rolling-window top-up extending forward without duplicating existing slots), `tests/test_slots.py` (new — the top-up job and its endpoint, including active-hospitals-only scoping), `tests/test_onboarding.py` (extended doctor fields end-to-end plus the Phase 8 double-booking proof, Tier 2 fields saved correctly, Tier 3 succeeds with zero API fields and shows the manually-assisted message, malformed doctor lines rejected with specific errors). 159 tests passing total (up from 144). Verified live via an extended smoke test: a genuine hospital onboarded with two doctors on different working patterns generated the correct distinct slot sets for each, a Tier 2 and a Tier 3 hospital were both onboarded correctly, the top-up job correctly no-ops against an already-full window, and Phase 9's webhook routing still worked afterward.
- ✅ Section 6/12.6 — **Migrated off SQLite onto Postgres (Neon)**, per Section 6's original "move off SQLite before real production load" plan — this is the actual database now, not a future plan. `db/connection.py` (confirmed beforehand to be the *only* module that ever instantiated SQLite directly — `db/repository.py` and everywhere else only ever call `get_connection()` and use `.execute()`/`.commit()`) was rewritten around `psycopg2` (sync, not `asyncpg` — chosen because every `db/repository.py` function was already plain sync code called directly from async FastAPI handlers, same as the old `sqlite3` driver; `asyncpg` would have meant async-ifying every repository function and caller, a far bigger change than swapping the database backend), reading the connection string from a required `DATABASE_URL` env var (Neon provides this directly; there's no default anymore — the app raises a clear error at startup if it's missing, same spirit as `WHATSAPP_VERIFY_TOKEN`'s required-env-var pattern). A small `_PGConnection` adapter class in `db/connection.py` is what actually kept the swap mostly isolated there: it gives a psycopg2 connection `sqlite3.Connection`'s `conn.execute(sql, params).fetchone()/.fetchall()` chaining convenience (psycopg2 has no such method on the connection object itself), translates the `?` placeholders `db/repository.py` already used into psycopg2's `%s` style, and defaults every cursor to `psycopg2.extras.RealDictCursor` so existing `row["column"]` access kept working unchanged. Also re-exports `IntegrityError` (`= psycopg2.IntegrityError`) from `db/connection.py` so `core/booking_flow.py`'s double-booking race catch and `admin/onboarding.py`'s duplicate-`phone_number_id` catch import it from there instead of knowing the driver directly — both previously imported `sqlite3` just for that one exception type.

  **What genuinely couldn't stay isolated to `db/connection.py`** (flagged rather than glossed over): (1) `cur.lastrowid` has no psycopg2 equivalent — the 4 call sites that used it (`create_hospital`, `create_appointment`, and `db/seed.py`'s two hospital inserts) now use `INSERT ... RETURNING id` + `cur.fetchone()["id"]` instead. (2) SQLite's `INSERT OR IGNORE` has no direct equivalent either — the 2 call sites (`mark_reminded`, `generate_slots_for_doctor`'s per-slot insert) now use `INSERT ... ON CONFLICT (<the UNIQUE columns>) DO NOTHING`, naming the conflict target explicitly (Postgres requires this; SQLite's `OR IGNORE` didn't). (3) A real behavioral gap found *during* this migration, not anticipated going in: Postgres aborts an *entire* transaction after any failed statement — every subsequent statement on that connection raises `"current transaction is aborted"` until a `ROLLBACK`, even unrelated `SELECT`s, which SQLite never did. Since `core/booking_flow.py`'s and `admin/onboarding.py`'s `IntegrityError` catches both immediately continue with more queries on the same connection afterward, this would have silently broken both flows the first time either one actually fired against Postgres. Fixed by setting `autocommit = True` on the psycopg2 connection (`db/connection.py`) — matches this codebase's existing pattern of never spanning a transaction across multiple repository calls (every write already calls `.commit()` immediately after), and a live smoke test specifically proves a caught `IntegrityError` doesn't poison the connection for the query right after it.

  `db/schema.sql` conversion: `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY` (4 tables); `datetime('now')` defaults → `(now()::text)` (kept as TEXT, not retyped to `TIMESTAMP` — every datetime column is still written as an ISO-8601 string via Python's `.isoformat()` and read back with `datetime.fromisoformat()`, exactly as under SQLite, and Postgres's `TEXT` type plus lexical ISO-8601 ordering behaves identically for every comparison/range query this app does, so there was no correctness reason to retype them, only churn). Departments/doctors' `TEXT PRIMARY KEY` (application-generated UUID-based ids, no autoincrement involved) needed no change at all. The double-booking partial unique index (`WHERE status = 'booked'`) converted with **zero syntax changes** — SQLite's partial-index syntax is borrowed directly from Postgres's. `CREATE TABLE/INDEX IF NOT EXISTS` is supported identically in Postgres.

  **Test infrastructure (the "flag which approach" ask):** `tests/conftest.py`'s in-memory-SQLite-per-test fixture had no direct Postgres equivalent (a real Postgres instance can't be recreated from scratch per-test anywhere near as cheaply as an in-memory file), so this now runs against **testcontainers** (`testcontainers[postgres]`, `postgres:16-alpine`), chosen over requiring a manually-configured free-tier/local Postgres because it reproduces the same "just run `pytest`, zero manual setup" experience the old in-memory fixture gave every contributor for free, on any machine or CI runner that already has Docker (which this project's Docker-based deploy path assumes anyway) — a `TEST_DATABASE_URL` env var escape hatch is also supported (skips testcontainers entirely) for environments without Docker-in-Docker, or to test against the exact Postgres version/provider (Neon) production uses. The container starts once per test session at `conftest.py`'s *module* level (not inside a fixture) and sets the real `DATABASE_URL` env var immediately — necessary because `core/main.py` calls `db.init_db.init_db()` at *import* time, before any pytest fixture runs, so `DATABASE_URL` has to already be valid the moment the first test file imports `core.main`. Each test then gets `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` plus a fresh `init_db_on_connection()` + `seed_test_hospital()` — the schema-level equivalent of the old fixture's "every test starts from nothing." New tests specifically re-confirming the double-booking and reminder-dedup `UNIQUE` guards under Postgres (`tests/test_db.py`, `tests/test_reminders.py` — both already existed and needed no logic changes, just now genuinely exercise Postgres's constraint enforcement rather than SQLite's). 159 tests passing, unchanged in count from before the migration (this was a backend swap, not new functionality) — full suite runtime went from ~19s (in-memory SQLite) to ~4 minutes (real Postgres container + a schema reset per test), a known and accepted tradeoff of testing against real infrastructure rather than an in-memory mock; worth revisiting (e.g. `TRUNCATE`-based reset instead of `DROP/CREATE SCHEMA`) if it becomes a bottleneck. Verified live twice: the full suite passes against a testcontainers Postgres, and a separate smoke test against a completely fresh container proves the *actual production startup path* (`core/main.py`'s import-time `init_db()`, not the test fixture) works end-to-end — seeding, real slot generation, the double-booking guard (including the autocommit fix), webhook routing, reminders, slot top-up, and onboarding a genuine second hospital, all against real Postgres.
- ✅ Neon connection-resilience fix (distinct from the Postgres migration above — a follow-up bug found running against the real Neon instance, not part of the SQLite→Postgres swap itself). Symptom: the app crashed with `psycopg2.InterfaceError: connection already closed` on `db/connection.py`'s `execute()` after periods of inactivity — Neon (serverless Postgres) closes idle connections server-side, but the app's single long-lived module-level connection had no way to detect or recover from that. Fixed in `_PGConnection` (`db/connection.py`) with two layers, both needed: (1) a pre-check — `execute()`/`executescript()` check `self._conn.closed` before running a statement and transparently reconnect first if it's already known-closed; (2) a catch-and-retry — both methods also catch `psycopg2.InterfaceError`/`OperationalError` *from the statement itself*, reconnect once, and retry that exact statement before giving up. Layer (2) is the one that actually matters for Neon's real failure mode: psycopg2's `.closed` attribute only flips once the client has *tried and failed* to use the connection, so a connection Neon silently closed server-side still reports `.closed == 0` right up until the next query hits the dead socket — layer (1) alone would never catch that case. Only one retry is attempted per statement — a second consecutive failure means something actually wrong (Neon down, bad `DATABASE_URL`), not another idle timeout, and should surface as a real error rather than retry forever. `commit()`/`close()` were left as-is (a fresh connection from the retry is always what a following `.commit()` call sees, since `execute()` always returns with `self._conn` already valid). Tests: `tests/test_db.py` — one simulates the pre-check path (explicitly `.close()`s the underlying connection, confirms the next query transparently reconnects), one simulates the actual Neon failure mode faithfully using real Postgres behavior rather than mocks (`pg_terminate_backend()` from a second connection kills the first connection's backend process server-side; `.closed` is confirmed still `0` immediately after, proving the assertion exercises the catch-and-retry path specifically, not the pre-check; the next query still transparently reconnects and succeeds). 161 tests passing (up from 159). **Recommendation flagged, not implemented**: a single persistent connection is adequate for this app's current traffic and is what this fix targets, but it's a stopgap — Neon's own pooled connection string (the `-pooler` host, already the Neon default) or a client-side pool (`psycopg2.pool.ThreadedConnectionPool`, or pgbouncer) would avoid reconnect latency entirely and handle concurrent requests better once traffic grows past what one serialized connection can handle; worth revisiting before that becomes a bottleneck, not urgent now. Also fixed in passing while chasing the original 401-after-token-update report that led here: `psycopg2-binary`/`testcontainers` had only been `pip install`ed into a different (global) Python environment during the migration work, not the project's actual `venv/` — reinstalled `requirements.txt` into `venv/` directly; unrelated to the connection bug itself but was blocking the app from starting at all beforehand.

**Key lessons learned during Phase 1 setup — don't rediscover these:**
1. `.env` values are not auto-loaded — `python-dotenv`'s `load_dotenv()` must be explicitly called at the top of `core/main.py` before any `os.environ[...]` reads or `config.loader.load_config()` runs.
2. A message-processing lock (`_acquire_message_lock` in `core/main.py`) connects to Redis directly with no fallback — this crashes with a 500 if Redis isn't running locally. Needs the same in-memory fallback pattern as `core/history.py`'s session store.
3. Webhook field subscriptions (messages, etc.) being "Subscribed" in the dashboard is **not sufficient** — the app must also be explicitly subscribed to the specific WhatsApp Business Account via `POST /{WABA_ID}/subscribed_apps` with the access token. Without this, Meta logs the event internally but never calls the webhook URL at all. This is the most likely silent failure point if webhooks stop arriving after everything else looks correctly configured.
4. Meta's default temporary access token (from API Setup) expires roughly every 24 hours, causing a `401`/`OAuthException code 190` on send calls. Fix: generate a **System User token** (Business Settings → Users → System Users) instead — doesn't expire on this rolling basis. Do this once, early, rather than repeatedly refreshing the temporary token.
5. Meta's dashboard "Send a message" demo button (on the API Setup page) fires directly from Meta's servers using a canned `hello_world` template — it does **not** exercise the actual webhook/bot at all. Always test by messaging the number directly from a real WhatsApp client on a verified test recipient's phone.

---

## 1. Product Summary

A WhatsApp-based appointment booking and reminder system, integrated into an existing Hospital ERP. Patients can:
- Click a **"Chat on WhatsApp" button on the hospital website** to open a pre-filled WhatsApp conversation
- Message the hospital's WhatsApp number to book an appointment (department → doctor → time slot → confirm)
- Receive automated reminder messages before their appointment
- Reschedule/cancel via WhatsApp

Staff continue to use the existing ERP; WhatsApp is an additional booking channel writing into the same appointment data.

**Core priorities driving every technical decision below:**
- **Free to run** — stay on free-tier infrastructure as long as possible; the only unavoidable recurring cost is Meta's per-message charge (see cost discussion earlier in this project)
- **Minimal maintenance** — prefer managed/serverless services over anything self-hosted that needs patching or uptime babysitting
- **Easy to integrate** — the website touchpoint is a single embeddable button, not a custom-built chat widget

**Build approach:** Fork an existing open-source WhatsApp booking bot (see Section 10) rather than building the webhook/messaging plumbing from scratch. Replace its scheduling backend with calls into the hospital ERP.

**Non-goals for v1:** No AI/LLM dependency anywhere in the booking flow — menu-driven only (tap-to-select department/doctor/slot via WhatsApp interactive buttons and lists), for reliability and zero per-conversation API cost in a medical context. No payment collection over WhatsApp. No multi-language support (English/Hindi menu only, decide later). No official Meta BSP/Tech Provider partner status — using Meta's Cloud API directly under our own app.

---

## 2. Architecture Overview

```
Hospital Website
      │
      ▼
"Chat on WhatsApp" button (wa.me/<number>?text=... link — no API call, just a link)
      │
      ▼
Patient's WhatsApp app opens, pre-filled message ready to send
      │
      ▼
Meta WhatsApp Cloud API  ──(webhook)──▶  Our Webhook Endpoint
      ▲                                         │
      │ (send message)                          ▼
      └────────────────────────────────  Conversation Handler
                                                 │
                                                 ▼
                                          State Store (per-patient session)
                                                 │
                                                 ▼
                                          ERP Integration Layer
                                                 │
                                                 ▼
                                          ERP Database (appointments, doctors, departments)

Separate process:
Scheduled Job (hourly) ──▶ Query upcoming appointments ──▶ Send reminder via Meta API
```

**Deployment model:** Serverless-first (see Section 6). Business logic must stay decoupled from platform-specific serverless features so migration to a VPS later is a redeploy, not a rewrite.

**Website integration (the "button"):** No SDK or API integration needed on the website side. A `wa.me` click-to-chat link, styled as a floating button/icon, is enough:
```html
<a href="https://wa.me/91XXXXXXXXXX?text=Hi%2C%20I%27d%20like%20to%20book%20an%20appointment"
   target="_blank" rel="noopener">
  Chat on WhatsApp
</a>
```
This opens WhatsApp (app or web) with the hospital's number and a pre-filled opening message. Once sent, it arrives at the webhook exactly like any other incoming message — no separate integration path to build or maintain.

---

## 3. Core Components to Build

### 3.1 Webhook Receiver
- Single HTTP endpoint that Meta calls on incoming messages/status updates.
- Verifies Meta's webhook signature (security requirement — reject unsigned/invalid requests).
- Parses incoming payload: sender phone number, message type (text, button reply, list reply), message content.
- Passes parsed message to the Conversation Handler.
- Must respond to Meta within their timeout window (~a few seconds) — do heavy work asynchronously if needed, acknowledge receipt first.

### 3.2 Message Sender
- Wrapper function(s) around Meta's `POST /messages` API.
- Needs to support: plain text, interactive buttons (max 3 options), interactive lists (for >3 options, e.g. department/doctor lists), and template messages (for reminders sent outside the 24h window).
- Centralize this so every part of the app sends messages the same way (easier to swap providers later if ever needed).

### 3.3 Conversation State Machine
- Tracks each patient's (phone number's) current position in the booking flow.
- **No AI/LLM involved at any step.** Each state sends a fixed WhatsApp interactive message (button or list) with a closed set of options; the patient's reply is always a **button/list selection**, never free text to interpret. State transitions are simple lookups: "which option did they tap?" → move to the next fixed state.
- States (v1 minimal set):
  - `IDLE` — no active flow; any incoming message here triggers the welcome message + main menu (Book / Reschedule / Cancel / FAQ)
  - `AWAITING_DEPARTMENT` — list message of departments
  - `AWAITING_DOCTOR` — list message of doctors in the selected department
  - `AWAITING_SLOT` — list message of available time slots for the selected doctor
  - `AWAITING_CONFIRMATION` — button message: Confirm / Cancel
  - `BOOKED` (terminal, resets to IDLE)
  - `AWAITING_CANCEL_CONFIRM` / `AWAITING_RESCHEDULE_SLOT` (for cancel/reschedule flows, same button/list pattern)
- State persists between messages (patient may take minutes/hours to reply) — store in the database, not in-memory.
- Each state transition should have a timeout/expiry (e.g., if a patient goes silent for 30+ minutes mid-flow, reset to IDLE next time they message, rather than resuming a stale flow).
- **Invalid input handling:** since WhatsApp interactive replies are constrained to the options shown, most invalid input is naturally prevented. Still handle the case where a patient types free text instead of tapping — reply with "Please choose an option from the list above" and re-send the current step's menu, rather than attempting to interpret what they typed.

### 3.4 ERP Integration Layer
- Functions the Conversation Handler calls into — this is the bridge to existing hospital data:
  - `getDepartments(hospitalId)`
  - `getDoctors(hospitalId, departmentId)`
  - `getAvailableSlots(doctorId, dateRange)`
  - `createAppointment(patientPhone, doctorId, slot)`
  - `getUpcomingAppointments(withinHours)` — used by the reminder job
  - `cancelAppointment(appointmentId)`
  - `rescheduleAppointment(appointmentId, newSlot)`
- These should read/write the **same tables** the existing ERP uses for appointments — WhatsApp is just another entry point, not a parallel data store.

### 3.5 Reminder Scheduler
- Scheduled job, runs hourly (adjustable).
- Logic: find appointments happening in the next N hours (e.g., 24h) that haven't had a reminder sent yet; send templated reminder message; mark as reminded (avoid duplicate sends).
- Uses template messages (pre-approved by Meta) since this is an outbound message outside any active 24h conversation window.

---

## 4. Data Model (additions to existing ERP schema)

```
hospitals
  id, name, whatsapp_phone_number_id, meta_access_token_ref, app_secret_ref, timezone,
  welcome_message_text, reminder_offsets_hours (e.g. [24, 1] — supports one or many custom reminders per hospital),
  reminder_template_name (which approved Meta template to use for this hospital's reminders),
  is_active, created_at

departments  (was hardcoded in mock_data.py — becomes real, per-hospital)
  id, hospital_id, name

doctors  (was hardcoded in mock_data.py — becomes real, per-hospital)
  id, hospital_id, department_id, name

patients  (may already exist in ERP — extend if so)
  id, phone_number (unique, WhatsApp-linked), name, hospital_id

conversation_sessions
  id, patient_phone, hospital_id, current_state, context (JSON: selected dept/doctor/slot so far), updated_at

appointments  (likely already exists — add if missing)
  id, patient_id, doctor_id, hospital_id, scheduled_at, status (booked/cancelled/completed), source (whatsapp/front_desk/etc), reminder_sent_at

message_templates
  id, hospital_id, name, category (utility/marketing/authentication), meta_template_status (pending/approved/rejected), body_text
```

**Note on `reminder_offsets_hours`:** this is what makes reminders "custom per hospital" per Section 12 — a hospital can be configured for a single 24h-before reminder, or multiple (e.g. `[48, 24, 2]`), without any code change — the scheduler just loops over whatever's in this array for each hospital.

Note the `hospital_id` on every table — this is the multi-tenancy hook, even if v1 only serves one hospital. Do not skip this field now; retrofitting it later means migrating existing data.

---

## 5. Build Phases (in order)

| Phase | Goal | Depends on |
|---|---|---|
| 0 | Meta Developer App + test phone number set up; fork base repo and delete AI-dependent files (Section 9) | Meta account, GitHub |
| 1 | Get stripped-down repo running locally with test number; confirm plain-text webhook send/receive works with zero AI dependency | Phase 0 |
| 2 | Build the menu state machine (Section 3.3) with hardcoded department/doctor/slot lists — no ERP wiring yet | Phase 1 |
| 3 | Wire the menu flow to real ERP data (read-only: real departments/doctors/slots) | Phase 2, existing ERP schema — **on hold, waiting on client** |
| 4 | Booking write-back (confirmed slot creates real appointment row) | Phase 3 |
| 5 | Cancel/reschedule flow (adapt the fork's existing cancel/modify logic to the menu pattern + mock data for now) | Phase 2 — can start now against mock data |
| 6 | Reminder scheduler (adapt the fork's existing reminder job; use mock data for now, swap to ERP data once Phase 3 unblocks) | Phase 2, Meta template approval — can start now against mock data |
| 7 | Add the website "Chat on WhatsApp" button (Section 2) | Any point after Phase 1 — independent of backend work |
| 8 | Edge cases: double-booking race conditions, free-text-instead-of-tap handling, session timeout/reset, delivery failure fallback | Phase 4–6 stable |
| 9 | **Multi-tenancy**: `hospital_id` routing by `phone_number_id`, per-hospital config/data isolation (Section 12) | Phase 8 stable for one hospital |
| 10 | **Onboarding process**: manual-assisted flow for adding a new hospital (Section 12) | Phase 9 |

**Do not start Phase 6 (reminders) until template messages are submitted early** — Meta approval has lag time, so submit templates during Phase 3–4, not right before you need them.

**Why fork instead of building Phases 0-1 from scratch:** webhook signature verification and message send/receive wrapping are already solved, tested code in the base repo — see Section 9. Stripping the AI layer is a deletion, not a rebuild, so this still saves the bulk of the infrastructure work even though the AI-driven conversation logic itself is discarded.

**Current sequencing note:** Phase 3 is blocked on the client confirming ERP details. Phases 5 and 6 (reschedule, reminders) do not depend on Phase 3 and can be built now against `mock_data.py` — swapping to real ERP data later is a small change once Phase 3 unblocks, not a rebuild. Phase 9/10 (multi-tenancy, onboarding) should come after Phases 4-8 are solid for one real hospital — easier to bolt multi-tenant scoping onto proven single-hospital logic than to build both at once.

---

## 6. Infrastructure Choices (v1, cost-minimized)

- **Hosting:** Serverless functions (Supabase Edge Functions, Vercel, or Cloudflare Workers — pick one; Supabase preferred since it bundles DB + functions + cron in one account)
- **Database:** ✅ **Postgres, hosted on Neon — this is the actual database now, not a future plan.** SQLite (Section 12.6 Tier 1's original implementation) served the single-hospital build through Phase 10, but per this section's original "move off SQLite before real production load" plan, the app now connects to Postgres via `DATABASE_URL` (`db/connection.py`) — see the migration entry in Section 0. `db/schema.sql`'s tables, the double-booking partial unique index, and the reminder/slot dedup `UNIQUE` constraints are unchanged in shape, just running on Postgres instead of SQLite.
- **Scheduler:** Platform-native cron (Supabase `pg_cron`, Vercel Cron, or Cloudflare Cron Triggers) — hits `/internal/send-reminders` and `/internal/top-up-slots`
- **WhatsApp API:** Meta Cloud API directly — test number during development, production number once business verification clears
- **No BSP** — direct Meta integration to avoid platform markup fees

**Portability rule for Claude Code to follow:** Keep all business logic (state machine, ERP integration, message formatting) in plain functions with no direct dependency on the serverless platform's SDK beyond the entry-point handler. The entry-point file (e.g., `handler.ts`) should be a thin adapter that calls into portable logic — this is what makes a later move to a VPS/always-on server cheap.

---

## 7. Environment/Secrets Needed

- `META_ACCESS_TOKEN` — from Meta Developer App
- `META_PHONE_NUMBER_ID` — WhatsApp number ID (test or production)
- `META_WEBHOOK_VERIFY_TOKEN` — arbitrary string you set, used to verify webhook subscription with Meta
- `META_APP_SECRET` — used to verify incoming webhook payload signatures
- `DATABASE_URL` — **required, no default.** The Postgres/Neon connection string (`db/connection.py`); the app raises a clear error at startup if this isn't set. Per-hospital Meta credentials (`whatsapp_phone_number_id`/access token/app secret) live in the `hospitals` table itself (Section 4/12.2), not as separate env vars, since Phase 9 made those per-hospital rather than global.
- **`ANTHROPIC_API_KEY` is NOT needed** — the base fork requires this by default, but it's removed along with `core/ai.py` per Section 9. Do not add this key; if the app fails to start asking for it, that's a sign a leftover AI-dependent import wasn't fully removed.

---

## 8. Open Decisions to Confirm Before/During Build

- [ ] Menu language: English only for v1, or English + Hindi toggle?
- [ ] How many reminders per appointment (one 24h-before, or also a 1h-before)?
- [ ] Should reschedule/cancel be available via WhatsApp in v1, or phase 5 later?
- [ ] Does the existing ERP already have an `appointments` table we extend, or is this net-new?
- [ ] Single hospital for now — confirm `hospital_id` scoping is still worth building in from day one (recommended: yes).

---

## 9. Fork Base Repository

**Base repo:** `martin-minghetti/whatsapp-ai-receptionist` (github.com/martin-minghetti/whatsapp-ai-receptionist)
MIT licensed, Python/FastAPI, no heavyweight framework dependency (direct Anthropic SDK calls, ~50 lines of core logic by design).

**Fork strategy — what stays vs. what gets replaced:**

| Component in base repo | Action | Notes |
|---|---|---|
| `core/main.py` — FastAPI webhook handlers, intent routing | Keep, adapt | This is the webhook receiver from Section 3.1 — remove the call into `core/ai.py` and replace with the menu state machine's routing instead |
| Webhook HMAC signature validation | Keep as-is | Already correct; don't rewrite |
| `core/whatsapp.py` — WhatsApp Cloud API client | Keep, extend | This is the Message Sender from Section 3.2 — extend it to send **interactive list and button messages** (Meta supports these natively), not just plain text |
| `core/ai.py` — Claude integration, intent extraction | **Delete entirely** | No AI dependency in v1 (see Non-goals, Section 1). Removes the `ANTHROPIC_API_KEY` requirement and its per-conversation API cost. |
| `core/transcribe.py` — voice message transcription | **Delete** | Voice input relies on the AI pipeline; out of scope for a menu-driven flow |
| `core/history.py` — conversation state (Redis / in-memory fallback) | Keep, extend | Maps to Section 3.3's state machine; extend states to match the department→doctor→slot menu flow |
| `modules/booking/calendar.py` — Google Calendar integration | **Replace entirely** | This becomes the ERP Integration Layer (Section 3.4) — swap Google Calendar calls for ERP database queries |
| `modules/payments/` — Mercado Pago integration | **Delete** | Out of scope (see Non-goals in Section 1) |
| `reminders/scheduler.py` — 24h reminder sender | Keep, adapt | Point at ERP's `appointments` table instead of Google Calendar events |
| `config.yaml` — per-client config | Keep, extend | Natural fit for the `hospital_id` multi-tenancy model in Section 4 — one config block per hospital; also where department/doctor lists for the menus can be sourced or cached from |
| `knowledge/client.txt` — free-text knowledge base | **Delete** | Was AI-only input; no longer read by anything once `core/ai.py` is removed |

**First implementation step:** since the AI pipeline is being removed rather than adapted, don't bother testing the fork's original Google Calendar + AI booking flow first. Instead: (1) delete `core/ai.py`, `core/transcribe.py`, `modules/payments/`, and `knowledge/client.txt` up front, (2) get the bare webhook + message-sending running against the Meta test number (confirm you can send/receive a plain text message), (3) then build the menu state machine from Section 3.3 on top of the remaining `core/whatsapp.py` and `core/history.py`.

---

## 10. Website Integration Checklist

- [ ] Get the hospital's WhatsApp Business number (same one used for the Cloud API)
- [ ] Build the `wa.me` link per the template in Section 2, with a pre-filled opening message
- [ ] Style it as a floating action button (standard convention: bottom-right corner, WhatsApp-green circular icon) — this is a small, static HTML/CSS component, no framework needed
- [ ] Add `target="_blank" rel="noopener"` so it opens in a new tab/app without navigating away from the hospital site
- [ ] Test on both desktop (opens WhatsApp Web or prompts to open the app) and mobile (opens the WhatsApp app directly)
- [ ] No backend work needed for the button itself — it's a static link; all the real logic lives in the webhook (Section 3.1) that receives whatever the patient sends after clicking it

---

## 12. Multi-Tenancy & Onboarding (product phase — after single-hospital flow is proven)

### 12.1 Onboarding model: guided wizard (current, definitive design)

Each new hospital signs up and self-configures through a **guided step-by-step wizard inside your product** — not Meta's official Embedded Signup (that requires becoming a Meta Tech Provider — see Section 12.5, deliberately deferred). The wizard's job is to remove *confusion* around Meta's own required steps, and to let the hospital fully configure their booking system (departments, doctors, working hours, reminders, and which database tier they're using) without you writing any code per hospital.

**Full wizard flow, as it stands now:**

- **Step 1 — Create Meta Business Account**
  Link opens `business.facebook.com`. Instruction: "Sign in and create a Business Account for your hospital."

- **Step 2 — Set up WhatsApp on a Meta app**
  Link to `developers.facebook.com` with instructions: "Create an app → Add the WhatsApp product."

- **Step 3 — Business verification + production number + payment method**
  Guided copy walking through verifying the hospital's real business, registering their production number, and adding a payment method (free to add, only charged per message later, per earlier cost discussion).

- **Step 4 — Generate a permanent token**
  Guided copy specifically steering the hospital to generate a **System User access token** (Business Settings → Users → System Users), not the default 24h temporary one — directly reusing lesson #4 from Section 0's progress log, written as reusable instructions for any hospital instead of something you debug manually each time.

- **Step 5 — Paste credentials into the wizard**
  Form fields: `[ Phone Number ID ]` `[ Access Token ]` `[ App Secret ]`. Validated against the existing uniqueness constraint on `whatsapp_phone_number_id` (Section 12.6/Phase 10).

- **Step 6 — Choose data connection tier (Section 12.6)**
  A simple choice presented in the wizard: **(a)** "Use this platform to manage my appointments" (Tier 1 — the default, no further setup needed), **(b)** "Connect my existing system's API" (Tier 2 — collects an API base URL + API key, stored per-hospital, actual connector logic built out only once a real Tier 2 hospital exists — see Section 12.6), or **(c)** "Connect my database directly" (Tier 3 — flagged in the UI as requiring a secure/VPN-reachable connection and a scoped DB user, treated as a manually-assisted case, not fully self-serve).

- **Step 7 — Hospital & doctor configuration**
  - Hospital name, welcome message text, reminder offsets (e.g. "24,1"), reminder template name.
  - Repeatable department entries, each with one or more doctors. Each doctor has: name, specialization, qualification, years of experience (optional), working days, working hours (one or more ranges), and slot duration in minutes — this pattern drives real slot generation (Section 12.1.1) rather than mock/placeholder slots.

- **Step 8 — Submit**
  Inserts real rows into `hospitals`, `departments`, `doctors` (Section 4/Phase 10), and triggers initial slot generation (Section 12.1.1) for a rolling window (e.g. next 14 days) so the hospital is immediately bookable.

**What this removes vs. what it doesn't:** removes the hospital admin having to Google "how do I get a WhatsApp Phone Number ID" or needing you personally on a call — replaced by clear in-product copy, direct links, and paste-in fields at the right moment. Does **not** remove the hospital's own responsibility to complete Meta's business verification, number registration, or payment method setup — those remain genuine per-hospital steps regardless of how good the wizard is (Section 12.3).

#### 12.1.1 Slot generation from doctor working patterns

Rather than mock/hardcoded slots, each doctor's bookable slots are generated from their configured working pattern (working days, working hour ranges, slot duration):
- A rolling window (e.g. next 14 days) of real slot rows is generated at onboarding time, and kept topped up by a periodic job (same pattern as the reminder scheduler) as days pass.
- Generated slots integrate directly with the existing Phase 8 availability logic — already-booked slots are excluded, and the database-level double-booking constraint still applies unchanged.

### 12.2 Multi-tenant routing (technical requirement)

- **Every incoming webhook message must be resolved to a `hospital_id` first**, using the `phone_number_id` present in Meta's webhook payload, looked up against the `hospitals` table — before any state machine or ERP logic runs.
- **Every subsequent read/write** (session state, department/doctor lookups, appointment creation, reminder queries) must be scoped by that resolved `hospital_id`. No query should ever return or write data without this filter — this is the single most important thing to get right, since a missed scope is a cross-hospital data leak, not just a bug.
- **Outbound sends** (replies, reminders) must use the correct hospital's access token and `phone_number_id` — the sender wrapper (Section 3.2) needs to accept these as parameters per-call rather than reading a single global config value.
- **The reminder scheduler** loops over all active hospitals, and for each one, uses that hospital's own `reminder_offsets_hours` and `reminder_template_name` (Section 4) — not a single global schedule.

### 12.3 Constraints to plan around (not solvable in code)

- **One Meta phone number per hospital is a hard requirement** — not a design choice. Onboarding always includes this manual per-hospital step.
- **New numbers start at Meta's lowest per-day messaging tier** and scale up based on usage/quality over time — a brand-new hospital's number can't suddenly message thousands of unique patients on day one.
- **Template approval is per-template** — if a hospital wants custom reminder wording, that specific wording needs its own Meta approval, adding lag time to onboarding that specific hospital's reminders (plan for this, don't let it block the booking flow itself from working).
- **Shared infrastructure = shared blast radius** — once multiple hospitals run on the same deployment, a bug or outage affects all of them simultaneously; this raises the bar on testing before adding a 2nd hospital, not just the 1st.

### 12.4 Sequencing

Do not start Phase 9 (multi-tenancy) until Phase 8 (edge cases) is solid for the first hospital — retrofitting `hospital_id` scoping onto already-correct single-hospital logic is straightforward; debugging scoping bugs and booking-logic bugs simultaneously is not.

### 12.6 Database Connection Models (three tiers — decide per hospital during onboarding)

Different hospitals will have different existing systems. The product must support all three without assuming one universally:

**Tier 1 — Product-owned database (v1 default, build this first)**
Your product maintains its own persistent database as the source of truth for WhatsApp-originated bookings. Hospital staff input their departments/doctors/available slots directly through the onboarding wizard (Section 12.1) — no connection to any pre-existing hospital system required. This is the only tier needed to onboard any hospital regardless of what (if anything) they already run, and requires zero cooperation from a hospital's IT/security team. **This replaces `mock_data.py`/`mock_appointments.py` with a real persistent database** — same schema as Section 4, just no longer in-memory/mock.

**Tier 2 — Integration against hospital's existing API**
If a hospital's existing ERP already exposes a REST API for availability/booking, the bot calls that directly instead of maintaining its own appointment data. Fastest integration when it exists, but entirely dependent on the hospital already having one — not something to assume or build for generically.

**Tier 3 — Direct database connection**
Only viable when: the hospital's DB is reachable via a secure channel (VPN/SSH tunnel, never open internet), a scoped-down read/write DB user is provided (not admin credentials), and someone maps their specific schema (table/column names) to the bot's expected fields. Genuine security and schema-mapping work on both sides — treat as a case-by-case, higher-effort engagement, not a self-serve "paste your connection string" field.

**Why only one tier can be "the truth" per hospital:** if two independent systems (e.g. a hospital's own website booking form and the WhatsApp bot) both write appointment data without a single shared source of truth, double-booking becomes structurally possible — no amount of application-level locking fixes it if the two systems don't even know about each other's writes. Whichever tier is chosen for a given hospital, all booking channels for that hospital must write to the *same* underlying data.

**Important simplification — the common case:** if a hospital has **no other digital booking channel** (no separate website booking form, no other appointment app — WhatsApp is the *only* way patients book), Tier 1 has **zero cross-channel double-booking risk by definition**, since there's only one channel writing to the data at all. This is likely the majority case for smaller/mid-size hospitals and should be the assumed default during onboarding unless the hospital explicitly says otherwise — worth asking directly in the onboarding wizard ("Do patients currently book appointments anywhere else, like a website or another app?") to decide whether Tier 2/3 is even a conversation worth having for that hospital.

---

## 13. Instructions for Claude Code

When implementing:
1. Check Section 0 (Progress Log) first — don't redo completed phases or rediscover already-solved issues (especially the 5 lessons learned listed there).
2. Follow the phase order in Section 5; Phase 3 (real ERP data) is currently on hold — work on Phases 5/6 (reschedule, reminders) against mock data in the meantime rather than blocking.
3. Use the data model in Section 4 as the schema baseline — adjust field names to match existing ERP conventions if they differ, but keep the `hospital_id` scoping and `conversation_sessions` table as-is.
4. Keep business logic platform-agnostic per Section 6's portability rule.
5. Ask before assuming which serverless platform/database is already set up — confirm what's actually provisioned rather than assuming Supabase by default.
6. Every state in Section 3.3 must be implemented as a WhatsApp interactive list/button message, never a free-text prompt expecting a typed answer.
7. Do not begin Section 12 (multi-tenancy/onboarding) work until Phase 8 (edge cases) is confirmed solid for the single hospital currently in progress.
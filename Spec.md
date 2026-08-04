# WhatsApp Hospital Appointment System — Build Spec

**Purpose of this doc:** Hand this to Claude Code (or any dev agent) as the source of truth for building this feature. It covers architecture, phases, data model, and file structure so implementation can proceed without re-deriving decisions already made.

---

## 0. Progress Log (update as you go)

**Status as of last update:**
- ✅ Phase 0 — AI stripped from fork (`core/ai.py`, `core/transcribe.py`, `modules/payments/`, `knowledge/` deleted; `openai` dependency removed; broken AI/payment tests deleted)
- ✅ Phase 1 — Live Meta webhook connection confirmed working end-to-end (test number, ngrok tunnel, real message round-trip)
- ✅ Phase 2 — Menu state machine built (`core/booking_flow.py`) — department → doctor → slot → confirm flow
- ✅ Phase 5, 6 — Cancel/reschedule and reminders (`reminders/scheduler.py`, `/internal/send-reminders`)
- ✅ Phase 8 — Edge-case hardening (double-booking races, stale sessions, malformed webhooks, concurrent messages, empty slot lists, delivery failures)
- ✅ Section 12 — Multi-tenancy + guided onboarding wizard, Postgres/Neon migration, connector interface (Tier 1/2/3), authenticated tenant-edit path, hospital-staff bookings portal (view bookings, self-serve hospital settings, add/edit doctors), shared admin/portal design system, public landing page — all done, all self-serve, no direct SQL needed for day-to-day operation
- ⏳ Phase 3 — ERP data wiring — still on hold, waiting on client to confirm ERP schema/details (Tier 1's own Neon DB has stood in for this since Section 12.6)
- ✅ Section 14 — Flow types (multi-industry engine): Stage 1 (dispatch mechanism) and Stage 2 (FAQ flow, `faq_flow.py`) both landed — see entries below. Booking is the default/only flow for hospital #1 and DaaPrime; FAQ flow is built and live-verified but not yet in use by a real tenant (Section 14.4's DaaPrime migration is a deliberate follow-up, not done as part of this).
- ✅ Section 14.5 — Flow types superseded by a feature-toggle model: `hospitals.enabled_features` (JSON array) replaces the single-value `flow_type`, so one tenant can enable booking/reschedule/cancel/faq/etc. simultaneously instead of picking one exclusive conversation shape. `flows.py` rewritten from a dispatch table into the actual conversation entry point (owns IDLE/menu-building/reset-keyword logic directly); `faq_flow.py` gained a persistent `STATE_FAQ_ACTIVE` so its topic loop survives as one feature among several. Onboarding wizard reordered (tier choice is now Step 0) and Step 6 rebuilt as a 9-item multi-select feature grid (3 of the 9 — Talk to Reception, Payment Link, Reports & Results — are wizard-selectable placeholders that reply "coming soon," not real sub-flows yet). Idempotent migration backfills every pre-existing tenant's `enabled_features` from its old `flow_type`, verified to reproduce the old fixed 4-item booking menu exactly. Full details in Section 14.5. 264 tests passing (up from 248).
- ✅ Section 14.7 — Richer doctor scheduling: `doctors` gained `breaks`, `max_bookings_per_slot`, `daily_booking_limit`, `online_quota`/`walkin_quota` (stored + validated, not yet enforced — no walk-in booking path exists), `followup_duration_minutes`, and `effective_from`; new `doctor_leave` table for whole-day unavailability. `generate_slots_for_doctor()` now excludes break windows, skips leave dates, caps generation per day at `daily_booking_limit` (soonest-first), and gates on `effective_from`; `update_doctor()`'s regeneration is `effective_from`-scoped so a future-dated schedule change never touches already-offered earlier slots. The old single-column double-booking unique index was replaced with a 3-column `(doctor_id, scheduled_at, booking_ordinal)` one (a documented, deliberate exception to the no-destructive-migrations convention — it's a constraint, not data) so `max_bookings_per_slot > 1` can actually allow group bookings while every doctor still at the default (1) behaves byte-for-byte as before — verified live under genuine concurrent access (real separate DB connections, real threads, a real Postgres instance), not just sequential test calls. Wizard Step 7 and the portal's doctor forms both gained the new fields plus a "copy to other days" convenience (pure form population — working hours/breaks already apply uniformly to every checked day, so this is just bulk day-selection); the portal's doctor-edit page also gained leave-date management. A new non-blocking "warning" channel (separate from hard validation errors) flags an online+walk-in quota sum that exceeds the daily limit without rejecting the submission. 291 tests passing (up from 264). Full details in Section 14.7.
- ✅ Section 12.7/12.8 — Staff dashboard (`/portal/dashboard`, new default landing page after login): stat tiles (today's appointments/confirmed/new patients/no-shows, each with a week-over-week % change vs. the same weekday last week), a 7-day appointments trend line and a 30-day appointments-by-department donut (Chart.js via CDN, no frontend build step), a recent-appointments table, and a recent-activity feed. The activity feed needed one small schema addition — `appointments.updated_at`, stamped on cancel/reschedule — since nothing in this build previously logged WhatsApp messages or status-change timestamps to reuse; flagged and added as the smallest fix rather than building new message logging. New left-sidebar layout scoped to this one page only (every other portal page keeps its existing single-column layout). 305 tests passing (up from 291), including hospital-scoped isolation and empty-state coverage. Full details in Section 12.8.

**Key lessons learned during Phase 1 setup — don't rediscover these:**
1. `.env` values are not auto-loaded — `python-dotenv`'s `load_dotenv()` must be explicitly called at the top of `core/main.py` before any `os.environ[...]` reads or `config.loader.load_config()` runs.
2. A message-processing lock (`_acquire_message_lock` in `core/main.py`) connects to Redis directly with no fallback — this crashes with a 500 if Redis isn't running locally. Needs the same in-memory fallback pattern as `core/history.py`'s session store.
3. Webhook field subscriptions (messages, etc.) being "Subscribed" in the dashboard is **not sufficient** — the app must also be explicitly subscribed to the specific WhatsApp Business Account via `POST /{WABA_ID}/subscribed_apps` with the access token. Without this, Meta logs the event internally but never calls the webhook URL at all. This is the most likely silent failure point if webhooks stop arriving after everything else looks correctly configured.
4. Meta's default temporary access token (from API Setup) expires roughly every 24 hours, causing a `401`/`OAuthException code 190` on send calls. Fix: generate a **System User token** (Business Settings → Users → System Users) instead — doesn't expire on this rolling basis. Do this once, early, rather than repeatedly refreshing the temporary token.
5. Meta's dashboard "Send a message" demo button (on the API Setup page) fires directly from Meta's servers using a canned `hello_world` template — it does **not** exercise the actual webhook/bot at all. Always test by messaging the number directly from a real WhatsApp client on a verified test recipient's phone.

**Section 14 progress:**
- ✅ **Stage 1 (14.1): flow-type dispatch mechanism, zero behavior change — confirmed.** New `hospitals.flow_type` column (`db/schema.sql`, idempotent `ALTER ... ADD COLUMN IF NOT EXISTS` for the live DB, `NOT NULL DEFAULT 'booking'` — every existing tenant migrates to `booking` automatically, no manual step). New top-level `flows.py` module, deliberately mirroring `connectors.py`'s `get_connector_for_hospital()` dispatch pattern exactly: a `_FLOW_HANDLERS` dict (`{"booking": core.booking_flow.handle_incoming}`) and a single dispatch point `get_flow_handler_for_hospital(hospital)`, raising a new `FlowNotImplementedError` (mirroring `ConnectorNotImplementedError`) for an unrecognized `flow_type` rather than silently guessing. `core/main.py`'s `_process_message()` now resolves the flow handler right after resolving the connector, then calls whichever handler `flows.py` returns with `booking_flow.handle_incoming`'s existing argument list unchanged — `core/booking_flow.py` itself was not touched. `Hospital.flow_type` added to the dataclass/`_row_to_hospital()`; `create_hospital()`/`update_hospital()` both gained a `flow_type` parameter (defaulting to `"booking"`) — `update_hospital()`'s callers (`admin/onboarding.py`'s edit-tenant route, `portal.py`'s settings route) were updated to pass the hospital's own current `flow_type` through unchanged, so editing anything else about a tenant can never silently reset its flow_type back to the default. **Confirmed a true wire-up, not a rewrite**: full suite passing with **zero test changes** (229 tests, same count as before this change), and a live webhook round-trip (real Neon DB, real signature verification, only the outbound Meta HTTP call mocked) for both hospital #1 and DaaPrime — both resolve `flow_type='booking'` via the migration default, dispatch correctly through `flows.py`, and produce byte-identical replies to before (same welcome text, same 4 main-menu options, sent under each hospital's own `phone_number_id`).
- ✅ **Stage 2 (14.2/14.3): FAQ flow — built, wired, and live-verified.** New `faq_topics` table (`id, hospital_id, topic_label, answer_text, display_order`, exactly Section 14.2's schema) with the same idempotent-migration treatment as every other schema addition this project makes. New top-level `faq_flow.py`: `handle_incoming()` matching `core/booking_flow.py`'s exact call signature (so `flows.py`'s dispatch never has to special-case it), registered under `"faq"` in `flows.py`'s `_FLOW_HANDLERS`. Deliberately shallow (Section 14.2: "no deeper state") — first contact, a topic tap, unrecognized input, and free text (reset keywords included) all resolve to the same "show the topic list" behavior, so unlike `core/booking_flow.py` there's no dedicated reset-keyword check needed; `sessions.reset()` runs on every message since there's no multi-step progress to ever get stuck in. New `db.get_faq_topics()`/`db.find_faq_topic()`/`db.create_faq_topic()`. **Extracted shared flow helpers** into new `core/flow_common.py` (`cap_rows()`/`MAX_LIST_ROWS`, the WhatsApp 10-row limit fix; `is_reset_keyword()`/`RESET_KEYWORDS`, the stuck-session fix) — pulled out of `core/booking_flow.py` specifically because a second flow type is exactly the case that extraction was for: a fix made once must actually apply everywhere, not just wherever it happened to be found first. `core/booking_flow.py` itself re-exports the old private names (`_cap_rows`, `_MAX_LIST_ROWS`, `_RESET_KEYWORDS`) so nothing else calling it needed to change; confirmed behavior-preserving by the full existing `tests/test_booking_flow.py` suite passing unchanged.

**Onboarding wizard (Section 14.3):** new Step 6 ("What kind of conversation does your WhatsApp number need?" — booking vs. FAQ, reusing the tier-card visual pattern), pushing Data Connection to Step 7, Hospital Details to Step 8, Review to Step 9 (9 steps total now, renumbered cleanly rather than a fractional "6.5" in the actual UI). Step 6 → Step 7 is skipped entirely for `faq` (dedicated Next/Back handlers jump 6→8/8→6, bypassing the now-irrelevant data-tier choice), and Step 8 swaps between the existing department/doctor builder and a new repeatable topic-label/answer-text builder based on the Step 6 choice — same underlying `<form>`, just different fields shown, mirroring the existing tier2-fields/tier3-note conditional-visibility pattern already used for the data-tier step. The review screen (Step 9) branches its "Hospital details" section the same way and omits the "Data connection" section entirely for `faq`. Backend: one shared `onboard_hospital_submit()` route now forks on `flow_type` — `faq` validates topics (new `_build_faq_topics()`, mirroring `_build_departments()`'s "skip an empty card, error on a half-filled one" shape) and calls `db.create_faq_topic()` per topic instead of `create_department()`/`create_doctor()`; `data_tier` is stored as an inert `"tier1"` default for `faq` tenants (never read, since FAQ flow doesn't use the connector interface at all) rather than whatever stray value a hidden, unshown field might carry. The confirmation page also branches (topics list instead of departments, no tier note for `faq`).

**Verification:** 19 new tests across three files — `tests/test_flows.py` (dispatch resolves `booking`/`faq` to the right handler, raises on an unrecognized `flow_type`, a live webhook round-trip proves `core/main.py` actually reaches `faq_flow.py` and not `booking_flow.py`), `tests/test_faq_flow.py` (welcome + topic list, tap-answer-then-loop-back, unrecognized tap and reset keywords all correctly falling through to the topic list, empty-topics graceful message, the shared 10-row cap, cross-hospital topic isolation), `tests/test_faq_onboarding.py` (real hospital + `faq_topics` rows created via the actual wizard route, review page shows topics not departments, missing/half-filled topics rejected, data-tier fields correctly ignored, and the existing default-`flow_type` booking submission confirmed unaffected). Full suite: **248 passing** (229 + 19). Beyond the automated suite, also live-verified end to end against the real Neon database: onboarded a genuine `Live FAQ Test Clinic` tenant purely through the wizard HTTP route, sent it a real (signature-verified) webhook message, confirmed the reply was the correct FAQ topic list (not a booking main menu) under that tenant's own `phone_number_id`, then cleaned up the test tenant — hospital #1 and DaaPrime were re-confirmed still `flow_type='booking'` and untouched throughout. Section 14.4 (migrating DaaPrime's real tenant record to `flow_type='faq'` and retiring its placeholder department/doctor data) is next, deliberately not done as part of this — it's a live edit to a real tenant, kept as its own explicit step.

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
- **Database:** Supabase (Postgres) free tier, or existing ERP database if it can be extended directly
- **Scheduler:** Platform-native cron (Supabase `pg_cron`, Vercel Cron, or Cloudflare Cron Triggers)
- **WhatsApp API:** Meta Cloud API directly — test number during development, production number once business verification clears
- **No BSP** — direct Meta integration to avoid platform markup fees

**Portability rule for Claude Code to follow:** Keep all business logic (state machine, ERP integration, message formatting) in plain functions with no direct dependency on the serverless platform's SDK beyond the entry-point handler. The entry-point file (e.g., `handler.ts`) should be a thin adapter that calls into portable logic — this is what makes a later move to a VPS/always-on server cheap.

---

## 7. Environment/Secrets Needed

- `META_ACCESS_TOKEN` — from Meta Developer App
- `META_PHONE_NUMBER_ID` — WhatsApp number ID (test or production)
- `META_WEBHOOK_VERIFY_TOKEN` — arbitrary string you set, used to verify webhook subscription with Meta
- `META_APP_SECRET` — used to verify incoming webhook payload signatures
- Database connection string (Supabase URL + key, or existing ERP DB credentials)
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
  Link opens `business.facebook.com`. Detailed sub-steps shown in the wizard:
  1. Click **Create Account** (top right).
  2. Enter your hospital's name, your own name, and your work email.
  3. Check your email inbox and click the verification link Meta sends you.
  4. Come back to this wizard and check the box below once done.

- **Step 2 — Set up WhatsApp on a Meta app**
  Link to `developers.facebook.com`. Detailed sub-steps:
  1. Log in with the **same** account you used in Step 1.
  2. Click **My Apps** (top right) → **Create App**.
  3. Choose **Business** as the app type → give it any name (e.g. "[Hospital Name] WhatsApp") → enter a contact email → **Create App**.
  4. On your new app's dashboard, scroll to **Add Products to Your App** → find **WhatsApp** → click **Set Up**.
  5. This takes you to the **API Setup** page — you'll come back here in Step 5 to copy two values.

- **Step 3 — Business verification + production number + payment method**
  Detailed sub-steps:
  1. Go to **business.facebook.com/settings** → left sidebar → **Security Center** → **Start Verification**.
  2. Follow Meta's prompts — you'll need your hospital's legal business name, address, and a document like a business registration certificate or tax ID.
  3. This can take Meta a few hours to a few days to review — you can continue to later wizard steps while waiting, but your number won't be able to message real patients until this completes.
  4. Once verified, go back to your app's **WhatsApp → API Setup** page → find **Step 2: Add a phone number** → register your hospital's real WhatsApp number (not a personal number already using regular WhatsApp) and verify it via the code Meta texts you.
  5. Still on that page, find **Add payment method** → add a card. This is required before sending messages, but you are only charged for messages actually sent later — adding the card itself is free.

- **Step 4 — Generate a permanent access token**
  Detailed sub-steps (this avoids the default token expiring every 24 hours):
  1. Go to **business.facebook.com/settings** → **Users** → **System Users** → **Add**.
  2. Give it a name (e.g. "[Hospital Name] Bot") and set its role to **Admin**.
  3. Click **Assign Assets** → **Apps** tab → select the app you created in Step 2 → give it **Full Control**.
  4. Click **Generate New Token** → select that same app → under permissions, check **whatsapp_business_messaging** and **whatsapp_business_management** → set expiration to **Never** → **Generate Token**.
  5. **Copy the token immediately and paste it below** — Meta only shows it once; if you lose it, you'll need to generate a new one.

- **Step 5 — Paste your remaining credentials**
  Detailed sub-steps:
  1. Go back to your app's **WhatsApp → API Setup** page (from Step 2).
  2. Copy the **Phone Number ID** shown there and paste it below.
  3. Go to your app's **Settings → Basic** → click **Show** next to **App Secret** → copy and paste it below.

- **Step 6 — Choose data connection tier (Section 12.6)**
  A simple choice presented in the wizard, led by the decision question from Section 12.6.1 ("Does a system you already use manage appointments/doctor scheduling today?"): **(a)** "Use this platform to manage my appointments" (Tier 1 — the default, no further setup needed), **(b)** "Connect my existing system's API" (Tier 2 — collects an API base URL + API key, stored per-hospital, actual connector logic built out only once a real Tier 2 hospital exists — see Section 12.6), or **(c)** "Connect my database directly" (Tier 3 — flagged in the UI as requiring a secure/VPN-reachable connection and a scoped DB user, treated as a manually-assisted case, not fully self-serve).
  Inline guidance shown beneath the decision question: "Most hospitals should pick option (a) — it means WhatsApp booking works immediately with no extra setup. Only pick (b) or (c) if you already have a separate system where doctors' schedules live today, and you need it to stay the single source of truth."
  Each card also shows a one-line consequence: Tier 1 → "Ready immediately, no IT involvement needed." Tier 2 → "Requires your existing system's API details — we'll build the connection once you provide them." Tier 3 → "Requires your IT team to set up secure access — our team will follow up with you directly."

- **Step 7 — Hospital & doctor configuration**
  - Hospital name, welcome message text (with a placeholder example shown greyed-out in the field: "Hi! Welcome to [Hospital Name]. How can we help you today?"), reminder offsets (with inline help: "Enter hours before the appointment, separated by commas — e.g. 24,1 sends a reminder one day before and one hour before"), reminder template name (with a note: "This must match a message template you've submitted for approval in Meta's WhatsApp Manager — we'll help you with the exact wording to submit").
  - Repeatable department entries, each with one or more doctors. Each doctor has: name, specialization, qualification, years of experience (optional), working days (with a "Select all weekdays" quick-toggle), working hours (with an example placeholder: "e.g. 10:00-13:00, 17:00-20:00 — separate multiple shifts with a comma"), and slot duration in minutes (with inline help: "This is how long each appointment lasts — e.g. 20 means patients can book a new slot every 20 minutes"). This pattern drives real slot generation (Section 12.1.1) rather than mock/placeholder slots.

- **Step 8 — Submit**
  A full review screen listing everything entered in Steps 5-7 (credentials masked/partially hidden for the token and app secret, everything else shown in full) with an "Edit" link next to each section that jumps back to that step without losing other entered data. Below the review, a closing note: "Once you submit, your hospital will be live and bookable through WhatsApp within a few minutes." Submitting inserts real rows into `hospitals`, `departments`, `doctors` (Section 4/Phase 10), and triggers initial slot generation (Section 12.1.1) for a rolling window (e.g. next 14 days) so the hospital is immediately bookable.

**What this removes vs. what it doesn't:** removes the hospital admin having to Google "how do I get a WhatsApp Phone Number ID" or needing you personally on a call — replaced by clear, granular, click-by-click in-product copy (per the detailed sub-steps above), direct links, and paste-in fields at the exact right moment. Does **not** remove the hospital's own responsibility to complete Meta's business verification, number registration, or payment method setup — those remain genuine per-hospital steps regardless of how good the wizard is (Section 12.3).

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
If a hospital's existing ERP already exposes a REST API for availability/booking, the bot calls that directly instead of maintaining its own appointment data. The onboarding wizard (Section 12.1, Step 6) already collects an API base URL + API key for this choice, stored on the hospital's record — but **the actual connector logic (calling their specific API shape) is deliberately not built generically ahead of time.** Build it only once a real Tier 2 hospital exists, against their actual documented API — a speculative generic connector built before seeing a real API's shape tends to need rework anyway.

**Tier 3 — Direct database connection**
Only viable when: the hospital's DB is reachable via a secure channel (VPN/SSH tunnel, never open internet), a scoped-down read/write DB user is provided (not admin credentials), and someone maps their specific schema (table/column names) to the bot's expected fields. Genuine security and schema-mapping work on both sides — treat as a case-by-case, higher-effort engagement, not a self-serve "paste your connection string" field. The wizard can flag this option as "contact us to set this up" rather than fully self-serve.

**Why only one tier can be "the truth" per hospital:** if two independent systems (e.g. a hospital's own website booking form and the WhatsApp bot) both write appointment data without a single shared source of truth, double-booking becomes structurally possible — no amount of application-level locking fixes it if the two systems don't even know about each other's writes. Whichever tier is chosen for a given hospital, all booking channels for that hospital must write to the *same* underlying data.

**Important simplification — the common case:** if a hospital has **no other digital booking channel** (no separate website booking form, no other appointment app — WhatsApp is the *only* way patients book), Tier 1 has **zero cross-channel double-booking risk by definition**, since there's only one channel writing to the data at all. This is likely the majority case for smaller/mid-size hospitals and should be the assumed default during onboarding unless the hospital explicitly says otherwise — the wizard's Step 6 choice is exactly this decision point.

### 12.6.1 Decision guide: which tier should a given tenant pick?

Ask one question at Step 6: **"Does a system you already use manage appointments/doctor scheduling today?"**

- **No** (WhatsApp will be the only place bookings happen, or the existing system is unrelated — e.g. a general CRM with no scheduling) → **Tier 1**. This is the default and covers the majority of tenants, including using this product for your own CRM if that CRM has no built-in appointment/doctor scheduling of its own.
- **Yes, and it's a system you fully own/control** (e.g. your own CRM, if it *does* already handle scheduling) → **Tier 3, direct connection**, is actually the fastest and lowest-friction path for this specific case — the usual Tier 3 concerns (an unknown third party's IT team needing to expose a production DB over a secure channel, unfamiliar schema requiring mapping) don't apply when it's your own system: you already have full access and already know the schema.
- **Yes, and it's a third party's existing system** (a hospital's own separate ERP/booking system that you don't control) → **Tier 2 if they have a documented API** (build the specific connector once real, per 12.6.2), or **Tier 3 as a manually-assisted, case-by-case engagement** if no API exists (per the constraints already listed above — this is real, slower, higher-touch work, not self-serve).

### 12.6.2 Connector interface contract (for Tier 2 and Tier 3 implementations)

Regardless of tier, `core/booking_flow.py` and `reminders/scheduler.py` should only ever call a small, fixed set of functions — never branch on tier internally. This is what lets Tier 2/3 connectors slot in without touching booking logic:

```
get_departments(hospital_id) -> list of departments
get_doctors(hospital_id, department_id) -> list of doctors
get_available_slots(hospital_id, doctor_id, date_range) -> list of slots
create_booking(hospital_id, doctor_id, slot, patient_phone) -> booking confirmation or conflict error
cancel_booking(hospital_id, booking_id) -> success/failure
reschedule_booking(hospital_id, booking_id, new_slot) -> success/failure or conflict error
get_upcoming_appointments(hospital_id, within_hours) -> list, for the reminder scheduler
```

- **Tier 1's implementation** of this contract is `db/repository.py` as it exists today — reads/writes the product's own Neon tables.
- **Tier 2's implementation**, when a real hospital needs it, is a per-hospital adapter module that translates these calls into that hospital's specific API shape (their own request/response format) — built only once a real case exists, per 12.6.
- **Tier 3's implementation**, for a self-owned system like your own CRM, is the same contract implemented against that system's actual schema/tables directly, scoped by `hospital_id` exactly like Tier 1 is today.
- Which implementation is used for a given hospital is selected once, based on that hospital's stored `data_tier` value, at the point where `core/main.py` resolves the hospital for an incoming message — not scattered as tier-checks throughout the booking flow itself.

### 12.7 Hospital-staff bookings portal

A self-serve dashboard for a hospital's OWN staff (`portal.py`) — distinct from `admin/onboarding.py`'s platform-wide `ADMIN_SECRET`-gated routes. Each hospital logs in with its own password (set during onboarding or via `/admin/edit-tenant/{id}`, hashed with `db.hash_portal_password()`) and sees only its own data, `hospital_id`-scoped throughout, same isolation discipline as every other query in `db/repository.py`. Auth is a signed, httponly session cookie (HMAC-SHA256 over `hospital_id.expires_epoch`, `PORTAL_SECRET`) — same "basic protection, not production-grade auth" posture as `ADMIN_SECRET`/`INTERNAL_SECRET` elsewhere. Covers: bookings list (`/portal/bookings`), doctors & departments management including Section 14.7's richer scheduling fields and leave dates (`/portal/doctors`), and hospital settings (`/portal/settings`). Section 12.8 below adds a dashboard as the new default landing page.

### 12.8 Staff dashboard (Section 12.7 follow-up)

`/portal/dashboard` — the default landing page after login (`/portal/bookings` etc. remain reachable via the sidebar). Reuses Section 12.7's existing session-cookie auth and `hospital_id` scoping exactly; every query is a new `db/repository.py` function, hospital-scoped like everything else in that file.

**Stat tiles** (`db.get_dashboard_stats()`): today's appointments, confirmed today, new patients today, no-shows today, each with a week-over-week % change.
- **"Today's appointments"**: every appointment (any status) with `scheduled_at` today. **"Confirmed today"**: of those, still `status='booked'` (not cancelled) — "confirmed" reads as "still on," not a separate re-confirmation action (none exists in this app). **"New patients today"**: distinct phones whose EARLIEST appointment ever at this hospital (by `created_at`) was created today — derived from first-appearance-in-`appointments`, since there's no separate `patients` table. **"No-shows today"**: still-`booked` appointments whose `scheduled_at` has already passed as of now. **Known limitation, flagged deliberately**: this app has no "attended"/"completed" status, so a no-show is a heuristic (a booked appointment whose time passed, never marked otherwise) — an appointment the patient actually attended looks identical once its time has passed. Not solved here; flagged rather than silently treated as exact.
- **Week-over-week comparison**: today vs. the SAME WEEKDAY exactly 7 days ago (not a rolling 7-day average) — picked as the simplest comparison that's still apples-to-apples (a Monday against last Monday), needing only one extra date offset. A zero baseline (nothing happened on the comparison day) returns `None`, rendered as "—", rather than a divide-by-zero or a misleading "+100%".

**Weekly appointments trend** (`db.get_weekly_appointment_counts()`): one point per day, last 7 calendar days including today, by `scheduled_at` (any status) — kept consistent with the stat tiles' own volume-by-day definition rather than a `created_at`-based booking-activity trend (an equally valid alternative, documented as the choice made).

**Appointments by department** (`db.get_appointments_by_department()`): grouped counts over a rolling 30-day window ending now, ordered largest-share-first.

**Recent appointments table**: reuses the existing `db.get_all_appointments_for_hospital(hospital_id, limit=10)` (same ordering the bookings page already uses) rather than a new near-duplicate query.

**Recent activity feed** (`db.get_recent_activity_feed()`): SPEC-required check for an existing WhatsApp message log to reuse turned up none — this build persists conversation STATE (`core/history.py`'s session store) but never inbound/outbound message text or a change log, so there was nothing to reuse as-is. **Smallest addition that captures it**: a new `appointments.updated_at TEXT` column (idempotent `ALTER TABLE ADD COLUMN IF NOT EXISTS`, nullable), stamped by `cancel_appointment()`/`mark_rescheduled()` whenever they change status. The feed reads `COALESCE(updated_at, created_at)` as each row's event time and labels it by current status ("Booked appointment" at `created_at` for a still-booked row; "Cancelled"/"Rescheduled appointment" at `updated_at` for the others) — a reschedule legitimately produces two feed entries over time (the old row's "Rescheduled," the new row's later "Booked"), which is correct, not a double-count.

**Charting**: Chart.js loaded via CDN (`cdn.jsdelivr.net`, pinned version), a `<canvas>` per chart fed by JSON embedded in an inline `<script>` block (same bootstrap-JSON pattern `admin/onboarding.py`'s wizard already uses) — no frontend build step introduced. An empty department breakdown (nothing booked in the last 30 days) shows an empty-state message instead of an empty donut; the weekly trend always has 7 days to plot even if every count is 0, so it never needs a separate empty state.

**Layout**: a new left-sidebar shell (`.dashboard-shell`/`.dashboard-sidebar` in `admin/theme.py`) scoped to this one page, matching the reference dashboard mockup's sidebar/stat-card/chart layout — every other portal.py page keeps its existing single-column layout with the horizontal nav strip (now with a "Dashboard" link added so it's reachable from anywhere); rebuilding every existing page around a permanent sidebar was out of scope for this pass.

**Tests** (`tests/test_portal_dashboard.py`, 14 tests): stat tile counts and week-over-week deltas (up/down/flat/no-baseline) against known, hand-inserted data (raw SQL inserts, since `create_appointment()` has no way to backdate `created_at`/`updated_at` and these queries are specifically about dates); weekly trend and department breakdown correctness and windowing; the activity feed's `updated_at`-vs-`created_at` ordering; cross-tenant isolation at both the HTTP layer (hospital A's rendered dashboard never contains hospital B's phone numbers/department names) and the repository layer; and empty-state rendering for a brand-new hospital with zero departments/doctors/appointments (every section falls back to its empty-state message, nothing errors). Full suite: **305 passing** (291 + 14).

---

---

## 14. Flow Types (multi-industry engine, product phase after single-flow-type is proven)

**⚠️ Superseded by 14.5.** Sections 14.0–14.4 below describe the original single-value `flow_type` dispatch mechanism (a tenant picks exactly one exclusive conversation shape: `booking` OR `faq`) and are kept as historical record of how it was built and why. **14.5 replaced this with a feature-toggle model** — a tenant enables a *set* of capabilities simultaneously (e.g. booking AND faq at once) instead of picking one exclusive flow_type. Read 14.5 first for the current architecture; 14.0–14.4 explain how we got there.

### 14.0 Why this section exists

Every tenant onboarded so far (hospital #1, DaaPrime, the isolation-test tenant) is implicitly running the **booking flow** (Section 3.3) — even DaaPrime, whose real need is answering FAQs about its own business, not scheduling appointments, and is currently forced through placeholder "General Enquiries / Support Team" department/doctor data as a workaround. This section replaces that workaround with a real, general mechanism: a tenant declares **which conversation shape** it needs, and `core/main.py` dispatches to the matching handler — the same dispatch-by-stored-value pattern already proven by Section 12.6.2's connector interface (`data_tier` → connector implementation), just one level up (`flow_type` → conversation handler).

**Build order, deliberately one at a time, each driven by real need rather than speculation:**
1. **FAQ flow** — real, immediate need (DaaPrime). Build first.
2. **Lead-capture flow** — build once flow-type dispatch is proven by FAQ, and a real tenant needs it.
3. **Feedback flow** — build once a real tenant needs it, likely as an add-on to an existing flow (post-appointment, post-interaction) rather than always standalone.

Booking (already built) and Commerce (separate repo) are not rebuilt as part of this — booking becomes flow_type `booking` for the dispatch mechanism's purposes, but its existing code is reused as-is, not rewritten.

### 14.1 The dispatch mechanism

- New column: `hospitals.flow_type` (e.g. `booking`, `faq` — more values added as each flow type is built), set during onboarding (Step 6.5, a new wizard step — see 14.3).
- `core/main.py`'s webhook handler, right after resolving `hospital_id` (Section 12.2) and before any conversation logic runs, looks up `flow_type` and dispatches to the matching handler module — mirroring `get_connector_for_hospital()`'s existing dispatch point exactly.
- Each flow type is its own module implementing one fixed entry point, e.g. `handle_incoming(hospital, message, session) -> None` — same shape regardless of flow type, so `core/main.py` never branches on flow-specific logic itself, only on which module to call.
- `core/booking_flow.py` becomes the `booking` flow_type's implementation, unchanged internally — it already has this exact entry-point shape (`handle_incoming`), so this is a wire-up, not a rewrite.
- Existing tenants (hospital #1, DaaPrime's current placeholder setup) default to `flow_type = 'booking'` via migration, preserving current behavior with zero disruption.

### 14.2 FAQ flow (build first)

**Conversation shape**, deliberately smaller than booking — no state machine depth beyond one level:
- `IDLE` — any incoming message shows the welcome message + a list of topics (a fixed, tenant-configured list, e.g. "Our Services," "Timings," "Location," "Pricing")
- Patient taps a topic → bot replies with that topic's configured answer text, then re-shows the topic list (no deeper state — every reply loops back to the topic menu, not a linear flow like booking's department→doctor→slot)
- Same free-text fallback and reset-keyword handling as booking (Section 3.3, Phase 8's `hi`/`menu`/`restart` reset) — reuse, don't reimplement
- Same WhatsApp 10-row list cap (Section 12.7's `_cap_rows()` finding) applies here too — reuse that helper, don't re-solve the same bug

**Data model:**
```
faq_topics
  id, hospital_id, topic_label, answer_text, display_order
```
No `appointments`, no `doctor_slots`, no departments/doctors at all for a pure FAQ-flow tenant — this flow type genuinely doesn't need most of Section 4's schema, which is exactly why forcing DaaPrime through booking's placeholder data was the wrong fit.

**Connector interface note:** FAQ flow_type doesn't use Section 12.6.2's connector interface at all (no bookings, no Tier 1/2/3 choice relevant) — Step 6 (data tier) of the wizard should be skipped entirely for `flow_type = 'faq'` tenants, not shown as an irrelevant choice.

### 14.3 Onboarding wizard changes for flow_type

- New **Step 6.5** (inserted between the existing Step 6 data-tier choice and Step 7 configuration): "What kind of conversation does your WhatsApp number need?" — options: **Appointment booking** (`booking`) or **FAQ / information bot** (`faq`), with more options added as later flow types are built.
- If `faq` is chosen: Step 6 (data tier) is skipped entirely (per 14.2), and Step 7 becomes a repeatable topic/answer list builder (topic label + answer text pairs) instead of department/doctor configuration.
- If `booking` is chosen: wizard behaves exactly as it does today (Steps 6-7 unchanged).
- Step 8's review screen adapts its summary section to whichever flow_type was chosen, reusing the existing per-section "Edit" link pattern.

### 14.4 Migration path for DaaPrime

Once the FAQ flow ships, DaaPrime's tenant record should be edited (via the now-existing `/admin/edit-tenant/{id}` path, Section 12.1's gap-closed edit flow) to set `flow_type = 'faq'`, and its placeholder "General Enquiries / Support Team" department/doctor rows retired in favor of real topic/answer content — this is the concrete proof-of-need this whole section is built to satisfy, not a hypothetical.

### 14.5 Feature-toggle architecture (supersedes 14.1–14.4's single flow_type)

**Why:** a real hospital doesn't pick one exclusive conversation shape — it wants booking AND reschedule AND cancel AND FAQ, all live on the same WhatsApp number at once. The single-value `flow_type` model made that structurally impossible (one tenant, one handler module, full stop). This section replaces it with a set of independently-togglable capabilities per tenant, matching the reference onboarding design's Step "Patient Experience" multi-select grid.

**Data model:**
- New column `hospitals.enabled_features` — a JSON array of feature-key strings (e.g. `["booking","reschedule","cancel","faq"]`), `TEXT`-typed like every other JSON-shaped column in this schema, parsed/serialized in `db/repository.py`.
- `hospitals.flow_type` is **kept, not dropped** (this project's standing no-destructive-migrations convention) — it becomes a historical/unread column, its only remaining reader being the one-time backfill described below.
- Idempotent backfill (`db/init_db.py`'s `_backfill_enabled_features()`, run on every startup via `init_db_on_connection()`, touches only rows where `enabled_features IS NULL`):
  - `flow_type = 'booking'` → `["booking","reschedule","cancel","hospital_info"]` — this is an **exact, item-for-item reproduction of the old fixed 4-item booking main menu** (Book Appointment / Reschedule / Cancel / a static "FAQ" button that just sent hospital-info text, now named the `hospital_info` feature). Deliberately does *not* add `view_appointments` or `reception_handoff` — those are capabilities no existing tenant had before, so migration grants zero new capability, only renames what was already there.
  - `flow_type = 'faq'` → `["faq"]`.
  - Anything else (a `flow_type` the migration doesn't recognize) → `[]`, never a guess.

**The feature set** (`flows.py`'s `_FEATURE_MENU`, in main-menu display order):

| Feature key | Menu label | Status |
|---|---|---|
| `booking` | Book Appointment | Real |
| `reschedule` | Reschedule Appointment | Real |
| `cancel` | Cancel Appointment | Real |
| `view_appointments` | My Appointments | Real |
| `hospital_info` | Hospital Information | Real |
| `reception_handoff` | Talk to Reception | **Placeholder** |
| `faq` | FAQ / Information | Real |
| `payment_link` | Payment Link | **Placeholder** |
| `reports` | Reports & Results | **Placeholder** |

`flows.REAL_FEATURES` / `flows.PLACEHOLDER_FEATURES` / `flows.ALL_FEATURES` are the source of truth for this split. **Real** features either hand off to an existing sub-flow's own state machine (`booking`/`reschedule`/`cancel` → `core/booking_flow.py`'s existing handlers, reused unchanged; `faq` → `faq_flow.py`) or are one-shot replies that return straight to IDLE (`view_appointments` reads `Connector.get_upcoming_appointments(hospital_id, phone=...)`, already supported by the connector interface with no changes needed; `hospital_info` sends the same static text the old booking flow's "FAQ" button always sent). **Placeholder** features are selectable in the onboarding wizard (so the UI honestly reflects what's coming) but reply with a fixed "coming soon, contact the hospital directly" message if a patient taps one — no sub-flow exists for them yet.

**The router (`flows.py`):** no longer a lookup table returning someone else's handler — it's now the actual conversation entry point `core/main.py` calls directly (`flows.handle_incoming(wa, sessions, phone, hospital_id, reply, hospital_name, connector, enabled_features)`), because building the IDLE main menu is inherently cross-cutting once more than one feature can be enabled at once; no single flow module can own it anymore.
- **IDLE / unrecognized state:** builds a WhatsApp list from whichever of `enabled_features` are set, in `_FEATURE_MENU`'s fixed order, capped to Meta's 10-row limit (`core/flow_common.py`'s `cap_rows()`, reused). Tapping a row for a feature the tenant hasn't enabled (a stale tap from before it was disabled, or a cross-hospital id) falls back to re-showing the current menu rather than starting anything. Zero enabled features shows a graceful "hasn't finished setting up yet" text message, never an empty list.
- **A state belonging to `core/booking_flow.py`'s own state machine** (`STATE_AWAITING_DEPARTMENT`, the slot/confirm/cancel/reschedule states): delegated straight to `booking_flow.py`'s existing per-state handlers, unchanged. `booking_flow.py`'s own `handle_incoming()`/`_handle_idle()` (the old fixed 4-item menu) are left in place, not deleted — `core/main.py` no longer calls them for live traffic, but `tests/test_booking_flow.py` still exercises them directly as a standalone unit test of the state machine's internals.
- **`faq_flow.STATE_FAQ_ACTIVE`:** delegated to `faq_flow.handle_incoming()`, which now sets this state on every message (instead of resetting to true IDLE, as it did back when FAQ was its own exclusive top-level `flow_type`) — this is what lets the topic-tap loop survive across multiple incoming messages once FAQ is one feature among several rather than the whole conversation.
- **A reset keyword, in any state:** always returns to the **top-level unified menu** — not whichever sub-flow's own idea of "start over" is. Deliberate new behavior: a patient two levels deep (e.g. mid-FAQ, having tapped in from the unified menu) typing "hi" lands back at the full menu of everything the hospital offers, not just FAQ's own topic list.

**Onboarding wizard changes** (Section 12.1's step sequence, matching the reference design):
- **Step 0** is now the tier choice (Tier 1/2/3, Section 12.6's existing options) — moved from its old position after the Meta credential steps to the very first step, per the reference design. Steps 1–5 (Meta Business Account → WhatsApp on Meta App → Verify Business & Number → Permanent Access Token → Phone Number & App Secret) follow, unchanged internally.
- **Step 6 ("Patient Experience")** replaced the old single-select "conversation type" cards with a **multi-select checkbox grid** — all nine features above, wired directly to `enabled_features`. At least one must be checked to proceed.
- **Step 7 ("Hospital Details")** shows the department/doctor builder if `booking` is checked, the topic/answer builder if `faq` is checked — **independently, not either/or** (both can show at once now).
- **Step 8 (Review)** lists every checked feature by label, and shows the departments summary and/or the topics summary depending on which of `booking`/`faq` are checked (both possible simultaneously).
- Backend (`admin/onboarding.py`'s `onboard_hospital_submit()`): `enabled_features: list[str] = Form(default=[])` replaces the old `flow_type: str = Form("booking")` parameter. Tier is now collected and validated unconditionally (Step 0 always runs, regardless of which features get enabled downstream) rather than being skipped for `faq`. Validation is now independent per feature (`"booking" in enabled_features` → departments required; `"faq" in enabled_features` → topics required) rather than one exclusive `if/else` fork; an unrecognized feature key or an empty selection is rejected the same way an unrecognized `flow_type` used to be.

**Tests:** `tests/test_flows.py` (rewritten — the IDLE menu shows only enabled features in the fixed order and never an unselected one, a dual booking+faq tenant can reach both sub-flows in the same conversation with a reset keyword returning to the top-level menu from either, a tap for a disabled feature falls back to the menu instead of starting it, `view_appointments`/`hospital_info` one-shot replies, all three placeholder features reply "coming soon" and never start a real sub-flow, a live webhook round-trip against a migrated hospital row), `tests/test_enabled_features_migration.py` (new — the exact `flow_type='booking'`/`'faq'` → `enabled_features` mapping, idempotency, never clobbers a manually-set value, unrecognized `flow_type` gets `[]`), `tests/test_faq_onboarding.py` (rewritten for `enabled_features` form fields, plus a new booking+faq-both-enabled wizard submission test), `tests/test_faq_flow.py` (one assertion updated for the new `STATE_FAQ_ACTIVE` persistent state). Full suite: **264 passing**.

### 14.7 Richer doctor scheduling

**Why:** the doctor model (`working_days`/`working_hours`/`slot_duration_minutes`) only ever expressed "when a doctor works and how long each visit takes" — no way to carve out a break, cap how busy a day gets, let more than one patient hold the same slot, or say "this new pattern starts next month, don't touch what's already offered." This section adds those on top of the existing model, deliberately kept flat on `doctors` (SPEC Section 4) rather than a separate `doctor_schedule_settings` table — one doctor has exactly one active pattern at a time, so a 1:1 side table would just be this table with extra joins.

**New `doctors` columns** (all idempotent `ALTER TABLE ADD COLUMN IF NOT EXISTS`, same convention as every other addition to this schema):
- `breaks TEXT NOT NULL DEFAULT ''` — comma-separated `HH:MM-HH:MM` windows, **stored and applied exactly like `working_hours` already is: uniformly across every working day, not a per-specific-day structure.** `working_hours` itself has never been per-day in this model (one set of shifts applies to every checked working day), so per-day breaks would have been an inconsistent one-off; a break just needs to fall inside *some* shift, on whichever day that shift runs.
- `max_bookings_per_slot INTEGER NOT NULL DEFAULT 1` — how many separate booked appointments can share one doctor+`scheduled_at`. Default 1 reproduces every doctor's exact pre-14.7 behavior.
- `daily_booking_limit INTEGER` (nullable = uncapped) — caps how many slots `generate_slots_for_doctor()` creates for a given date, independent of shift length.
- `online_quota` / `walkin_quota INTEGER` (nullable) — reserved WhatsApp-vs-front-desk split of `daily_booking_limit`. **Stored and validated now, not enforced anywhere yet** — there's no walk-in booking creation path in the portal yet (upcoming work), so there's nothing on the walk-in side to actually split capacity against. This is the one deliberately-inert piece of 14.7, flagged the same way Section 14.5 flags its placeholder features.
- `followup_duration_minutes INTEGER` (nullable) — a separate, typically shorter duration for follow-up visits. Stored and surfaced in every form; no dedicated "new visit vs. follow-up" UI toggle was built in the patient-facing booking flow itself (out of scope for this pass) — this is data-model-and-UI-only for now, same inert status as the quota fields.
- `effective_from TEXT` (nullable ISO date, = "effective immediately") — see `update_doctor()` below.

**New `doctor_leave` table:** `(id, hospital_id, doctor_id, date, reason)`, `UNIQUE(doctor_id, date)`. One row per whole day this doctor is unavailable. `generate_slots_for_doctor()` skips any date listed here entirely. Managed only from the portal's doctor-edit page (`/portal/doctors/{id}/leave`, add and delete) — not part of the onboarding wizard, since a brand-new doctor has no known leave dates yet.

**`generate_slots_for_doctor()` changes**, all reading straight off the doctor row already fetched:
- A candidate slot overlapping any break window (`_overlaps_break()`: `break_start < slot_end AND break_end > slot_start`, a real interval-overlap check, not "fully contained") is skipped.
- Any date present in `doctor_leave` for this doctor is skipped entirely.
- Once a given date would have `daily_booking_limit` candidate slots, generation stops for **that date only** — candidates are already built in ascending time order per day, so this naturally keeps the soonest slots (same "cap from the front, not a random subset" philosophy as `core/flow_common.py`'s `cap_rows()`).
- Dates before `effective_from` are skipped, so a future-dated schedule change never adds new-pattern slots alongside still-standing old-pattern ones (see `update_doctor()` below for the other half of this).
- Every doctor at the pre-14.7 defaults (no breaks, no leave, no daily cap, no `effective_from`) generates byte-identical output to before — none of this is a behavior change unless a doctor opts in.

**`update_doctor()` and `effective_from`:** previously, editing a doctor's pattern always wiped and regenerated the *entire* `doctor_slots` window (safe because `doctor_slots` carries no FK from `appointments` — an already-booked appointment is matched by `scheduled_at` string equality, not a row reference, so it's untouched either way). With `effective_from` set, the wipe is scoped to `scheduled_at >= effective_from` only — any earlier still-unbooked slots (generated under the doctor's *previous* pattern) are left exactly as they were. `effective_from = None` (the default) keeps the old "wipe everything" behavior exactly.

**`max_bookings_per_slot` and the double-booking guard:** the old guard was a single `UNIQUE(doctor_id, scheduled_at) WHERE status='booked'` partial index — elegant, but unconditional, so it would have incorrectly blocked the 2nd..Nth booking for any doctor with `max_bookings_per_slot > 1`. Replaced with:
- A new `appointments.booking_ordinal INTEGER NOT NULL DEFAULT 0` column (existing rows all default to 0, preserving their old uniqueness under the new scheme).
- The unique index is now `UNIQUE(doctor_id, scheduled_at, booking_ordinal) WHERE status='booked'` (`ux_appointments_doctor_slot_ordinal_booked`) — the old two-column index is dropped outright (`DROP INDEX IF EXISTS`), a deliberate, documented exception to this file's no-destructive-migrations convention, since it's a constraint, not stored data, and keeping it alongside would silently defeat the feature it's dropped to enable.
- `create_appointment()` now counts existing booked appointments at that doctor+`scheduled_at`, assigns the next ordinal, and inserts — retrying (bounded to `max_bookings_per_slot` attempts) if a concurrent request wins the ordinal it just tried, since autocommit means a failed statement never poisons the connection (`db/connection.py`'s own docstring). For the default `max_bookings_per_slot=1`, every booking's ordinal is always 0, so this is byte-for-byte the same single-INSERT-single-round-trip guarantee as before for every doctor that hasn't opted in. `get_slots()` correspondingly counts booked appointments per `scheduled_at` (not just "does one exist") and keeps offering a slot until that count reaches `max_bookings_per_slot`.

**Validation** (`admin/onboarding.py`'s `_validate_doctor_fields()`, shared by both the wizard and `portal.py` — unchanged in that respect): breaks must individually match `HH:MM-HH:MM`, each must fall entirely within some working-hours shift, no two breaks may overlap, and every shift must retain at least one `slot_duration_minutes`-sized bookable window after its breaks are subtracted — all **hard errors**, same severity as the pre-existing working-hours checks. `max_bookings_per_slot` must be a whole number ≥ 1; `daily_booking_limit`/`online_quota`/`walkin_quota` must be whole numbers ≥ 0 if provided; `effective_from` must be a valid ISO date if provided. `online_quota + walkin_quota > daily_booking_limit` (when all three are set) is the one **warning, not an error** — a hospital might intentionally leave headroom, so this doesn't block submission; it's carried through as a third `warnings` return value (`_validate_doctor_fields()`/`_build_departments()` now both return `(doctor_or_departments, errors, warnings)`, not a 2-tuple) and rendered as a distinct amber banner on the wizard's confirmation page and the portal's doctor pages, separate from the red hard-error banner.

**UI:** the wizard's Step 7 doctor-card template and the portal's add/edit doctor forms both gained: a repeatable (wizard) / single fixed-row (portal, matching its existing two-shift-max simplicity) break-window picker next to working hours, bookings-per-slot + daily-limit in one row, online/walk-in quota in another (with an inline note that the walk-in side isn't live yet), follow-up duration, and an effective-from date picker. "Copy to other days" (wizard only) is a **pure form-population convenience** — since working hours/breaks/duration already apply uniformly to every checked working day (there's no per-day configuration to copy *from*), "copying" them to more days is exactly "select more days," so the button just reveals a day checklist that turns on additional day-toggles via their own existing click handlers; the backend sees nothing different from a doctor who checked every day by hand. The portal's doctor-edit page also gained a leave-dates section (add/remove) fed by the new `doctor_leave` table.

**Tests:** new `tests/test_doctor_scheduling.py` (27 tests) — break exclusion (including partial-overlap, not just full-containment), `doctor_leave` skip and CRUD, `daily_booking_limit` capping soonest-first, `effective_from` gating generation and scoping `update_doctor()`'s regeneration (mirroring the existing booking-preserving regeneration test), `max_bookings_per_slot` default-parity plus >1 group-booking behavior (and that it still fills up and blocks once full), every validation rule (breaks outside a shift / overlapping / consuming a whole shift, negative limits, zero bookings-per-slot, bad dates, the quota-warning non-blocking case), and end-to-end wizard/portal HTTP submissions covering every new field plus the leave-management endpoints. Full suite: **291 passing** (264 + 27).

---



## 15. Instructions for Claude Code

When implementing:
1. Check Section 0 (Progress Log) first — don't redo completed phases or rediscover already-solved issues (especially the lessons learned listed there).
2. Follow the phase order in Section 5, informed by Section 0's current status — single-hospital and multi-tenancy phases are done; current focus is Section 14 (flow types), starting with the FAQ flow per Section 14.2.
3. Use the data model in Section 4 as the schema baseline, extended per Section 12.1's Step 7 fields, Section 12.6's Tier 2 fields, and Section 14.2's `faq_topics` table as they're built.
4. Keep business logic platform-agnostic per Section 6's portability rule.
5. Ask before assuming which serverless platform/database is already set up — confirm what's actually provisioned rather than assuming Supabase by default.
6. Every state in Section 3.3 (and Section 14.2's FAQ flow) must be implemented as a WhatsApp interactive list/button message, never a free-text prompt expecting a typed answer.
7. Do not begin a new flow type (Section 14) until the flow-type dispatch mechanism (14.1) itself is proven working for existing `booking`-type tenants with zero behavior change, before building FAQ on top of it.
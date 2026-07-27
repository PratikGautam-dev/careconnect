# WhatsApp Hospital Appointment System — Build Spec

**Purpose of this doc:** Hand this to Claude Code (or any dev agent) as the source of truth for building this feature. It covers architecture, phases, data model, and file structure so implementation can proceed without re-deriving decisions already made.

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
  id, name, whatsapp_phone_number_id, meta_access_token_ref, timezone

patients  (may already exist in ERP — extend if so)
  id, phone_number (unique, WhatsApp-linked), name, hospital_id

conversation_sessions
  id, patient_phone, hospital_id, current_state, context (JSON: selected dept/doctor/slot so far), updated_at

appointments  (likely already exists — add if missing)
  id, patient_id, doctor_id, hospital_id, scheduled_at, status (booked/cancelled/completed), source (whatsapp/front_desk/etc), reminder_sent_at

message_templates
  id, hospital_id, name, category (utility/marketing/authentication), meta_template_status (pending/approved/rejected), body_text
```

Note the `hospital_id` on every table — this is the multi-tenancy hook, even if v1 only serves one hospital. Do not skip this field now; retrofitting it later means migrating existing data.

---

## 5. Build Phases (in order)

| Phase | Goal | Depends on |
|---|---|---|
| 0 | Meta Developer App + test phone number set up; fork base repo and delete AI-dependent files (Section 9) | Meta account, GitHub |
| 1 | Get stripped-down repo running locally with test number; confirm plain-text webhook send/receive works with zero AI dependency | Phase 0 |
| 2 | Build the menu state machine (Section 3.3) with hardcoded department/doctor/slot lists — no ERP wiring yet | Phase 1 |
| 3 | Wire the menu flow to real ERP data (read-only: real departments/doctors/slots) | Phase 2, existing ERP schema |
| 4 | Booking write-back (confirmed slot creates real appointment row) | Phase 3 |
| 5 | Cancel/reschedule flow (adapt the fork's existing cancel/modify logic to the menu pattern + ERP data) | Phase 4 |
| 6 | Reminder scheduler (adapt the fork's existing reminder job; point it at ERP appointment data) | Phase 4, Meta template approval |
| 7 | Add the website "Chat on WhatsApp" button (Section 2) | Any point after Phase 1 — independent of backend work |
| 8 | Edge cases: double-booking race conditions, free-text-instead-of-tap handling, session timeout/reset, delivery failure fallback | Phase 4–6 stable |
| 9 (optional/later) | Multi-tenant config, admin dashboard for staff | Phase 8 stable, only if productizing beyond one hospital |

**Do not start Phase 6 (reminders) until template messages are submitted early** — Meta approval has lag time, so submit templates during Phase 3–4, not right before you need them.

**Why fork instead of building Phases 0-1 from scratch:** webhook signature verification and message send/receive wrapping are already solved, tested code in the base repo — see Section 9. Stripping the AI layer is a deletion, not a rebuild, so this still saves the bulk of the infrastructure work even though the AI-driven conversation logic itself is discarded.

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

## 11. Instructions for Claude Code

When implementing:
1. Start by forking `martin-minghetti/whatsapp-ai-receptionist` (Section 9), then **immediately delete the AI-dependent files** (`core/ai.py`, `core/transcribe.py`, `modules/payments/`, `knowledge/client.txt`) and remove `ANTHROPIC_API_KEY` from `.env` and the Anthropic SDK from `requirements.txt` before writing anything new.
2. Get the stripped-down webhook + plain-text send/receive working against the Meta test number first, confirming the app runs with zero AI dependency, before building the menu state machine on top.
3. Follow the phase order in Section 5; don't skip to reminders (Phase 6) before booking write-back (Phase 4) is solid.
4. Use the data model in Section 4 as the schema baseline — adjust field names to match existing ERP conventions if they differ, but keep the `hospital_id` scoping and `conversation_sessions` table as-is.
5. Keep business logic platform-agnostic per Section 6's portability rule.
6. Ask before assuming which serverless platform/database is already set up — confirm what's actually provisioned rather than assuming Supabase by default.
7. Every state in Section 3.3 must be implemented as a WhatsApp interactive list/button message, never a free-text prompt expecting a typed answer.

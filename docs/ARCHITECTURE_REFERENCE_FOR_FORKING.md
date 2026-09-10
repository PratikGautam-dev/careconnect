# Architecture Reference — for forking into a new vertical (e.g. "Dine Connect")

## Why this document exists

This repo ("CareConnect") is a WhatsApp-based appointment booking product built for
hospitals/clinics. You're planning a **new product in a different vertical**
(restaurant table booking / dine-in experience — "Dine Connect") and want to clone
this repo as the starting point, keeping the hard, already-solved infrastructure and
stripping/renaming the healthcare-specific parts.

This file is written so you can hand it to Claude (or anyone else) **cold**, in the
freshly cloned repo, with an instruction like: *"Read
docs/ARCHITECTURE_REFERENCE_FOR_FORKING.md, then strip out everything under 'Delete
or heavily rework' and rename per the vocabulary table, keeping everything under
'Reusable as-is / rename only.'"*

It does **not** duplicate `docs/Spec.md` (954 lines, the full build history/decision
log of THIS product) or `docs/ARCHITECTURE_PLAN.md` (the `flows.booking` package
split rationale) — both stay in this repo as historical record. This file is a
**map + a keep/cut/rename decision list**, written from the outside, for a different
codebase's future author.

---

## 1. What this product actually is, structurally

Strip away "hospital" and "appointment" and this is a **generic pattern**:

```
Meta WhatsApp Cloud API ──(webhook)──▶ Webhook Receiver
        ▲                                    │
        │ (send message)                     ▼
        └──────────────────────────  Conversation State Machine
                                             │
                                             ▼
                                   Per-tenant Session Store (Redis/in-memory)
                                             │
                                             ▼
                                   Connector Interface (abstracts the data layer)
                                             │
                                             ▼
                                   Tenant's own Postgres tables (multi-tenant, one DB)

Separate surfaces:
- A Next.js staff portal (per-tenant login, RBAC-gated pages) for managing the
  underlying data (doctors/departments today; tables/menu/staff for Dine Connect)
  and viewing/managing what WhatsApp created.
- An onboarding wizard (guided, in-product) that self-serves a brand-new tenant's
  full setup — Meta credentials, working-hours-equivalent config, feature toggles.
- A reminder/notification scheduler, cron-triggered, hourly.
```

This shape — **WhatsApp in, structured state machine, pluggable data backend,
staff web portal, self-serve onboarding** — is 100% reusable for a restaurant
product. A diner booking a table via WhatsApp is structurally identical to a
patient booking an appointment: pick criteria (department→doctor vs.
section→table, or just party size), pick a time, confirm, get reminded.

---

## 2. Tech stack (all reusable, keep as-is)

- **Backend:** Python, FastAPI (`core/main.py` is the entry point), `uv` for
  dependency management (`pyproject.toml` + `uv.lock`).
- **DB:** Postgres (Neon in production, Docker `postgres:16-alpine` locally on
  port 5433), raw SQL via `psycopg2`/SQLAlchemy Core (not a heavy ORM — see
  `db/repository.py`), plus a thin SQLAlchemy `orm_models.py` layer used only for
  Alembic migrations. Two migration mechanisms run in parallel (see §7).
- **Session/cache:** Redis (`core/redis_client.py`, `core/session_store.py`),
  with an in-memory fallback (`InMemorySessionStore`) used by the entire test
  suite and any deployment without Redis configured.
- **Frontend:** Next.js (App Router), TypeScript, Tailwind (custom token/breakpoint
  scale, not defaults — see `frontend/src/app/globals.css` if present), lucide-react
  icons, a small hand-rolled `components/ui/*` design-system layer (`Button`,
  `Card`, etc.) — no heavy component library.
- **Auth:** JWT-based staff sessions (`auth/jwt_session.py`), a separate doctor-only
  session (`auth/doctor_session.py`), a separate super-admin JWT
  (`auth/super_admin.py`) — each with its **own** signing secret, deliberately,
  so a leaked secret only forges the one thing it's for.
- **Deployment:** Railway (backend + Postgres), Vercel-style static hosting for
  the frontend (see `docs/DEPLOYMENT.md`) — serverless-first, business logic
  decoupled from platform specifics so a move to a VPS is a redeploy, not a rewrite.

---

## 3. Reusable as-is / rename only

This is the "hard part already solved" — the whole reason to fork instead of
starting from zero. Keep the mechanism, rename the vocabulary.

### 3.1 WhatsApp integration layer
- `core/whatsapp.py` — `WhatsAppClient`: thin wrapper around Meta's Cloud API
  (`send_text`, `send_buttons` (max 3 options), `send_list` (>3 options, capped
  to WhatsApp's 10-row limit via `flows/common.py`'s `cap_rows()`), `send_document`).
  **100% generic, zero domain vocabulary inside it.** Keep verbatim.
- `webhook/` — receiver, Meta signature verification (`WHATSAPP_APP_SECRET`),
  payload parsing (text / button reply / list reply → one normalized
  `{"type": "interactive_reply"|"text", ...}` shape). Keep verbatim.
- Reminder template requirement: any outbound message sent **outside** the 24h
  customer-service window must be a Meta-approved template, not free text — this
  constraint is protocol-level, not product-specific. Applies identically to
  "your table reservation reminder."

### 3.2 Conversation state machine pattern
- `flows/booking/state.py` — `STATE_*` constants, a **step-history stack**
  (`_push_history`/`_history_pop`/`_history_pop_to`) that makes "Back" and
  "change an earlier answer from the confirmation screen" work generically for
  any linear multi-step flow, row-id encode/decode helpers. This stack mechanism
  is the single most valuable, most-reused piece of infrastructure in the repo —
  every sub-flow (booking, cancel, reschedule, view, manage-patients) rides it.
- `flows/booking/dispatch.py` — the `_HANDLERS` state→handler-function lookup
  table + `handle_incoming()`. Adding a new state to any flow is: define the
  constant, write the handler, add one dict entry. Keep this exact pattern.
- **Session store** (`core/session_store.py`): `sessions.get/set/reset`, scoped by
  `(hospital_id, phone)` → generalize the key to `(tenant_id, phone)`. Handles
  session expiry/timeout (configurable per tenant) automatically. Keep as-is.

### 3.3 The `TypeFlow` abstraction — the most valuable pattern here
`flows/booking/types/base.py`'s `TypeFlow` dataclass is a **generic "pluggable
booking variant" engine**. A hospital has `new` / `followup` / `tele` /
`second_opinion` / `procedure` / `diagnostic` / `lab` appointment types, each
sharing ~90% of the same department→doctor→date→slot→confirm pipeline but
differing in a few specific hook points:

```python
TypeFlow(
    type_id: str,
    steps: tuple[str, ...],                       # which states this type walks through
    validate_booking: BookingValidator | None,     # extra conflict check at confirm-time
    validate_department: DepartmentValidator | None,  # extra conflict check at dept-pick time
    on_selected: OnSelectedHook | None,             # fully replace "go to steps[0]" (e.g. Follow-up's
                                                     # eligible-visit picker, or tele's own
                                                     # New/Follow-up sub-choice)
    on_booking_confirmed: OnBookingConfirmedHook | None,  # post-creation side effect (e.g. Meet link)
    build_confirmation_summary: ConfirmationSummaryBuilder | None,  # override the generic card text
    build_success_summary: SuccessSummaryBuilder | None,
)
```
`flows/booking/types/registry.py` maps a stored `appointment_types.id` string to
its `TypeFlow`; an unrecognized id safely falls back to the generic `FULL_FLOW`.

**For a restaurant, this maps directly onto "reservation types":** a plain table
booking, a "book for a special occasion" flow with extra fields, a "private
dining room" flow with a deposit/consent step, a "waitlist join" flow that
skips straight to a queue instead of a fixed slot — all could be `TypeFlow`
variants sharing the same core pipeline. **Keep this abstraction, rename the
concrete type modules.**

### 3.4 Multi-tenancy + pluggable data backend (Connector interface)
- `connectors.py` (`Connector` ABC, `Tier1Connector` the concrete Postgres-backed
  implementation) is the **one seam** `flows/`, `reminders/scheduler.py`, and the
  portal talk through — never raw SQL from flow code directly. This is what lets
  a hospital that already has its own scheduling system plug in via API (Tier 2)
  or a direct DB connection (Tier 3) without touching booking logic at all
  (`docs/Spec.md` §12.6.2 has the exact contract).
- **Directly reusable for Dine Connect**: a restaurant that already runs
  OpenTable/Toast/Zomato-equivalent internally is exactly the Tier 2/3 case — the
  same connector-interface seam applies, same reasoning, same "don't build the
  specific adapter until a real tenant needs it" discipline.
- `hospitals` table (rename → `restaurants`/`venues`) is the tenant root — every
  domain table carries a `hospital_id`/`tenant_id` FK, every query is
  tenant-scoped. This whole isolation discipline (see `tests/test_multi_tenant.py`
  equivalent) is the backbone of the product being multi-tenant SaaS at all —
  keep the pattern exactly, rename the column if you like (or don't; renaming a
  FK column touched by ~40 files for a cosmetic reason is a lot of blast radius
  for zero behavior change — consider just keeping `hospital_id` as an internal
  name and changing only user-facing copy).

### 3.5 Staff identity, RBAC, and the portal
- `auth/jwt_session.py` + `portal/deps.py` (`get_current_staff`,
  `require_permission`) + `portal/permissions.py`
  (`DEFAULT_PERMISSIONS_BY_ROLE`, page-key/action grid) — a real per-page,
  per-role, per-tenant permission system (admin/receptionist/doctor roles today
  → admin/host/waiter/kitchen-staff roles for a restaurant). Keep the mechanism
  entirely; only the role **names** and which pages exist need to change.
- `db/repositories/` split by domain table, `portal/routes/` split by resource —
  this file organization convention (one module per table/resource, both
  backend and its portal routes) should be kept as the organizing principle for
  new domain tables (e.g. `db/repositories/tables.py`, `portal/routes/tables.py`
  for restaurant tables; `db/repositories/menu_items.py`, etc.).
- `audit_logs` table + `db.record_audit_log()` — generic (`action`, `entity_type`,
  `entity_id`, `actor`) — keep verbatim, it's already domain-agnostic.
- Frontend: `frontend/src/app/portal/*` page structure, `components/portal/*`,
  the settings/roles/staff management sub-pages, the `Card`/`Button`/design-token
  system in `components/ui/*` — all reusable UI scaffolding. Swap page *content*
  (schedule → floor plan, doctors list → tables/staff list), keep the shell,
  auth guards, and navigation pattern (`PortalSidebar`, `useStaffSession`,
  `usePermission`).

### 3.6 Onboarding wizard pattern
`docs/Spec.md` §12.1 — the step-by-step guided Meta-credential wizard (Business
Account → App → Verification → Access Token → paste credentials) is **entirely
Meta-API-specific, not hospital-specific** — every WhatsApp Cloud API product
goes through the exact same Meta setup regardless of vertical. Keep this whole
wizard verbatim, just change the **domain configuration step** (Step 7:
departments/doctors/working-hours → sections/tables/floor-capacity, or
menu-categories/items) and the **feature-toggle grid** (§3.9 below).

### 3.7 Reminders
`reminders/scheduler.py` — cron-triggered (`POST /internal/send-reminders`),
per-tenant configurable offsets (`hospital_settings.reminder_offsets_hours`,
e.g. `[24, 1]`), idempotent (`mark_reminder_sent` prevents double-sends). Fully
generic — "your appointment reminder" becomes "your table reservation reminder"
with zero mechanism change, just copy.

### 3.8 Translations
`core/translations/` — a flat `STRINGS[key][lang]` dict + `t(key, lang, **kwargs)`
lookup function, English/Hindi today, WhatsApp button (20-char) and list-row
(24-char) length limits **enforced by a real test**
(`tests/test_translations.py`) rather than trusted by convention. Keep the
mechanism and the length-limit test discipline exactly; retranslate the actual
copy.

### 3.9 Feature-toggle architecture
`docs/Spec.md` §14.5 — `hospitals.enabled_features` (a stored JSON array of
capability keys), `flows/patient_identity/menu.py`'s `_FEATURE_MENU` (ordered
dict of `feature_key → (row_id, translation_key)`), a hidden-from-menu escape
hatch (`_HIDDEN_FROM_MENU`, added this session for `hospital_info`) for a
feature that's live in the data model but not yet patient-facing. **This exact
mechanism is how you'll ship Dine Connect's own main menu** (Book a Table /
View My Reservations / Cancel / Reschedule / Join Waitlist / Order Ahead / Talk
to Staff / FAQ), toggle-able per restaurant, with placeholder ("coming soon")
features supported from day one.

### 3.10 Patient (→ "Diner"/"Guest") identity & multi-profile-per-phone
`patient_links` table + `db/repository.py`'s `create_patient_profile`/
`get_active_patients_for_phone`/`unlink_patient` — one WhatsApp number can link
up to N profiles (a parent booking for their spouse and kids), captured once,
selected on later use, never re-asked. **Directly applicable**: a family phone
booking a table "for Mom's birthday" vs. "for the kids" is the identical shape.
Keep the whole mechanism; rename `patients`/`patient_links` → `guests`/
`guest_links` if desired (same blast-radius tradeoff note as §3.4).

### 3.11 Migration discipline
`db/init_db.py`'s **idempotent, replayed-on-every-boot** `ALTER TABLE ... ADD
COLUMN IF NOT EXISTS` pattern, run alongside a **separate** Alembic migration
history (`db/migrations/`) — both apply the same logical change, so either path
independently brings a DB up to date (local dev usually hits `init_db.py`'s
path on every hot-reload; CI/prod deploys run Alembic). The
"never destructive, always additive, dedupe-then-repoint for a genuine schema
change" discipline (see the Google Calendar hospital-scoping migration in this
repo's own recent history for a worked example) is a **process to keep**, not
specific code.

### 3.12 Crypto / secrets-at-rest
`core/crypto.py` (Fernet symmetric encryption) — used today only for Google
Calendar OAuth tokens, but the pattern (`encrypt_secret`/`decrypt_secret`,
`CryptoNotConfiguredError` on missing/bad key) is exactly what you'd reuse for
any stored third-party credential (a payment gateway's API secret, a POS
integration key, etc.).

---

## 4. Reusable *pattern*, but needs a genuinely new concrete implementation

These are architecturally the right shape to imitate, but the actual logic is
healthcare-specific and won't port by renaming alone.

- **`doctors` table + `generate_slots_for_doctor()`** (`docs/Spec.md` §14.7):
  working days/hours, breaks, leave days, slot duration, daily booking cap,
  `max_bookings_per_slot` (group bookings), `effective_from`-gated schedule
  changes. The **concepts** (a resource has a working pattern, breaks, leave,
  capacity, and schedule changes must not retroactively touch already-booked
  slots) map onto "a table has a seating pattern" or "a staff member has a
  shift," but **table/reservation availability is fundamentally different from
  doctor slots**: a doctor slot is a fixed duration per patient; a restaurant
  table's "slot" depends on party size, turnover time, and how many tables of
  that size/section exist simultaneously (a resource *pool*, not a single
  resource) — closer in shape to this repo's **procedure/diagnostic resource
  pool model** (`procedure_resources`, `procedure_resource_slots`,
  multi-resource reservation under an advisory lock — see
  `db/repositories/appointments.py::create_procedure_appointment`) than to the
  single-doctor model. **Study `flows/booking/types/procedure.py` and its
  resource-pool locking pattern as the closer template**, not
  `new_consultation.py`.
- **Appointment-type consent flow** (`requires_consent`, `dpdp_consents` table,
  India's Digital Personal Data Protection Act framing) — the *mechanism*
  (an extra consent tap before certain booking types) is reusable for, e.g., a
  private event booking needing a deposit-forfeiture-policy acknowledgment; the
  *content and legal framing* is healthcare/India-specific and must be rewritten
  entirely, likely dropped if not needed.
- **Google Calendar/Meet integration** (`modules/google_calendar.py`,
  `auth/google_calendar_oauth.py`, per-hospital admin-connected single Google
  account): the OAuth/encryption/per-tenant-connection *pattern* is generic and
  reusable for **any** third-party integration a restaurant might want (a POS
  system, a payments provider, Google Business Profile reviews sync) — but
  tele-consultation Meet links themselves are meaningless for dining and should
  be deleted, not adapted.

---

## 5. Delete or heavily rework (healthcare-specific, no dining equivalent)

Be blunt about cutting these rather than trying to "genericize" — they exist
because hospitals specifically need them, and forcing dining vocabulary onto
them (as `docs/Spec.md` §14.0 itself notes happened to DaaPrime being forced
through fake "General Enquiries" department/doctor data) produces exactly the
kind of awkward placeholder-data workaround this repo's own history warns
against.

| Remove / rework | Why |
|---|---|
| `flows/booking/types/tele_consultation.py`, Google Meet integration | No video-consultation concept in dining. |
| `flows/booking/types/diagnostic.py`, `lab.py`, `_diagnostic_shared.py`, `diagnostic_tests`/`diagnostic_test_variants`/`lab_service_areas`/`appointment_lab_tests` tables | Medical tests have no restaurant equivalent. |
| `flows/booking/types/second_opinion.py` | Medical-specific consultation type. |
| `flows/booking/types/followup.py`'s "eligible attended visit" concept | A restaurant doesn't have "follow-up to your last visit" as a first-class flow — though the *underlying mechanism* (auto-suggest based on order history, e.g. "rebook your usual table") could inspire a "Book Again" feature reusing the same code shape. Worth reviewing before deleting outright. |
| `patient_documents` (prescriptions/lab reports), `portal/routes/documents.py`, the "Reports & Prescriptions" WhatsApp menu feature | No documents concept in dining (unless you want digital receipts — different enough to rebuild fresh). |
| `patient_visit_notes` | Clinical notes have no equivalent. |
| DPDP-consent-specific health-data framing | Rework as generic ToS/privacy consent if needed at all; drop the health-data-specific legal language. |
| `hospital_info`/business-hours-as-a-menu-feature naming | Keep the *mechanism* (a static info reply), rename to "Restaurant Info" (address/hours/parking). |
| Doctor-specific fields: `specialization`, `qualification`, `years_of_experience` | Replace with staff-relevant fields (role, section assigned) or drop if staff aren't patient-facing "pickable" the way doctors are. |
| `doctor/` frontend routes and `DoctorShell`/`useDoctorGuard` | Only relevant if Dine Connect has an equivalent "staff self-service portal" (e.g. a waiter checking their own section's reservations) — otherwise delete. |

---

## 6. Suggested vocabulary remap

Not a mandate — a reference table for renaming as you go. Column/table renames
are optional (real cost, zero behavior change); user-facing copy renames are
not optional (they're the whole point).

| CareConnect (hospital) | Dine Connect (restaurant) |
|---|---|
| Hospital / tenant | Restaurant / venue |
| Department | Section / cuisine station (or drop — many restaurants have no departments) |
| Doctor | Table (for booking) *or* Staff member (for the portal) — these are two different concepts CareConnect conflates into one "doctor" resource; **don't conflate them for Dine Connect** |
| Patient | Diner / Guest |
| Appointment | Reservation (or "Order" for a food-ordering feature — keep these conceptually separate) |
| Appointment type (new/followup/tele/...) | Reservation type (standard/private-room/large-party/waitlist) |
| Slot | Table availability / seating time |
| Working hours / working days | Operating hours / open days |
| Consultation fee | Deposit / minimum spend |
| Reminder | Reservation reminder |
| Reception / "Talk to Reception" | Talk to Host / Talk to Staff |
| Patient Code (`patient_display_id`) | Guest reference / loyalty number, if you want one |
| Reference ID (booking confirmation number) | Reservation confirmation number (keep as-is, just renamed) |

---

## 7. Net-new territory this repo doesn't have at all

Be explicit with whoever (Claude or a human) picks this up that these need
building from scratch — don't waste time hunting for a template for them here:

- **Payment gateway.** Confirmed via direct code search this session: **there is
  no payment integration anywhere in this repo** — no Razorpay/Stripe/PayU/etc.
  The only money-related code is *display-only* fee text (`new_consultation_fee`/
  `followup_fee` shown as a line on the confirmation card, never actually
  charged). If Dine Connect needs to take a deposit or prepay an order, that's
  a fully new integration: gateway SDK, webhook for payment-confirmed events,
  a `payments` table, refund/cancellation-policy logic tied into the existing
  cancel flow. The `core/crypto.py` pattern (§3.12) and the Connector-interface
  discipline (§3.4) are the right *shape* to hang this off of, but none of the
  actual payment logic exists to reuse.
- **Table/resource-pool availability with party size + turnover time.** Closer
  to `procedure.py`'s multi-resource pattern than to doctor slots (§4), but
  still needs real design work — a doctor slot's duration is fixed per visit; a
  table's effective "duration" depends on party size and how fast people
  actually eat, which is a genuinely different capacity-planning problem.
  Menu/ordering (if in scope) is entirely new.
- **Waitlist.** No concept of "no slot available right now, but join a live
  queue and get notified" exists in this codebase — bookings are always against
  a pre-generated fixed slot. A real-time waitlist is new state-machine + new
  notification-trigger design.

---

## 8. File map (backend)

```
backend/
  core/                    Generic infra -- KEEP: whatsapp.py, session_store.py,
                            translations/, crypto.py, config.py, phone.py,
                            rate_limit.py, redis_client.py, storage.py
  webhook/                 KEEP verbatim
  auth/                    KEEP mechanism (jwt_session, doctor_session ->
                            rename, super_admin, google_calendar_oauth pattern)
  db/
    schema.sql             Table-by-table -- keep tenant/staff/RBAC/audit
                            tables, cut medical-specific tables (see §5)
    repository.py          Split by domain already (repositories/) -- keep the
                            file-per-table convention, write new files for new
                            domain tables
    init_db.py              KEEP the idempotent-ALTER discipline
    migrations/             KEEP Alembic setup, write new revisions
  connectors.py             KEEP verbatim (the Tier 1/2/3 interface)
  flows/
    common.py               KEEP (cap_rows, reset-keyword handling)
    router.py                KEEP the dispatch shape, rewrite feature branches
    patient_identity/        KEEP the multi-profile-per-phone mechanism (rename)
    booking/
      state.py, dispatch.py, messages.py, book.py   KEEP the state-machine
                                                     engine, rewrite prompts
      cancel.py, reschedule.py, view_appointments.py, manage_patients.py
                                                     KEEP mechanism, rename
      types/
        base.py, registry.py                        KEEP the TypeFlow engine
        new_consultation.py, followup.py             Templates for a "standard
                                                       reservation" type flow
        tele_consultation.py, second_opinion.py,
        diagnostic.py, lab.py, _diagnostic_shared.py  DELETE (see §5)
        procedure.py                                 STUDY as the closer
                                                       template for table
                                                       resource-pool booking
  reminders/                KEEP verbatim
  portal/
    deps.py, permissions.py, permission_cache.py     KEEP RBAC mechanism
    routes/                  One file per resource -- keep files for
                              staff/roles/settings/dashboard/auth, rewrite
                              content of doctors.py/appointment_types.py-
                              equivalents, delete documents.py/
                              diagnostic_*.py/lab_service_areas.py
  admin/                     Platform-level (cross-tenant) admin -- KEEP
  modules/google_calendar.py, modules/booking/       Google integration
                              pattern reusable for a different 3rd-party
                              integration; tele-specific content -> delete
  scripts/                   Seed scripts -- rewrite seed data, keep structure
  tests/                     Rewrite fixtures/domain data, keep test
                              *organization* (one file per feature area) and
                              the "reproduce before fixing" discipline
```

## 9. File map (frontend)

```
frontend/src/
  app/
    page.tsx, privacy/, terms/    Marketing/legal pages -- rewrite copy, keep
                                  structure (BrandMark component, Card-based
                                  legal-page layout)
    auth/                          Meta OAuth wizard entry -- KEEP
    admin/                         Platform admin (tenants, users) -- KEEP
    portal/
      login/                       KEEP
      dashboard/                   Rewrite widgets, keep shell
      doctors/ -> tables/ or staff/  Rewrite content, keep list/detail pattern
      schedule/                    Rewrite for table floor-plan or shift view
      appointments/ -> reservations/  Rewrite content, keep list/detail/
                                    filter pattern
      patients/ -> guests/         Rewrite content, keep pattern
      new-booking/ -> new-reservation/  Rewrite form, keep structure
      settings/, settings/roles/, settings/staff/, settings/activity/
                                    KEEP verbatim (RBAC/audit UI is generic)
      messages/                    KEEP if you want a staff-facing WhatsApp
                                    conversation viewer (currently hospital-
                                    agnostic already)
    doctor/                        Only keep if a staff self-service portal
                                    (e.g. waiter's own section) is in scope
  components/
    ui/                            KEEP entirely (design system primitives)
    portal/                        Rewrite content components, keep shell
                                    components (PortalSidebar, session hooks)
    marketing/                     Rewrite content (ClinicSetupButton ->
                                    equivalent), keep BrandMark pattern
    onboarding/                    KEEP the wizard step-machine, rewrite
                                    Step 6/7 content (feature grid, domain
                                    config) per §3.6/§3.9
  hooks/, lib/                     KEEP (staffAuth, API client, generic hooks)
```

---

## 10. Suggested first prompt to Claude in the new repo

Once cloned, a good opening instruction (adapt as needed):

> Read `docs/ARCHITECTURE_REFERENCE_FOR_FORKING.md`. This repo is a clone of a
> hospital-appointment WhatsApp product being turned into a restaurant
> table-reservation product ("Dine Connect"). Delete everything listed under
> "Delete or heavily rework," keep everything under "Reusable as-is / rename
> only" and "Reusable pattern, needs new implementation" (studying
> `flows/booking/types/procedure.py` as the template for table availability,
> per §4), and apply the vocabulary remap table. Do this in stages: (1) delete
> the dead files and their tests, confirm the app still boots and the existing
> test suite (minus the deleted tests) still passes, (2) rename the surviving
> domain tables/vocabulary, (3) only then start building the new
> table-availability and menu/ordering logic, which has no existing template
> to copy from this codebase (§7).

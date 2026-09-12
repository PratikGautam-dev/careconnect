# Portal UI audit

Tracks, per portal page, what's wired to real backend data vs. what's
built to match a reference design but has no data source yet. Updated as
each page gets redesigned.

## Patients

`frontend/src/app/portal/patients/page.tsx`

Table + a "selected patient" detail rail (mockup layout, same pattern as
Doctors), replacing the old plain search-and-delete list. Search, bulk
delete, and the checkbox/select-all columns are all kept, just relocated
into the new "Patient Management" card rather than dropped.

### Wired (some via a small, additive backend change)

- **Total Patients, Active Patients (of total)** — real, client-side counts
  over the loaded list, "Live count"/"of N total" hint (no historical
  snapshot to diff against, same treatment as other pages' cumulative
  totals).
- **New Registrations** — new: `list_patients()` (`db/repositories/
  patients.py`) now also selects `created_at` (already a real column,
  just not previously returned by this query); counted client-side as
  "created in the last 7 days," labeled "Last 7 days" rather than a fake
  "vs last week" delta, since there's no prior-period comparison anywhere.
- **Department, Age/Gender, Status, Last visit columns** — real:
  - **Department** — new: a correlated scalar subquery finds the
    *most recent appointment's* department for each patient (same
    join pattern `get_all_appointments_for_hospital()` already uses,
    `AppointmentRow` outerjoined to `Department`); "—" for a patient with
    no appointment yet.
  - **Age / Gender** — new: `list_patients()` now also selects
    `PatientRow.age`/`PatientRow.gender` (both already-real columns).
  - **Status** — real `active`/`blocked`/`inactive` (`PatientRow.status`,
    staff-set via the existing detail page). The mockup's 3rd pill state,
    "Follow-up Due," is **not** a real status value here (see Missing).
  - **Contact / Last visit** — unchanged real fields.
- **Department/Status/Gender filter dropdowns** — real, client-side over
  the loaded list; Department options are scoped to departments this
  patient list has actually had a visit in (derived from the same
  last-visit subquery above), not the hospital's full department catalog.
- **Detail panel — Overview tab**: Date of Birth, Gender, Phone, Address
  (real, via a light per-patient fetch of the same `/api/portal/patients/
  {id}` the full detail page already exposes); **Latest Visit** date +
  doctor + department — new: a second correlated subquery (same shape as
  Department above) resolves the most recent appointment's doctor name too.
- **Detail panel — Medical History / Appointments / Reports tabs** — real:
  this patient's actual notes / visit history / uploaded documents, via
  the same fetch. Read-only here; adding a note, rescheduling, or
  uploading/sending a document all stay on the full `/portal/patients/[id]`
  page (one link away from each tab), rather than duplicating that
  page's much larger edit surface.
- **Quick actions**: Book Appointment (opens `NewBookingDialog`, now
  pre-filled with the selected patient's name/phone via two new optional
  props threaded through `useNewBooking`), View Reports (switches to the
  Reports tab), Open full record (the existing detail page) — all real.
- **Numbered pagination + "N per page" dropdown** — `DataTable` gained an
  opt-in `pageSizeOptions` prop (numbered buttons with ellipsis, a page-size
  `<select>`) to match the mockup; every other table keeps the previous
  Prev/Next footer unchanged (prop omitted = old behavior).
- **Department/Status/Gender filters** — a new shared `FilterSelect`
  (`components/ui/FilterSelect.tsx`) component, driven by `options` built
  from a single labels map per filter (`STATUS_LABELS`/`GENDER_LABELS` in
  `patients-columns.tsx`, mirroring the backend's real enums) rather than
  hand-typed `<option>` tags — the table's status pill and the detail
  panel's status badge read the exact same maps, so they can't drift. The
  mockup's "More Filters" button was dropped rather than shown disabled:
  search + these 3 real dropdowns are the whole filter surface, so a
  "More Filters" button would open onto nothing.

### Missing

- **"+ Add Patient"** — disabled. Every patient record today is created
  as a side effect of a booking (staff new-booking form, or WhatsApp
  self-registration) — there's no standalone "create a patient" form.
- **Follow-up Due** (stat tile + status pill state) — no due-date/recall
  concept exists anywhere in this schema. The only near-miss field
  (`appointments.followup_override_until` + `hospital_settings.
  followup_validity_days`) means the *opposite*: it's a booking-type fee
  eligibility window ("still allowed to book a cheap follow-up"), not a
  "come back by X" reminder — confirmed before ruling this out, rather
  than building something with inverted semantics. Shown as "—".
- **Blood Group, Marital Status, Email, Allergies, Current Diagnosis** —
  none of these are tracked anywhere in this app (migration 0001's own
  schema comment explicitly scopes allergies/conditions/diagnosis codes
  as out of scope). Shown as "—" or an explanatory note, not invented.
- **Send Message** quick action — no patient-facing internal messaging
  exists. Disabled, "Coming soon".

## Doctors

`frontend/src/app/portal/doctors/page.tsx`

Table + a "selected doctor" detail rail (mockup layout) replacing the old
single expandable list; the Doctors/Departments tab switch, add/edit doctor
form, CSV import, and per-doctor schedule/leave management are all kept,
just relocated (see below) rather than dropped for the new layout.

### Wired (some via a small, additive backend change)

- **Total doctors, Active doctors (of total), Departments covered** — real,
  client-side counts, same "Live count" no-delta treatment as other pages'
  cumulative totals (no historical snapshot to diff against).
- **On leave** (today) — new: `get_doctors_on_leave_today_count()`
  (`db/repositories/doctors.py`), a `DoctorLeave` count for today's date;
  wired into `/api/portal/doctors` as `on_leave_today_count`. Backend tests
  (134 doctor-related) still pass.
- **Doctor table**: avatar, name, specialization, department — unchanged
  real fields.
  - **Qualification, Experience, Email** — new: `get_all_doctors_for_hospital()`
    now also selects `qualification`/`years_experience`/`email`/
    `working_days`/`working_hours` (same query, no extra round trip) so the
    table and detail panel don't need a separate per-doctor fetch just to
    show them.
  - **Availability** — real, but only the existing binary
    Available/Unavailable (`is_active`) toggle; there's no real-time
    presence tracking, so the mockup's finer In Consultation/In Surgery
    states aren't shown.
  - **Contact** — email is real; phone shows "Not tracked" (no phone field
    exists anywhere on a doctor record in this schema).
- **Detail panel**: Department, Experience, Email, and **Consulting
  hours** (derived from the same `working_days`/`working_hours` fields the
  edit form already used) are all real.
- **Quick actions**: Edit profile (opens the existing edit form), Book
  appointment (opens the existing `NewBookingDialog` — not pre-filled with
  this doctor, since that dialog has no such param yet), Mark
  available/unavailable, View schedule (today's appointments + the slot
  manager, both pre-existing components), Manage leave (the pre-existing
  leave manager) — all real, all reused, not rebuilt.
- Add doctor / Bulk import / Departments tab / Add department — unchanged,
  moved into the page header / a header toggle instead of always-visible
  page furniture, same underlying forms and mutations as before.

### Missing

- **Employee ID, Phone, Location, Room/Cabin, "Available since HH:MM"** —
  none of these exist anywhere in this schema (doctors have no phone,
  employee ID, location, or room-assignment field, and no timestamp on the
  active/inactive toggle). Shown as "—" with an explanatory note in the
  panel, not invented.
- **Send message** quick action — no doctor-facing internal messaging
  exists. Disabled, "Coming soon".
- **Filters** button — no filter panel beyond the existing search +
  available/unavailable select. Disabled, "Coming soon".

## Admin dashboard

`frontend/src/app/portal/dashboard/page.tsx`

### Wired

- **Today's appointments, new patients, no-shows** — `/api/portal/dashboard`
  stats (`get_dashboard_stats`), with week-over-week deltas.
- **Total appointments** — derived from the same ±30-day department-breakdown
  query the donut uses, so the tile and the donut's center total agree.
- **Active doctors** (of total) — `get_staffing_stats()`, counts real
  `DoctorRow` rows.
- **Staff on duty** (of total) — same `get_staffing_stats()`, counts active
  `StaffDetail`/`Identity` rows. Labeled as active *accounts*, not
  attendance (see Missing).
- **Appointment trends** (bar chart) — `get_weekly_appointment_counts`.
- **Appointments by department** (donut) — `get_appointments_by_department`.
- **Recent appointments** table — `get_all_appointments_for_hospital`. Now
  shares its exact column styling (avatar+name+phone Patient cell,
  Appointment type icon+label, Status colors, Mode) with the Doctor
  appointments table, via the same exported `AVATAR_TINTS`/`STATUS_STYLES`/
  `STATUS_LABELS`/`TYPE_ICONS`/`initials` from `appointments-columns.tsx`,
  instead of a second, independently-drifting copy of the same fields;
  `appointment_type_id`/`video_link` newly added to `/api/portal/
  dashboard`'s response (already on the same row, no extra query) to make
  that possible. Read-only (no select/Actions column) — this is a preview
  of the full table, not a place to manage a booking from. "View all
  patients" → "View all appointments", now linking to `/portal/
  appointments`.
- **Today's activity** feed — `get_recent_activity_feed`; the backend
  already returned this on `/api/portal/dashboard`, it just wasn't typed/used
  on the frontend before this pass.
- **Account menu** (top bar) — real session/settings/logout.
- **Caching**: `/api/portal/dashboard` (7+ queries per request, including a
  per-row `get_patient_by_phone` call) now has a 20s-TTL, no-invalidation
  cache (same two-tier local-dict-in-front-of-Redis shape as the mini
  calendar's own cache below) — TTL matches the frontend's own poll
  interval, so a page-switch-and-back or a second staff member viewing at
  the same time returns instantly from cache. Frontend-side, `usePortalDashboard`
  now goes through the app's single `QueryClient` (`useQuery`, same as
  `useAppointments.ts`) instead of local `useState` — navigating away from
  `/portal/dashboard` and back shows the last-known data immediately from
  the client-side cache (with a background refetch) rather than blanking to
  "Loading…" and paying a fresh round trip every time.
- **Quick actions**: Add doctor, Add staff, Create test — real navigation to
  the pages that already own those add-forms. Book appointment/Book test open
  `NewBookingDialog`/`NewTestBookingDialog` (see Doctor appointments/
  Diagnostic & lab sections below) directly from the dashboard. Export
  report — disabled, no backend.
- **Mini calendar** — now real: one fetch per month navigated to (not per
  day) via the new `GET /api/portal/bookings/calendar?year=&month=&category=`,
  the doctor-portal's own existing `/api/doctor/appointments/calendar`
  pattern (`AppointmentCalendar.tsx`) generalized to hospital-wide +
  category-scoped. Day cells show a booking-count badge; clicking a day
  lists that day's bookings (patient, time, status) below the grid, all
  derived client-side from the one month-array already fetched — no
  per-day request. Scoped to **all** appointment types here (Dashboard);
  the Doctor appointments/Diagnostic & lab pages pass `category="doctor"`/
  `"diagnostic"` respectively (see those sections). Cached server-side for
  60s (local dict + Redis via `core/redis_client.py`, no invalidation
  wired into booking create/cancel/reschedule — a glanceable widget being
  up to a minute stale is an accepted tradeoff against touching every
  booking-mutation call site).

### Missing (no backend concept yet)

- **Pending leave requests** tile / **Pending approvals** card — doctor leave
  (`db/repositories/leave.py`) is a direct, unmoderated whole-day-off record;
  there's no pending/approved status, and no staff-leave or schedule-change
  request type exists at all. Shown as sample entries.
- **Revenue / Collections** tile — no billing/invoice backend anywhere in
  this app.
- **Staff attendance (today)** widget — no check-in/attendance tracking
  exists (only account-active, not "present today"). Shown as an explicit
  empty state, not an invented percentage.
- **Header search** — no cross-entity search endpoint (patient search exists
  but is scoped to the Patients page only). Disabled, "Coming soon".
- **Notification bell** — no notification system exists. Disabled, "Coming
  soon".
- **Quick actions**: Broadcast message, Export report — no backend endpoint
  for either. Disabled, "Coming soon".

## Doctor appointments

`frontend/src/app/portal/appointments/page.tsx`

Now scoped to doctor-type appointments only (`appointment_type_id` in
new/followup/tele, plus legacy typeless rows) — diagnostic/lab/daycare and
second-opinion (report review) appointments are excluded, matching the
sidebar's own 3-way split (`appointment_types.py`'s
`BOOK_DOCTOR_APPOINTMENT_CATEGORY`/`TESTS_DIAGNOSTICS_CATEGORY`). The
type-tab bar (New/Follow-up/Tele/...) was replaced by the mockup's
time/status tabs.

### Wired

- **Total doctor appointments, Today's appointments** (+ vs-yesterday delta) —
  computed client-side from the already-loaded, already doctor-scoped list
  (same "list is small, no server round trip needed" approach the search box
  already used here).
- **Completed consultations** — real count of `status="attended"` rows.
- **All / Today / Upcoming / Completed / Cancelled tabs + counts** — real,
  derived from `scheduled_at`/`status` on the loaded list.
- **Search** (patient name/phone/doctor/department/reference/ID) — same
  predicate the page already had.
- **Today's schedule** card — real, today's doctor appointments sorted by
  time.
- **Add new appointment** — opens the existing `NewBookingDialog`. The other
  4 quick-action buttons now all carry a real icon too, matching the mockup.
- **Table columns rebuilt to match the mockup, and to drop every
  test/diagnostic-only field** (per direct instruction — this table is
  doctor-appointments-only now):
  - Dropped: Reference, Patient ID, Booked-at, Source, and the **Lab
    Status** column entirely (always null here anyway, since lab/diagnostic
    appointments never reach this page).
  - Patient cell now shows a colored initials avatar + name + phone (no
    age/sex — not in this schema).
  - Appointment Type cell shows a small icon (per new/follow-up/tele) next
    to the label.
  - Attendance marking (previously its own "Visited" Yes/No column) moved
    into the row's Actions menu as "Mark attended"/"Mark no-show", so
    Actions stays a single kebab column like the mockup's.
  - Added a **Mode** column (Video vs In-person, derived from
    `appointment_type_id`/`video_link` — both real); the mockup's "Room"
    half of "Room / Mode" has no backing field anywhere in this schema, so
    it was dropped rather than shown as invented data.
  - Selection checkboxes and the bulk-delete button were kept (real,
    pre-existing functionality the mockup doesn't show) — flagged here as a
    deliberate difference from the image, not an oversight.
- Mini calendar — same real, per-month-bookings widget as the dashboard's
  (see that section), scoped here to `category="doctor"` only.

### Missing

- **Pending confirmations** tile — no such status exists; every booked row
  already reads "Confirmed". Shown as "—".
- **Filter** button — no filter panel built yet (search box covers the
  common case). Disabled, "Coming soon".
- **Export appointments** quick action — no backend for it. Disabled,
  "Coming soon".
- **Send reminder** — moved into each row's own Actions menu (next to the
  real Reschedule/Cancel there) rather than staying as a page-level Quick
  Action; still disabled, since no reminder backend exists. Reschedule and
  Cancel were already real, per-row-only actions (no "pick an appointment"
  flow from a standalone button exists, or is needed) — the page-level
  Quick Actions no longer duplicate them as disabled placeholders pointing
  back at the row.
- "Room / Mode" (from the mockup's table) — no room-assignment concept
  exists in this schema at all; not added as a column rather than shown with
  invented values.

## Diagnostic & lab test appointments

`frontend/src/app/portal/appointments/diagnostic/page.tsx`

Scoped to test-type appointments only (`appointment_type_id` in
diagnostic/lab/daycare), the other half of the same 3-way split Doctor
appointments uses — shares `useAppointments` (`category: "diagnostic"`),
`RescheduleDialog`, and the same `AppointmentCellAction` menu (now extended
with lab-status advancement).

### Wired

- **Total test bookings, Diagnostics today, Lab tests today** (+ real
  vs-yesterday deltas) — same client-side computation as the Doctor
  appointments page's tiles.
- **Report-lifecycle tracking now covers Diagnostics too, not just Lab
  Test** — previously `lab_status` was only ever set for `"lab"`-category
  bookings, so a Diagnostics-type row (MRI/CT Scan/X-Ray/...) had genuinely
  no way to track/advance its status at all, and even a Lab Test booking
  created via the staff "New test booking" dialog never got `lab_status`
  set in the first place (a real bug — `portal_create_new_test_booking`
  never called `set_lab_status()`). Both fixed: the dialog now calls
  `db.set_lab_status(hospital.id, created.id, "booked")` right after
  creation for either category, and `portal_advance_lab_status`
  (`POST /api/portal/bookings/{id}/lab-status`) now picks a per-category
  forward-map — Lab Test still goes `booked -> sample_collected ->
  processing` (a physical sample to collect), Diagnostics goes straight
  `booked -> processing` (nothing to collect for a scan). `report_ready` is
  reached the same way for both: automatically, the moment a lab report
  document is uploaded — never a manual staff click. Frontend mirrors this
  with a per-category `LAB_STATUS_NEXT_LABEL` map in
  `appointments-cellaction.tsx` ("Mark sample collected"/"Mark processing"
  for Lab Test, "Mark in progress" for Diagnostics).
- **Pending report uploads** — now counts BOTH Lab Test and Diagnostics
  rows still booked without a report (previously Lab Test-only, back when
  Diagnostics had no status field to check).
- **All bookings / Diagnostics / Lab tests / Completed / Pending /
  Cancelled tabs + counts** — real, derived from `appointment_type_id`/
  `status` on the loaded list.
- **Status column** — reads `lab_status` (Pending/Sample Collected/
  Processing/Completed) for a still-booked row of EITHER category now (a
  Diagnostics row just never actually shows "Sample Collected", since its
  forward-map skips that stage) — falls back to the plain appointment
  status (Confirmed/Attended/Cancelled/...) for any resolved row, or one
  with no `lab_status` at all.
- **Today's lab queue** card — deliberately stays Lab Test-only (unlike
  Pending report uploads above): its stage labels ("Waiting for sample
  collection", "Sample collected") describe a physical specimen workflow
  that doesn't apply to Diagnostics/imaging at all, so folding them in here
  would misrepresent them rather than just under-counting. Real breakdown by
  `lab_status` among today's Lab Test bookings (Diagnostics-type has no
  equivalent stage tracking IN THIS CARD specifically — see above — so
  this card is Lab Test-only too).
- **Test / Procedure, Assigned department, Patient ID** columns — real
  (`diagnostic_test_name`, `department_name`, `patient_display_id`).
- **New test booking** quick action — opens `NewTestBookingDialog`, a
  resource-bound sibling of `NewBookingDialog` (Patient → Test/service →
  Date → Slot, no department/doctor step). Posts to the new
  `POST /api/portal/new-test-booking`, which reuses the existing
  `/api/portal/new-booking/context` data (departments/doctors/resources) and
  the same `connector.create_booking(diagnostic_test_id=...)` path
  `RescheduleDialog` already exercised for resource-bound appointments. Also
  mounted from the Dashboard's Quick Actions ("Book test") the same way
  "Book appointment" mounts `NewBookingDialog` there.
- **2026-09-11 schema cleanup**: `appointments` used to carry two separate
  FK columns pointing at `diagnostic_tests.id` — `resource_id` (the one
  actually wired into the slot-locking/double-booking check, the unique
  index, and the doctor-or-resource-or-procedure CHECK constraint) and a
  fully-redundant `diagnostic_test_id` always set to the same value (or left
  `NULL` for a Lab Test basket booking). Merged into one column,
  `diagnostic_test_id`, via a real Alembic migration (data preserved) — see
  that migration's own docstring. Every backend/frontend reference
  (`_appointment_json`'s `resource_id`/`resource_name` keys, the
  `/new-booking/slots?resource_id=` query param, the `Appointment` TS type's
  fields, etc.) renamed to match.
- **Multi-test lab booking (parity with the WhatsApp Lab Test basket)**:
  `NewTestBookingDialog` now lets staff pick MULTIPLE lab-category tests in
  one booking (checkboxes + a running chip list + price total), matching
  `flows/booking/types/lab.py`'s existing basket for patients booking via
  WhatsApp — one collection method (Visit/Home, with pincode+address for
  Home) and one slot for the whole basket, anchored on the first test
  picked, persisted via the same `set_appointment_lab_order_details()` call
  (which also bulk-inserts the N-row `appointment_lab_tests` basket table —
  previously only ever written by the WhatsApp flow, so it looked
  permanently empty from the portal side). Diagnostic-category tests stay
  single-select (no basket concept there either, on either booking path);
  picking a test of a different category than what's already selected
  replaces the whole selection rather than mixing categories, mirroring the
  backend's own rejection of a mixed-category basket.
- **Bug fix**: the route wasn't setting `appointment_type_id` on the created
  appointment, so it defaulted to `NULL` -- which `_apply_category_filter()`'s
  legacy-row convention folds into the "doctor" category, so a test booking
  showed up on the Doctor appointments page instead of here. Fixed by
  passing `appointment_type_id=test["category"]` ("diagnostic" or "lab",
  `diagnostic_tests.category`'s own CHECK constraint) through to
  `connector.create_booking()`.
- **Perf follow-up** (both booking dialogs, `RescheduleDialog`, and the
  patient page's follow-up "Book now" panel): `/api/portal/new-booking/context`
  used to eager-load EVERY doctor's and EVERY resource's available slots on
  every open (`slots_by_doctor`/`slots_by_resource`) -- for even this app's
  small dev seed (10 doctors + 15 tests), that's 25 items x several real DB
  round trips each (a Redis cache hit still costs 2 queries; a miss costs
  several more plus a hospital-settings write), noticeably slow to open. Now
  `/context` returns only departments/doctors/resources (list-only, cheap),
  and slots for whichever ONE doctor/resource is actually relevant are
  fetched lazily via the new `GET /api/portal/new-booking/slots?doctor_id=`/
  `?diagnostic_test_id=` (`fetchSlotsByDate` in `useAppointments.ts`, shared by all
  four consumers). Also dropped the disabled "Branch" field from both
  dialogs (single-location hospital — nothing to actually choose).
- **View pending reports** quick action — switches to the Pending tab.
- Lab-status advancement ("Mark sample collected" / "Mark processing") and
  attendance marking, both folded into the row Actions menu — real,
  pre-existing hook mutations, previously only wired on the old combined
  appointments page.
- Mini calendar — same real, per-month-bookings widget as the dashboard's
  (see that section), scoped here to `category="diagnostic"` only.

### Missing

- **Upload lab report** — disabled. Document upload exists
  (`/portal/patients/[id]`, `document_type: "lab_report"`), but only
  patient-scoped, not from a specific booking here.
- **Generate test report**, **Filter** button — no backend for either.
  Disabled, "Coming soon".
- "Assigned Department / Lab Room" (mockup) — Department is real; no
  room-assignment concept exists anywhere in this schema, so "Lab Room" was
  dropped rather than invented (same call as the Doctor appointments page's
  "Room / Mode").
- Known gap found while building this, not fixed here (out of scope): the
  appointment detail page's "Doctor" field has no `diagnostic_test_name`
  fallback, so "View Details" on a diagnostic/lab row won't show its test
  name there.
- **Bug fix, found while investigating the lab_status work above**: the
  patient detail page's (`/portal/patients/[id]`) "Book follow-up now" panel
  wasn't gated by visit type at all -- only by `status === "attended"` --
  so it offered "Follow-up…" for a resource-bound (Diagnostics/Lab) attended
  visit too, even though "follow-up" is a doctor-consultation-only
  appointment_type_id with no test-category equivalent. Clicking it would
  have created a new appointment with `doctor_id`/`department_id`/
  `diagnostic_test_id` all `NULL` -- the exact invalid shape that violates
  `appointments_doctor_or_resource_or_procedure_chk` and crashes `init_db()`
  for everyone on next backend restart (the same incident that briefly took
  the dev server down while building this feature). Fixed at both layers:
  `portal_book_followup_now` now rejects a resource-bound source appointment
  with a 400 (defense in depth, since a direct API call bypasses the
  frontend), and `visit-history-columns.tsx`'s Follow-up cell now hides the
  action entirely for a Diagnostics/Lab/Daycare-type visit instead of
  offering something that always fails.

## Settings

`frontend/src/app/portal/settings/page.tsx`

Being rebuilt tab-by-tab against a reference mockup (segmented tabs:
General / Hospital Profile / Departments / Notifications / Integrations /
Security) — one screenshot per tab, General first. The previous single-page
real settings form is preserved untouched at `_reference/legacy-general-
settings-page.tsx` (a `_`-prefixed, unrouted folder) so nothing is lost
while each of its pieces finds a new home across these tabs.

### General tab — Wired

- **Advance Booking Limit** = real `future_booking_days`
  (`usePortalSettings`, 1–90 days).
- **Session Timeout** = real `session_timeout_minutes` (`usePortalSettings`,
  2–120 minutes).
- **Language** = real `default_language` (English/Hindi), plus a real
  **"Ask patients to choose a language"** toggle = `language_prompt_enabled`
  — both in the Hospital Information card now, not just the Appointment
  Settings/Security cards.
- **Business Hours** = real `business_hours_text` — added to Hospital
  Information (wasn't in the mockup as its own field, but fit naturally
  alongside Address/Phone/Email rather than needing its own tab).
- All four load/save through the same `/api/portal/settings` the legacy
  form used — Save Changes submits the real settings object (just these
  fields changed here), with the hook's own inline error/saved state shown
  next to the button. The two dropdowns' (Advance Booking Limit, Session
  Timeout) preset options are widened to include whatever value is actually
  stored, so a non-preset real value never mismatches the `<select>`.

### General tab — Mock (no backend concept yet)

- **Hospital Information**: Address, Phone Number, Email Address, Timezone,
  Date Format — none of these exist on `hospital_settings`/`hospitals`.
  **Hospital Name** is editable here; the legacy page makes it read-only
  ("tied to your Meta WhatsApp connection") — worth matching once this is
  wired, not free text. (Language, the language-prompt toggle, and Business
  Hours in this same card are real now — see Wired above.)
- **Hospital Branding** — logo upload (local `FileReader` preview only, not
  persisted), primary/secondary color, tagline: no branding concept exists
  anywhere in this schema.
- **WhatsApp Configuration** — enable toggle, business number, API key,
  connection status/Test Connection: no such config surface exists (the
  WhatsApp Business API credentials live in infra config, not app DB).
- **Appointment Settings** — Default Duration, Buffer Time, Maximum
  Appointments/Day, Allow Online Appointments, Require Appointment Approval,
  Send Appointment Reminders: none of these are real (Advance Booking Limit,
  above, is the one exception).
- **Notification Preferences** (all 6 toggles) — none are real; the closest
  existing concept is `reminder_offsets_hours`/`reminder_template_name`
  (configurable timing, not an on/off toggle).
- **Security & Session Settings** — Password Expiry, Require 2FA, Enforce
  Strong Password Policy, Allow Multiple Sessions, Log User Activities: none
  exist (Session Timeout, above, is the one exception).

### Real settings not yet placed in any new tab (still only in the legacy reference page)

- Welcome message text, Closing/thank-you message, Privacy notice text —
  real (`hospital_settings`); bot messaging content, not "info about your
  hospital," so no natural fit in Hospital Information (unlike Business
  Hours and Language/language-prompt, both now wired there — see above).
- Handoff auto-resolve hours, Require explicit patient confirmation — real.
- Follow-up appointments: eligibility window (days), follow-up fee, new
  consultation fee, home sample collection charge — real; doesn't appear
  anywhere in the new mockup yet.
- **Google Calendar connection** (`GoogleCalendarCard`) — real; likely
  belongs under a future **Integrations** tab.
- **Appointment type toggles** (`AppointmentTypeToggles`) — real; likely
  **Departments** (or a dedicated services tab not in the current 6).
- **Diagnostic tests manager** (`DiagnosticTestsManager`) — real; likely
  **Departments**.
- **Leave policy manager** (`LeavePolicyManager`) — real; unclear fit yet,
  maybe **Hospital Profile**.
- **Lab service areas manager** (`LabServiceAreasManager`) — real; likely
  **Departments**.

### Hospital Profile tab — Wired

- **Hospital Name** — real, read straight from the already-loaded
  `hospital.name` prop (`usePortalGuard`), disabled with the same "contact
  the platform team" hint as the legacy page and General tab's Hospital
  Information card. Not part of this tab's own mock state, so there's no
  third, independently-editable copy of it anywhere.

### Hospital Profile tab — Mock (no backend concept yet)

Everything else on this tab is local mock state
(`hospital-profile-mock.ts`) — none of it exists on `hospital_settings`/
`hospitals`/anywhere else in this schema:

- **Hospital Overview** — Short Name, Hospital Type, Established Year,
  About Hospital (with a live character counter).
- **Hospital Logo & Cover** — logo AND cover image, both local `FileReader`
  previews only, not persisted (same non-persistence as General tab's own
  logo upload).
- **Registration & License Details** — registration/license numbers,
  issuing authority, validity dates.
- **Accreditation & Certifications** — accreditation body/number/validity.
- **Contact Information** — Alternate Phone and Website are net-new mock
  fields; Phone/Email/Address duplicate General tab's Hospital Information
  card fields (also mock there) rather than sharing one source of truth —
  matches the reference mockup, which shows Address in both places too, but
  worth flagging: editing one does NOT update the other.
- **Emergency Contact**, **Operating Hours**, **Bed Capacity** — no
  equivalent concept anywhere in this app.
- **Specialties & Services** — an editable chip list (add/remove); no
  specialty/service catalog exists on a hospital record (doctors have their
  own `specialization` field, unrelated to this).
- **Branch / Campus Information** — a small local table; "+ Add Branch"
  appends a mock row, editing a non-main-campus row is a stub ("isn't wired
  to a backend yet" toast). No multi-branch/campus concept exists anywhere
  — this app models one hospital per tenant.

### Departments tab — fully real (by explicit request, not mocked)

`frontend/src/app/portal/settings/_components/DepartmentsTab.tsx` /
`frontend/src/hooks/useDepartments.ts` (`useDepartmentsAdmin`) / backend
`portal/routes/departments.py`, migration `20260912141027`.

Unlike General/Hospital Profile, this tab was built real end-to-end,
confirmed with the user up front. `departments` was previously just
`(id, hospital_id, name)` — this migration adds a profile (`floor_wing`,
`consultation_hours`, `description`, `head_doctor_id`), an internal
`is_active` status, and three patient-facing visibility flags.

- **Stat tiles** (Total/Active Departments, Doctors/Support Staff
  Assigned) — real, computed client-side from the loaded list. No
  historical snapshot exists for a "+2 this month" delta (no `created_at`
  on departments) — rendered as "Live count", same no-history treatment
  Patients/Doctors already give their own cumulative tiles.
- **Department Directory table** (search, status filter, numbered
  pagination) and **Department Details** panel (Head of Department,
  Floor/Wing, Consultation Hours, doctor/support-staff counts,
  Description) — all real, via the new `GET /api/portal/departments`
  (`get_all_departments_for_hospital`): doctor_count/support_staff_count
  are correlated-subquery counts against `doctors`/`staff_details`
  (support-staff rows there are already exclusively non-doctor, enforced
  by the existing `ck_staff_details_department_doctor_role` CHECK), and
  Head of Department is an outer join to `doctors` (+ `staff_details`/
  `identities` for their portal-login email, same source
  `get_all_doctors_for_hospital`'s own `login_email` uses — `doctors.email`
  itself was dropped in migration `20260911190251`).
- **Add/Edit Department**, **Deactivate/Activate** — real
  (`POST`/`PATCH /api/portal/departments[/…]`, `.../active`), gated by the
  existing `manage_departments` capability the original bare create route
  already used.
- **Patient-Facing Availability** (3 toggles, from the user's own separate
  design note, not the original screenshot) — **`show_on_frontend`** and
  **`whatsapp_booking_enabled`** are both real: they gate
  `db.get_departments()`, the WhatsApp booking flow's one department-picker
  query (`connector.get_departments()`, called throughout `flows/
  booking/*.py`) — a hidden or deactivated department is confirmed (via
  `tests/test_booking_flow.py`) to actually disappear from that menu.
  **`online_booking_enabled`** is real (stored, toggleable, returned) but
  **has no enforcement point of its own** — this app's only real
  patient-facing channel is WhatsApp (confirmed: no separate web/online
  booking route exists anywhere in this codebase), so there's nothing
  else to gate yet. Flagged in its own hint text in the UI, not left
  silently inert.
- **Quick Actions — Assign Doctor / Manage Staff** — real, no new backend
  needed: "Assign Doctor" fetches the doctor's full existing record first
  (`GET /api/portal/doctors/{id}`) and resubmits it with `department_id`
  changed (the update route fully re-validates/replaces every field, same
  as the Doctors page's own edit form — a bare `{department_id}` PATCH
  would have blanked out their specialization/qualification/hours).
  "Manage Staff" is a true partial `PATCH /api/portal/staff/{id}`
  (`department_id` only) — the staff route reads `model_fields_set`, so
  this one genuinely doesn't need the fetch-full-record dance.
- **Staff-facing call sites fixed to NOT use the new patient-only filter**:
  `GET /api/portal/doctors`'s own bundled `departments` list (the Doctors
  page's department list + Add/Edit Doctor's department picker), the CSV
  doctor-import's existing-department lookup, and the staff portal's own
  "new booking" context (`auth/session.py`, new `connector.
  get_all_departments()`) — all three now call the unfiltered
  `get_all_departments_for_hospital` instead of the newly-filtered
  `get_departments`, so a department a staff member hid from WhatsApp
  patients doesn't also silently disappear from staff's own tools.

### Notifications / Integrations / Security tabs

Not built yet — each renders a plain "share the reference screenshot to
build it out" placeholder card until its own mockup arrives.

## Sidebar navigation

`frontend/src/components/portal/PortalSidebar.tsx`

Visual pass only (menu list/order/labels/icons matched to the reference
mockup) — deeper wiring below is deliberate follow-up, not done yet.

### Wired

- Dashboard, Doctor appointments, Diagnostic & lab test appointments,
  Patients, Doctors, Staff, Messages, Roles & permissions, Settings —
  real routes (Doctor appointments/Staff relabeled from "Appointments"/
  "Staff" for the mockup's wording; Diagnostic & lab test appointments and
  Doctor appointments share the "appointments" RBAC permission, being two
  views of the same underlying list).

### Missing (disabled, "Coming soon")

- **Report review**, **Billing**, **Report analytics**, **Leave requests**
  (as a request queue) — no backend/page for any of these exists.

### Dropped from the visible list

- **Schedule** (`/portal/schedule`) — a doctor's own schedule/leave view,
  real and doctor-role-only. Not in the reference mockup's menu, so it's
  out of the visible list for now; a doctor account currently has no
  sidebar link to it. Flagging in case that's unwanted — easy to add back.

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
- **Quick actions**: Add doctor, Add staff, Create test — real navigation to
  the pages that already own those add-forms.

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
- **Mini calendar** — a real, date-correct month grid, but no events
  plotted; no calendar/scheduling backend exists (dropped from
  `PortalSidebar`'s nav for the same reason).
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
- Mini calendar — same real, date-correct (but eventless) grid as the
  dashboard's.

### Missing

- **Pending confirmations** tile — no such status exists; every booked row
  already reads "Confirmed". Shown as "—".
- **Filter** button — no filter panel built yet (search box covers the
  common case). Disabled, "Coming soon".
- **Reschedule appointment / Cancel appointment / Send reminder / Export
  appointments** quick actions — reschedule/cancel already exist per-row in
  the table (no "pick an appointment" flow from a standalone button yet);
  reminders and export have no backend at all. Disabled, "Coming soon".
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
- **Pending report uploads** — real, but **Lab Test-only**: count of
  still-booked Lab Test rows whose `lab_status` hasn't reached
  `report_ready`. Diagnostics-type bookings have no equivalent status field
  at all, so they can't be counted here (see Missing).
- **All bookings / Diagnostics / Lab tests / Completed / Pending /
  Cancelled tabs + counts** — real, derived from `appointment_type_id`/
  `status` on the loaded list.
- **Status column** — reads `lab_status` (Pending/Sample Collected/
  Processing/Completed) for a still-booked Lab Test row; falls back to the
  plain appointment status (Confirmed/Attended/Cancelled/...) for
  Diagnostics-type rows and any resolved row of either type.
- **Today's lab queue** card — real breakdown by `lab_status` among today's
  Lab Test bookings (Diagnostics-type has no equivalent stage tracking, so
  this card is Lab Test-only too).
- **Test / Procedure, Assigned department, Patient ID** columns — real
  (`resource_name`, `department_name`, `patient_display_id`).
- **View pending reports** quick action — switches to the Pending tab.
- Lab-status advancement ("Mark sample collected" / "Mark processing") and
  attendance marking, both folded into the row Actions menu — real,
  pre-existing hook mutations, previously only wired on the old combined
  appointments page.

### Missing

- **New test booking** — disabled. `NewBookingDialog` only supports a
  doctor/department/date/slot flow; there's no resource/test equivalent
  picker yet, even though rescheduling an *existing* resource-bound booking
  already works (`RescheduleDialog` handles it).
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
  appointment detail page's "Doctor" field has no `resource_name` fallback,
  so "View Details" on a diagnostic/lab row won't show its test name there.

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

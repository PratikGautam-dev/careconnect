# Staff management, RBAC, leave & attendance — reference for porting

A map for someone picking this up cold in another repo (e.g. Dine Connect). It
describes what this repo actually contains for staff management, roles &
permissions, leave and attendance — data model, routes, UI structure, and the
sharp edges. It does not replace this repo's own history.

## Read this first: source and staleness

- **Frontend** paths (`src/...`) are read from this repo's current HEAD (`8d70fa7`).
- **Backend** paths (`backend/...`) are read from git history at `3448932`, the
  last commit before the split ("Split backend into a separate repo",
  `e9e1dc0`). The backend now lives in another repo, so it may have moved on.
  Treat backend details as accurate to that snapshot, and re-verify against the
  live backend repo before copying.
- Vocabulary here is CareConnect's (hospital, doctor, department). See the
  remap notes at the end.

## What exists

| Ask | Status | Where |
|---|---|---|
| 1. Staff management page | **Exists**, full CRUD except hard delete | `/portal/settings/staff` |
| 2. Roles & Permissions page | **Exists**, dynamic roles + per-page/per-action grid + per-user overrides | `/portal/settings/roles` |
| 3a. Doctor/resource schedule leave (blackout dates) | **Exists** | Doctors page → "leave" dialog; also diagnostic tests |
| 3b. Staff HR leave (request / approve / balance) | **Exists** — not a new feature | `/portal/holiday-application`, `/portal/leave-requests`, policy in Settings → General |
| 4. Staff attendance / clock-in | **Exists**, two independent things (see §5) | `/portal/check-in-out`, `/portal/attendance`, Settings → Attendance |

So nothing on the list is greenfield in this repo. The two items most likely
to be assumed missing (HR leave, attendance) are both built.

---

## 1. Data model (Postgres)

Identity is split: one shared credential row, plus a hospital-scoped extension.

- `identities(id, email, name, password_hash, google_id, is_active, token_version, ...)`
  — one row per human, globally unique email. `token_version` is the revocation
  counter (bumped on password reset/deactivate → all sessions die).
- `staff_details(identity_id PK→identities, hospital_id, role_id→roles, doctor_id?, department_id?, phone, address, reports_to_id→identities, attendance_status, employee_id, working_days, working_hours, breaks)`
  - `working_days/hours/breaks` are comma-joined TEXT (same model doctors use);
    validated in the app layer, no CHECK.
  - `attendance_status` ∈ `present|on_leave|half_day` — a **manually set**
    current status, unrelated to `attendance_records` (see §5).
  - `employee_id` is server-generated `EMP-ST-NNNNN` (empty for doctor-linked rows).
  - A doctor-linked row takes its department from the doctor, so `department_id`
    and `doctor_id` can't both be set (app-level check).
- `roles(id, hospital_id, name, description, is_protected)` — unique on
  `(hospital_id, lower(name))`. Only the seeded Admin is `is_protected`
  (undeletable). Receptionist/Doctor are ordinary roles.
- `role_permissions(hospital_id, role_id, page_key, can_view, can_write, can_delete)`
  — one row per (role, page). A role with **zero rows resolves to all-false**
  (fail-closed). The legacy `role` TEXT column is still there alongside `role_id`.
- `staff_permission_overrides(hospital_id, staff_id, page_key, can_view?, can_write?, can_delete?)`
  — sparse; NULL = inherit the role. The row is deleted once all three go NULL.
- `leave_requests(hospital_id, identity_id, leave_type, from_date, to_date, is_half_day, reason, status, decided_by, decided_at)`
  — `leave_type` ∈ casual/sick/annual/maternity/conference/personal;
  `status` ∈ pending/approved/rejected. Dates are ISO TEXT.
- `hospitals.doctor_annual_leave_days` (default 20), `hospitals.staff_annual_leave_days` (default 30).
- `doctor_leave(hospital_id, doctor_id, date, reason)` — `UNIQUE(doctor_id, date)`.
  Same idea exists for diagnostic tests / procedure resources
  (`diagnostic_resource_leave`, `procedure_resource_leave`).
- `attendance_records(hospital_id, staff_id→identities, date, check_in_at/lat/lng/ip/verified_method, check_out_at/lat/lng/ip, break_started_at, break_minutes, status, late_minutes, working_minutes, overtime_minutes)`
  — `UNIQUE(staff_id, date)`; status ∈ on_time/late/absent/leave/half_day.
- `hospital_settings` gained 9 nullable `attendance_*` columns (lat/lng, radius,
  allowed IP/CIDR list, shift start/end, early-checkin and late-threshold
  minutes, auto-checkout grace minutes). NULL = "not configured, skip that check".
- `audit_logs` records every write (see route tables).

Migrations live in two parallel mechanisms: Alembic (`db/migrations/versions`) and
a hand-maintained replay in `db/init_db.py`. New columns must be added to both.

## 2. Permission model (shared by everything below)

- **Page keys** are fixed strings in `portal/permissions.py`: `dashboard`,
  `appointments`, `daycare_appointments`, `diagnostic_appointments`, `patients`,
  `doctors`, `messages`, `settings`, `staff`, `roles`, `schedule`,
  `diagnostic_tests`, `leave_requests`, `holiday_application`, `attendance`,
  `check_in_out`, `attendance_settings`, `report-review`, `report-analytics`.
  Actions are `view | write | delete`.
- **Seed defaults** (`DEFAULT_PERMISSIONS_BY_ROLE_KIND`) are used only at hospital
  onboarding and when an admin creates a role from a "kind". Never consulted at
  request time.
- **Resolution** — `has_permission(hospital, staff, role, page, action)`: a
  non-NULL per-user override wins; otherwise the role matrix; otherwise false.
  Both layers are Redis-cached with pub/sub invalidation
  (`portal/permission_cache.py`), so edits apply immediately across workers.
- **Route guard pattern** (`portal/deps.py`):
  ```python
  principal = get_current_staff(authorization)      # JWT + fresh DB re-fetch
  if principal is None: return 401
  forbidden = require_permission(principal, "staff", "write")
  if forbidden: return forbidden                    # 403
  ```
  `get_current_staff` re-reads the staff row on every request, so deactivation,
  role changes and `token_version` bumps take effect on the very next call.
- **Two auth generations coexist.** Newer routes use the above. Older routes
  (`_authenticate` + `require_capability`, e.g. doctor leave, diagnostic tests)
  gate on the *tenant's* capability, not the caller's role.
- **Frontend** gets a `permissions` map at login/`/me` and uses
  `usePermission(page, action)` and `<PermissionGate page action>` to hide UI.
  The backend 403 is the real enforcement.

## 3. Staff management page — `/portal/settings/staff`

**Shows:** a 4-tile stat row (Total, Active, On Leave today, Departments) and a
two-column layout: a searchable, filterable, paginated staff directory
(DataTable; filters: department, active/inactive; search by name/email/dept/phone)
beside a detail panel for the selected row (auto-selects the first row).
Columns: Employee ID, Name (avatar + initials), Role, Department, Attendance
Status, Phone, row actions. Doctors are excluded server-side — they're managed
on the Doctors page.

**CRUD that exists:**

| Op | Route | Perm | Notes |
|---|---|---|---|
| List | `GET /api/portal/staff` | staff:view | excludes doctor-linked rows; includes leave balance |
| Options | `GET /api/portal/staff/options` | staff:view | `{id,name}` for every role incl. doctors, for the "reports to" picker |
| Create | `POST /api/portal/staff` | staff:write | name, email, password (≥8), role_id, optional doctor_id/phone/address/department_id/schedule/reports_to |
| Update | `PATCH /api/portal/staff/{id}` | staff:write | `is_active`, name, phone, address, department, schedule, reports_to, attendance_status. Uses `model_fields_set` so a sent `null` can clear a field |
| Reset password | `POST /api/portal/staff/{id}/password` | staff:write | admin-initiated, no current-password check; bumps `token_version` |
| Delete | — | — | **none** — deactivate only |

Every write is scoped to the caller's hospital by re-listing that hospital's
staff and matching the id (the underlying setters have no hospital filter).
Every write writes an audit log entry.

**Frontend structure:** `src/app/portal/settings/staff/page.tsx` (page),
`_components/staff-columns.tsx` (column defs), `staff-cellaction.tsx` (row menu),
`StaffDetailPanel.tsx`; `components/portal/AddStaffDialog.tsx`,
`EditStaffDialog.tsx`, `StaffContactFields.tsx`; hooks `useStaffManagement`
(list, toggle active, set attendance, reset password), `useAddStaff`,
`useEditStaff`, `useStaffDetail`. The Add dialog is also opened from the dashboard's
Quick Actions, which is why it has its own hook. The reset-password dialog is
inline in the page and validated with a zod schema (`lib/validation/setStaffPassword.ts`).

**Related:** `/portal/settings/profile-settings` is a *read-only* own-profile page
(edit is a "coming soon" stub) with a working change-password card.

## 4. Roles & Permissions page — `/portal/settings/roles`

**Shows:** 4 stat tiles; a "Role Management" table (per role: user count and
actions Edit Permissions / Manage Users / Rename / Delete); a Quick Actions card
(Add New Role, Audit Logs link); and a read-only "Module Access Overview"
matrix (roles × pages, check/dash for *view*).

**Dialogs:** (a) *Edit permissions* — a page × {view, write, delete} checkbox grid
for one role; each toggle is an optimistic `PUT` rolled back on failure.
(b) *Manage Users* — lists staff on the role, then a nested dialog with a
per-user override grid (pre-filled from the role, "Custom" tag to reset a cell).
(c) *Add / Rename role* — name, description, optional "clone permissions from".

| Op | Route | Perm |
|---|---|---|
| List roles (with staff counts) | `GET /api/portal/roles` | roles:view |
| Create | `POST /api/portal/roles` | roles:write (optionally clones another role's *current* rows) |
| Rename / describe | `PATCH /api/portal/roles/{id}` | roles:write |
| Delete | `DELETE /api/portal/roles/{id}` | roles:write; blocked if protected or any active staff still on it |
| Permission matrix | `GET /api/portal/roles/permissions` | roles:view |
| Batch update cells | `PUT /api/portal/roles/permissions` | roles:write, body `{updates:[{role_id,page_key,can_*}]}` |
| Users on a role + overrides | `GET /api/portal/roles/{id}/users` | roles:view |
| Set/clear a user's overrides | `PUT /api/portal/staff/{id}/permissions` | roles:write, each action true/false/null |

Frontend: `settings/roles/page.tsx`, `_components/role-columns.tsx`,
`hooks/usePortalRoles.ts` (state + matrix + all mutations). The grid's page list
and labels are **hard-coded twice** (frontend `PAGE_KEYS`/`PAGE_LABEL` and backend
`ALL_PAGES`) — they must be kept in sync by hand.

## 5. Leave and attendance

### 5a. Doctor / resource schedule leave (blackout dates)
Whole-day unavailability. `generate/compute slots` skips any date present in
`doctor_leave`, so the doctor simply stops being bookable that day.
- Routes: `GET/POST /api/portal/doctors/{id}/leave`, `POST .../leave/range`
  (From/To, max 366 days, idempotent per day), `POST .../leave/{leave_id}/delete`.
- UI: `components/portal/DoctorLeaveManager.tsx` + `hooks/useDoctorLeave.ts`,
  shown in a dialog on the Doctors page ("Dr. X — leave"). A list of dates with a
  delete icon, plus From / To / Reason inputs and "Confirm leave". Diagnostic tests
  have the same pattern (`TestLeaveManager`, `useTestLeave`) but key leave by date.
- **No approval workflow or balance** — it's a scheduling switch, distinct from 5b.
- Gap: these routes are gated by tenant capability (`manage_doctors`), not by a
  role permission, so any authenticated staff role reaches them.

### 5b. Staff HR leave (request → approve → balance)
This exists and is separate from 5a.
- **Apply** (self-service, any role): `/portal/holiday-application`
  (`HolidayApplicationView.tsx`) — balance tiles (quota / used / pending), an apply
  form (type, from/to, full-day vs half-day, reason), a leave calendar coloured by
  status, and request history. `GET/POST /api/portal/leave-requests/mine`,
  perm `holiday_application`. Half-day only for a single day; reason required.
- **Review** (admin): `/portal/leave-requests` — 5 stat tiles, tabs (All / Doctors /
  Staff / Pending / Approved / Rejected), search, table, detail panel with
  approve/reject. `GET /api/portal/leave-requests`, `POST .../{id}/approve|reject`,
  perm `leave_requests`. The "Filters" button is a disabled stub.
- **Policy:** annual allowance per hospital, one number for doctors and one for
  other staff (`GET/POST /api/portal/leave-requests/policy`, edited via
  `LeavePolicyManager` in Settings → General). Balance = quota − approved days used
  in the current calendar year (half-day counts as 0.5; a request spanning New
  Year is clipped to each year; usage resets every Jan 1 with no carry-over).
- **Link to 5a:** approving a full-day request for a doctor-linked applicant
  auto-creates `doctor_leave` rows for the range, so approved leave blocks
  bookings. Half-day approvals do **not** (the blackout table has no half-days).
- Limits: leave balance is only tracked for roles literally named "receptionist"
  (matched by role *name*, so renaming the role drops tracking); admin rows show
  no balance.

### 5c. Attendance / clock-in — two disconnected mechanisms
1. **Manual status:** `staff_details.attendance_status` (present / on_leave /
   half_day), set by an admin from the staff detail panel (`PATCH /staff/{id}`).
   This feeds the "On Leave" tile on the staff page. No timestamps, no history.
2. **Real geofenced check-in/out** (built later, migrations `2026091809xxxx`):
   - `POST /api/portal/attendance/check-in` (lat/lng from the browser
     Geolocation API + server-seen IP), `/check-out`, `/break/start`,
     `/break/end`; `GET /today`, `/summary?days=`, `/hospital?for_date=`.
   - A check-in passes if **either** configured check passes — GPS within radius
     (geopy geodesic) **or** IP in an allowed IP/CIDR list. If neither is
     configured, it's allowed. Rejections report the measured distance.
   - On-time/late is computed in the hospital's timezone against the staff
     member's own earliest shift start, falling back to the hospital-wide shift
     start. One row per staff per day.
   - Auto-checkout: `POST /internal/auto-checkout` (external cron + secret +
     Redis lock) closes open rows at `shift_end + grace`. It rolls over midnight.
   - UI: `/portal/check-in-out` (status tiles, live work timer, quick actions,
     recent history, check-in confirmation modal), `/portal/attendance`
     (personal stats, trend chart, status donut, records table), and Settings →
     Attendance (`AttendanceSettingsTab`: location, radius, IP list with an
     "add my current IP" helper, shift window, grace period). A
     `DashboardStaffAttendance` widget exists on the dashboard.
   - Permissions: `check_in_out` (do it), `attendance` (view), `attendance_settings`
     (configure; admin-only seed). Non-admin roles are seeded with the first two;
     **Admin is deliberately seeded with neither** (an admin can grant them).
   - Known holes: **Absent days always report 0** and the Leave slice never
     appears (nothing writes `status='leave'`, and there's no cross-check against
     working days or approved leave). Automatic break start/end is designed but not
     built. The monthly trend is a proxy, not worked/expected.

## 6. Sharp edges to fix rather than copy

1. **Overrides don't reach the frontend.** `/login` and `/me` return
   `get_permission_matrix(...).get(role_id)` — the role only. Per-user overrides
   are enforced by the backend but never merged into that map, so the UI can show
   a control that 403s (revoked override) or hide one that would work (granted
   override). Merge `get_staff_override_matrix` into that response.
2. **Inconsistent error shapes.** Most routes return `{"error": "..."}`, but
   `PUT /roles/permissions` and `PUT /staff/{id}/permissions` return
   `{"errors": [...]}`. The frontend's `staffFetch` reads `.error`, so those
   messages are swallowed. (The same bug already bit `POST /staff` once.)
3. **`attendance_settings` isn't in the frontend grid.** The backend has the page
   key, but the roles page's `PAGE_KEYS` omits it, so an admin can't edit it there.
4. **Server date vs hospital timezone.** `check_in` keys the record on
   `date.today()` (server-local) while on-time/late uses the hospital timezone; a
   non-UTC hospital near midnight can disagree.
5. **Role-name coupling.** Leave-balance tracking matches the role name
   "receptionist".
6. **Two page-key lists** (frontend + backend) and a stale comment in
   `usePortalRoles.ts` referring to a `useRoleManagement.ts` that doesn't exist.

## 7. Porting notes for a new vertical

- **Keep as-is (rename only):** identities/staff_details split, roles +
  role_permissions + overrides + the resolution function, the route-guard pattern,
  the Redis cache invalidation, the audit log, `employee_id` numbering, all three UIs.
- **Rework:** the page-key list (replace healthcare pages with your own, in *both*
  places), the seed defaults per role kind, and the "doctor" coupling —
  `staff_details.doctor_id` and the doctor-leave link exist only because doctors
  are bookable resources. Dine Connect should decide whether tables/hosts are
  bookable resources (then keep 5a under their name) or whether "staff" is purely
  HR (then drop `doctor_id`, `is_doctor_role`, and the leave→blackout hook).
- **Vocabulary:** hospital → restaurant/venue; department → section/station;
  doctor → the bookable resource, if any.
- **Decide early:** whether attendance needs the geofence at all (a restaurant with
  a fixed site probably does; a multi-site chain needs a *list* of locations — this
  repo supports exactly one per tenant).
- **Not present anywhere:** shift scheduling/rostering (who works when) beyond the
  free-text working-days/hours fields, payroll/timesheet export, and leave
  carry-over/accrual rules. Design those fresh.

## 8. File map

Frontend (this repo, `src/`): `app/portal/settings/{staff,roles,profile-settings}/`,
`app/portal/{leave-requests,holiday-application,check-in-out,attendance}/`,
`app/portal/settings/_components/{AttendanceSettingsTab,GeneralSettingsTab}.tsx`,
`components/portal/{AddStaffDialog,EditStaffDialog,StaffContactFields,DoctorLeaveManager,TestLeaveManager,LeavePolicyManager,HolidayApplicationView,DashboardStaffAttendance,PermissionGate,StaffSessionProvider}.tsx`,
`hooks/{useStaffManagement,useAddStaff,useEditStaff,useStaffDetail,useStaffProfile,usePortalRoles,useDoctorLeave,useTestLeave,useLeaveRequests,useLeavePolicy,useHolidayApplication,useAttendanceSettings}.ts`,
`lib/{staffAuth,portalAuth}.ts` (`portalFetch` is just an alias of `staffFetch`).

Backend (pre-split snapshot, `backend/`): `portal/routes/{staff,roles,leave_requests,attendance,doctors,settings,staff_auth}.py`,
`portal/{permissions,deps,permission_cache}.py`,
`db/repositories/{staff_users,roles,role_permissions,staff_permissions,leave,leave_requests,attendance,hospital_settings}.py`,
`db/schema.sql`, `db/migrations/versions/` (dynamic roles `144a8eabac9a`, overrides
`4055364a2019`, leave `20260912065049` + `6eda12041ecf`, attendance
`20260918090000/090100/090200`, `20260919080000`), `webhook/cron_routes.py`
(auto-checkout). Tests: `tests/test_staff_management.py`,
`test_staff_permission_overrides.py`, `test_leave_requests.py`, `test_staff_set_password.py`,
`test_staff_change_password.py`, `test_staff_profile.py`. There is no dedicated
attendance test file in that snapshot.

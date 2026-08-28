# Tenant-Type Toggling & Future Hospital-Only Features — Hardening Plan

**Status: done.** All five gaps below are closed and covered by
`backend/tests/test_capability_gating.py` (27 tests in that file, 10 new).
Full backend suite: 670 passed. Frontend (`edit-tenant/[id]/page.tsx`)
typechecks clean. See "What actually shipped" at the end of this doc for the
few places the implementation diverged from the original plan below.

## Context

The concern that started this: a clinic tenant onboards today, and later
wants to add a department, or upgrade to "hospital" to get access to a
hospital-only feature (day care, etc.). That shouldn't require
re-onboarding, which would risk losing the clinic's existing data (patients,
appointments, doctors).

Investigation found **the hard part was already built and correctly
designed** (see `tenant-capability-gating-plan.md`). There is no separate
"tenant" table — `hospitals` is the tenant table for both hospitals and
clinics, and it already had:

- `tenant_type` (`'hospital'|'clinic'`) — descriptive/default-seeding metadata only.
- `admin_capabilities` (nullable JSON array) — the actual staff-portal gate,
  resolved via `backend/portal/capabilities.py`'s `get_capabilities()`
  (explicit override when set, else `DEFAULT_CAPABILITIES_BY_TYPE[tenant_type]`
  when `NULL`).
- A working toggle end-to-end: `POST /api/admin/tenants/{id}`
  (`backend/admin/tenants_api.py`) already accepted `tenant_type` and
  `admin_capabilities` updates, and the frontend
  (`frontend/src/app/admin/edit-tenant/[id]/page.tsx`) already had a "Tenant
  type" dropdown + capability checkboxes wired to it.
- Crucially, **nothing about this toggle ever deletes or touches
  departments/doctors/appointments/patients** — `admin_capabilities` only
  gates staff-portal *management* routes (`portal/routes/doctors.py`'s
  create/update/delete department & doctor endpoints, via
  `require_capability()`). Booking, viewing appointments, documents, and
  handoffs (`bookings.py`, `documents.py`, `handoffs.py`) are deliberately
  never capability-gated — any authenticated tenant can still see/manage its
  own existing data regardless of tenant_type. So flipping clinic → hospital
  or hospital → clinic was already **safe and non-destructive** by
  construction — there's no re-onboarding path to lose data in because
  nothing is ever deleted by this toggle.
- The single-department/single-doctor UX (a hospital with exactly one dept +
  one doctor "looks like a clinic" to patients) was **already handled
  correctly** in `backend/flows/booking/book.py` (`_handle_awaiting_appointment_type`,
  ~lines 149-184): it auto-skips department/doctor selection based on the
  *actual data shape* (`len(departments) == 1 and len(doctors) == 1`), not on
  `tenant_type`. Right pattern, needed no change — it degrades safely
  whether the tenant is tagged "clinic" or "hospital."

So this work was **not** "build tenant-type toggling" — it closed the real
gaps that would bite the *next* hospital-only feature (day care, and
whatever comes after it), plus a couple of rough edges in the toggle itself.

### Gaps found

1. **No tenant-aware gating for appointment types.** `appointment_types` was
   seeded identically for every tenant regardless of `tenant_type`
   (`db/init_db.py::_backfill_appointment_types`, using the fixed
   `DEFAULT_APPOINTMENT_TYPES` tuple in
   `db/repositories/appointment_types.py`). That tuple **already includes a
   `"daycare"` type** — seeded active for clinics and hospitals alike. A
   clinic would see "Daycare" in its WhatsApp booking menu exactly like a
   hospital would. This was precisely the "hospital-only feature" problem,
   already latent in the codebase.
2. **No portal CRUD for appointment types at all** (flagged in
   `tenant-capability-gating-plan.md` itself — "only seeded at onboarding").
   `manage_appointment_types` capability existed in the registry but was
   never checked anywhere — dead code.
3. **`manage_staff` is likewise defined but never enforced** — fine for now
   (no staff-management routes exist yet), left as-is; flagged so whoever
   builds those routes later knows to wire `require_capability`.
4. **Toggling `tenant_type` in the edit-tenant form didn't resync
   `admin_capabilities`.** The dropdown and the checkboxes were independent
   controls — switching "Clinic" → "Hospital" left the old capability
   checkboxes as-is until the operator manually rechecked them.
5. **No audit trail** for who changed a tenant's type/capabilities and when.

## Design (as implemented)

### 1. Tenant-type-aware appointment type defaults (closes the "day care" gap)

`backend/db/repositories/appointment_types.py` gained
`DEFAULT_ACTIVE_TYPES_BY_TENANT_TYPE` and `default_is_active(tenant_type, id)`,
mirroring `DEFAULT_CAPABILITIES_BY_TYPE` in `portal/capabilities.py`:

```python
DEFAULT_ACTIVE_TYPES_BY_TENANT_TYPE: dict[str, set[str]] = {
    "hospital": {t["id"] for t in DEFAULT_APPOINTMENT_TYPES},
    "clinic": {t["id"] for t in DEFAULT_APPOINTMENT_TYPES if t["id"] != "daycare"},
}
```

Both `create_hospital()` (`db/repositories/hospitals.py`) and the startup
backfill (`_backfill_appointment_types()` in `db/init_db.py`) now resolve
`is_active` from this map instead of hardcoding `True`. A row still exists
for every type on every tenant — only `is_active` differs — so upgrading a
clinic to a hospital later is a pure `is_active` flip, never a
re-seed/backfill. `admin/onboarding_api.py` needed no direct change: it
already passes `tenant_type` into `create_hospital()`, which now handles the
rest internally.

When a genuinely new hospital-only feature is added later, the convention is:
add it to `DEFAULT_APPOINTMENT_TYPES` once, decide its default per tenant
type in this same map, and never write a `tenant_type` check into flow code
— `flows/booking/book.py` already reads only the *active* set via
`connector.get_appointment_types()`.

### 2. Portal CRUD for appointment types, gated by `manage_appointment_types`

New file `backend/portal/routes/appointment_types.py` (registered in
`portal/routes/__init__.py`):

- `GET /api/portal/appointment-types` — active AND inactive types for the
  tenant (so the toggle UI can show what's off), authenticated only.
- `POST /api/portal/appointment-types/{id}/active` — toggles `is_active`,
  gated by `require_capability(hospital, "manage_appointment_types")`.

Backed by two new repository functions:
`get_all_appointment_types_for_hospital()` and
`set_appointment_type_active()`. This makes `manage_appointment_types` a
real, exercised capability instead of a dead registry entry, and is the
literal "toggle a feature per tenant" mechanism the original ask was for.

### 3. Resync capabilities when tenant_type changes (frontend safeguard)

`admin/tenants_api.py`'s `_tenant_detail()` now exposes
`default_capabilities_by_type` (the same map `DEFAULT_CAPABILITIES_BY_TYPE`
already computed, just shaped for the frontend). The edit-tenant page
(`frontend/src/app/admin/edit-tenant/[id]/page.tsx`) uses it for:

- A "Reset to {type} defaults" button next to the capability checkboxes.
- An inline warning when the current capability set doesn't match either
  type's default (`capabilitiesMatch()` helper).

This is a convenience + visibility improvement, not a forced reset — an
operator can still deliberately keep a custom mix, matching
`get_capabilities()`'s "explicit override always wins" semantics.

### 4. Two-level audit log (platform_admin, portal)

New table `audit_logs` (migration `db/migrations/versions/
0007_audit_logs.py`, mirrored in `db/schema.sql`, and — since
`init_db_on_connection()` deliberately never runs Alembic for tests — also
inlined as an idempotent `CREATE TABLE IF NOT EXISTS` in
`db/init_db.py::init_db_on_connection()`, same pattern every migration since
0002 already follows there):

```sql
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_level TEXT NOT NULL CHECK (actor_level IN ('platform_admin', 'portal')),
    hospital_id INTEGER REFERENCES hospitals(id),
    actor_label TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    before_value TEXT,
    after_value TEXT,
    created_at TEXT NOT NULL DEFAULT (now()::text)  -- ISO-8601 TEXT, same convention as every other timestamp column in this schema
);
```

`actor_label` is free text, not a FK: neither level has real per-individual
identity today (platform-admin is one shared secret; portal auth resolves to
a `Hospital`, not a named staff member — `hospital_users.role` stays unused).
Adding real per-user identity later is a value-population change, not a
schema migration.

New repository `backend/db/repositories/audit_logs.py`:
- `record_audit_log(actor_level, hospital_id, actor_label, action, *, entity_type=None, entity_id=None, before=None, after=None)`
  — JSON-encodes `before`/`after` (diffed fields only), with unconditional
  redaction of `access_token`/`app_secret`/`portal_password_hash`/
  `external_api_key` → logged as `"<changed>"`, never the value.
  `created_at` is stamped explicitly in Python
  (`datetime.now().isoformat()`), not left to the DB's `server_default` —
  SQLAlchemy's ORM insert sends every mapped column explicitly, so relying
  on the DB default alone triggers a `NOT NULL` violation.
- `get_audit_logs(hospital_id=None, actor_level=None, limit=100)` —
  paginated, newest first.

Wired in at:
- **Platform level** — `admin/tenants_api.py::update_tenant()` diffs
  `name`/`data_tier`/`tenant_type`/`admin_capabilities`/`enabled_features`
  before vs. after and records one `tenant.update` entry only for whichever
  fields actually changed; `assign_tenant_owner()` records
  `tenant.assign_owner`.
- **Portal level** — `portal/routes/doctors.py` (`department.create`,
  `doctor.create`, `doctor.update`, `doctor.active_toggle`),
  `portal/routes/appointment_types.py` (`appointment_type.toggle`),
  `portal/routes/settings.py` (`settings.update`).

Exposed via:
- `GET /api/admin/tenants/{id}/audit-log` — both levels for one tenant,
  `TENANTS_ADMIN_SECRET`-gated.
- `GET /api/portal/audit-log` — that tenant's own `portal`-level rows only,
  gated by `manage_settings` (reuses the capability that already gates the
  settings-update route rather than inventing a new one).

### Edge cases confirmed / verified

- **Hospital with only one department/one doctor**: unchanged, still
  data-shape-driven, still covered by
  `tests/test_clinic_single_doctor_booking.py`.
- **Downgrade hospital → clinic with existing departments/doctors**: no
  data deleted; portal management routes 403; existing doctors/departments
  remain fully readable via the portal and bookable via the connector.
  Covered by `test_downgrading_a_hospital_to_clinic_never_deletes_
  departments_or_doctors`.
- **Clinic upgrading a hospital-only feature on**: `test_clinic_can_turn_
  on_daycare_once_granted_the_capability` — onboard a clinic, grant
  `manage_appointment_types`, flip `daycare`'s `is_active` via the portal
  route, confirm it now appears in `get_appointment_types()` and nothing
  else about the tenant's data changed.
- **Audit redaction**: `test_audit_log_redacts_secret_fields` confirms
  `access_token`/etc. never appear in stored `before_value`/`after_value`.

## What actually shipped (diverged slightly from the original sketch)

- The portal toggle route is `POST /api/portal/appointment-types/{id}/active`
  (not `PATCH /api/portal/appointment-types/{id}`) — matches this
  codebase's existing convention for boolean toggles (see
  `POST /api/portal/doctors/{doctor_id}/active`).
- `admin/onboarding_api.py` needed no direct edit — `create_hospital()`
  already receives `tenant_type` and now resolves appointment-type
  `is_active` internally, so the tenant-aware seeding "just worked" once
  `hospitals.py`/`init_db.py` were updated.
- Audit calls were added to the highest-value doctor/department mutations
  (create department, create/update/toggle-active doctor) rather than every
  leave/slot micro-action in `doctors.py`, to keep the audit trail readable
  (one event per meaningful action) without auditing routine scheduling
  operations.
- `db/schema.sql`'s `audit_logs.created_at` uses `TEXT DEFAULT (now()::text)`,
  not `TIMESTAMPTZ` — this codebase stores every timestamp as ISO-8601 TEXT,
  never a native Postgres timestamp type (see `db/orm_models.py`'s header
  comment); the original sketch used `TIMESTAMPTZ` before this was caught
  during implementation.

## Verification performed

- `backend/tests/test_capability_gating.py`: 27 passed (10 new — daycare
  default gap, portal appointment-type gating, downgrade data-safety,
  audit recording + redaction + tenant scoping).
- Full backend suite: 670 passed, 0 failed.
- Frontend: `npx tsc --noEmit` clean.
- Alembic migration chain (`0001` → `0007`) verified linear via
  `ScriptDirectory.walk_revisions()`.

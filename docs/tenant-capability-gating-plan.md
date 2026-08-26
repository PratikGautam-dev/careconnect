# Tenant-Type-Driven Capability Gating (Hospital vs Clinic)

## Context

Today every tenant is a row in `hospitals` (there is no separate "tenant" concept — `hospitals` *is* the tenant table, used for both hospitals and clinics). There is no `tenant_type`/`hospital_vs_clinic` distinction anywhere, and no RBAC: portal auth (`backend/portal/deps.py::_authenticate`) resolves a Bearer token straight to a `Hospital` row, and every route that's reachable with a valid session gets full access — manage doctors, manage departments, etc. (`backend/portal/routes/doctors.py`). There's no CRUD for `appointment_types` yet at all (only seeded at onboarding).

The business need: hospitals keep full admin capability; clinics should not manage doctors and should have a reduced management surface. Doing this with `if tenant_type == "clinic"` branches scattered through routes would mean new backend logic (and more branches) every time capabilities differ. The instinct — configure this at onboarding time, let a tenant manager (platform admin) adjust it later, no new bespoke logic per tenant type — is the right shape, and it mirrors a pattern **already proven in this codebase**: `hospitals.enabled_features` (a JSON list column) already drives which WhatsApp menu features are shown per tenant, checked by simple membership tests. We extend the same pattern to staff-portal capabilities instead of inventing a new mechanism.

Goal: one generic "does this tenant have capability X" check, config-driven per tenant, defaulted by tenant type at onboarding, editable later by the platform/tenant admin — with zero per-type conditional business logic in feature code.

## Design

### 1. Data model changes (SQL) — ✅ DONE

> Implemented in `backend/db/schema.sql` (`tenant_type`, `admin_capabilities` columns on `hospitals`, added via the existing idempotent `ALTER TABLE ADD COLUMN IF NOT EXISTS` convention) and `backend/db/init_db.py` (`_backfill_admin_capabilities()`, registered in `init_db_on_connection()` next to `_backfill_enabled_features()`). Verified against a real Postgres test container: `uv run pytest tests/ -k hospital` → 93 passed. No Python model/repository/route code touched yet — see remaining sections below.

Add two things to `hospitals`:

- `tenant_type TEXT NOT NULL DEFAULT 'hospital' CHECK (tenant_type IN ('hospital','clinic'))`
  Purely descriptive/default-seeding metadata — not read by feature routes directly.
- `admin_capabilities TEXT` — JSON array column, same pattern as `enabled_features`.
  e.g. `["manage_doctors","manage_departments","manage_appointment_types","manage_bookings","manage_settings"]`
  This is the column every portal route actually checks. Nullable/empty falls back to a default set resolved from `tenant_type` at read time (or backfilled at migration time — see below).

```sql
ALTER TABLE hospitals ADD COLUMN tenant_type TEXT NOT NULL DEFAULT 'hospital'
    CHECK (tenant_type IN ('hospital', 'clinic'));

ALTER TABLE hospitals ADD COLUMN admin_capabilities TEXT; -- JSON array, nullable

-- Backfill existing rows explicitly so nothing silently relies on "default = full access"
UPDATE hospitals SET admin_capabilities = '["manage_doctors","manage_departments","manage_appointment_types","manage_bookings","manage_settings","manage_staff"]'
WHERE tenant_type = 'hospital';

UPDATE hospitals SET admin_capabilities = '["manage_bookings","manage_settings"]'
WHERE tenant_type = 'clinic'; -- no rows today, but future-proof
```

Keep `enabled_features` exactly as-is (patient-facing WhatsApp menu) — it's a different concern and shouldn't be conflated with staff/admin capability.

### 2. Central capability registry (single source of truth, not per-route logic)

One module, e.g. `backend/portal/capabilities.py`:

- `ALL_CAPABILITIES = {"manage_doctors", "manage_departments", "manage_appointment_types", "manage_bookings", "manage_settings", "manage_staff", ...}`
- `DEFAULT_CAPABILITIES_BY_TYPE = {"hospital": {...all...}, "clinic": {"manage_bookings", "manage_settings"}}`
- `get_capabilities(hospital: Hospital) -> set[str]` — parses `admin_capabilities` JSON if present, else falls back to `DEFAULT_CAPABILITIES_BY_TYPE[hospital.tenant_type]`.
- `has_capability(hospital, capability: str) -> bool`

This mirrors `_FEATURE_MENU`/`REAL_FEATURES` in `backend/flows/patient_identity.py` almost exactly — same shape, same validation pattern, so it's a familiar/reusable idiom in this codebase rather than a new one.

### 3. Enforcement — one dependency, reused everywhere (no new logic per route)

Add a small FastAPI dependency factory in `backend/portal/deps.py`, alongside the existing `_authenticate`:

```python
def require_capability(capability: str):
    def _check(hospital: Hospital = Depends(_authenticate)) -> Hospital:
        if not has_capability(hospital, capability):
            raise HTTPException(403, f"Tenant does not have '{capability}' capability")
        return hospital
    return _check
```

Then routes just swap their dependency:

- `backend/portal/routes/doctors.py` → doctor/department routes use `Depends(require_capability("manage_doctors"))` / `"manage_departments"` instead of bare `Depends(_authenticate)`.
- Any future `appointment_types` portal CRUD (doesn't exist yet — worth flagging: currently only seeded at onboarding, no portal endpoint) would use `Depends(require_capability("manage_appointment_types"))` from day one.

This is the entire "backend logic" footprint: one dependency factory + a swapped `Depends(...)` per route group. No `if tenant_type == "clinic"` anywhere in feature code — clinics simply don't have the capability string in their set, so the same route logic 403s for them automatically.

### 4. Onboarding — set capabilities once, at creation time

`backend/admin/onboarding_api.py` (`POST /api/onboarding`): accept `tenant_type` in the onboarding payload (default `"hospital"` for backward compatibility), pass it into `db.create_hospital(...)`, and set `admin_capabilities` from `DEFAULT_CAPABILITIES_BY_TYPE[tenant_type]` at creation (write it explicitly rather than relying on the DB default, so it's visible/auditable per row, matching how `enabled_features` is already set explicitly in this same function).

If a clinic later wants to add a department or appointment type, per the original proposal: they contact the tenant manager, who edits capabilities (or the underlying data) through the existing admin surface — see next point. No self-service capability escalation needed initially.

### 5. Tenant-manager editing after onboarding — reuse the existing admin surface

`backend/admin/tenants_api.py` already has `PATCH /api/admin/tenants/{id}` for editing `enabled_features` post-hoc, gated by `TENANTS_ADMIN_SECRET`. Extend that same endpoint (not a new one) to accept `admin_capabilities` and `tenant_type` updates, validated against `ALL_CAPABILITIES`. This gives the tenant/platform admin a way to:
- Flip a clinic's capability set (e.g. grant `manage_departments` if they now want to self-manage that), or
- Directly add a department/doctor/appointment type on the clinic's behalf via the existing hospital-scoped admin tooling, without touching capabilities at all.

Both are already "contact the tenant manager" workflows described above — this just wires the capability toggle into the endpoint that already exists for the analogous `enabled_features` case, rather than building new admin plumbing.

### What this deliberately does NOT do
- No user-level/per-staff RBAC (the `hospital_users.role` column stays unused as today) — out of scope; this is tenant-level capability gating only, matching the actual ask (hospital vs. clinic, not user vs. user).
- No new tables — piggybacks on the existing `hospitals` row + JSON-column pattern already proven by `enabled_features`.
- No duplicated capability logic per route — every route delegates to the same `has_capability`/`require_capability` check.

## Files touched
- `backend/db/schema.sql` — add `tenant_type`, `admin_capabilities` columns (+ migration script, following this repo's existing migration convention if any).
- `backend/db/models.py` — add fields to `Hospital` dataclass.
- `backend/portal/capabilities.py` — new small module: capability registry + `get_capabilities`/`has_capability`.
- `backend/portal/deps.py` — add `require_capability(...)` dependency factory next to `_authenticate`.
- `backend/portal/routes/doctors.py` — swap `Depends(_authenticate)` for `Depends(require_capability("manage_doctors"))` / `"manage_departments"` on the relevant routes.
- `backend/admin/onboarding_api.py` — accept `tenant_type`, write `admin_capabilities` at creation.
- `backend/admin/tenants_api.py` — extend the existing `PATCH /api/admin/tenants/{id}` to allow editing `tenant_type`/`admin_capabilities`.

## Verification
- Unit test `get_capabilities`/`has_capability` against both a hospital and clinic row (with and without an explicit `admin_capabilities` override).
- Integration test: clinic-tenant portal session hits `POST /portal/doctors` → expect 403; hospital-tenant session hits same route → expect success (reuse existing session-mocking test setup near `backend/portal/routes/doctors.py`).
- Manually onboard a clinic via `POST /api/onboarding` with `tenant_type: "clinic"`, confirm `admin_capabilities` is set to the reduced default set in the DB, then confirm doctor-management portal routes 403 for that tenant while booking/settings routes still work.

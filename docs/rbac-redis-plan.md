# RBAC (Admin / Receptionist / Doctor / Super Admin) + Redis

## Context

Today there is no real per-person staff identity anywhere in the hospital portal. Auth is three parallel, independently-signed custom HMAC bearer-token schemes:

- **Shared hospital portal login** (`backend/auth/session.py`) — one password *per hospital tenant*, not per person. Every staff member at a hospital who has this password gets full access to everything.
- **Dedicated doctor login** (`backend/auth/doctor_session.py`, `doctors.email`/`password_hash`, added very recently) — the only place an individual has their own credentials today.
- **Platform admin** (`backend/admin/tenants_api.py`) — a single shared secret header (`X-Admin-Secret`), not tied to any individual at all.

There's a `hospital_users.role` column that's explicitly documented as "stored but not enforced" (every row is `'owner'`), and a tenant-level (not user-level) capability system (`backend/portal/capabilities.py`) that gates whole *tenant types* (hospital vs clinic) — the closest existing pattern to what we're building, and the one this plan deliberately mirrors.

The goal: give each hospital an Admin / Receptionist / Doctor role structure with individually-configurable, per-page view/write/delete permissions that the frontend hides (nav items, buttons) and the backend enforces (403s), plus a Super Admin platform layer with its own individual accounts. Redis, already a soft dependency in this codebase (rate limiting, session store, chat history — all gated on `REDIS_URL` with in-memory fallback), gets a shared client module so it can serve permission caching, pub/sub invalidation, and future cache/queue needs generally, not just this feature.

Decisions locked in with the user:
- **Unified `staff_users` table** for Admin, Receptionist, and Doctor — individual login for everyone, including migrating doctors off their brand-new `doctors.email/password_hash` columns.
- **Permissions are per-role only** (not per-individual overrides) — one matrix per hospital: role × page × {view, write, delete}. Admin defaults to all-true but is editable.
- **Super admin gets individual accounts** (`super_admins` table), replacing the `X-Admin-Secret` shared secret, for a real audit trail.
- **Auth token strategy: JWT access tokens + Redis-backed refresh tokens**, not the existing custom HMAC scheme — chosen for standard tooling, statelessly-embedded role/permission claims, and because Redis makes revocation (the HMAC scheme's real gap) cheap.
- **`staff_users.email` is globally unique** (user's explicit choice) — login is just email + password, no hospital selector needed.
- **Existing hospitals** (only ~2 live today, onboarded manually by the team via the admin-secret-gated `/api/onboarding` flow, not self-serve) get their `staff_users` admin row created **manually by the operator** — no self-service "claim your account" bridge needed at this scale. The old shared-password login stays alive only until those specific hospitals are migrated, then is removed in cleanup.

## Data model

**New table `staff_users`** (`backend/db/schema.sql`):

```sql
CREATE TABLE IF NOT EXISTS staff_users (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    role TEXT NOT NULL CHECK (role IN ('admin', 'receptionist', 'doctor')),
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    doctor_id TEXT REFERENCES doctors(id),   -- set iff role='doctor'
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    token_version INTEGER NOT NULL DEFAULT 0, -- bumped on password change/deactivation/role change -> invalidates outstanding JWTs immediately
    created_at TEXT NOT NULL DEFAULT (now()::text),
    updated_at TEXT NOT NULL DEFAULT (now()::text)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_staff_users_email ON staff_users(lower(email));
CREATE UNIQUE INDEX IF NOT EXISTS ux_staff_users_doctor_id ON staff_users(doctor_id) WHERE doctor_id IS NOT NULL;
ALTER TABLE staff_users ADD CONSTRAINT ck_staff_users_doctor_role_pairing
    CHECK ((role = 'doctor') = (doctor_id IS NOT NULL));
```

**New table `role_permissions`** — a row per (hospital, role, page), not a JSON blob, since this is read on every request and edited cell-by-cell by the admin UI:

```sql
CREATE TABLE IF NOT EXISTS role_permissions (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    role TEXT NOT NULL CHECK (role IN ('admin', 'receptionist', 'doctor')),
    page_key TEXT NOT NULL,
    can_view BOOLEAN NOT NULL DEFAULT FALSE,
    can_write BOOLEAN NOT NULL DEFAULT FALSE,
    can_delete BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE(hospital_id, role, page_key)
);
CREATE INDEX IF NOT EXISTS ix_role_permissions_hospital_role ON role_permissions(hospital_id, role);
```

**New table `super_admins`** (global, not hospital-scoped — mirrors `users`, not `hospital_users`):

```sql
CREATE TABLE IF NOT EXISTS super_admins (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    token_version INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (now()::text)
);
```

**Existing schema changes:**
- `doctors.email` / `doctors.password_hash` / `ux_doctors_email`: migrate data into `staff_users` (`role='doctor'`, `doctor_id=doctors.id`) then drop these columns — in a **follow-up migration**, after Phase 3 routes are cut over and verified (don't drop in the same deploy that lands the schema, to avoid stranding live doctor logins).
- `hospitals.portal_password_hash`: kept as-is (not dropped now); onboarding stops issuing new ones; dropped in cleanup once both live hospitals have a `staff_users` admin row.
- `hospital_users.role`: untouched — that's the transient Google-OAuth hospital-picker path, unrelated to `staff_users.role`.
- `audit_logs`: keep `actor_label` free text, just populate it with the real `f"{staff.name} <{staff.email}>"` (or super admin email) instead of a session-hash/literal string — no schema change needed, this is exactly the "value-population change, not a migration" the table's own docstring anticipates.

Write as Alembic migration `backend/db/migrations/versions/0013_staff_users_role_permissions_super_admins.py` (follow `0012_doctor_login.py`'s style: dense docstring, explicit `upgrade`/`downgrade`, `IF NOT EXISTS`-safe), mirrored in `schema.sql`, and add ORM classes to `backend/db/orm_models.py`. Add corresponding `backend/db/repositories/staff_users.py`, `role_permissions.py`, `super_admins.py`.

## Permission registry

New file `backend/portal/permissions.py`, structured as the direct sibling of `capabilities.py`:

```python
PAGE_DASHBOARD = "dashboard"
PAGE_APPOINTMENTS = "appointments"
PAGE_PATIENTS = "patients"
PAGE_DOCTORS = "doctors"
PAGE_MESSAGES = "messages"
PAGE_SETTINGS = "settings"
PAGE_STAFF = "staff"     # staff management page
PAGE_ROLES = "roles"     # roles & permissions editor

ALL_PAGES = {...}
ACTIONS = ("view", "write", "delete")

DEFAULT_PERMISSIONS_BY_ROLE = {
    "admin": {page: {"view": True, "write": True, "delete": True} for page in ALL_PAGES},
    "receptionist": {...},  # view+write on appointments/patients/messages, view-only dashboard, nothing on doctors/settings/staff/roles
    "doctor": {...},        # view+write on appointments/patients, view-only dashboard/messages, nothing else
}

def resolve_default_permissions(role: str) -> dict: ...
def get_permission_matrix(hospital_id: int) -> dict: ...  # DB read, Redis-cached; falls back to defaults if hospital has no rows yet
def has_permission(hospital_id: int, role: str, page_key: str, action: str) -> bool: ...
```

Seeded explicitly at onboarding (mirrors `resolve_default_capabilities()`'s "write it now, don't rely on a runtime fallback" discipline) — `admin/onboarding_api.py`'s `submit_onboarding()` loops all (role, page) pairs and writes `role_permissions` rows right after `db.create_hospital(...)`.

New admin-facing routes (`backend/portal/routes/roles.py`):
- `GET /api/portal/roles/permissions` — full matrix for the caller's hospital.
- `PUT /api/portal/roles/permissions` — updates one or more (role, page_key) rows; invalidates the Redis permission cache; writes an `audit_logs` row.

Both gated by `require_permission(principal, "roles", "view"/"write")` — i.e., admin-only by default, but itself editable like everything else.

## Backend auth layer

**`backend/auth/jwt_session.py`** (new) — PyJWT-based issuance/verification for staff tokens (`issue_access_token`, `verify_access_token`), 15-minute TTL, claims `{sub, hospital_id, role, tv, exp, typ: "staff"}`. A separate `SUPER_ADMIN_JWT_SECRET` and `typ: "super_admin"` keep super-admin tokens structurally non-interchangeable with staff tokens — same "a leaked secret only forges the one thing it's for" precedent as `DOCTOR_SECRET` vs `PORTAL_SECRET`. New `core/config.py` fields: `JWT_SECRET`, `SUPER_ADMIN_JWT_SECRET`. Add `PyJWT==2.9.0` to `backend/pyproject.toml`.

**`backend/auth/refresh_tokens.py`** (new) — opaque random refresh tokens, stored in Redis (`refresh:{hash} -> {staff_id, hospital_id, role}`, 7-day TTL), rotated on each use. Follows the exact `RedisX`/`InMemoryX` dual-class + `_build_x()` factory pattern already used in `core/rate_limit.py`/`core/session_store.py`, so it degrades gracefully (logout-everywhere just loses effect across restarts) when `REDIS_URL` is unset, matching this project's documented "basic protection" posture.

**`backend/core/redis_client.py`** (new, the shared client explicitly requested) — `get_redis()` (same `from_url` + `ping()` + `except: None` gating as every existing call site, `REDIS_URL` read live per call, never through `core/config.py`, matching that module's own documented reason), plus generic `cache_get_json`/`cache_set_json`/`cache_delete`/`publish` helpers. Existing five Redis call sites are **not** migrated onto this in this change (separate low-risk cleanup later) — this module exists so this feature and any future cache/pub-sub/queue need reach for one shared thing instead of a sixth bespoke implementation.

**`backend/portal/permission_cache.py`** (new) — `get_cached_matrix`/`set_cached_matrix`/`invalidate(hospital_id)` (deletes local key + publishes on `perms:invalidate`). A startup subscriber (added to `backend/main.py`) listens on `perms:invalidate` and drops the local cache entry on every worker/instance, so a permission edit takes effect immediately everywhere. No Redis → this whole layer no-ops, permission checks hit Postgres directly (fine at this project's scale).

**Unified principal, in `backend/portal/deps.py`** (extending, not replacing the file's existing manual-guard-clause idiom — no `Depends()` DI, per the codebase's own established convention):

```python
class StaffPrincipal:
    def __init__(self, hospital, staff_id, role, name, doctor_id): ...

def get_current_staff(authorization: str | None) -> StaffPrincipal | None:
    # verifies JWT, re-checks token_version (Redis-cached, Postgres on miss) and is_active

def require_permission(principal: StaffPrincipal, page_key: str, action: str) -> JSONResponse | None:
    # same "forbidden = require_permission(...); if forbidden: return forbidden" shape as require_capability
```

`doctor_portal.py` routes are migrated from `_authenticate_doctor` to `get_current_staff` (reading `principal.doctor_id`), preserving the existing "doctor_id only ever comes from the verified token" isolation guarantee. `_authenticate` / `_authenticate_doctor` / `auth/session.py` / `auth/doctor_session.py` are **kept** until Phase 6 cleanup, not deleted immediately.

**Login endpoints:**
- `POST /api/portal/staff/login` (new `backend/portal/routes/staff_auth.py`) — `{email, password}` (global email uniqueness means no hospital selector needed). Rate-limited via the existing `core/rate_limit.py` pattern. Returns `{access_token, refresh_token, staff: {id, name, role, hospital_id}, permissions: <role's matrix>}`.
- `POST /api/portal/staff/refresh`, `POST /api/portal/staff/logout`.
- `POST /api/admin/super/login` (new `backend/admin/super_auth.py`) — same shape against `super_admins`, own rate-limit scope, own JWT secret.
- `admin/tenants_api.py`, `admin/onboarding_api.py`, `admin/platform_settings_api.py`'s `X-Admin-Secret`/`ADMIN_SECRET` checks are replaced by a `get_current_super_admin(authorization)` verifier, same shape as `_authenticate`.
- `/api/portal/login` (shared password) and `/api/doctor/login` are kept alive through the migration window, removed in Phase 6.

**Onboarding update**: `admin/onboarding_api.py`'s `OnboardingSubmission` gains `admin_email`/`admin_password` fields (replacing `portal_password`), and `submit_onboarding()` creates the hospital's first `staff_users` admin row plus the default `role_permissions` rows as part of hospital creation — new hospitals never touch the old shared-password path at all.

## Frontend

- **`frontend/src/lib/staffAuth.ts`** (new, additive alongside `portalAuth.ts` during the transition) — `StaffSession { id, name, role, hospital, permissions }`, `saveStaffSession`/`getStaffSession`/`clearStaffSession`, `staffFetch()` (like `portalFetch` but attempts one silent refresh via `/api/portal/staff/refresh` on 401 before clearing session, since the JWT's 15-min TTL means a bare "401 → logout" would log people out constantly), and:
  ```ts
  export function usePermission(pageKey: string, action: "view"|"write"|"delete"): boolean {
    const session = getStaffSession();
    if (!session) return true; // fails open, same posture as PortalSidebar's existing capability check
    return !!session.permissions[pageKey]?.[action];
  }
  ```
- **`PortalSidebar.tsx`** — generalize the existing single hardcoded `admin_capabilities.includes("manage_doctors")` filter into `usePermission(item.pageKey, "view")` for every nav item; add "Staff" and "Roles & Permissions" items (admin-only by default via their own page keys).
- **`frontend/src/components/portal/PermissionGate.tsx`** (new) — wraps action buttons:
  ```tsx
  export function PermissionGate({ page, action, children }) {
    if (!usePermission(page, action)) return null;
    return <>{children}</>;
  }
  ```
  Used to hide Delete/Edit buttons per page.
- **New pages**: `app/portal/settings/staff/page.tsx` (create/deactivate staff_users — admin, receptionist, doctor), `app/portal/settings/roles/page.tsx` (role × page permission grid), staff login page (repurpose `app/portal/login`).
- **Super admin**: `AdminSecretGate.tsx` replaced by an email+password gate posting to `/api/admin/super/login`, storing a JWT instead of the raw secret in `adminAuth.ts`.

## Redis setup

Add to `docker-compose.dev-db.yml` (the file already dedicated to local-dev-only infra, alongside its Postgres precedent):
```yaml
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```
`REDIS_URL=redis://localhost:6379/0` documented in `.env.example`. Production points `REDIS_URL` at a managed instance (Upstash/Redis Cloud/self-hosted), same "not bundled, use managed" posture `docker-compose.prod.yml` already states for Postgres. The shared `core/redis_client.py` module is written generically (get/set-with-TTL, publish) so it's ready for future cache or pub/sub needs beyond RBAC without a redesign; no queue abstraction is built until something actually needs one.

## Rollout order

0. **Write this plan to `docs/rbac-redis-plan.md`** in the repo, matching the existing convention of `docs/tenant-capability-gating-plan.md` and `docs/ARCHITECTURE_PLAN.md` — this document's own text becomes the doc, not a summary of it, so implementers and code comments (which already reference sibling plan docs by name in this codebase) can cite it directly.
1. **Schema**: migration 0013 (new tables only — no destructive changes yet), ORM models, repositories, `PyJWT` dependency, config secrets, docker-compose Redis service.
2. **Auth/permission modules**: `jwt_session.py`, `refresh_tokens.py`, `redis_client.py`, `permissions.py`, `permission_cache.py` — independently testable, no routes touched yet.
3. **Backend routes**: `get_current_staff`/`require_permission` in `deps.py`; new staff/super-admin login+refresh+logout routes; migrate `doctor_portal.py` to `get_current_staff` (keeping `_authenticate_doctor` as a fallback until every doctor has a `staff_users` row); migrate platform-admin routes to `get_current_super_admin`; update onboarding to create the admin `staff_users` row + seed `role_permissions` for new hospitals.
4. **Manual migration of the 2 live hospitals**: operator creates their `staff_users` admin rows directly (real email/password chosen by the team, communicated to each hospital) and backfills `role_permissions` defaults for them.
5. **Frontend**: `staffAuth.ts`, `PermissionGate`, permission-aware `PortalSidebar`, Staff Management + Roles & Permissions pages, staff login page, super-admin login.
6. **Cleanup** (separate later change, after confirming nothing depends on the old paths): drop `doctors.email/password_hash`, delete `/api/doctor/login` + `auth/doctor_session.py`; drop `hospitals.portal_password_hash` + `/api/portal/login`; remove `X-Admin-Secret`/`TENANTS_ADMIN_SECRET`/`ADMIN_SECRET`.

**Must not break during rollout**: WhatsApp bot flows and patient-facing booking (`flows/*`, `connectors/*`, `core/main.py`) are entirely untouched — no dependency on any auth path here. `doctor_portal.py` must keep working for any doctor not yet migrated to `staff_users` throughout Phase 3 (dual-path support), since doctors are actively using dedicated login today.

## Verification

- Run the existing pytest suite (`backend/tests/`) after each phase — especially anything touching `portal/deps.py`, `doctor_portal.py`, `onboarding_api.py`, `tenants_api.py`.
- Manually exercise: staff login (admin/receptionist/doctor) → correct nav items/buttons show per role; edit a role's permission in the new Roles & Permissions UI → confirm the affected role's session immediately loses/gains access (tests the Redis pub/sub invalidation path) without needing to wait for token expiry (tests `token_version` revocation).
- Confirm doctor login still works for any doctor not yet migrated (dual-path), and that a migrated doctor's old `/api/doctor/login` token no longer works after cutover.
- Confirm super admin login replaces `X-Admin-Secret` across `admin/tenants_api.py`, `admin/onboarding_api.py`, `admin/platform_settings_api.py`, and that `frontend/src/app/admin/*` pages work end-to-end against it.
- Verify Redis-down behavior: stop the local Redis container, confirm login/permission checks still work (falling back to Postgres/in-memory) rather than 500ing.

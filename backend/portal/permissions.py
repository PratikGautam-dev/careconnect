# portal/permissions.py
"""
Per-role, per-page view/write/delete permissions (docs/rbac-redis-plan.md) --
the direct sibling of portal/capabilities.py, same fixed-set-+-membership-
tests shape, just one level more granular: capabilities.py gates whole
PAGES/features on for a TENANT (hospital vs. clinic); this module gates
individual ACTIONS on those pages for a ROLE within one tenant (Admin can
delete a patient, Receptionist can only view/write, Doctor can't see
Settings at all). The two are orthogonal and both apply -- a clinic tenant
without MANAGE_DOCTORS capability shows no Doctors nav item to ANY role
regardless of what role_permissions says, since capabilities.py's gate runs
first, at the tenant level.

Permissions are per-ROLE by default -- every Admin at a hospital has
identical permissions to every other Admin there; editing "Admin" changes it
for every admin at that hospital at once, via ONE row per (hospital, role,
page) (db/schema.sql's role_permissions table). A second, sparse,
per-INDIVIDUAL layer sits on top of that (db/repositories/staff_permissions.py's
staff_permission_overrides table, see get_staff_override_matrix() below) --
an admin can grant or revoke one action on one page for one specific staff
member (e.g. `delete` on Appointments for one particular doctor) without
touching the rest of their role; that override, when set, always wins over
whatever the role itself says.
"""
from db.repositories.role_permissions import get_role_permissions
from db.repositories.roles import list_roles
from db.repositories.staff_permissions import get_staff_overrides
from portal.permission_cache import (
    get_cached_matrix, get_cached_overrides, set_cached_matrix, set_cached_overrides,
)

PAGE_DASHBOARD = "dashboard"
PAGE_APPOINTMENTS = "appointments"
PAGE_PATIENTS = "patients"
PAGE_DOCTORS = "doctors"
PAGE_MESSAGES = "messages"
PAGE_SETTINGS = "settings"
PAGE_STAFF = "staff"  # staff management page (create/deactivate staff_users)
PAGE_ROLES = "roles"  # roles & permissions editor (this module's own admin UI)
PAGE_SCHEDULE = "schedule"  # a doctor's own working hours/breaks/leave editor
# Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5): the
# Diagnostic Tests management page (each test carries its own schedule) --
# same weight as PAGE_DOCTORS, off by default for receptionist/doctor.
PAGE_DIAGNOSTIC_TESTS = "diagnostic_tests"
# Leave Requests admin page (migration 20260912065049): review/approve/
# reject doctor+receptionist leave requests -- admin-only by default, same
# weight as PAGE_STAFF/PAGE_ROLES (staff-management-adjacent, not a page a
# receptionist or doctor manages for others).
PAGE_LEAVE_REQUESTS = "leave_requests"
# Holiday Application (migration 6eda12041ecf): the self-service SUBMISSION
# form this same leave_requests table feeds FROM -- any staff member applies
# for their own leave here, doctor or not, so unlike every other non-admin
# page above this defaults to view+write for every role, not just one kind.
PAGE_HOLIDAY_APPLICATION = "holiday_application"

ALL_PAGES = {
    PAGE_DASHBOARD, PAGE_APPOINTMENTS, PAGE_PATIENTS, PAGE_DOCTORS,
    PAGE_MESSAGES, PAGE_SETTINGS, PAGE_STAFF, PAGE_ROLES, PAGE_SCHEDULE, PAGE_DIAGNOSTIC_TESTS,
    PAGE_LEAVE_REQUESTS, PAGE_HOLIDAY_APPLICATION,
}
ACTIONS = ("view", "write", "delete")

_ALL_TRUE = {"view": True, "write": True, "delete": True}
_VIEW_ONLY = {"view": True, "write": False, "delete": False}
_VIEW_WRITE = {"view": True, "write": True, "delete": False}
_NONE = {"view": False, "write": False, "delete": False}

# Dynamic-roles migration: this is now SEED-TIME-ONLY data, consulted at
# exactly two moments -- (a) a new hospital's onboarding, seeding its 3
# default roles' permission rows, and (b) an admin's "Add Role" flow picking
# a starting-point kind (as opposed to cloning an existing role's actual
# current permissions). It is NEVER consulted by get_permission_matrix()/
# has_permission() at request time -- a role with zero role_permissions rows
# (a brand-new custom role before its first permission edit) resolves to
# all-False, not to some named-kind default it was never seeded from.
# Admin defaults to all-true on every page (including STAFF/ROLES -- an
# admin manages other staff and edits this very matrix by default) but is
# editable like everything else -- this is only ever a STARTING point, not
# a floor.
DEFAULT_PERMISSIONS_BY_ROLE_KIND: dict[str, dict[str, dict[str, bool]]] = {
    "admin": {page: dict(_ALL_TRUE) for page in ALL_PAGES},
    "receptionist": {
        PAGE_DASHBOARD: dict(_VIEW_ONLY),
        PAGE_APPOINTMENTS: dict(_VIEW_WRITE),
        PAGE_PATIENTS: dict(_VIEW_WRITE),
        PAGE_MESSAGES: dict(_VIEW_WRITE),
        PAGE_DOCTORS: dict(_NONE),
        PAGE_SETTINGS: dict(_NONE),
        PAGE_STAFF: dict(_NONE),
        PAGE_ROLES: dict(_NONE),
        PAGE_SCHEDULE: dict(_NONE),
        PAGE_DIAGNOSTIC_TESTS: dict(_NONE),
        PAGE_LEAVE_REQUESTS: dict(_NONE),
        # Not doctor-only -- a receptionist applies for their own leave too.
        PAGE_HOLIDAY_APPLICATION: dict(_VIEW_WRITE),
    },
    "doctor": {
        PAGE_DASHBOARD: dict(_VIEW_ONLY),
        PAGE_APPOINTMENTS: dict(_VIEW_WRITE),
        PAGE_PATIENTS: dict(_VIEW_WRITE),
        PAGE_MESSAGES: dict(_VIEW_ONLY),
        PAGE_DOCTORS: dict(_NONE),
        PAGE_SETTINGS: dict(_NONE),
        PAGE_STAFF: dict(_NONE),
        PAGE_ROLES: dict(_NONE),
        # Own-schedule self-service (working days/hours/breaks/leave) --
        # off by default for admin/receptionist, toggleable via Roles &
        # Permissions since admin already manages any doctor's schedule
        # through /portal/doctors regardless.
        PAGE_SCHEDULE: dict(_VIEW_WRITE),
        PAGE_DIAGNOSTIC_TESTS: dict(_NONE),
        PAGE_LEAVE_REQUESTS: dict(_NONE),
        PAGE_HOLIDAY_APPLICATION: dict(_VIEW_WRITE),
    },
}


def resolve_default_permissions(kind: str) -> dict[str, dict[str, bool]]:
    """Onboarding's own explicit-write helper (mirrors
    capabilities.resolve_default_capabilities()) -- `kind` is one of
    DEFAULT_PERMISSIONS_BY_ROLE_KIND's 3 keys ("admin"/"receptionist"/
    "doctor"), NOT a role_id -- returns a plain dict (not the shared
    DEFAULT_PERMISSIONS_BY_ROLE_KIND reference) so a caller can freely pass
    it into a DB write without risking a later in-place mutation corrupting
    the module-level default for every other hospital."""
    return {page: dict(actions) for page, actions in DEFAULT_PERMISSIONS_BY_ROLE_KIND.get(kind, {}).items()}


def get_permission_matrix(hospital_id: int) -> dict[int, dict[str, dict[str, bool]]]:
    """{role_id: {page_key: {view, write, delete}}} for every role this
    hospital currently has -- Redis-cached (portal/permission_cache.py)
    since this is read on every permission-gated request via has_permission()
    below. Base case is every role in db.list_roles(hospital_id), defaulted
    to all-False, THEN overlaid with actual role_permissions rows -- a role
    with zero rows (a brand-new custom role before its first permission
    edit) resolves to all-False by construction, never to some named-kind
    default it was never seeded from (see DEFAULT_PERMISSIONS_BY_ROLE_KIND's
    own docstring for why that's a deliberate fail-closed choice)."""
    cached = get_cached_matrix(hospital_id)
    if cached is not None:
        return {int(role_id): pages for role_id, pages in cached.items()}

    role_ids = [r["id"] for r in list_roles(hospital_id)]
    matrix: dict[int, dict[str, dict[str, bool]]] = {
        role_id: {page: dict(_NONE) for page in ALL_PAGES} for role_id in role_ids
    }
    for row in get_role_permissions(hospital_id):
        role_id, page_key = row["role_id"], row["page_key"]
        matrix.setdefault(role_id, {})[page_key] = {
            "view": row["can_view"], "write": row["can_write"], "delete": row["can_delete"],
        }
    set_cached_matrix(hospital_id, matrix)
    return matrix


def get_staff_override_matrix(hospital_id: int, staff_id: int) -> dict[str, dict[str, bool | None]]:
    """{page_key: {view, write, delete}} for one staff member's own
    overrides -- each action value is True/False (an explicit override) or
    None (no opinion, inherit the role). Redis-cached (its own key, separate
    from the per-hospital role matrix above) since has_permission() below
    reads this on every permission-gated request too. Sparse by
    construction: a page never touched here simply isn't a key, which
    has_permission() treats the same as an explicit None on every action."""
    cached = get_cached_overrides(hospital_id, staff_id)
    if cached is not None:
        return cached
    overrides: dict[str, dict[str, bool | None]] = {}
    for row in get_staff_overrides(hospital_id, staff_id):
        overrides[row["page_key"]] = {
            "view": row["can_view"], "write": row["can_write"], "delete": row["can_delete"],
        }
    set_cached_overrides(hospital_id, staff_id, overrides)
    return overrides


def has_permission(hospital_id: int, staff_id: int, role_id: int, page_key: str, action: str) -> bool:
    """The check every route calls (via portal/deps.py's require_permission())
    -- checks this staff member's own override first (dynamic-roles
    migration's user-level-overrides follow-up: a non-None value here wins
    outright, regardless of what the role says), and only falls back to the
    role matrix when the override is absent/None for that cell. An
    unrecognized role_id or page_key still resolves to False (fail closed),
    matching this codebase's general "an unrecognized key is simply never
    granted/read" discipline (e.g. capabilities.get_capabilities()'s
    `& ALL_CAPABILITIES` intersection)."""
    override = get_staff_override_matrix(hospital_id, staff_id).get(page_key, {}).get(action)
    if override is not None:
        return override
    matrix = get_permission_matrix(hospital_id)
    return bool(matrix.get(role_id, {}).get(page_key, {}).get(action, False))

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

Permissions are per-ROLE only (locked in with the user, docs/rbac-redis-plan.md's
own "Decisions locked in" section) -- not per-individual overrides. Every
Admin at a hospital has identical permissions to every other Admin there;
editing "Admin" changes it for every admin at that hospital at once. This is
what makes ONE row per (hospital, role, page) (db/schema.sql's
role_permissions table) sufficient, rather than needing a row per staff
member.
"""
from db.repositories.role_permissions import get_role_permissions
from portal.permission_cache import get_cached_matrix, set_cached_matrix

PAGE_DASHBOARD = "dashboard"
PAGE_APPOINTMENTS = "appointments"
PAGE_PATIENTS = "patients"
PAGE_DOCTORS = "doctors"
PAGE_MESSAGES = "messages"
PAGE_SETTINGS = "settings"
PAGE_STAFF = "staff"  # staff management page (create/deactivate staff_users)
PAGE_ROLES = "roles"  # roles & permissions editor (this module's own admin UI)

ALL_PAGES = {
    PAGE_DASHBOARD, PAGE_APPOINTMENTS, PAGE_PATIENTS, PAGE_DOCTORS,
    PAGE_MESSAGES, PAGE_SETTINGS, PAGE_STAFF, PAGE_ROLES,
}
ACTIONS = ("view", "write", "delete")

_ALL_TRUE = {"view": True, "write": True, "delete": True}
_VIEW_ONLY = {"view": True, "write": False, "delete": False}
_VIEW_WRITE = {"view": True, "write": True, "delete": False}
_NONE = {"view": False, "write": False, "delete": False}

# Single source of truth for both onboarding's explicit seeding write
# (submit_onboarding() below) and get_permission_matrix()'s runtime fallback
# for a hospital that predates this feature -- same role
# DEFAULT_CAPABILITIES_BY_TYPE plays for portal/capabilities.py's
# get_capabilities(). Admin defaults to all-true on every page (including
# STAFF/ROLES -- an admin manages other staff and edits this very matrix by
# default) but, per the plan, is editable like everything else -- this is
# only ever the STARTING point for a hospital's admin role, not a floor.
DEFAULT_PERMISSIONS_BY_ROLE: dict[str, dict[str, dict[str, bool]]] = {
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
    },
}


def resolve_default_permissions(role: str) -> dict[str, dict[str, bool]]:
    """Onboarding's own explicit-write helper (mirrors
    capabilities.resolve_default_capabilities()) -- returns a plain dict
    (not the shared DEFAULT_PERMISSIONS_BY_ROLE reference) so a caller can
    freely pass it into a DB write without risking a later in-place mutation
    corrupting the module-level default for every other hospital."""
    return {page: dict(actions) for page, actions in DEFAULT_PERMISSIONS_BY_ROLE.get(role, {}).items()}


def get_permission_matrix(hospital_id: int) -> dict[str, dict[str, dict[str, bool]]]:
    """{role: {page_key: {view, write, delete}}} for every role -- Redis-
    cached (portal/permission_cache.py) since this is read on every
    permission-gated request via has_permission() below. Falls back to
    DEFAULT_PERMISSIONS_BY_ROLE for any (role, page) this hospital has no row
    for at all -- covers both a hospital that predates this feature entirely
    (zero rows) and a hospital with rows for some roles/pages but not a
    newly-added page_key (a future page added after this hospital was
    onboarded), so a permission check never has to treat "no row" as
    "access denied" by default."""
    cached = get_cached_matrix(hospital_id)
    if cached is not None:
        return cached

    rows = get_role_permissions(hospital_id)
    matrix: dict[str, dict[str, dict[str, bool]]] = {
        role: resolve_default_permissions(role) for role in DEFAULT_PERMISSIONS_BY_ROLE
    }
    for row in rows:
        role, page_key = row["role"], row["page_key"]
        matrix.setdefault(role, {})[page_key] = {
            "view": row["can_view"], "write": row["can_write"], "delete": row["can_delete"],
        }
    set_cached_matrix(hospital_id, matrix)
    return matrix


def has_permission(hospital_id: int, role: str, page_key: str, action: str) -> bool:
    """The check every route calls (via portal/deps.py's require_permission())
    -- an unrecognized role or page_key resolves to False (fail closed),
    matching this codebase's general "an unrecognized key is simply never
    granted/read" discipline (e.g. capabilities.get_capabilities()'s
    `& ALL_CAPABILITIES` intersection)."""
    matrix = get_permission_matrix(hospital_id)
    return bool(matrix.get(role, {}).get(page_key, {}).get(action, False))

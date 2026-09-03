# portal/capabilities.py
"""
Tenant-type-driven capability gating (tenant-capability-gating-plan.md).

Every tenant is a row in `hospitals` -- there's no separate tenant table.
Today every authenticated staff-portal session gets full access to every
route; the business need is a reduced admin surface for `tenant_type =
'clinic'` rows (no doctor/department management) without scattering
`if tenant_type == "clinic"` conditionals through route code. This module is
the single source of truth both the default-by-type resolution and every
route's own capability check go through -- mirrors `flows.patient_identity`'s
`_FEATURE_MENU`/`REAL_FEATURES` pattern almost exactly (a fixed set +
membership tests), just for staff/admin capabilities instead of the
patient-facing WhatsApp menu. Deliberately a SEPARATE concept from
`hospitals.enabled_features` (which controls the WhatsApp menu, not this
staff-portal surface) -- the two must never be conflated.
"""
from db.models import Hospital

MANAGE_DOCTORS = "manage_doctors"
MANAGE_DEPARTMENTS = "manage_departments"
MANAGE_APPOINTMENT_TYPES = "manage_appointment_types"
MANAGE_BOOKINGS = "manage_bookings"
MANAGE_SETTINGS = "manage_settings"
MANAGE_STAFF = "manage_staff"
# Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5): a
# diagnostic resource (machine/equipment) is a schedulable entity of the
# same weight as a doctor -- hospital-tier only, same default tier as
# MANAGE_DOCTORS/MANAGE_DEPARTMENTS. Test/variant catalog CRUD reuses
# MANAGE_APPOINTMENT_TYPES instead (same portal screen area as
# daycare_duration_options -- no new capability needed for a catalog toggle/
# edit screen).
MANAGE_DIAGNOSTIC_RESOURCES = "manage_diagnostic_resources"

ALL_CAPABILITIES = {
    MANAGE_DOCTORS, MANAGE_DEPARTMENTS, MANAGE_APPOINTMENT_TYPES,
    MANAGE_BOOKINGS, MANAGE_SETTINGS, MANAGE_STAFF, MANAGE_DIAGNOSTIC_RESOURCES,
}

# Single source of truth for both the onboarding-time default AND
# db/init_db.py's own one-time backfill (that migration keeps its own
# literal JSON snapshot -- see its docstring for why it doesn't import this
# module directly).
DEFAULT_CAPABILITIES_BY_TYPE: dict[str, set[str]] = {
    "hospital": {
        MANAGE_DOCTORS, MANAGE_DEPARTMENTS, MANAGE_APPOINTMENT_TYPES,
        MANAGE_BOOKINGS, MANAGE_SETTINGS, MANAGE_STAFF, MANAGE_DIAGNOSTIC_RESOURCES,
    },
    "clinic": {MANAGE_BOOKINGS, MANAGE_SETTINGS},
}


def get_capabilities(hospital: Hospital) -> set[str]:
    """hospital.admin_capabilities is the parsed JSON list from the
    `hospitals.admin_capabilities` column (None when that column is
    genuinely NULL -- db/repositories/hospitals.py's own row-mapper keeps
    this distinct from an explicit `[]`) -- present, it's authoritative
    (including a deliberately-empty tenant); absent, falls back to this
    tenant's type default."""
    if hospital.admin_capabilities is not None:
        return set(hospital.admin_capabilities) & ALL_CAPABILITIES
    return DEFAULT_CAPABILITIES_BY_TYPE.get(hospital.tenant_type, DEFAULT_CAPABILITIES_BY_TYPE["hospital"])


def has_capability(hospital: Hospital, capability: str) -> bool:
    return capability in get_capabilities(hospital)


def resolve_default_capabilities(tenant_type: str) -> list[str]:
    """Onboarding's own explicit-write helper (Section 4 of the plan): a new
    hospital gets its admin_capabilities set EXPLICITLY at creation time
    from this default (passed straight into db.create_hospital()'s own
    admin_capabilities param, which json-encodes it), rather than left NULL
    and relying on get_capabilities()'s runtime fallback -- same "write it
    explicitly, visible/auditable per row" discipline enabled_features
    already follows at onboarding."""
    capabilities = DEFAULT_CAPABILITIES_BY_TYPE.get(tenant_type, DEFAULT_CAPABILITIES_BY_TYPE["hospital"])
    return sorted(capabilities)

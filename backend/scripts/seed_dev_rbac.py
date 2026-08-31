#!/usr/bin/env python3
"""
Local-dev-only convenience seed for the RBAC rollout (docs/rbac-redis-plan.md)
-- creates a super admin AND a hospital admin with FIXED, known credentials
(printed below) so you can log into both dashboards without going through
onboarding by hand. Unlike scripts/seed_super_admin.py (interactive password
prompt, meant for a real operator account), this is deliberately
non-interactive with a hardcoded test password -- do not run this against a
production database; it exists purely to unblock local testing.

Destructive by design, every run: DELETEs every staff_users and super_admins
row FIRST, then creates fresh ones from the constants below -- so editing
SUPER_ADMIN_EMAIL/HOSPITAL_ADMIN_EMAIL (or the passwords) in this file and
re-running always takes effect, rather than silently no-op'ing against a
stale row left over from a previous email. role_permissions and the
hospital row itself are NOT touched -- only login identities are reset, not
the tenant or its permission matrix.

If no hospital exists yet, one is created (data_tier="tier1", a throwaway
whatsapp_phone_number_id) so there's somewhere for the admin account to
belong to -- if a hospital already exists, the FIRST one (by id) is reused
instead of creating a second.

Usage:
    python -m scripts.seed_dev_rbac
"""
from typing import cast

from dotenv import load_dotenv

# Must run before any db.* import below reads DATABASE_URL -- same ordering
# requirement main.py's own module docstring documents for load_dotenv()
# there. Unlike main.py (imported by uvicorn, which already runs from a
# shell that's sourced .env), this script is invoked directly via
# `python -m scripts.seed_dev_rbac`, so nothing else loads .env for it first.
load_dotenv()

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.engine import CursorResult  # noqa: E402

import db.repository as db  # noqa: E402
from db.connection import get_session  # noqa: E402
from db.orm_models import Identity, StaffDetail, SuperAdminDetail
from db.repositories.hospitals import hash_portal_password
from portal.permissions import DEFAULT_PERMISSIONS_BY_ROLE, resolve_default_permissions

SUPER_ADMIN_EMAIL = "super@careconnect.com"
SUPER_ADMIN_PASSWORD = "Super@123"
SUPER_ADMIN_NAME = "Dev Super Admin"

HOSPITAL_ADMIN_EMAIL = "admin@careconnect.com"
HOSPITAL_ADMIN_PASSWORD = "admin@123"
HOSPITAL_ADMIN_NAME = "Dev Hospital Admin"

_DEV_HOSPITAL_NAME = "Dev Test Hospital"
_DEV_WHATSAPP_PHONE_NUMBER_ID = "dev-test-hospital-phone-id"


def _clear_existing_accounts() -> None:
    """Wipes every staff (StaffDetail) and super-admin (SuperAdminDetail)
    identity -- deliberately ALL of them, not just rows matching this file's
    current EMAIL constants, so this is a genuine reset regardless of what
    email a previous run used. Migration 0016: staff/super-admin accounts
    now live as an Identity row plus an extension row (StaffDetail/
    SuperAdminDetail), so clearing one means deleting both -- the extension
    row first (its FK points at identities.id), then the Identity row
    itself. Deliberately does NOT touch any OAuth hospital-owner identity
    (one with no StaffDetail/SuperAdminDetail row) -- this script only ever
    resets login credentials for the two dev accounts it seeds, never a real
    person's Google sign-in. doctor_id/role_permissions are independent of
    WHICH login identity happens to hold them, so clearing accounts doesn't
    cascade into losing a doctor's clinical record or a hospital's
    permission matrix."""
    session = get_session()
    staff_identity_ids = session.execute(select(StaffDetail.identity_id)).scalars().all()
    super_admin_identity_ids = session.execute(select(SuperAdminDetail.identity_id)).scalars().all()
    session.execute(delete(StaffDetail))
    session.execute(delete(SuperAdminDetail))
    staff_deleted = 0
    if staff_identity_ids:
        staff_deleted = cast(
            CursorResult, session.execute(delete(Identity).where(Identity.id.in_(staff_identity_ids)))
        ).rowcount
    super_admin_deleted = 0
    if super_admin_identity_ids:
        super_admin_deleted = cast(
            CursorResult, session.execute(delete(Identity).where(Identity.id.in_(super_admin_identity_ids)))
        ).rowcount
    session.commit()
    print(f"Cleared {staff_deleted} staff identity(ies) and {super_admin_deleted} super-admin identity(ies).")


def _seed_super_admin() -> None:
    super_admin = db.create_super_admin(SUPER_ADMIN_EMAIL, hash_portal_password(SUPER_ADMIN_PASSWORD), SUPER_ADMIN_NAME)
    print(f"Created super admin #{super_admin['id']}: {super_admin['email']}")


def _get_or_create_dev_hospital():
    hospitals = db.get_all_hospitals()
    if hospitals:
        hospital = hospitals[0]
        print(f"Reusing existing hospital #{hospital.id}: {hospital.name}")
        return hospital
    hospital = db.create_hospital(
        _DEV_HOSPITAL_NAME, _DEV_WHATSAPP_PHONE_NUMBER_ID,
        enabled_features=["booking", "reschedule", "cancel", "view_appointments"],
    )
    print(f"Created hospital #{hospital.id}: {hospital.name}")
    return hospital


def _seed_hospital_admin(hospital_id: int) -> None:
    staff = db.create_staff_user(
        hospital_id, "admin", HOSPITAL_ADMIN_EMAIL, hash_portal_password(HOSPITAL_ADMIN_PASSWORD), HOSPITAL_ADMIN_NAME,
    )
    print(f"Created hospital admin #{staff['id']}: {staff['email']} (hospital {hospital_id})")


def _seed_default_permissions(hospital_id: int) -> None:
    # Onboarding normally does this at hospital-creation time
    # (admin/onboarding_api.py) -- repeated here so a hospital reused from an
    # earlier, pre-RBAC seed (or created by _get_or_create_dev_hospital above)
    # still ends up with every (role, page) cell explicitly set, matching
    # resolve_default_permissions()'s own "write it now, don't rely on the
    # runtime fallback" discipline. upsert is idempotent, so re-running this
    # is safe even if the hospital already had rows -- deliberately NOT
    # cleared by _clear_existing_accounts() above, since a permission edit
    # you made through the Roles & Permissions UI shouldn't be wiped out just
    # because you're resetting login credentials.
    rows = [
        {"role": role, "page_key": page_key, "can_view": actions["view"], "can_write": actions["write"], "can_delete": actions["delete"]}
        for role in DEFAULT_PERMISSIONS_BY_ROLE
        for page_key, actions in resolve_default_permissions(role).items()
    ]
    db.upsert_role_permissions(hospital_id, rows)
    print(f"Seeded default role_permissions for hospital {hospital_id}.")


def main() -> None:
    _clear_existing_accounts()
    _seed_super_admin()
    hospital = _get_or_create_dev_hospital()
    _seed_hospital_admin(hospital.id)
    _seed_default_permissions(hospital.id)

    print()
    print("=" * 60)
    print("Super admin login (any /admin/* page):")
    print(f"  email:    {SUPER_ADMIN_EMAIL}")
    print(f"  password: {SUPER_ADMIN_PASSWORD}")
    print()
    print("Hospital admin login (/portal/login, staff login tab):")
    print(f"  email:    {HOSPITAL_ADMIN_EMAIL}")
    print(f"  password: {HOSPITAL_ADMIN_PASSWORD}")
    print("=" * 60)


if __name__ == "__main__":
    main()

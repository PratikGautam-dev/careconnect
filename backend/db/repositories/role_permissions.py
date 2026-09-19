# db/repositories/role_permissions.py
"""Per-(hospital, role_id, page) permission grid -- one
row per cell, not a JSON blob, since portal/permissions.py's
get_permission_matrix() reads this on every permission check (Redis-cached
by portal/permission_cache.py, so the row-per-cell shape isn't a per-request
cost in practice) and the Roles & Permissions admin UI edits it cell-by-cell
via PUT /api/portal/roles/permissions."""
from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.connection import get_session
from db.orm_models import RolePermission

_PERMISSION_COLUMNS = (
    RolePermission.role_id, RolePermission.page_key,
    RolePermission.can_view, RolePermission.can_write, RolePermission.can_delete,
)


def get_role_permissions(hospital_id: int) -> list[dict]:
    """Every row this hospital has, across every role -- callers
    (portal/permissions.py's get_permission_matrix(), the roles route's GET)
    group by role_id themselves; a role with no rows at all here simply
    isn't in the returned list -- the caller resolves that to all-False
    (a brand-new custom role that hasn't had any permission granted yet),
    not an error."""
    session = get_session()
    rows = session.execute(
        select(*_PERMISSION_COLUMNS).where(RolePermission.hospital_id == hospital_id)
    ).all()
    return [dict(r._mapping) for r in rows]


def seed_default_role_permissions(hospital_id: int, rows: list[dict]) -> None:
    """Onboarding's explicit-write step (submit_onboarding() calls this right
    after seeding this hospital's 3 default roles) -- `rows` is a flat list
    of {role_id, page_key, can_view, can_write, can_delete} dicts, built by
    the caller from portal.permissions.DEFAULT_PERMISSIONS_BY_ROLE_KIND via
    resolve_default_permissions() for each seeded role, same "write it now,
    don't rely on a runtime fallback" discipline resolve_default_capabilities()
    already established for admin_capabilities. ON CONFLICT DO NOTHING makes
    this safe to call at most once per hospital without double-seeding if a
    caller ever retries; a brand-new hospital_id can never already have rows,
    so there's nothing to overwrite."""
    if not rows:
        return
    session = get_session()
    session.execute(
        insert(RolePermission).values([{**row, "hospital_id": hospital_id} for row in rows])
    )
    session.commit()


def upsert_role_permissions(hospital_id: int, updates: list[dict]) -> None:
    """PUT /api/portal/roles/permissions's write path -- `updates` is a list
    of {role_id, page_key, can_view, can_write, can_delete} dicts for the
    cells an admin just changed (not necessarily the full matrix). One
    INSERT ... ON CONFLICT (hospital_id, role_id, page_key) DO UPDATE per
    call (a single multi-row statement, not one round-trip per cell) covers
    both "this role already has a row for this cell" (the normal case, since
    onboarding/clone-on-create seed every cell) and "this role has never had
    this cell touched" (first edit for that cell creates it) without the
    caller needing to know which case applies."""
    if not updates:
        return
    session = get_session()
    stmt = pg_insert(RolePermission).values(
        [{**row, "hospital_id": hospital_id} for row in updates]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[RolePermission.hospital_id, RolePermission.role_id, RolePermission.page_key],
        set_={
            "can_view": stmt.excluded.can_view,
            "can_write": stmt.excluded.can_write,
            "can_delete": stmt.excluded.can_delete,
        },
    )
    session.execute(stmt)
    session.commit()

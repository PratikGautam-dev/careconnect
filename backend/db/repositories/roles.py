# db/repositories/roles.py
"""Dynamic RBAC -- a hospital's own admin-defined roles. Kept separate from
role_permissions.py (a different table/concern) and staff_users.py (roles
are not staff)."""
from typing import cast

import sqlalchemy.exc
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import CursorResult

from db.connection import get_session, reraise_as_driver_integrity_error
from db.orm_models import Identity, RolePermission, RoleRow, StaffDetail

_ROLE_COLUMNS = (
    RoleRow.id, RoleRow.hospital_id, RoleRow.name, RoleRow.description, RoleRow.is_protected,
)


def list_roles(hospital_id: int) -> list[dict]:
    """Every role this hospital has, with live staff_count/active_staff_count
    -- the Roles & Permissions page's Role Management table's data source
    (replacing the old hardcoded 3-entry ROLES array), and also what
    create_staff()/update_staff()'s role_id validation looks up against.
    Both counts are role-membership counts (StaffDetail.role_id), counted
    regardless of whether a member happens to be linked to a doctor profile
    -- doctor-ness is no longer a role concept, so there's no special-casing
    needed here the way an earlier version of this feature required.
    active_staff_count mirrors count_staff_with_role(active_only=True)'s own
    definition, so a role showing 0 active members is exactly the case the
    delete-guard would accept. Ordered by is_protected DESC, name -- the
    protected Admin role first, then everything else (including
    Receptionist/Doctor, fully ordinary rows) alphabetically."""
    session = get_session()
    staff_count = (
        select(StaffDetail.role_id, func.count(StaffDetail.identity_id).label("n"))
        .group_by(StaffDetail.role_id)
        .subquery()
    )
    active_staff_count = (
        select(StaffDetail.role_id, func.count(StaffDetail.identity_id).label("n"))
        .join(Identity, Identity.id == StaffDetail.identity_id)
        .where(Identity.is_active.is_(True))
        .group_by(StaffDetail.role_id)
        .subquery()
    )
    rows = session.execute(
        select(
            *_ROLE_COLUMNS,
            func.coalesce(staff_count.c.n, 0).label("staff_count"),
            func.coalesce(active_staff_count.c.n, 0).label("active_staff_count"),
        )
        .outerjoin(staff_count, staff_count.c.role_id == RoleRow.id)
        .outerjoin(active_staff_count, active_staff_count.c.role_id == RoleRow.id)
        .where(RoleRow.hospital_id == hospital_id)
        .order_by(RoleRow.is_protected.desc(), RoleRow.name)
    ).all()
    return [dict(r._mapping) for r in rows]


_DEFAULT_ROLE_KINDS = (
    ("admin", "Admin", "Full access to every module by default.", True),
    ("receptionist", "Receptionist", "Front-desk staff: appointments, patients, messages.", False),
    ("doctor", "Doctor", "A doctor with a portal login, linked to their own doctor profile.", False),
)


def seed_default_roles(hospital_id: int) -> dict[str, dict]:
    """Onboarding's own hospital-creation-time seeding (submit_onboarding()
    calls this right after db.create_hospital()) -- the per-request
    counterpart to db/init_db.py's _seed_default_roles_and_backfill_role_id()
    (which only runs at server-startup/test-DB-reset time, for hospitals
    that already existed before this feature). Returns {"admin": {...},
    "receptionist": {...}, "doctor": {...}} so the caller can pull each
    seeded role's id straight out (e.g. the first staff_details row's
    role_id, and resolve_default_permissions()'s rows). Only the Admin role
    is seeded is_protected -- Receptionist/Doctor are ordinary, fully
    rename/delete-able roles from the moment they're created."""
    return {kind: create_role(hospital_id, name, description, is_protected=is_protected)
            for kind, name, description, is_protected in _DEFAULT_ROLE_KINDS}


def get_role(hospital_id: int, role_id: int) -> dict | None:
    """Hospital-scoped lookup -- the guard every write path (staff create/
    edit, permission updates) uses to confirm a caller-supplied role_id
    actually belongs to THIS hospital, not just that it exists somewhere."""
    session = get_session()
    row = session.execute(
        select(*_ROLE_COLUMNS).where(RoleRow.hospital_id == hospital_id, RoleRow.id == role_id)
    ).first()
    return dict(row._mapping) if row is not None else None


def create_role(
    hospital_id: int, name: str, description: str = "",
    *, is_protected: bool = False, clone_from_role_id: int | None = None,
) -> dict:
    """Raises db.connection.IntegrityError (via reraise_as_driver_integrity_error)
    if `name` collides case-insensitively with an existing role at this
    hospital (ux_roles_hospital_name) -- the route layer catches this and
    turns it into a 400. If `clone_from_role_id` is given, the new role's
    permission rows are seeded by copying that SOURCE role's actual current
    role_permissions rows (this hospital's real, possibly-customized values,
    not the factory onboarding defaults) -- otherwise the role starts with
    zero permission rows, which portal/permissions.py's get_permission_matrix()
    resolves to all-False (fail-closed) rather than some named-kind default
    it was never seeded from. is_protected is never settable by a portal
    admin through the API -- only seed_default_roles() ever passes True,
    for the one Admin role."""
    session = get_session()
    try:
        new_id = session.execute(
            insert(RoleRow)
            .values(hospital_id=hospital_id, name=name, description=description, is_protected=is_protected)
            .returning(RoleRow.id)
        ).scalar_one()
        if clone_from_role_id is not None:
            source_rows = session.execute(
                select(RolePermission.page_key, RolePermission.can_view, RolePermission.can_write, RolePermission.can_delete)
                .where(RolePermission.hospital_id == hospital_id, RolePermission.role_id == clone_from_role_id)
            ).all()
            if source_rows:
                session.execute(
                    insert(RolePermission).values([
                        {
                            "hospital_id": hospital_id, "role_id": new_id, "page_key": r.page_key,
                            "can_view": r.can_view, "can_write": r.can_write, "can_delete": r.can_delete,
                        }
                        for r in source_rows
                    ])
                )
        session.commit()
    except sqlalchemy.exc.IntegrityError as e:
        session.rollback()
        reraise_as_driver_integrity_error(e)
    return get_role(hospital_id, new_id)  # type: ignore[return-value]


def update_role(
    hospital_id: int, role_id: int, *, name: str | None = None, description: str | None = None,
) -> dict | None:
    """Partial update (only the fields explicitly passed are touched) --
    name/description only; is_protected is never editable through this
    path. Raises IntegrityError on a name collision, same as create_role().
    Returns None if no such role at this hospital."""
    if get_role(hospital_id, role_id) is None:
        return None
    values = {}
    if name is not None:
        values["name"] = name
    if description is not None:
        values["description"] = description
    if not values:
        return get_role(hospital_id, role_id)
    session = get_session()
    try:
        session.execute(update(RoleRow).where(RoleRow.hospital_id == hospital_id, RoleRow.id == role_id).values(**values))
        session.commit()
    except sqlalchemy.exc.IntegrityError as e:
        session.rollback()
        reraise_as_driver_integrity_error(e)
    return get_role(hospital_id, role_id)


def count_staff_with_role(hospital_id: int, role_id: int, *, active_only: bool = False) -> int:
    """The delete-guard's own count (active_only=True -- deactivated staff
    don't block deleting a role, matching this codebase's "deactivate,
    don't delete" offboarding posture)."""
    session = get_session()
    query = select(func.count(StaffDetail.identity_id)).where(
        StaffDetail.hospital_id == hospital_id, StaffDetail.role_id == role_id,
    )
    if active_only:
        query = query.join(Identity, Identity.id == StaffDetail.identity_id).where(Identity.is_active.is_(True))
    return session.execute(query).scalar_one()


def delete_role(hospital_id: int, role_id: int) -> bool:
    """Permission rows cascade-delete via role_permissions.role_id's
    ON DELETE CASCADE FK -- no second application-level delete needed.
    Callers (the DELETE route) are responsible for checking is_protected/
    count_staff_with_role() BEFORE calling this; this function itself has
    no guard, matching create_doctor()-style repository functions that
    trust the route layer for business-rule checks and only do the actual
    write here. Returns False if no such role at this hospital."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        delete(RoleRow).where(RoleRow.hospital_id == hospital_id, RoleRow.id == role_id)
    ))
    session.commit()
    return result.rowcount > 0

# db/repositories/super_admins.py
"""Individual platform-operator accounts (docs/rbac-redis-plan.md), replacing
the X-Admin-Secret/ADMIN_SECRET/TENANTS_ADMIN_SECRET shared-secret gates.

Migration 0016: reads/writes db.orm_models.Identity + SuperAdminDetail now,
not the historical SuperAdmin table (kept, untouched, as a backup -- see
that migration's own docstring). Every function here keeps the exact same
name and dict shape ({id, email, password_hash, name, is_active,
token_version}) callers (admin/super_auth.py, portal/deps.py) already
expect -- only the underlying tables changed. "id" here is identities.id,
the same id issue_access_token()/JWT claims already treat as this
principal's identifier.

A super admin identity is one with a matching SuperAdminDetail row --
deliberately a JOIN, not a flag on Identity, for the safety reasoning
Identity's own docstring gives (a shared, widely-written table should never
carry a privilege column something else could accidentally flip)."""
from typing import cast

import sqlalchemy.exc
from sqlalchemy import exists, func, insert, select, update
from sqlalchemy.engine import CursorResult

from db.connection import get_session, reraise_as_driver_integrity_error
from db.orm_models import Identity, SuperAdminDetail

_SUPER_ADMIN_COLUMNS = (
    Identity.id, Identity.email, Identity.password_hash, Identity.name,
    Identity.is_active, Identity.token_version,
)


def create_super_admin(email: str, password_hash: str, name: str) -> dict:
    """Operator-provisioned only (no self-service signup) -- raises
    db.connection.IntegrityError if email is already taken
    (ux_identities_email UNIQUE, shared across every identity kind now, not
    just other super admins), same reraise_as_driver_integrity_error pattern
    every other unique-constraint-backed write in this codebase uses. Two
    inserts, in one transaction: the Identity row, then the SuperAdminDetail
    marker row that actually grants super-admin status."""
    session = get_session()
    try:
        new_id = session.execute(
            insert(Identity).values(email=email, password_hash=password_hash, name=name).returning(Identity.id)
        ).scalar_one()
        session.execute(insert(SuperAdminDetail).values(identity_id=new_id))
        session.commit()
    except sqlalchemy.exc.IntegrityError as e:
        session.rollback()
        reraise_as_driver_integrity_error(e)
    return get_super_admin_by_id(new_id)  # type: ignore[return-value]


def get_super_admin_by_email(email: str) -> dict | None:
    """Login lookup, case-insensitive (lower(email)) -- returns an inactive
    row too, same "let the caller distinguish wrong-password from
    deactivated" reasoning staff_users.get_staff_user_by_email() documents.
    The JOIN to SuperAdminDetail is what makes this "get a super admin by
    email" rather than "get any identity by email" -- an OAuth hospital
    owner or hospital staff member sharing that email (see migration 0016's
    merge-by-email note) never matches here."""
    session = get_session()
    row = session.execute(
        select(*_SUPER_ADMIN_COLUMNS)
        .join(SuperAdminDetail, SuperAdminDetail.identity_id == Identity.id)
        .where(func.lower(Identity.email) == email.lower())
    ).first()
    return dict(row._mapping) if row is not None else None


def get_super_admin_by_id(super_admin_id: int) -> dict | None:
    """The token_version/is_active re-check get_current_super_admin()
    (portal/deps.py) does on every request."""
    session = get_session()
    row = session.execute(
        select(*_SUPER_ADMIN_COLUMNS)
        .join(SuperAdminDetail, SuperAdminDetail.identity_id == Identity.id)
        .where(Identity.id == super_admin_id)
    ).first()
    return dict(row._mapping) if row is not None else None


def bump_super_admin_token_version(super_admin_id: int) -> bool:
    """Not called anywhere yet (there's no super-admin management UI in this
    change) -- included for the same "revocation must be possible, not just
    theoretically supported by the schema" reason staff_users.py's own bump
    helper exists, ready for a future deactivate/reset-password action."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(Identity)
        .where(
            Identity.id == super_admin_id,
            exists().where(SuperAdminDetail.identity_id == Identity.id),
        )
        .values(token_version=Identity.token_version + 1)
    ))
    session.commit()
    return result.rowcount > 0

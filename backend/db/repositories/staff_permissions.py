# db/repositories/staff_permissions.py
"""Per-(hospital, staff, page) permission overrides -- a second, finer-
grained layer sitting on top of role_permissions.py's per-role grid. An admin
uses this to grant or revoke ONE action on ONE page for ONE specific staff
member without touching the rest of their role -- e.g. give one doctor
`delete` on Appointments while every other doctor keeps view+write only.
portal/permissions.py's has_permission() checks this table first; a NULL
(or missing) cell here falls through to that staff member's role."""
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.connection import get_session
from db.orm_models import Identity, StaffDetail, StaffPermissionOverride

_OVERRIDE_COLUMNS = (
    StaffPermissionOverride.staff_id, StaffPermissionOverride.page_key,
    StaffPermissionOverride.can_view, StaffPermissionOverride.can_write, StaffPermissionOverride.can_delete,
)


def get_staff_overrides(hospital_id: int, staff_id: int) -> list[dict]:
    """This one staff member's override rows -- sparse (only pages ever
    touched), used both by portal/permissions.py's get_staff_override_matrix()
    and by the "Users on this role" panel's per-user detail view."""
    session = get_session()
    rows = session.execute(
        select(*_OVERRIDE_COLUMNS).where(
            StaffPermissionOverride.hospital_id == hospital_id, StaffPermissionOverride.staff_id == staff_id,
        )
    ).all()
    return [dict(r._mapping) for r in rows]


def get_overrides_for_role(hospital_id: int, role_id: int) -> dict[int, list[dict]]:
    """Every override row belonging to a staff member CURRENTLY on this
    role, grouped by staff_id -- one query (not N), backing GET
    /api/portal/roles/{role_id}/users. A staff member with zero override
    rows simply isn't a key in the returned dict."""
    session = get_session()
    rows = session.execute(
        select(*_OVERRIDE_COLUMNS)
        .join(StaffDetail, StaffDetail.identity_id == StaffPermissionOverride.staff_id)
        .where(
            StaffPermissionOverride.hospital_id == hospital_id,
            StaffDetail.role_id == role_id,
        )
    ).all()
    grouped: dict[int, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r.staff_id, []).append(dict(r._mapping))
    return grouped


def list_staff_for_role(hospital_id: int, role_id: int) -> list[dict]:
    """{staff_id, name, email, is_active} for every staff member currently
    on this role -- the "Users on this role" panel's own row list, paired
    with get_overrides_for_role() above for each user's current overrides."""
    session = get_session()
    rows = session.execute(
        select(Identity.id.label("staff_id"), Identity.name, Identity.email, Identity.is_active)
        .join(StaffDetail, StaffDetail.identity_id == Identity.id)
        .where(StaffDetail.hospital_id == hospital_id, StaffDetail.role_id == role_id)
        .order_by(Identity.name)
    ).all()
    return [dict(r._mapping) for r in rows]


def upsert_staff_override(
    hospital_id: int, staff_id: int, page_key: str,
    can_view: bool | None, can_write: bool | None, can_delete: bool | None,
) -> None:
    """Writes one page's full override triple for one staff member. If the
    resulting triple is all-NULL (every action reset back to "inherit"),
    the row is deleted outright instead of written -- there's no such thing
    as a meaningless all-NULL row sitting in this table, so "reset to role
    default" is a real, visible state rather than a lingering zombie row."""
    session = get_session()
    if can_view is None and can_write is None and can_delete is None:
        session.execute(
            delete(StaffPermissionOverride).where(
                StaffPermissionOverride.hospital_id == hospital_id,
                StaffPermissionOverride.staff_id == staff_id,
                StaffPermissionOverride.page_key == page_key,
            )
        )
        session.commit()
        return
    stmt = pg_insert(StaffPermissionOverride).values(
        hospital_id=hospital_id, staff_id=staff_id, page_key=page_key,
        can_view=can_view, can_write=can_write, can_delete=can_delete,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            StaffPermissionOverride.hospital_id, StaffPermissionOverride.staff_id, StaffPermissionOverride.page_key,
        ],
        set_={"can_view": stmt.excluded.can_view, "can_write": stmt.excluded.can_write, "can_delete": stmt.excluded.can_delete},
    )
    session.execute(stmt)
    session.commit()

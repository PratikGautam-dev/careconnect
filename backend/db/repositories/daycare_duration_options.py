# db/repositories/daycare_duration_options.py
"""Daycare Phase 2 (docs/per-appointment-type-flow-plan.md): the duration
options shown at STATE_AWAITING_DAYCARE_DURATION -- hospital-configurable,
confirmed with the user directly (not a fixed list, since a same-day
few-hour stay and a multi-night admission both need to be expressible and
hospitals price/label these differently). Same "seeded fixed catalog,
editable via the portal" shape as db/repositories/appointment_types.py,
except a hospital can also add/remove its own options here (appointment
types are a closed catalog; duration options aren't)."""
from sqlalchemy import delete, select, update

from db.connection import get_session
from db.orm_models import DaycareDurationOption

# Seeded once per hospital at onboarding/backfill (db/init_db.py) -- a
# starting point every hospital can freely relabel, deactivate, add to, or
# delete from afterwards via the portal.
DEFAULT_DAYCARE_DURATION_OPTIONS = (
    {"label": "4-6 hours", "hours": 6},
    {"label": "Full day", "hours": 10},
    {"label": "Overnight (1 night)", "hours": 24},
)

_COLUMNS = (
    DaycareDurationOption.id, DaycareDurationOption.label, DaycareDurationOption.hours,
    DaycareDurationOption.is_active, DaycareDurationOption.sort_order,
)


def get_daycare_duration_options(hospital_id: int) -> list[dict]:
    """Active only, in display order -- powers the WhatsApp duration list,
    same "only ever read the active subset" discipline as
    connector.get_appointment_types()."""
    session = get_session()
    rows = session.execute(
        select(*_COLUMNS)
        .where(DaycareDurationOption.hospital_id == hospital_id, DaycareDurationOption.is_active.is_(True))
        .order_by(DaycareDurationOption.sort_order, DaycareDurationOption.id)
    ).all()
    return [dict(r._mapping) for r in rows]


def get_all_daycare_duration_options_for_hospital(hospital_id: int) -> list[dict]:
    """Active AND inactive, for the portal's own management screen."""
    session = get_session()
    rows = session.execute(
        select(*_COLUMNS)
        .where(DaycareDurationOption.hospital_id == hospital_id)
        .order_by(DaycareDurationOption.sort_order, DaycareDurationOption.id)
    ).all()
    return [dict(r._mapping) for r in rows]


def create_daycare_duration_option(hospital_id: int, label: str, hours: int) -> dict:
    session = get_session()
    max_sort_order = session.execute(
        select(DaycareDurationOption.sort_order)
        .where(DaycareDurationOption.hospital_id == hospital_id)
        .order_by(DaycareDurationOption.sort_order.desc())
        .limit(1)
    ).scalar()
    option = DaycareDurationOption(
        hospital_id=hospital_id, label=label, hours=hours, is_active=True,
        sort_order=(max_sort_order + 1) if max_sort_order is not None else 0,
    )
    session.add(option)
    session.commit()
    return {
        "id": option.id, "label": option.label, "hours": option.hours,
        "is_active": option.is_active, "sort_order": option.sort_order,
    }


def update_daycare_duration_option(hospital_id: int, option_id: int, label: str, hours: int) -> dict | None:
    session = get_session()
    result = session.execute(
        update(DaycareDurationOption)
        .where(DaycareDurationOption.hospital_id == hospital_id, DaycareDurationOption.id == option_id)
        .values(label=label, hours=hours)
    )
    session.commit()
    if result.rowcount == 0:
        return None
    row = session.execute(select(*_COLUMNS).where(DaycareDurationOption.id == option_id)).first()
    return dict(row._mapping) if row else None


def set_daycare_duration_option_active(hospital_id: int, option_id: int, is_active: bool) -> dict | None:
    session = get_session()
    result = session.execute(
        update(DaycareDurationOption)
        .where(DaycareDurationOption.hospital_id == hospital_id, DaycareDurationOption.id == option_id)
        .values(is_active=is_active)
    )
    session.commit()
    if result.rowcount == 0:
        return None
    row = session.execute(select(*_COLUMNS).where(DaycareDurationOption.id == option_id)).first()
    return dict(row._mapping) if row else None


def delete_daycare_duration_option(hospital_id: int, option_id: int) -> bool:
    session = get_session()
    result = session.execute(
        delete(DaycareDurationOption)
        .where(DaycareDurationOption.hospital_id == hospital_id, DaycareDurationOption.id == option_id)
    )
    session.commit()
    return result.rowcount > 0

# db/repositories/lab_service_areas.py
"""Lab Test Phase 2 follow-up: the hospital-configurable list of PIN codes
serviceable for home sample collection. Same "hospital-editable catalog"
shape as db/repositories/daycare_duration_options.py -- a hospital adds/
removes its own serviceable areas, starting from an empty list (there's no
sensible universal default the way daycare durations have one)."""
from sqlalchemy import delete, select, update

from db.connection import get_session
from db.orm_models import LabServiceArea

_COLUMNS = (LabServiceArea.id, LabServiceArea.pincode, LabServiceArea.is_active)


def get_service_areas(hospital_id: int) -> list[dict]:
    """Active only -- the bot-facing membership check reads through
    is_pincode_serviceable() below instead, but the portal's own read of
    "what's currently serviceable" uses this."""
    session = get_session()
    rows = session.execute(
        select(*_COLUMNS)
        .where(LabServiceArea.hospital_id == hospital_id, LabServiceArea.is_active.is_(True))
        .order_by(LabServiceArea.pincode)
    ).all()
    return [dict(r._mapping) for r in rows]


def get_all_service_areas_for_hospital(hospital_id: int) -> list[dict]:
    """Active AND inactive, for the portal's own management screen."""
    session = get_session()
    rows = session.execute(
        select(*_COLUMNS).where(LabServiceArea.hospital_id == hospital_id).order_by(LabServiceArea.pincode)
    ).all()
    return [dict(r._mapping) for r in rows]


def is_pincode_serviceable(hospital_id: int, pincode: str) -> bool:
    """The bot flow's own check, right after a patient enters a PIN code for
    Home Sample Collection -- an inactive area is NOT serviceable, same as
    every other is_active-gated bot-facing lookup in this codebase."""
    session = get_session()
    row = session.execute(
        select(LabServiceArea.id)
        .where(
            LabServiceArea.hospital_id == hospital_id, LabServiceArea.pincode == pincode,
            LabServiceArea.is_active.is_(True),
        )
    ).first()
    return row is not None


def create_service_area(hospital_id: int, pincode: str) -> dict:
    session = get_session()
    area = LabServiceArea(hospital_id=hospital_id, pincode=pincode, is_active=True)
    session.add(area)
    session.commit()
    return {"id": area.id, "pincode": area.pincode, "is_active": area.is_active}


def set_service_area_active(hospital_id: int, area_id: int, is_active: bool) -> dict | None:
    session = get_session()
    result = session.execute(
        update(LabServiceArea)
        .where(LabServiceArea.hospital_id == hospital_id, LabServiceArea.id == area_id)
        .values(is_active=is_active)
    )
    session.commit()
    if result.rowcount == 0:
        return None
    row = session.execute(select(*_COLUMNS).where(LabServiceArea.id == area_id)).first()
    return dict(row._mapping) if row else None


def delete_service_area(hospital_id: int, area_id: int) -> bool:
    session = get_session()
    result = session.execute(
        delete(LabServiceArea).where(LabServiceArea.hospital_id == hospital_id, LabServiceArea.id == area_id)
    )
    session.commit()
    return result.rowcount > 0

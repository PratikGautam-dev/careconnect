# db/repositories/procedure_resources.py
"""Daycare/Procedure rebuild: bookable bed/chair, equipment, and staff pools
-- a direct clone of db/repositories/diagnostic_resources.py's shape,
resource_type-discriminated (one pool per constraint kind a procedure needs,
see db/repositories/procedure_slots.py for how they're combined)."""
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import delete, insert, select, update

from db.connection import get_connection, get_session
from db.orm_models import ProcedureResource, ProcedureResourceSlot
from db.repositories.doctors import _overlaps_break, _parse_time_range, _WEEKDAY_ABBREVS

_SLOT_DAYS_AHEAD = 14

_RESOURCE_FULL_COLUMNS = (
    ProcedureResource.id, ProcedureResource.resource_type, ProcedureResource.department_id, ProcedureResource.name,
    ProcedureResource.working_days, ProcedureResource.working_hours, ProcedureResource.slot_duration_minutes,
    ProcedureResource.breaks, ProcedureResource.max_bookings_per_slot, ProcedureResource.daily_booking_limit,
    ProcedureResource.effective_from, ProcedureResource.is_active,
)


def _parse_resource_row(d: dict) -> dict:
    d["working_days"] = [x for x in d["working_days"].split(",") if x]
    d["working_hours"] = [x for x in d["working_hours"].split(",") if x]
    d["breaks"] = [x for x in (d.get("breaks") or "").split(",") if x]
    return d


def get_all_procedure_resources_for_hospital(hospital_id: int, resource_type: str | None = None) -> list[dict]:
    """Every resource, active or not -- portal management list, optionally
    filtered to one resource_type."""
    session = get_session()
    stmt = select(
        ProcedureResource.id, ProcedureResource.resource_type, ProcedureResource.department_id,
        ProcedureResource.name, ProcedureResource.is_active,
    ).where(ProcedureResource.hospital_id == hospital_id)
    if resource_type is not None:
        stmt = stmt.where(ProcedureResource.resource_type == resource_type)
    rows = session.execute(stmt.order_by(ProcedureResource.name)).all()
    return [dict(r._mapping) for r in rows]


def get_active_procedure_resources_for_hospital(hospital_id: int, resource_type: str) -> list[dict]:
    """Active-only pool of one resource_type -- the availability engine's own
    read (db/repositories/procedure_slots.py)."""
    session = get_session()
    rows = session.execute(
        select(*_RESOURCE_FULL_COLUMNS)
        .where(
            ProcedureResource.hospital_id == hospital_id, ProcedureResource.resource_type == resource_type,
            ProcedureResource.is_active.is_(True),
        )
        .order_by(ProcedureResource.name)
    ).all()
    return [_parse_resource_row(dict(r._mapping)) for r in rows]


def get_procedure_resource_full(hospital_id: int, resource_id: str) -> dict | None:
    session = get_session()
    row = session.execute(
        select(*_RESOURCE_FULL_COLUMNS)
        .where(ProcedureResource.hospital_id == hospital_id, ProcedureResource.id == resource_id)
    ).first()
    return _parse_resource_row(dict(row._mapping)) if row else None


def create_procedure_resource(
    hospital_id: int,
    resource_type: str,
    name: str,
    department_id: str | None = None,
    working_days: list[str] | None = None,
    working_hours: list[str] | None = None,
    slot_duration_minutes: int = 30,
    breaks: list[str] | None = None,
    max_bookings_per_slot: int = 1,
    daily_booking_limit: int | None = None,
    effective_from: str | None = None,
) -> dict:
    resource_id = f"h{hospital_id}_pres_{uuid.uuid4().hex[:8]}"
    session = get_session()
    session.execute(
        insert(ProcedureResource).values(
            id=resource_id, hospital_id=hospital_id, resource_type=resource_type, department_id=department_id,
            name=name, working_days=",".join(working_days or []), working_hours=",".join(working_hours or []),
            slot_duration_minutes=slot_duration_minutes, breaks=",".join(breaks or []),
            max_bookings_per_slot=max_bookings_per_slot, daily_booking_limit=daily_booking_limit,
            effective_from=effective_from,
        )
    )
    session.commit()
    generate_slots_for_procedure_resource(hospital_id, resource_id)
    return {"id": resource_id, "name": name, "resource_type": resource_type}


def update_procedure_resource(
    hospital_id: int,
    resource_id: str,
    name: str,
    department_id: str | None = None,
    working_days: list[str] | None = None,
    working_hours: list[str] | None = None,
    slot_duration_minutes: int = 30,
    breaks: list[str] | None = None,
    max_bookings_per_slot: int = 1,
    daily_booking_limit: int | None = None,
    effective_from: str | None = None,
) -> dict | None:
    session = get_session()
    result = session.execute(
        update(ProcedureResource)
        .where(ProcedureResource.hospital_id == hospital_id, ProcedureResource.id == resource_id)
        .values(
            name=name, department_id=department_id,
            working_days=",".join(working_days or []), working_hours=",".join(working_hours or []),
            slot_duration_minutes=slot_duration_minutes, breaks=",".join(breaks or []),
            max_bookings_per_slot=max_bookings_per_slot, daily_booking_limit=daily_booking_limit,
            effective_from=effective_from,
        )
    )
    if result.rowcount == 0:
        return None
    slot_delete = delete(ProcedureResourceSlot).where(
        ProcedureResourceSlot.hospital_id == hospital_id, ProcedureResourceSlot.resource_id == resource_id,
    )
    if effective_from:
        slot_delete = slot_delete.where(ProcedureResourceSlot.scheduled_at >= effective_from)
    session.execute(slot_delete)
    session.commit()
    generate_slots_for_procedure_resource(hospital_id, resource_id)
    return {"id": resource_id, "name": name}


def set_procedure_resource_active(hospital_id: int, resource_id: str, is_active: bool) -> bool:
    session = get_session()
    result = session.execute(
        update(ProcedureResource)
        .where(ProcedureResource.hospital_id == hospital_id, ProcedureResource.id == resource_id)
        .values(is_active=is_active)
    )
    session.commit()
    return result.rowcount > 0


def delete_procedure_resource(hospital_id: int, resource_id: str) -> bool:
    session = get_session()
    session.execute(
        delete(ProcedureResourceSlot).where(
            ProcedureResourceSlot.hospital_id == hospital_id, ProcedureResourceSlot.resource_id == resource_id,
        )
    )
    result = session.execute(
        delete(ProcedureResource).where(ProcedureResource.hospital_id == hospital_id, ProcedureResource.id == resource_id)
    )
    session.commit()
    return result.rowcount > 0


def generate_slots_for_procedure_resource(
    hospital_id: int, resource_id: str, days_ahead: int = _SLOT_DAYS_AHEAD, now: date | None = None, conn=None,
) -> int:
    """Line-for-line adaptation of diagnostic_resources.py's own
    generate_slots_for_resource() -- see that function's docstring for the
    full reasoning (idempotent ON CONFLICT DO NOTHING, raw-SQL/conn-based)."""
    conn = conn or get_connection()
    resource_row = conn.execute(
        "SELECT working_days, working_hours, slot_duration_minutes, breaks, daily_booking_limit, effective_from "
        "FROM procedure_resources WHERE hospital_id = ? AND id = ?",
        (hospital_id, resource_id),
    ).fetchone()
    if resource_row is None:
        return 0

    working_days = {d.strip() for d in resource_row["working_days"].split(",") if d.strip()}
    working_hours = [h.strip() for h in resource_row["working_hours"].split(",") if h.strip()]
    slot_duration = resource_row["slot_duration_minutes"]
    if not working_days or not working_hours or not slot_duration:
        return 0

    breaks = (
        [_parse_time_range(b) for b in resource_row["breaks"].split(",") if b.strip()] if resource_row["breaks"] else []
    )
    daily_booking_limit = resource_row["daily_booking_limit"]
    effective_from = date.fromisoformat(resource_row["effective_from"]) if resource_row["effective_from"] else None

    today = now or date.today()
    leave_dates = {
        row["date"] for row in conn.execute(
            "SELECT date FROM procedure_resource_leave WHERE hospital_id = ? AND resource_id = ?",
            (hospital_id, resource_id),
        ).fetchall()
    }

    candidates: list[tuple] = []
    for i in range(1, days_ahead + 1):
        d = today + timedelta(days=i)
        if _WEEKDAY_ABBREVS[d.weekday()] not in working_days:
            continue
        if effective_from and d < effective_from:
            continue
        if d.isoformat() in leave_dates:
            continue
        day_count = 0
        for time_range in working_hours:
            start_str, end_str = _parse_time_range(time_range)
            current = datetime.combine(d, datetime.strptime(start_str, "%H:%M").time())
            end = datetime.combine(d, datetime.strptime(end_str, "%H:%M").time())
            step = timedelta(minutes=slot_duration)
            while current + step <= end:
                if daily_booking_limit is not None and day_count >= daily_booking_limit:
                    break
                if not _overlaps_break(current, current + step, breaks, d):
                    candidates.append((hospital_id, resource_id, current.isoformat()))
                    day_count += 1
                current += step

    if not candidates:
        return 0

    placeholders = ", ".join(["(?, ?, ?)"] * len(candidates))
    flat_params = [value for row in candidates for value in row]
    cur = conn.execute(
        f"INSERT INTO procedure_resource_slots (hospital_id, resource_id, scheduled_at) VALUES {placeholders} "
        "ON CONFLICT (resource_id, scheduled_at) DO NOTHING",
        flat_params,
    )
    inserted = cur.rowcount
    conn.commit()
    return inserted


# --- Leave (mirrors diagnostic_resources.py's own leave functions) ---

def get_procedure_resource_leave_dates(hospital_id: int, resource_id: str) -> list[str]:
    session = get_session()
    rows = session.execute(
        select(ProcedureResource.id).where(ProcedureResource.hospital_id == hospital_id, ProcedureResource.id == resource_id)
    ).first()
    if rows is None:
        return []
    conn = get_connection()
    return [
        r["date"] for r in conn.execute(
            "SELECT date FROM procedure_resource_leave WHERE hospital_id = ? AND resource_id = ? ORDER BY date",
            (hospital_id, resource_id),
        ).fetchall()
    ]


def add_procedure_resource_leave(hospital_id: int, resource_id: str, leave_date: str, reason: str | None = None) -> bool:
    conn = get_connection()
    conn.execute(
        "INSERT INTO procedure_resource_leave (hospital_id, resource_id, date, reason) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (resource_id, date) DO NOTHING",
        (hospital_id, resource_id, leave_date, reason),
    )
    conn.commit()
    conn.execute(
        "DELETE FROM procedure_resource_slots WHERE hospital_id = ? AND resource_id = ? "
        "AND scheduled_at >= ? AND scheduled_at < ?",
        (hospital_id, resource_id, f"{leave_date}T00:00:00", f"{leave_date}T23:59:59"),
    )
    conn.commit()
    return True


def remove_procedure_resource_leave(hospital_id: int, resource_id: str, leave_date: str) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM procedure_resource_leave WHERE hospital_id = ? AND resource_id = ? AND date = ?",
        (hospital_id, resource_id, leave_date),
    )
    conn.commit()
    generate_slots_for_procedure_resource(hospital_id, resource_id)
    return cur.rowcount > 0

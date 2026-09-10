# db/repositories/diagnostic_test_slots.py
"""Real, persisted diagnostic_test_slots rows -- mirrors
db/repositories/slots.py's doctor_slots handling exactly, test-keyed instead
of doctor-keyed. Split out from diagnostic_tests.py (catalog CRUD) the same
way doctors.py/slots.py are split. Renamed from resource_slots.py when
diagnostic tests/resources merged into one entity."""
from datetime import datetime
from typing import cast

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from db.connection import get_session
from db.models import STATUS_BOOKED
from db.orm_models import AppointmentRow, DiagnosticTest, DiagnosticTestSlot


def get_test_slots(hospital_id: int, test_id: int, now: datetime | None = None) -> list[dict]:
    """This test's generated slots, minus any that have already reached its
    max_bookings_per_slot worth of *booked* appointments at that exact time,
    and already-past slots -- see slots.py's get_slots() for the full
    reasoning, identical here."""
    session = get_session()
    test_row = session.execute(
        select(DiagnosticTest.max_bookings_per_slot)
        .where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.id == test_id)
    ).first()
    max_bookings_per_slot = test_row[0] if test_row else 1

    booked_rows = session.execute(
        select(AppointmentRow.scheduled_at).where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.resource_id == test_id,
            AppointmentRow.status == STATUS_BOOKED,
        )
    ).all()
    booked_counts: dict[str, int] = {}
    for row in booked_rows:
        booked_counts[row.scheduled_at] = booked_counts.get(row.scheduled_at, 0) + 1

    slot_rows = session.execute(
        select(DiagnosticTestSlot.scheduled_at)
        .where(
            DiagnosticTestSlot.hospital_id == hospital_id, DiagnosticTestSlot.test_id == test_id,
            DiagnosticTestSlot.blocked.is_(False),
            DiagnosticTestSlot.scheduled_at >= (now or datetime.now()).isoformat(),
        )
        .order_by(DiagnosticTestSlot.scheduled_at)
    ).all()

    slots = []
    for row in slot_rows:
        scheduled_at_iso = row.scheduled_at
        if booked_counts.get(scheduled_at_iso, 0) >= max_bookings_per_slot:
            continue
        dt = datetime.fromisoformat(scheduled_at_iso)
        slots.append({
            "id": scheduled_at_iso,
            "date": dt.date().isoformat(),
            "time": dt.strftime("%H:%M"),
            "label": f"{dt.strftime('%a %d %b')} {dt.strftime('%H:%M')}",
        })
    return slots


def get_test_slots_for_admin(
    hospital_id: int, test_id: int, date_str: str | None = None, now: datetime | None = None,
) -> list[dict]:
    """Every generated slot for this test, blocked or not and booked or not
    -- portal management view, mirrors get_doctor_slots_for_admin()."""
    session = get_session()
    slot_stmt = select(
        DiagnosticTestSlot.scheduled_at, DiagnosticTestSlot.blocked, DiagnosticTestSlot.block_reason,
    ).where(DiagnosticTestSlot.hospital_id == hospital_id, DiagnosticTestSlot.test_id == test_id)
    booked_stmt = select(AppointmentRow.scheduled_at).where(
        AppointmentRow.hospital_id == hospital_id, AppointmentRow.resource_id == test_id,
        AppointmentRow.status == STATUS_BOOKED,
    )
    if date_str:
        start, end = f"{date_str}T00:00:00", f"{date_str}T23:59:59"
        slot_stmt = slot_stmt.where(DiagnosticTestSlot.scheduled_at >= start, DiagnosticTestSlot.scheduled_at <= end)
        booked_stmt = booked_stmt.where(AppointmentRow.scheduled_at >= start, AppointmentRow.scheduled_at <= end)
    else:
        start = (now or datetime.now()).isoformat()
        slot_stmt = slot_stmt.where(DiagnosticTestSlot.scheduled_at >= start)
        booked_stmt = booked_stmt.where(AppointmentRow.scheduled_at >= start)
    slot_rows = session.execute(slot_stmt.order_by(DiagnosticTestSlot.scheduled_at)).all()
    booked_rows = session.execute(booked_stmt).all()
    booked_at = {row.scheduled_at for row in booked_rows}
    return [
        {
            "scheduled_at": row.scheduled_at,
            "date": datetime.fromisoformat(row.scheduled_at).date().isoformat(),
            "time": datetime.fromisoformat(row.scheduled_at).strftime("%H:%M"),
            "blocked": row.blocked,
            "block_reason": row.block_reason,
            "booked": row.scheduled_at in booked_at,
        }
        for row in slot_rows
    ]


def set_test_slot_blocked(
    hospital_id: int, test_id: int, scheduled_at: str, blocked: bool, reason: str | None = None,
) -> bool:
    session = get_session()
    if blocked:
        existing = session.execute(
            select(AppointmentRow.id).where(
                AppointmentRow.hospital_id == hospital_id, AppointmentRow.resource_id == test_id,
                AppointmentRow.scheduled_at == scheduled_at, AppointmentRow.status == STATUS_BOOKED,
            )
        ).first()
        if existing:
            return False
    result = cast(CursorResult, session.execute(
        update(DiagnosticTestSlot)
        .where(
            DiagnosticTestSlot.hospital_id == hospital_id, DiagnosticTestSlot.test_id == test_id,
            DiagnosticTestSlot.scheduled_at == scheduled_at,
        )
        .values(blocked=blocked, block_reason=reason if blocked else None)
    ))
    session.commit()
    return result.rowcount > 0


def add_custom_test_slot(hospital_id: int, test_id: int, scheduled_at: str) -> bool:
    session = get_session()
    session.execute(
        pg_insert(DiagnosticTestSlot)
        .values(hospital_id=hospital_id, test_id=test_id, scheduled_at=scheduled_at)
        .on_conflict_do_nothing(index_elements=["test_id", "scheduled_at"])
    )
    session.commit()
    return True


def remove_test_slot(hospital_id: int, test_id: int, scheduled_at: str) -> bool:
    session = get_session()
    existing = session.execute(
        select(AppointmentRow.id).where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.resource_id == test_id,
            AppointmentRow.scheduled_at == scheduled_at, AppointmentRow.status == STATUS_BOOKED,
        )
    ).first()
    if existing:
        return False
    result = cast(CursorResult, session.execute(
        delete(DiagnosticTestSlot).where(
            DiagnosticTestSlot.hospital_id == hospital_id, DiagnosticTestSlot.test_id == test_id,
            DiagnosticTestSlot.scheduled_at == scheduled_at,
        )
    ))
    session.commit()
    return result.rowcount > 0


def find_test_slot(hospital_id: int, test_id: int, slot_id: str) -> dict | None:
    for s in get_test_slots(hospital_id, test_id):
        if s["id"] == slot_id:
            return s
    return None

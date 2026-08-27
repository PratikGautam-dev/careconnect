# db/repositories/slots.py
"""Real, persisted doctor_slots rows (see db/repository.py's former module
docstring). Split out of db/repository.py -- see ARCHITECTURE_PLAN.md
Phase 1."""
from datetime import datetime
from typing import cast

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from db.connection import get_session
from db.models import STATUS_BOOKED
from db.orm_models import AppointmentRow, DoctorRow, DoctorSlot

# --- Slots (real, persisted rows — see module docstring) ---

def get_slots(hospital_id: int, doctor_id: str) -> list[dict]:
    """This doctor's generated doctor_slots rows, minus any that have already
    reached this doctor's max_bookings_per_slot worth of *booked* appointments
    at that exact time (Phase 8, extended by Section 14.7: the default
    max_bookings_per_slot=1 means "any booked appointment at all," exactly
    Phase 8's original behavior; >1 keeps offering the slot until that many
    patients have booked it)."""
    session = get_session()
    doctor_row = session.execute(
        select(DoctorRow.max_bookings_per_slot).where(DoctorRow.hospital_id == hospital_id, DoctorRow.id == doctor_id)
    ).first()
    max_bookings_per_slot = doctor_row[0] if doctor_row else 1

    booked_rows = session.execute(
        select(AppointmentRow.scheduled_at).where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id,
            AppointmentRow.status == STATUS_BOOKED,
        )
    ).all()
    booked_counts: dict[str, int] = {}
    for row in booked_rows:
        booked_counts[row.scheduled_at] = booked_counts.get(row.scheduled_at, 0) + 1

    slot_rows = session.execute(
        select(DoctorSlot.scheduled_at)
        .where(DoctorSlot.hospital_id == hospital_id, DoctorSlot.doctor_id == doctor_id, DoctorSlot.blocked.is_(False))
        .order_by(DoctorSlot.scheduled_at)
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


def get_doctor_slots_for_admin(
    hospital_id: int, doctor_id: str, date_str: str | None = None, now: datetime | None = None,
) -> list[dict]:
    """Item 1 (Spec.md Section 0) + "view all slots" follow-up: every
    generated slot for this doctor, blocked or not and booked or not -- the
    admin/portal view for manually blocking/removing individual slots needs
    to see all of them, unlike get_slots() above (the bot/staff-booking-
    facing list, which only ever shows what's actually still offerable).

    date_str scopes to one calendar day (the original behavior); omitting
    it returns every slot from now onward across the doctor's whole
    generated window, each row carrying its own "date" so the portal can
    group them by day in one list rather than paging through dates one at a
    time to find (and remove) a specific slot."""
    session = get_session()
    slot_stmt = select(DoctorSlot.scheduled_at, DoctorSlot.blocked, DoctorSlot.block_reason).where(
        DoctorSlot.hospital_id == hospital_id, DoctorSlot.doctor_id == doctor_id,
    )
    booked_stmt = select(AppointmentRow.scheduled_at).where(
        AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id,
        AppointmentRow.status == STATUS_BOOKED,
    )
    if date_str:
        start, end = f"{date_str}T00:00:00", f"{date_str}T23:59:59"
        slot_stmt = slot_stmt.where(DoctorSlot.scheduled_at >= start, DoctorSlot.scheduled_at <= end)
        booked_stmt = booked_stmt.where(AppointmentRow.scheduled_at >= start, AppointmentRow.scheduled_at <= end)
    else:
        start = (now or datetime.now()).isoformat()
        slot_stmt = slot_stmt.where(DoctorSlot.scheduled_at >= start)
        booked_stmt = booked_stmt.where(AppointmentRow.scheduled_at >= start)
    slot_rows = session.execute(slot_stmt.order_by(DoctorSlot.scheduled_at)).all()
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


def set_slot_blocked(
    hospital_id: int, doctor_id: str, scheduled_at: str, blocked: bool, reason: str | None = None,
) -> bool:
    """Item 1: manual per-slot override. Refuses to block a slot that
    already has a real BOOKED appointment on it (staff must cancel/
    reschedule that appointment first, same as this project's existing
    "never silently override an active booking" discipline elsewhere) --
    returns False rather than raising, since this is a normal/expected
    rejection a caller should show as a clear message, not a 500. Unblocking
    has no such restriction (a blocked slot can never have a real booking on
    it in the first place, since get_slots() never offers a blocked slot to
    book)."""
    session = get_session()
    if blocked:
        existing = session.execute(
            select(AppointmentRow.id).where(
                AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id,
                AppointmentRow.scheduled_at == scheduled_at, AppointmentRow.status == STATUS_BOOKED,
            )
        ).first()
        if existing:
            return False
    result = cast(CursorResult, session.execute(
        update(DoctorSlot)
        .where(DoctorSlot.hospital_id == hospital_id, DoctorSlot.doctor_id == doctor_id, DoctorSlot.scheduled_at == scheduled_at)
        .values(blocked=blocked, block_reason=reason if blocked else None)
    ))
    session.commit()
    return result.rowcount > 0


def add_custom_slot(hospital_id: int, doctor_id: str, scheduled_at: str) -> bool:
    """Add/remove-slot follow-up (Spec.md Section 0): a genuinely one-off
    extra slot outside the doctor's normal generated working-hours pattern
    (e.g. a special Saturday clinic, or filling in a date that generated
    none at all) -- distinct from set_slot_blocked() above, which only
    ever toggles an already-generated row. Same UNIQUE(doctor_id,
    scheduled_at) constraint doctor_slots already has (Section 12.1.1)
    makes this ON CONFLICT DO NOTHING, so adding a time that already exists
    is a harmless no-op, not an error.

    Caveat, not fully solved here (flagged rather than silently assumed
    away): a later doctor-schedule edit with no effective_from
    (db.update_doctor()) wipes and regenerates EVERY future doctor_slots
    row purely from the working-hours pattern -- a custom slot added here
    would be wiped out by that regeneration too, same as any other slot.
    Acceptable for now (matches how every other slot already behaves under
    a schedule edit); worth a dedicated "protect custom slots" fix only if
    that turns out to matter in practice."""
    session = get_session()
    session.execute(
        pg_insert(DoctorSlot)
        .values(hospital_id=hospital_id, doctor_id=doctor_id, scheduled_at=scheduled_at)
        .on_conflict_do_nothing(index_elements=["doctor_id", "scheduled_at"])
    )
    session.commit()
    return True


def remove_slot(hospital_id: int, doctor_id: str, scheduled_at: str) -> bool:
    """The other half of add/remove: a real hard DELETE of the doctor_slots
    row (not a soft-hide like set_slot_blocked(blocked=True), which keeps
    the row so it can be unblocked later) -- for permanently taking a slot
    out of the generated set rather than just toggling its availability.
    Refuses to remove a slot with a real BOOKED appointment on it, same
    guard set_slot_blocked() already uses -- cancel/reschedule that
    appointment first."""
    session = get_session()
    existing = session.execute(
        select(AppointmentRow.id).where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id,
            AppointmentRow.scheduled_at == scheduled_at, AppointmentRow.status == STATUS_BOOKED,
        )
    ).first()
    if existing:
        return False
    result = cast(CursorResult, session.execute(
        delete(DoctorSlot).where(
            DoctorSlot.hospital_id == hospital_id, DoctorSlot.doctor_id == doctor_id,
            DoctorSlot.scheduled_at == scheduled_at,
        )
    ))
    session.commit()
    return result.rowcount > 0


def find_slot(hospital_id: int, doctor_id: str, slot_id: str) -> dict | None:
    for s in get_slots(hospital_id, doctor_id):
        if s["id"] == slot_id:
            return s
    return None



# db/repositories/slots.py
"""A doctor's bookable slots, computed live (migration 0032) -- split out of
db/repository.py, see ARCHITECTURE_PLAN.md Phase 1.

get_doctor_grid() is the one place that merges doctors.py's live-computed
candidates with doctor_slot_overrides' exceptions (blocked/custom-added) --
every other function here either filters that grid down (get_slots(),
get_doctor_slots_for_admin()) or writes an override row (set_slot_blocked(),
add_custom_slot(), remove_slot()). Deliberately NOT cached here -- this repo
layer is storage-agnostic and stays correct even when Redis is unset;
connectors/tier1.py is where the (optional, purely a perf win) grid cache
lives, wrapping get_doctor_grid() for the bot-facing read path only."""
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.connection import get_session
from db.models import STATUS_BOOKED
from db.orm_models import AppointmentRow, DoctorRow, DoctorSlotOverride
from db.repositories.doctors import compute_doctor_candidate_slots, invalidate_doctor_slots_cache
from db.repositories.hospital_settings import get_future_booking_days

# --- The grid: live candidates + overrides, not yet filtered by booked state ---

def get_doctor_grid(hospital_id: int, doctor_id: str, days_ahead: int, now: datetime | None = None) -> list[dict]:
    """Every slot this doctor could conceivably offer -- the union of
    compute_doctor_candidate_slots()'s live-computed normal-pattern
    candidates and any is_custom override, each annotated with its current
    blocked/block_reason (defaulting to not-blocked for a plain candidate
    with no override row at all). NOT filtered by booked state or by `now`
    beyond what compute_doctor_candidate_slots() itself already excludes
    (today and the past) -- callers filter further for their own purpose
    (get_slots() removes blocked/past/booked-out; get_doctor_slots_for_admin()
    keeps blocked ones visible so staff can unblock them)."""
    today = (now or datetime.now()).date()
    candidates = compute_doctor_candidate_slots(hospital_id, doctor_id, days_ahead, now=today)

    session = get_session()
    override_rows = session.execute(
        select(
            DoctorSlotOverride.scheduled_at, DoctorSlotOverride.is_custom,
            DoctorSlotOverride.blocked, DoctorSlotOverride.block_reason, DoctorSlotOverride.excluded,
        )
        .where(DoctorSlotOverride.hospital_id == hospital_id, DoctorSlotOverride.doctor_id == doctor_id)
    ).all()
    overrides = {row.scheduled_at: row for row in override_rows}

    grid: dict[str, dict] = {}
    for scheduled_at in candidates:
        override = overrides.get(scheduled_at)
        if override and override.excluded:
            continue
        grid[scheduled_at] = {
            "scheduled_at": scheduled_at,
            "blocked": override.blocked if override else False,
            "block_reason": override.block_reason if override else None,
        }
    for scheduled_at, override in overrides.items():
        if override.excluded:
            continue
        if override.is_custom and scheduled_at not in grid:
            grid[scheduled_at] = {
                "scheduled_at": scheduled_at, "blocked": override.blocked, "block_reason": override.block_reason,
            }
    return sorted(grid.values(), key=lambda entry: entry["scheduled_at"])


def _is_valid_grid_entry(hospital_id: int, doctor_id: str, scheduled_at: str) -> bool:
    grid = get_doctor_grid(hospital_id, doctor_id, get_future_booking_days(hospital_id))
    return any(entry["scheduled_at"] == scheduled_at for entry in grid)


# --- Bot/staff-booking-facing: grid filtered to what's actually offerable ---

def filter_grid_to_available(hospital_id: int, doctor_id: str, grid: list[dict], now: datetime | None = None) -> list[dict]:
    """The live, never-cached half of availability -- booked state changes on
    every booking, so connectors/tier1.py caches get_doctor_grid()'s output
    (the slow-changing part) but always calls this fresh on top of it.
    max_bookings_per_slot (Phase 8, extended by Section 14.7: default 1
    means "any booked appointment at all"; >1 keeps offering the slot until
    that many patients have booked it) and the `scheduled_at >= now` filter
    (compute_doctor_candidate_slots() already excludes today/the past for
    normal-pattern candidates, but a custom-added override could be for any
    date) both matter here, same as this function's pre-migration-0032
    equivalent."""
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

    now_iso = (now or datetime.now()).isoformat()
    slots = []
    for entry in grid:
        if entry["blocked"] or entry["scheduled_at"] < now_iso:
            continue
        if booked_counts.get(entry["scheduled_at"], 0) >= max_bookings_per_slot:
            continue
        dt = datetime.fromisoformat(entry["scheduled_at"])
        slots.append({
            "id": entry["scheduled_at"],
            "date": dt.date().isoformat(),
            "time": dt.strftime("%H:%M"),
            "label": f"{dt.strftime('%a %d %b')} {dt.strftime('%H:%M')}",
        })
    return slots


def get_slots(hospital_id: int, doctor_id: str, now: datetime | None = None) -> list[dict]:
    """Convenience wrapper for callers that don't need the grid/booked-state
    split connectors/tier1.py's caching relies on (tests, portal code, etc.)
    -- same signature and output shape as before migration 0032."""
    grid = get_doctor_grid(hospital_id, doctor_id, get_future_booking_days(hospital_id), now=now)
    return filter_grid_to_available(hospital_id, doctor_id, grid, now=now)


def get_doctor_slots_for_admin(
    hospital_id: int, doctor_id: str, date_str: str | None = None, now: datetime | None = None,
) -> list[dict]:
    """Item 1 (Spec.md Section 0) + "view all slots" follow-up: every slot in
    this doctor's grid, blocked or not and booked or not -- the admin/portal
    view for manually blocking/removing individual slots needs to see all of
    them, unlike get_slots() above (the bot/staff-booking-facing list, which
    only ever shows what's actually still offerable).

    date_str scopes to one calendar day (the original behavior); omitting it
    returns every slot from now onward across the doctor's whole computed
    window, each row carrying its own "date" so the portal can group them by
    day in one list rather than paging through dates one at a time."""
    grid = get_doctor_grid(hospital_id, doctor_id, get_future_booking_days(hospital_id), now=now)
    if date_str:
        start, end = f"{date_str}T00:00:00", f"{date_str}T23:59:59"
        grid = [e for e in grid if start <= e["scheduled_at"] <= end]
    else:
        start = (now or datetime.now()).isoformat()
        grid = [e for e in grid if e["scheduled_at"] >= start]

    session = get_session()
    booked_rows = session.execute(
        select(AppointmentRow.scheduled_at).where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id,
            AppointmentRow.status == STATUS_BOOKED,
        )
    ).all()
    booked_at = {row.scheduled_at for row in booked_rows}
    return [
        {
            "scheduled_at": e["scheduled_at"],
            "date": datetime.fromisoformat(e["scheduled_at"]).date().isoformat(),
            "time": datetime.fromisoformat(e["scheduled_at"]).strftime("%H:%M"),
            "blocked": e["blocked"],
            "block_reason": e["block_reason"],
            "booked": e["scheduled_at"] in booked_at,
        }
        for e in grid
    ]


# --- Admin overrides: doctor_slot_overrides is the only thing written here ---

def set_slot_blocked(
    hospital_id: int, doctor_id: str, scheduled_at: str, blocked: bool, reason: str | None = None,
) -> bool:
    """Item 1: manual per-slot override. Refuses to block a slot that
    already has a real BOOKED appointment on it (staff must cancel/
    reschedule that appointment first, same as this project's existing
    "never silently override an active booking" discipline elsewhere) --
    returns False rather than raising, since this is a normal/expected
    rejection a caller should show as a clear message, not a 500. Also
    refuses (either direction) if scheduled_at isn't actually a slot this
    doctor's grid ever offers -- there being no persisted row to look up
    anymore (migration 0032) means "does this slot exist" has to be checked
    against the live grid instead of a simple row lookup.

    Unblocking an already-not-blocked slot still succeeds (matches this
    function's pre-migration-0032 contract) -- and if the resulting override
    row represents nothing anymore (not custom, not blocked), it's deleted
    rather than kept, so this table only ever holds real exceptions."""
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
    if not _is_valid_grid_entry(hospital_id, doctor_id, scheduled_at):
        return False

    if blocked:
        session.execute(
            pg_insert(DoctorSlotOverride)
            .values(
                hospital_id=hospital_id, doctor_id=doctor_id, scheduled_at=scheduled_at,
                is_custom=False, blocked=True, block_reason=reason,
            )
            .on_conflict_do_update(
                index_elements=["doctor_id", "scheduled_at"], set_={"blocked": True, "block_reason": reason},
            )
        )
    else:
        session.execute(
            update(DoctorSlotOverride)
            .where(
                DoctorSlotOverride.hospital_id == hospital_id, DoctorSlotOverride.doctor_id == doctor_id,
                DoctorSlotOverride.scheduled_at == scheduled_at,
            )
            .values(blocked=False, block_reason=None)
        )
        session.execute(
            delete(DoctorSlotOverride).where(
                DoctorSlotOverride.hospital_id == hospital_id, DoctorSlotOverride.doctor_id == doctor_id,
                DoctorSlotOverride.scheduled_at == scheduled_at, DoctorSlotOverride.is_custom.is_(False),
                DoctorSlotOverride.blocked.is_(False), DoctorSlotOverride.excluded.is_(False),
            )
        )
    session.commit()
    invalidate_doctor_slots_cache(hospital_id, doctor_id)
    return True


def add_custom_slot(hospital_id: int, doctor_id: str, scheduled_at: str) -> bool:
    """Add/remove-slot follow-up (Spec.md Section 0): a genuinely one-off
    extra slot outside the doctor's normal computed working-hours pattern
    (e.g. a special Saturday clinic, or filling in a date that computes
    none at all) -- distinct from set_slot_blocked() above, which only ever
    toggles an already-offerable slot. ON CONFLICT DO UPDATE (rather than DO
    NOTHING) so re-adding a slot that already has a blocked override just
    flips is_custom on without disturbing that existing block -- and clears
    excluded, so explicitly re-adding a previously-removed slot brings it
    back rather than leaving it silently suppressed."""
    session = get_session()
    session.execute(
        pg_insert(DoctorSlotOverride)
        .values(hospital_id=hospital_id, doctor_id=doctor_id, scheduled_at=scheduled_at, is_custom=True, blocked=False, excluded=False)
        .on_conflict_do_update(index_elements=["doctor_id", "scheduled_at"], set_={"is_custom": True, "excluded": False})
    )
    session.commit()
    invalidate_doctor_slots_cache(hospital_id, doctor_id)
    return True


def remove_slot(hospital_id: int, doctor_id: str, scheduled_at: str) -> bool:
    """The other half of add/remove: takes a slot out of the offered set
    outright -- gone from get_slots() AND the admin view, unlike
    set_slot_blocked() above which keeps it visible for later unblocking.
    A normal-pattern slot has no persisted row to delete (migration 0032),
    so this is recorded as its own exclusion (migration 0034's `excluded`
    column) rather than a DELETE -- otherwise the live computation would
    just regenerate the slot on the very next read. Refuses to remove a
    slot with a real BOOKED appointment on it, same guard set_slot_blocked()
    already uses, and refuses a scheduled_at that isn't currently a valid
    grid entry at all (matches this function's pre-migration-0032 contract
    of only ever affecting a real, existing slot)."""
    session = get_session()
    existing = session.execute(
        select(AppointmentRow.id).where(
            AppointmentRow.hospital_id == hospital_id, AppointmentRow.doctor_id == doctor_id,
            AppointmentRow.scheduled_at == scheduled_at, AppointmentRow.status == STATUS_BOOKED,
        )
    ).first()
    if existing:
        return False
    if not _is_valid_grid_entry(hospital_id, doctor_id, scheduled_at):
        return False
    session.execute(
        pg_insert(DoctorSlotOverride)
        .values(
            hospital_id=hospital_id, doctor_id=doctor_id, scheduled_at=scheduled_at,
            is_custom=False, blocked=False, excluded=True,
        )
        .on_conflict_do_update(index_elements=["doctor_id", "scheduled_at"], set_={"excluded": True})
    )
    session.commit()
    invalidate_doctor_slots_cache(hospital_id, doctor_id)
    return True


def find_slot(hospital_id: int, doctor_id: str, slot_id: str) -> dict | None:
    for s in get_slots(hospital_id, doctor_id):
        if s["id"] == slot_id:
            return s
    return None

# db/repositories/procedure_slots.py
"""Daycare/Procedure rebuild: the multi-resource-constraint availability
engine. No equivalent exists anywhere else in this codebase -- every other
booking type (doctor, diagnostic/lab resource) binds to exactly ONE
resource/timestamp pair. A procedure instead needs EVERY one of its required
resource pools (bed_chair/equipment/staff) to have at least one free resource
covering the full span [scheduled_at, scheduled_at + duration_minutes), on
each pool's OWN generated slot grid (db/repositories/procedure_resources.py's
generate_slots_for_procedure_resource) -- reusing that per-resource grid
directly rather than inventing a second, universal calendar."""
import math
from datetime import datetime, timedelta

from sqlalchemy import select

from db.connection import IntegrityError, get_session
from db.models import STATUS_BOOKED
from db.orm_models import AppointmentProcedureResource, AppointmentRow, Procedure, ProcedureResourceSlot
from db.repositories.procedure_resources import get_active_procedure_resources_for_hospital
from db.repositories.procedures import get_procedure


def _span_timestamps(start: datetime, duration_minutes: int, resource_slot_duration_minutes: int) -> list[str]:
    """The resource's own grid timestamps a booking of this duration,
    starting at `start`, would occupy -- e.g. a 30-min grid resource booked
    for a 180-min procedure occupies 6 consecutive sub-slots."""
    steps = math.ceil(duration_minutes / resource_slot_duration_minutes)
    return [(start + timedelta(minutes=k * resource_slot_duration_minutes)).isoformat() for k in range(steps)]


def _occupied_subslot_counts(hospital_id: int, resource_id: str, resource_slot_duration_minutes: int) -> dict[str, int]:
    """For every currently-booked appointment bound to this resource,
    expands its own span into individual resource-grid sub-slot timestamps
    and counts how many bookings occupy each -- generalizes
    resource_slots.py's own single-timestamp booked-count to a span, since a
    procedure's duration_minutes can cover more than one of the resource's
    own generated slots."""
    session = get_session()
    rows = session.execute(
        select(AppointmentRow.scheduled_at, Procedure.duration_minutes)
        .select_from(AppointmentProcedureResource)
        .join(AppointmentRow, AppointmentRow.id == AppointmentProcedureResource.appointment_id)
        .join(Procedure, Procedure.id == AppointmentRow.procedure_id)
        .where(
            AppointmentProcedureResource.hospital_id == hospital_id,
            AppointmentProcedureResource.resource_id == resource_id,
            AppointmentRow.status == STATUS_BOOKED,
        )
    ).all()
    counts: dict[str, int] = {}
    for scheduled_at_iso, proc_duration in rows:
        for ts in _span_timestamps(datetime.fromisoformat(scheduled_at_iso), proc_duration, resource_slot_duration_minutes):
            counts[ts] = counts.get(ts, 0) + 1
    return counts


def _resource_free_for_span(hospital_id: int, resource: dict, start: datetime, duration_minutes: int, now: datetime) -> bool:
    """True iff every one of this resource's own grid sub-slots across the
    requested span is (a) a real generated, unblocked slot (so a span can
    never spill past working hours, into a break, or onto a leave day -- all
    already enforced by generate_slots_for_procedure_resource's own
    generation), and (b) not already at max_bookings_per_slot worth of
    booked appointments at that sub-slot."""
    if start < now:
        return False
    resource_id = resource["id"]
    slot_dur = resource["slot_duration_minutes"]
    max_per_slot = resource["max_bookings_per_slot"]
    needed = _span_timestamps(start, duration_minutes, slot_dur)
    session = get_session()
    generated = set(session.execute(
        select(ProcedureResourceSlot.scheduled_at).where(
            ProcedureResourceSlot.hospital_id == hospital_id, ProcedureResourceSlot.resource_id == resource_id,
            ProcedureResourceSlot.blocked.is_(False), ProcedureResourceSlot.scheduled_at.in_(needed),
        )
    ).scalars().all())
    if not all(ts in generated for ts in needed):
        return False
    counts = _occupied_subslot_counts(hospital_id, resource_id, slot_dur)
    return all(counts.get(ts, 0) < max_per_slot for ts in needed)


def get_procedure_available_slots(hospital_id: int, procedure_id: int, now: datetime | None = None) -> list[dict]:
    """Every candidate start-time (drawn from the union of every required
    pool's own generated grid, soonest first) where EVERY required resource
    type has at least one free resource covering the procedure's full
    duration. A required pool with zero configured resources makes the
    whole procedure unbookable (same "no resource linked -> not available"
    discipline Diagnostic/Lab Test already enforce, no any-doctor-style
    fallback)."""
    now = now or datetime.now()
    procedure = get_procedure(hospital_id, procedure_id)
    if procedure is None:
        return []
    duration_minutes = procedure["duration_minutes"]
    required_types = procedure["required_resource_types"]
    if not required_types:
        return []
    pools = {rt: get_active_procedure_resources_for_hospital(hospital_id, rt) for rt in required_types}
    if any(not pool for pool in pools.values()):
        return []

    resource_ids = [r["id"] for pool in pools.values() for r in pool]
    session = get_session()
    candidate_rows = session.execute(
        select(ProcedureResourceSlot.scheduled_at)
        .where(
            ProcedureResourceSlot.hospital_id == hospital_id,
            ProcedureResourceSlot.resource_id.in_(resource_ids),
            ProcedureResourceSlot.blocked.is_(False),
            ProcedureResourceSlot.scheduled_at >= now.isoformat(),
        )
        .distinct()
        .order_by(ProcedureResourceSlot.scheduled_at)
    ).all()

    slots = []
    for (ts,) in candidate_rows:
        start = datetime.fromisoformat(ts)
        if all(
            any(_resource_free_for_span(hospital_id, r, start, duration_minutes, now) for r in pool)
            for pool in pools.values()
        ):
            slots.append({
                "id": ts, "date": start.date().isoformat(), "time": start.strftime("%H:%M"),
                "label": f"{start.strftime('%a %d %b')} {start.strftime('%H:%M')}",
            })
    return slots


def find_procedure_slot(hospital_id: int, procedure_id: int, slot_id: str) -> dict | None:
    for s in get_procedure_available_slots(hospital_id, procedure_id):
        if s["id"] == slot_id:
            return s
    return None


def _resource_free_for_span_conn(conn, hospital_id: int, resource: dict, start: datetime, duration_minutes: int) -> bool:
    """Raw-connection counterpart of _resource_free_for_span -- must run
    INSIDE the caller's own advisory-locked transaction (see
    reserve_procedure_resources' own docstring), so this stays on the same
    raw `conn`/transaction rather than a fresh ORM session."""
    resource_id = resource["id"]
    slot_dur = resource["slot_duration_minutes"]
    max_per_slot = resource["max_bookings_per_slot"]
    needed = _span_timestamps(start, duration_minutes, slot_dur)
    placeholders = ", ".join(["?"] * len(needed))
    generated_rows = conn.execute(
        f"SELECT scheduled_at FROM procedure_resource_slots WHERE hospital_id = ? AND resource_id = ? "
        f"AND blocked = FALSE AND scheduled_at IN ({placeholders})",
        (hospital_id, resource_id, *needed),
    ).fetchall()
    generated = {r["scheduled_at"] for r in generated_rows}
    if not all(ts in generated for ts in needed):
        return False
    booked_rows = conn.execute(
        "SELECT a.scheduled_at, p.duration_minutes FROM appointment_procedure_resources apr "
        "JOIN appointments a ON a.id = apr.appointment_id "
        "JOIN procedures p ON p.id = a.procedure_id "
        "WHERE apr.hospital_id = ? AND apr.resource_id = ? AND a.status = ?",
        (hospital_id, resource_id, STATUS_BOOKED),
    ).fetchall()
    counts: dict[str, int] = {}
    for row in booked_rows:
        for ts in _span_timestamps(datetime.fromisoformat(row["scheduled_at"]), row["duration_minutes"], slot_dur):
            counts[ts] = counts.get(ts, 0) + 1
    return all(counts.get(ts, 0) < max_per_slot for ts in needed)


def reserve_procedure_resources(hospital_id: int, procedure_id: int, scheduled_at: datetime, conn) -> list[dict]:
    """Called ONLY from inside create_procedure_appointment()'s/
    confirm_procedure_appointment()'s own pg_advisory_xact_lock transaction,
    after the lock is held: re-scans each required pool under that same
    connection/lock, picks the FIRST free resource per type, raising
    IntegrityError if any required type has none free anymore (a race lost
    since the slot menu was rendered) -- same "recheck under the lock, don't
    trust the earlier read" discipline create_appointment() already applies
    to its own single-resource ordinal check. Returns
    [{"resource_id", "resource_type", "resource_name"}, ...], one per
    required type."""
    proc_row = conn.execute(
        "SELECT duration_minutes FROM procedures WHERE hospital_id = ? AND id = ?", (hospital_id, procedure_id),
    ).fetchone()
    if proc_row is None:
        raise IntegrityError(f"procedure {procedure_id} not found for hospital {hospital_id}")
    duration_minutes = proc_row["duration_minutes"]
    resource_types = [
        r["resource_type"] for r in conn.execute(
            "SELECT resource_type FROM procedure_required_resource_types WHERE hospital_id = ? AND procedure_id = ?",
            (hospital_id, procedure_id),
        ).fetchall()
    ]
    reserved = []
    for resource_type in resource_types:
        pool = conn.execute(
            "SELECT id, name, slot_duration_minutes, max_bookings_per_slot FROM procedure_resources "
            "WHERE hospital_id = ? AND resource_type = ? AND is_active = TRUE",
            (hospital_id, resource_type),
        ).fetchall()
        chosen = next(
            (r for r in pool if _resource_free_for_span_conn(conn, hospital_id, r, scheduled_at, duration_minutes)),
            None,
        )
        if chosen is None:
            raise IntegrityError(
                f"No free {resource_type} resource for procedure {procedure_id} at {scheduled_at.isoformat()}"
            )
        reserved.append({"resource_id": chosen["id"], "resource_type": resource_type, "resource_name": chosen["name"]})
    return reserved

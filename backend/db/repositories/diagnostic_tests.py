# db/repositories/diagnostic_tests.py
"""The test catalog a patient picks from (Diagnostic Test / Lab Test menus)
and its own schedule.

Diagnostic tests/resources merge: a test used to be a thin catalog row
(name/category) pointing at a separate `diagnostic_resources` row that
carried the actual machine/equipment's schedule (working days/hours, slot
duration, breaks, capacity, leave). Hospitals were always creating exactly
one resource per test 1:1 anyway, so that indirection is gone -- a test now
carries its own schedule directly (mirrors DoctorRow's own shape) and has no
department at all. Test/variant merge: a test also carries its own price
directly now -- it only ever needed exactly one priced option, so the
separate diagnostic_test_variants child table (label + preparation_
instructions, neither of which earned their complexity) is gone too.
Schedule/slot-generation logic below is a line-for-line adaptation of what
used to live in db/repositories/diagnostic_resources.py (itself adapted from
doctors.py's own doctor+doctor_slots handling)."""
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select, update

from db.connection import get_connection, get_session
from db.orm_models import DiagnosticTest
from db.repositories.doctors import _overlaps_break, _parse_time_range, _WEEKDAY_ABBREVS
from db.repositories.hospital_settings import get_future_booking_days

CATEGORY_DIAGNOSTIC = "diagnostic"
CATEGORY_LAB = "lab"

# Seeded once per hospital at onboarding/backfill (db/init_db.py) -- a
# starting point every hospital can freely relabel/reprice/remove afterwards
# via the portal.
DEFAULT_DIAGNOSTIC_TESTS = (
    "MRI", "CT Scan", "X-Ray", "Ultrasound", "ECG", "Echocardiography", "Mammography", "Other Diagnostic Test",
)
DEFAULT_LAB_TESTS = (
    "CBC", "LFT", "KFT", "Lipid Profile", "Thyroid Profile", "Urine Routine", "Other Lab Test",
)

_SLOT_DAYS_AHEAD = 14

_TEST_COLUMNS = (
    DiagnosticTest.id, DiagnosticTest.category, DiagnosticTest.name, DiagnosticTest.price,
    DiagnosticTest.is_active, DiagnosticTest.sort_order,
)
_TEST_FULL_COLUMNS = (
    DiagnosticTest.id, DiagnosticTest.category, DiagnosticTest.name, DiagnosticTest.price,
    DiagnosticTest.working_days, DiagnosticTest.working_hours, DiagnosticTest.slot_duration_minutes,
    DiagnosticTest.breaks, DiagnosticTest.max_bookings_per_slot, DiagnosticTest.daily_booking_limit,
    DiagnosticTest.effective_from, DiagnosticTest.is_active, DiagnosticTest.sort_order,
)


def _parse_test_row(d: dict) -> dict:
    if d.get("price") is not None:
        d["price"] = float(d["price"])
    return d


def _parse_schedule_row(d: dict) -> dict:
    d = _parse_test_row(d)
    d["working_days"] = [x for x in d["working_days"].split(",") if x]
    d["working_hours"] = [x for x in d["working_hours"].split(",") if x]
    d["breaks"] = [x for x in (d.get("breaks") or "").split(",") if x]
    return d


def get_diagnostic_tests(hospital_id: int, category: str) -> list[dict]:
    """Active tests only -- powers the WhatsApp test-selection list."""
    session = get_session()
    test_rows = session.execute(
        select(*_TEST_COLUMNS)
        .where(
            DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.category == category,
            DiagnosticTest.is_active.is_(True),
        )
        .order_by(DiagnosticTest.sort_order, DiagnosticTest.id)
    ).all()
    return [_parse_test_row(dict(row._mapping)) for row in test_rows]


def get_diagnostic_test_summaries(hospital_id: int) -> list[dict]:
    """Every active test, both categories -- used by auth/session.py's
    portal-reschedule context builder to pre-load every resource-bound
    appointment's possible slots (mirrors the old get_diagnostic_resources()),
    and by the portal's new-test-booking dialog (NewTestBookingDialog.tsx) to
    group tests by category and show a price. category/price were added for
    that second caller -- the reschedule-context caller only ever used
    id/name and ignores the extra fields."""
    session = get_session()
    rows = session.execute(
        select(DiagnosticTest.id, DiagnosticTest.name, DiagnosticTest.category, DiagnosticTest.price)
        .where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.is_active.is_(True))
        .order_by(DiagnosticTest.name)
    ).all()
    # _parse_test_row: price is NUMERIC -> SQLAlchemy hands back Decimal,
    # which json.dumps() can't serialize -- same conversion every other test
    # read already goes through, needed here too now that this function
    # returns price at all.
    return [_parse_test_row(dict(r._mapping)) for r in rows]


def get_diagnostic_test(hospital_id: int, test_id: int) -> dict | None:
    session = get_session()
    row = session.execute(
        select(*_TEST_COLUMNS).where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.id == test_id)
    ).first()
    return _parse_test_row(dict(row._mapping)) if row else None


def get_diagnostic_test_full(hospital_id: int, test_id: int) -> dict | None:
    """Test row including its own schedule fields -- the portal's edit-form
    fetch, mirrors the old get_resource_full()."""
    session = get_session()
    row = session.execute(
        select(*_TEST_FULL_COLUMNS).where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.id == test_id)
    ).first()
    return _parse_schedule_row(dict(row._mapping)) if row else None


def get_all_diagnostic_tests_for_hospital(hospital_id: int, category: str | None = None) -> list[dict]:
    """Active AND inactive tests (with schedule fields), for the portal's own
    management screen."""
    session = get_session()
    stmt = select(*_TEST_FULL_COLUMNS).where(DiagnosticTest.hospital_id == hospital_id)
    if category is not None:
        stmt = stmt.where(DiagnosticTest.category == category)
    test_rows = session.execute(stmt.order_by(DiagnosticTest.sort_order, DiagnosticTest.id)).all()
    return [_parse_schedule_row(dict(row._mapping)) for row in test_rows]


def create_diagnostic_test(
    hospital_id: int,
    category: str,
    name: str,
    price: float | None = None,
    working_days: list[str] | None = None,
    working_hours: list[str] | None = None,
    slot_duration_minutes: int = 30,
    breaks: list[str] | None = None,
    max_bookings_per_slot: int = 1,
    daily_booking_limit: int | None = None,
    effective_from: str | None = None,
) -> dict:
    session = get_session()
    max_sort_order = session.execute(
        select(DiagnosticTest.sort_order)
        .where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.category == category)
        .order_by(DiagnosticTest.sort_order.desc()).limit(1)
    ).scalar()
    test = DiagnosticTest(
        hospital_id=hospital_id, category=category, name=name, price=price,
        working_days=",".join(working_days or []), working_hours=",".join(working_hours or []),
        slot_duration_minutes=slot_duration_minutes, breaks=",".join(breaks or []),
        max_bookings_per_slot=max_bookings_per_slot, daily_booking_limit=daily_booking_limit,
        effective_from=effective_from, is_active=True,
        sort_order=(max_sort_order + 1) if max_sort_order is not None else 0,
    )
    session.add(test)
    session.commit()
    generate_slots_for_test(hospital_id, test.id, days_ahead=get_future_booking_days(hospital_id))
    return get_diagnostic_test_full(hospital_id, test.id)


def update_diagnostic_test(
    hospital_id: int,
    test_id: int,
    name: str,
    price: float | None = None,
    working_days: list[str] | None = None,
    working_hours: list[str] | None = None,
    slot_duration_minutes: int = 30,
    breaks: list[str] | None = None,
    max_bookings_per_slot: int = 1,
    daily_booking_limit: int | None = None,
    effective_from: str | None = None,
) -> dict | None:
    """Regenerates diagnostic_test_slots against the (possibly changed)
    working pattern -- same "safe to drop and rebuild still-unbooked slots"
    reasoning as update_doctor()/the old update_resource()."""
    session = get_session()
    result = session.execute(
        update(DiagnosticTest)
        .where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.id == test_id)
        .values(
            name=name, price=price,
            working_days=",".join(working_days or []), working_hours=",".join(working_hours or []),
            slot_duration_minutes=slot_duration_minutes, breaks=",".join(breaks or []),
            max_bookings_per_slot=max_bookings_per_slot, daily_booking_limit=daily_booking_limit,
            effective_from=effective_from,
        )
    )
    if result.rowcount == 0:
        return None
    from db.orm_models import DiagnosticTestSlot
    slot_delete = delete(DiagnosticTestSlot).where(
        DiagnosticTestSlot.hospital_id == hospital_id, DiagnosticTestSlot.test_id == test_id,
    )
    if effective_from:
        slot_delete = slot_delete.where(DiagnosticTestSlot.scheduled_at >= effective_from)
    session.execute(slot_delete)
    session.commit()
    generate_slots_for_test(hospital_id, test_id, days_ahead=get_future_booking_days(hospital_id))
    return get_diagnostic_test_full(hospital_id, test_id)


def set_diagnostic_test_active(hospital_id: int, test_id: int, is_active: bool) -> dict | None:
    session = get_session()
    result = session.execute(
        update(DiagnosticTest)
        .where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.id == test_id)
        .values(is_active=is_active)
    )
    session.commit()
    if result.rowcount == 0:
        return None
    return get_diagnostic_test(hospital_id, test_id)


def delete_diagnostic_test(hospital_id: int, test_id: int) -> bool:
    session = get_session()
    result = session.execute(
        delete(DiagnosticTest).where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.id == test_id)
    )
    session.commit()
    return result.rowcount > 0


# --- Schedule/slot generation (mirrors db/repositories/doctors.py's own
# pre-live-grid generate_slots_for_doctor()) ---

def generate_slots_for_test(
    hospital_id: int, test_id: int, days_ahead: int = _SLOT_DAYS_AHEAD, now: date | None = None, conn=None,
) -> int:
    """Line-for-line adaptation of the old diagnostic_resources.py's
    generate_slots_for_resource() -- same idempotent ON CONFLICT DO NOTHING,
    same reasoning for staying raw-SQL/conn-based (see doctors.py's own
    generate_slots_for_doctor() docstring)."""
    conn = conn or get_connection()
    test_row = conn.execute(
        "SELECT working_days, working_hours, slot_duration_minutes, breaks, daily_booking_limit, effective_from "
        "FROM diagnostic_tests WHERE hospital_id = ? AND id = ?",
        (hospital_id, test_id),
    ).fetchone()
    if test_row is None:
        return 0

    working_days = {d.strip() for d in test_row["working_days"].split(",") if d.strip()}
    working_hours = [h.strip() for h in test_row["working_hours"].split(",") if h.strip()]
    slot_duration = test_row["slot_duration_minutes"]
    if not working_days or not working_hours or not slot_duration:
        return 0

    breaks = (
        [_parse_time_range(b) for b in test_row["breaks"].split(",") if b.strip()] if test_row["breaks"] else []
    )
    daily_booking_limit = test_row["daily_booking_limit"]
    effective_from = date.fromisoformat(test_row["effective_from"]) if test_row["effective_from"] else None

    today = now or date.today()
    leave_dates = {
        row["date"] for row in conn.execute(
            "SELECT date FROM diagnostic_test_leave WHERE hospital_id = ? AND test_id = ?",
            (hospital_id, test_id),
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
                    candidates.append((hospital_id, test_id, current.isoformat()))
                    day_count += 1
                current += step

    if not candidates:
        return 0

    placeholders = ", ".join(["(?, ?, ?)"] * len(candidates))
    flat_params = [value for row in candidates for value in row]
    cur = conn.execute(
        f"INSERT INTO diagnostic_test_slots (hospital_id, test_id, scheduled_at) VALUES {placeholders} "
        "ON CONFLICT (test_id, scheduled_at) DO NOTHING",
        flat_params,
    )
    inserted = cur.rowcount
    conn.commit()
    return inserted


# --- Leave (mirrors db/repositories/leave.py's doctor_leave functions) ---

def get_test_leave_dates(hospital_id: int, test_id: int) -> list[str]:
    session = get_session()
    row = session.execute(
        select(DiagnosticTest.id).where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.id == test_id)
    ).first()
    if row is None:
        return []
    conn = get_connection()
    return [
        r["date"] for r in conn.execute(
            "SELECT date FROM diagnostic_test_leave WHERE hospital_id = ? AND test_id = ? ORDER BY date",
            (hospital_id, test_id),
        ).fetchall()
    ]


def add_test_leave(hospital_id: int, test_id: int, leave_date: str, reason: str | None = None) -> bool:
    conn = get_connection()
    conn.execute(
        "INSERT INTO diagnostic_test_leave (hospital_id, test_id, date, reason) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (test_id, date) DO NOTHING",
        (hospital_id, test_id, leave_date, reason),
    )
    conn.commit()
    conn.execute(
        "DELETE FROM diagnostic_test_slots WHERE hospital_id = ? AND test_id = ? "
        "AND scheduled_at >= ? AND scheduled_at < ?",
        (hospital_id, test_id, f"{leave_date}T00:00:00", f"{leave_date}T23:59:59"),
    )
    conn.commit()
    return True


def remove_test_leave(hospital_id: int, test_id: int, leave_date: str) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM diagnostic_test_leave WHERE hospital_id = ? AND test_id = ? AND date = ?",
        (hospital_id, test_id, leave_date),
    )
    conn.commit()
    generate_slots_for_test(hospital_id, test_id, days_ahead=get_future_booking_days(hospital_id))
    return cur.rowcount > 0

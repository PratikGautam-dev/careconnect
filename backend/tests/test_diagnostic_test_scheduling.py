# tests/test_diagnostic_test_scheduling.py
"""Diagnostic tests/resources merge: a diagnostic_tests row now carries its
own schedule directly (working days/hours/breaks/capacity/leave) instead of
linking to a separate diagnostic_resources row -- hospitals always created
exactly one resource per test 1:1 anyway. This file covers schedule/slot-
generation CRUD (mirrors test_doctor_scheduling.py's own style for the
doctor-side equivalent), and the higher-level booking-flow behavior specific
to a test-bound booking: double-booking rejection,
reschedule carry-forward, and an unconfigured test correctly showing "not
available" rather than falling back to any-doctor-with-open-slots (removed --
confirmed with the user directly, see the test at the bottom of this file).
Renamed from test_diagnostic_resources.py when the merge happened."""
from datetime import datetime, timedelta

import pytest

import db.repository as db
from connectors import Tier1Connector
from db.connection import IntegrityError
from flows.booking import handle_incoming
from core.session_store import InMemorySessionStore


class FakeWhatsAppClient:
    def __init__(self):
        self.sent = []

    async def send_text(self, to, text):
        self.sent.append(("text", {"to": to, "text": text}))

    async def send_buttons(self, to, body_text, buttons):
        self.sent.append(("buttons", {"to": to, "body_text": body_text, "buttons": buttons}))

    async def send_list(self, to, body_text, button_text, sections):
        self.sent.append(("list", {"to": to, "body_text": body_text, "button_text": button_text, "sections": sections}))


PHONE = "+15550001111"


def tap(row_id: str) -> dict:
    return {"type": "interactive_reply", "id": row_id}


def _last_list(wa):
    for kind, kwargs in reversed(wa.sent):
        if kind == "list":
            return kwargs
    return None


def _row_ids(kwargs) -> set:
    return {r["id"] for s in kwargs["sections"] for r in s["rows"]}


# --- diagnostic_tests schedule CRUD + slot generation ---

def test_create_test_generates_slots_from_working_pattern(hospital_id):
    test = db.create_diagnostic_test(
        hospital_id, "diagnostic", "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-11:00"], slot_duration_minutes=30,
    )
    slots = db.get_test_slots(hospital_id, test["id"])
    assert slots
    assert all(s["time"] for s in slots)


def test_test_leave_date_excluded_from_slots(hospital_id):
    test = db.create_diagnostic_test(
        hospital_id, "diagnostic", "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-10:00"], slot_duration_minutes=30,
    )
    slots_before = db.get_test_slots(hospital_id, test["id"])
    leave_date = slots_before[0]["date"]
    db.add_test_leave(hospital_id, test["id"], leave_date, reason="Maintenance")
    slots_after = db.get_test_slots(hospital_id, test["id"])
    assert all(s["date"] != leave_date for s in slots_after)


def test_test_slot_block_and_remove(hospital_id):
    test = db.create_diagnostic_test(
        hospital_id, "diagnostic", "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-10:00"], slot_duration_minutes=30,
    )
    slots = db.get_test_slots(hospital_id, test["id"])
    target = slots[0]["id"]
    assert db.set_test_slot_blocked(hospital_id, test["id"], target, True, "Servicing")
    assert target not in {s["id"] for s in db.get_test_slots(hospital_id, test["id"])}
    assert db.set_test_slot_blocked(hospital_id, test["id"], target, False)
    assert target in {s["id"] for s in db.get_test_slots(hospital_id, test["id"])}
    assert db.remove_test_slot(hospital_id, test["id"], target)
    assert target not in {s["id"] for s in db.get_test_slots(hospital_id, test["id"])}


def test_test_max_bookings_per_slot(hospital_id):
    test = db.create_diagnostic_test(
        hospital_id, "diagnostic", "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-10:00"], slot_duration_minutes=30,
        max_bookings_per_slot=2,
    )
    scheduled_at = datetime.fromisoformat(db.get_test_slots(hospital_id, test["id"])[0]["id"])
    db.create_appointment(
        hospital_id, PHONE, db.get_departments(hospital_id)[0]["id"], None, scheduled_at,
        diagnostic_test_id=test["id"],
    )
    # Second booking at the exact same slot succeeds (capacity 2)...
    db.create_appointment(
        hospital_id, "+15550002222", db.get_departments(hospital_id)[0]["id"], None, scheduled_at,
        diagnostic_test_id=test["id"],
    )
    # ...a third does not.
    with pytest.raises(IntegrityError):
        db.create_appointment(
            hospital_id, "+15550003333", db.get_departments(hospital_id)[0]["id"], None, scheduled_at,
            diagnostic_test_id=test["id"],
        )


# --- Booking flow: double-booking, reschedule ---

@pytest.fixture
def sessions():
    return InMemorySessionStore()


async def _book_diagnostic_test(wa, sessions, hospital_id, test_name: str, phone: str = PHONE, confirm: bool = True):
    """Drives a fresh Diagnostic Test booking up to the confirmation card,
    picking the named test. confirm=True (default) also taps "confirm"; a
    caller that wants to inspect the confirmation card itself (not the final
    success card) passes confirm=False and taps it separately."""
    sessions.set(hospital_id, phone, "AWAITING_APPOINTMENT_TYPE", {"patient_name": "Ravi Kumar", "patient_age": 34})
    await handle_incoming(wa, sessions, phone, hospital_id, tap("diagnostic"))
    tests = db.get_diagnostic_tests(hospital_id, "diagnostic")
    test = next(t for t in tests if t["name"] == test_name)
    await handle_incoming(wa, sessions, phone, hospital_id, tap(str(test["id"])))
    context = sessions.get(hospital_id, phone)["context"]
    resource_id = context.get("resource_id")
    slots = db.get_test_slots(hospital_id, resource_id) if resource_id else db.get_slots(hospital_id, context["doctor_id"])
    date_str = slots[0]["date"]
    await handle_incoming(wa, sessions, phone, hospital_id, tap(date_str))
    slot = next(s for s in slots if s["date"] == date_str)
    await handle_incoming(wa, sessions, phone, hospital_id, tap(slot["id"]))
    assert sessions.get(hospital_id, phone)["state"] == "AWAITING_CONFIRMATION"
    if confirm:
        await handle_incoming(wa, sessions, phone, hospital_id, tap("confirm"))


@pytest.mark.asyncio
async def test_diagnostic_confirmation_shows_amount(hospital_id, sessions):
    wa = FakeWhatsAppClient()
    test = db.get_diagnostic_tests(hospital_id, "diagnostic")[0]
    db.update_diagnostic_test(
        hospital_id, test["id"], test["name"], price=4500,
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-17:00"], slot_duration_minutes=30,
    )

    await _book_diagnostic_test(wa, sessions, hospital_id, test["name"], confirm=False)

    # The confirmation card (pre-confirm) is where the amount shows -- the
    # final success card deliberately doesn't repeat it.
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "4500" in kwargs["body_text"] or "4,500" in kwargs["body_text"]

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))
    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    appt = next(a for a in due if a.phone == PHONE)
    assert appt.diagnostic_test_id == test["id"]
    assert appt.diagnostic_price == 4500
    assert appt.doctor_id is None


@pytest.mark.asyncio
async def test_two_patients_cannot_book_the_same_test_slot(hospital_id, sessions):
    """Real double-booking prevention (create_appointment()'s resource-scoped
    advisory lock + ux_appointments_resource_slot_ordinal_booked), exercised
    through the actual WhatsApp flow for patient 1, then verified directly:
    a second booking at the EXACT same test+scheduled_at raises."""
    wa = FakeWhatsAppClient()
    test = db.get_diagnostic_tests(hospital_id, "diagnostic")[0]
    db.update_diagnostic_test(
        hospital_id, test["id"], test["name"],
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-09:30"], slot_duration_minutes=30,
    )

    await _book_diagnostic_test(wa, sessions, hospital_id, test["name"])
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "booked" in kwargs["body_text"].lower()

    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    booked = next(a for a in due if a.phone == PHONE)
    with pytest.raises(IntegrityError):
        db.create_appointment(
            hospital_id, "+15559998888", booked.department_id, None, booked.scheduled_at,
            diagnostic_test_id=test["id"],
        )


@pytest.mark.asyncio
async def test_rescheduling_a_test_bound_appointment_carries_test_forward(hospital_id, sessions):
    wa = FakeWhatsAppClient()
    test = db.get_diagnostic_tests(hospital_id, "diagnostic")[0]
    db.update_diagnostic_test(
        hospital_id, test["id"], test["name"],
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-17:00"], slot_duration_minutes=30,
    )

    await _book_diagnostic_test(wa, sessions, hospital_id, test["name"])
    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    original = next(a for a in due if a.phone == PHONE)

    connector = Tier1Connector()
    new_appointment = connector.reschedule_booking(
        hospital_id, original.id, PHONE, original.department_id, None,
        original.scheduled_at + timedelta(minutes=30), diagnostic_test_id=test["id"],
    )
    assert new_appointment.diagnostic_test_id == test["id"]
    assert new_appointment.diagnostic_test_id == original.diagnostic_test_id
    assert new_appointment.diagnostic_price == original.diagnostic_price


@pytest.mark.asyncio
async def test_unconfigured_test_shows_not_available_instead_of_falling_back_to_a_doctor(hospital_id, sessions):
    """Confirmed with the user directly: a test with no schedule configured
    (the seeded default -- blank working_days/working_hours, same state a
    since-deactivated resource used to leave it in before tests/resources
    merged into one entity) no longer falls back to any-doctor-with-open-
    slots (that silently tied a lab/diagnostic booking to an unrelated
    doctor's calendar) -- it's simply "not available right now," the same
    treatment an unconfigured doctor (zero generated slots) already gets
    elsewhere in this app."""
    wa = FakeWhatsAppClient()
    test = db.get_diagnostic_tests(hospital_id, "diagnostic")[0]
    full = db.get_diagnostic_test_full(hospital_id, test["id"])
    assert not full["working_days"]

    sessions.set(hospital_id, PHONE, "AWAITING_APPOINTMENT_TYPE", {"patient_name": "Ravi Kumar", "patient_age": 34})
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("diagnostic"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(str(test["id"])))

    # Reset back to idle (main menu shown), not stuck mid-flow, and no
    # appointment was ever created.
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"
    kind, kwargs = wa.sent[-2]
    assert kind == "text"
    assert "no available slots" in kwargs["text"].lower() or "not available" in kwargs["text"].lower()
    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    assert not any(a.phone == PHONE for a in due)

# tests/test_diagnostic_resources.py
"""Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5):
diagnostic_resources CRUD + slot generation (mirrors test_doctor_scheduling.py's
own style for the doctor-side equivalents), and the higher-level booking-flow
behavior specific to a resource-bound test: variant selection, resource
double-booking rejection, reschedule carry-forward, and the resource-less
fallback to any-doctor-with-open-slots."""
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


# --- diagnostic_resources CRUD + slot generation ---

def test_create_resource_generates_slots_from_working_pattern(hospital_id):
    resource = db.create_resource(
        hospital_id, "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-11:00"], slot_duration_minutes=30,
    )
    slots = db.get_resource_slots(hospital_id, resource["id"])
    assert slots
    assert all(s["time"] for s in slots)


def test_resource_leave_date_excluded_from_slots(hospital_id):
    resource = db.create_resource(
        hospital_id, "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-10:00"], slot_duration_minutes=30,
    )
    slots_before = db.get_resource_slots(hospital_id, resource["id"])
    leave_date = slots_before[0]["date"]
    db.add_resource_leave(hospital_id, resource["id"], leave_date, reason="Maintenance")
    slots_after = db.get_resource_slots(hospital_id, resource["id"])
    assert all(s["date"] != leave_date for s in slots_after)


def test_resource_slot_block_and_remove(hospital_id):
    resource = db.create_resource(
        hospital_id, "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-10:00"], slot_duration_minutes=30,
    )
    slots = db.get_resource_slots(hospital_id, resource["id"])
    target = slots[0]["id"]
    assert db.set_resource_slot_blocked(hospital_id, resource["id"], target, True, "Servicing")
    assert target not in {s["id"] for s in db.get_resource_slots(hospital_id, resource["id"])}
    assert db.set_resource_slot_blocked(hospital_id, resource["id"], target, False)
    assert target in {s["id"] for s in db.get_resource_slots(hospital_id, resource["id"])}
    assert db.remove_resource_slot(hospital_id, resource["id"], target)
    assert target not in {s["id"] for s in db.get_resource_slots(hospital_id, resource["id"])}


def test_resource_max_bookings_per_slot(hospital_id):
    resource = db.create_resource(
        hospital_id, "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-10:00"], slot_duration_minutes=30,
        max_bookings_per_slot=2,
    )
    tests = db.get_diagnostic_tests(hospital_id, "diagnostic")
    variant_id = tests[0]["variants"][0]["id"]
    scheduled_at = datetime.fromisoformat(db.get_resource_slots(hospital_id, resource["id"])[0]["id"])
    db.create_appointment(
        hospital_id, PHONE, db.get_departments(hospital_id)[0]["id"], None, scheduled_at,
        resource_id=resource["id"], diagnostic_test_variant_id=variant_id,
    )
    # Second booking at the exact same slot succeeds (capacity 2)...
    db.create_appointment(
        hospital_id, "+15550002222", db.get_departments(hospital_id)[0]["id"], None, scheduled_at,
        resource_id=resource["id"], diagnostic_test_variant_id=variant_id,
    )
    # ...a third does not.
    with pytest.raises(IntegrityError):
        db.create_appointment(
            hospital_id, "+15550003333", db.get_departments(hospital_id)[0]["id"], None, scheduled_at,
            resource_id=resource["id"], diagnostic_test_variant_id=variant_id,
        )


# --- Booking flow: multi-variant selection, resource double-booking, reschedule ---

@pytest.fixture
def sessions():
    return InMemorySessionStore()


async def _book_diagnostic_test(
    wa, sessions, hospital_id, test_name: str, variant_index: int = 0, phone: str = PHONE, confirm: bool = True,
):
    """Drives a fresh Diagnostic Test booking up to the confirmation card,
    picking the named test and, if it has multiple variants, the variant at
    variant_index. confirm=True (default) also taps "confirm"; a caller that
    wants to inspect the confirmation card itself (not the final success
    card) passes confirm=False and taps it separately."""
    sessions.set(hospital_id, phone, "AWAITING_APPOINTMENT_TYPE", {"patient_name": "Ravi Kumar", "patient_age": 34})
    await handle_incoming(wa, sessions, phone, hospital_id, tap("diagnostic"))
    tests = db.get_diagnostic_tests(hospital_id, "diagnostic")
    test = next(t for t in tests if t["name"] == test_name)
    await handle_incoming(wa, sessions, phone, hospital_id, tap(str(test["id"])))
    session = sessions.get(hospital_id, phone)
    if session["state"] == "AWAITING_DIAGNOSTIC_VARIANT":
        variant = test["variants"][variant_index]
        await handle_incoming(wa, sessions, phone, hospital_id, tap(str(variant["id"])))
    context = sessions.get(hospital_id, phone)["context"]
    resource_id = context.get("resource_id")
    slots = db.get_resource_slots(hospital_id, resource_id) if resource_id else db.get_slots(hospital_id, context["doctor_id"])
    date_str = slots[0]["date"]
    await handle_incoming(wa, sessions, phone, hospital_id, tap(date_str))
    slot = next(s for s in slots if s["date"] == date_str)
    await handle_incoming(wa, sessions, phone, hospital_id, tap(slot["id"]))
    assert sessions.get(hospital_id, phone)["state"] == "AWAITING_CONFIRMATION"
    if confirm:
        await handle_incoming(wa, sessions, phone, hospital_id, tap("confirm"))


@pytest.mark.asyncio
async def test_variant_selection_shown_when_test_has_multiple_variants(hospital_id, sessions):
    wa = FakeWhatsAppClient()
    resource = db.create_resource(
        hospital_id, "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-17:00"], slot_duration_minutes=30,
    )
    test = db.get_diagnostic_tests(hospital_id, "diagnostic")[0]
    db.update_diagnostic_test(hospital_id, test["id"], test["name"], resource["id"])
    db.create_variant(hospital_id, test["id"], "With Contrast", 5000, "Fast for 4 hours before the scan.")

    sessions.set(hospital_id, PHONE, "AWAITING_APPOINTMENT_TYPE", {"patient_name": "Ravi Kumar", "patient_age": 34})
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("diagnostic"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(str(test["id"])))

    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DIAGNOSTIC_VARIANT"
    kwargs = _last_list(wa)
    assert len(_row_ids(kwargs)) == 2


@pytest.mark.asyncio
async def test_diagnostic_confirmation_shows_amount_and_preparation_instructions(hospital_id, sessions):
    wa = FakeWhatsAppClient()
    resource = db.create_resource(
        hospital_id, "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-17:00"], slot_duration_minutes=30,
    )
    test = db.get_diagnostic_tests(hospital_id, "diagnostic")[0]
    db.update_diagnostic_test(hospital_id, test["id"], test["name"], resource["id"])
    standard = test["variants"][0]
    db.update_variant(hospital_id, standard["id"], "Standard", 4500, "Please fast for 4 hours before the scan.")

    await _book_diagnostic_test(wa, sessions, hospital_id, test["name"], confirm=False)

    # The confirmation card (pre-confirm) is where amount/prep instructions
    # show -- the final success card deliberately doesn't repeat them.
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "4500" in kwargs["body_text"] or "4,500" in kwargs["body_text"]
    assert "fast for 4 hours" in kwargs["body_text"].lower()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))
    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    appt = next(a for a in due if a.phone == PHONE)
    assert appt.resource_id == resource["id"]
    assert appt.diagnostic_test_variant_id == standard["id"]
    assert appt.diagnostic_price == 4500
    assert appt.doctor_id is None


@pytest.mark.asyncio
async def test_two_patients_cannot_book_the_same_resource_slot(hospital_id, sessions):
    """Real double-booking prevention (create_appointment()'s resource-scoped
    advisory lock + ux_appointments_resource_slot_ordinal_booked), exercised
    through the actual WhatsApp flow for patient 1, then verified directly:
    a second booking at the EXACT same resource+scheduled_at raises."""
    wa = FakeWhatsAppClient()
    resource = db.create_resource(
        hospital_id, "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-09:30"], slot_duration_minutes=30,
    )
    test = db.get_diagnostic_tests(hospital_id, "diagnostic")[0]
    db.update_diagnostic_test(hospital_id, test["id"], test["name"], resource["id"])

    await _book_diagnostic_test(wa, sessions, hospital_id, test["name"])
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "booked" in kwargs["body_text"].lower()

    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    booked = next(a for a in due if a.phone == PHONE)
    variant_id = test["variants"][0]["id"]
    with pytest.raises(IntegrityError):
        db.create_appointment(
            hospital_id, "+15559998888", booked.department_id, None, booked.scheduled_at,
            resource_id=resource["id"], diagnostic_test_variant_id=variant_id,
        )


@pytest.mark.asyncio
async def test_rescheduling_a_resource_bound_appointment_carries_test_and_resource_forward(hospital_id, sessions):
    wa = FakeWhatsAppClient()
    resource = db.create_resource(
        hospital_id, "MRI Machine 1",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-17:00"], slot_duration_minutes=30,
    )
    test = db.get_diagnostic_tests(hospital_id, "diagnostic")[0]
    db.update_diagnostic_test(hospital_id, test["id"], test["name"], resource["id"])

    await _book_diagnostic_test(wa, sessions, hospital_id, test["name"])
    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    original = next(a for a in due if a.phone == PHONE)

    connector = Tier1Connector()
    new_appointment = connector.reschedule_booking(
        hospital_id, original.id, PHONE, original.department_id, None,
        original.scheduled_at + timedelta(minutes=30), resource_id=resource["id"],
    )
    assert new_appointment.resource_id == resource["id"]
    assert new_appointment.diagnostic_test_id == original.diagnostic_test_id
    assert new_appointment.diagnostic_test_variant_id == original.diagnostic_test_variant_id
    assert new_appointment.diagnostic_price == original.diagnostic_price


@pytest.mark.asyncio
async def test_resource_less_test_falls_back_to_any_doctor_with_open_slots(hospital_id, sessions):
    """A seeded default test has resource_id=None -- booking it should still
    work end to end via the pre-existing any-doctor fallback."""
    wa = FakeWhatsAppClient()
    test = db.get_diagnostic_tests(hospital_id, "diagnostic")[0]
    assert test.get("resource_id") is None

    await _book_diagnostic_test(wa, sessions, hospital_id, test["name"])
    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    appt = next(a for a in due if a.phone == PHONE)
    assert appt.resource_id is None
    assert appt.doctor_id is not None

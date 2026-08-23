# tests/test_phase8_edge_cases.py
"""
SPEC Section 5 Phase 8 edge-case hardening:
  1. Double-booking / race conditions
  2. Stale session resumption enforced everywhere a state is read
  5. Empty department/doctor/slot lists handled gracefully

Malformed webhook payloads, concurrent-message locking, and delivery-failure
handling (Phase 8 items 3/4/6) are covered in tests/test_main.py and
tests/test_whatsapp.py instead — those are properties of core/main.py's
webhook handler and core/whatsapp.py's send client, not of the booking flow
state machine tested here.
"""
from datetime import datetime, timedelta

import pytest

import db.connection as db_connection
import db.repository as db
from core.booking_flow import handle_incoming
from core.history import InMemorySessionStore


class FakeWhatsAppClient:
    """Records every outgoing send instead of hitting the network."""

    def __init__(self):
        self.sent = []  # list of ("text"|"list"|"buttons", kwargs)

    async def send_text(self, to, text):
        self.sent.append(("text", {"to": to, "text": text}))

    async def send_list(self, to, body_text, button_text, sections, header_text=None, footer_text=None):
        self.sent.append(("list", {"to": to, "body_text": body_text, "sections": sections}))

    async def send_buttons(self, to, body_text, buttons, header_text=None, footer_text=None):
        self.sent.append(("buttons", {"to": to, "body_text": body_text, "buttons": buttons}))


def text_reply(text):
    return {"type": "text", "text": text}


def tap(option_id, title=""):
    return {"type": "interactive_reply", "id": option_id, "title": title}


PHONE = "5491112345678"
OTHER_PHONE = "5499998887777"


def _row_ids(kind_kwargs):
    return {row["id"] for section in kind_kwargs["sections"] for row in section["rows"]}


def _list_sends(wa):
    return [kwargs for kind, kwargs in wa.sent if kind == "list"]


# --- 1. Double-booking / race conditions ---

@pytest.mark.asyncio
async def test_confirm_race_second_patient_gets_taken_message_and_updated_slot_list(hospital_id):
    """Two patients both reach AWAITING_CONFIRMATION for the exact same doctor+slot
    (e.g. two browser/app taps in quick succession) — the first confirm wins,
    the second is told the slot was taken and shown a list that no longer offers it."""
    wa = FakeWhatsAppClient()
    sessions_a = InMemorySessionStore()
    sessions_b = InMemorySessionStore()

    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    shared_context = {
        "department_id": "cardiology", "department_name": "Cardiology",
        "doctor_id": doctor_id, "doctor_name": "Dr. Anjali Rao",
        "date": slot["date"], "date_label": "Sat, Aug 8",
        "slot_id": slot["id"], "slot_date": slot["date"], "slot_time": slot["time"],
        "patient_name": "Test Patient",
    }
    sessions_a.set(hospital_id, PHONE, "AWAITING_CONFIRMATION", dict(shared_context))
    sessions_b.set(hospital_id, OTHER_PHONE, "AWAITING_CONFIRMATION", dict(shared_context))

    # Patient A confirms first -> succeeds. Item 3 (Spec.md Section 0): the
    # success message is now buttons, not plain text.
    await handle_incoming(wa, sessions_a, PHONE, hospital_id, tap("confirm"))
    assert "booked successfully" in wa.sent[-1][1]["body_text"].lower()
    assert sessions_a.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}

    # Patient B confirms the same doctor+slot next -> loses the race.
    await handle_incoming(wa, sessions_b, OTHER_PHONE, hospital_id, tap("confirm"))
    text_sends = [kwargs["text"] for kind, kwargs in wa.sent if kind == "text"]
    assert any("just taken" in t.lower() for t in text_sends)

    # B is sent back to time selection (same doctor/date, not re-asked
    # department/doctor/date) with a freshly-queried list that no longer
    # offers the taken slot.
    session_b = sessions_b.get(hospital_id, OTHER_PHONE)
    assert session_b["state"] == "AWAITING_TIME_SLOT"
    assert session_b["context"]["doctor_id"] == doctor_id
    assert slot["id"] not in _row_ids(_list_sends(wa)[-1])

    # Only one appointment actually exists for this doctor+slot — no double-booking.
    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    matching = [a for a in due if a.doctor_id == doctor_id and a.scheduled_at.isoformat() == f"{slot['date']}T{slot['time']}:00"]
    assert len(matching) == 1
    assert matching[0].phone == PHONE


@pytest.mark.asyncio
async def test_reschedule_race_leaves_original_appointment_intact(hospital_id):
    """If the new slot got taken by someone else between the reschedule-confirm
    menu being sent and the patient tapping Confirm, the patient must keep
    their ORIGINAL appointment — not end up with neither."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    original = db.create_appointment(hospital_id, PHONE, "cardiology", doctor_id, datetime.now() + timedelta(hours=48))

    contested_slot = db.get_slots(hospital_id, doctor_id)[0]
    # Someone else books the slot this patient is about to try to reschedule into.
    db.create_appointment(hospital_id, OTHER_PHONE, "cardiology", doctor_id,
                           datetime.fromisoformat(f"{contested_slot['date']}T{contested_slot['time']}:00"))

    sessions.set(hospital_id, PHONE, "AWAITING_RESCHEDULE_CONFIRM", {
        "reschedule_appointment_id": original.id,
        "department_id": "cardiology", "department_name": "Cardiology",
        "doctor_id": doctor_id, "doctor_name": "Dr. Anjali Rao",
        "slot_id": contested_slot["id"], "slot_label": contested_slot["label"],
        "slot_date": contested_slot["date"], "slot_time": contested_slot["time"],
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))

    text_sends = [kwargs["text"] for kind, kwargs in wa.sent if kind == "text"]
    assert any("just taken" in t.lower() for t in text_sends)
    # The original appointment must still be booked -- NOT marked rescheduled,
    # since the replacement booking never actually succeeded.
    assert db.get_appointment(hospital_id, original.id).status == db.STATUS_BOOKED
    assert db.get_upcoming_appointments_for_phone(hospital_id, PHONE) == [db.get_appointment(hospital_id, original.id)]
    # Item 3 (Spec.md Section 0): recovery re-shows a date-scoped TIME list
    # (_send_time_menu), not the old combined date+time list -- the taken
    # slot's own date, since context here only carries "slot_date" (this
    # session was seeded directly into AWAITING_RESCHEDULE_CONFIRM, skipping
    # the date-picking step, so there's no "date" key to fall back from).
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_RESCHEDULE_SLOT"
    kwargs = _list_sends(wa)[-1]
    assert contested_slot["id"] not in _row_ids(kwargs)
    assert _row_ids(kwargs) == {
        s["id"] for s in db.get_slots(hospital_id, doctor_id) if s["date"] == contested_slot["date"]
    }
    assert wa.sent[-1][0] == "buttons"  # the follow-up Back button (Spec.md Section 0)


@pytest.mark.asyncio
async def test_confirm_race_when_doctor_has_no_other_slots_left(hospital_id):
    """Edge case within the edge case: the doctor's only remaining slot is the
    one that was just taken -- the patient should get a clear "nothing left"
    message rather than an empty/broken list."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    all_slots = db.get_slots(hospital_id, doctor_id)
    last_slot = all_slots[-1]

    # Fill every slot except the last one.
    for s in all_slots[:-1]:
        db.create_appointment(hospital_id, "000", "cardiology", doctor_id, datetime.fromisoformat(f"{s['date']}T{s['time']}:00"))
    # Someone else grabs the last one right before this patient confirms.
    db.create_appointment(hospital_id, OTHER_PHONE, "cardiology", doctor_id, datetime.fromisoformat(f"{last_slot['date']}T{last_slot['time']}:00"))

    sessions.set(hospital_id, PHONE, "AWAITING_CONFIRMATION", {
        "department_id": "cardiology", "department_name": "Cardiology",
        "doctor_id": doctor_id, "doctor_name": "Dr. Anjali Rao",
        "date": last_slot["date"], "date_label": "Sat, Aug 8",
        "slot_id": last_slot["id"], "slot_date": last_slot["date"], "slot_time": last_slot["time"],
        "patient_name": "Test Patient",
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))

    # Item 9: the "nothing left" text is still sent, now followed by the
    # main menu as a recovery path (this is a genuine dead end, not item 1's
    # "pick another slot" case -- there's nothing left to pick).
    text_kind, text_kwargs = wa.sent[-2]
    assert text_kind == "text"
    assert "no other slots" in text_kwargs["text"].lower()
    menu_kind, menu_kwargs = wa.sent[-1]
    assert menu_kind == "list"
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_confirm_race_loser_picks_alternate_slot_without_being_reasked_name_or_age(hospital_id):
    """Full item-1 scenario: patient B loses the confirm race (like the test
    above), but this time actually picks one of the freshly-offered alternate
    slots -- since B's name/age were already collected THIS session (held in
    context) but never reached the DB (create_appointment()'s failed
    transaction rolls back before _upsert_patient() runs), B must go straight
    to a new confirmation card, not be asked for name/age a second time."""
    wa = FakeWhatsAppClient()
    sessions_a = InMemorySessionStore()
    sessions_b = InMemorySessionStore()

    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slots = db.get_slots(hospital_id, doctor_id)
    contested = slots[0]
    same_day_alternate = next(s for s in slots[1:] if s["date"] == contested["date"])

    shared_context = {
        "department_id": "cardiology", "department_name": "Cardiology",
        "doctor_id": doctor_id, "doctor_name": "Dr. Anjali Rao",
        "date": contested["date"], "date_label": "Sat, Aug 8",
        "slot_id": contested["id"], "slot_date": contested["date"], "slot_time": contested["time"],
        "patient_name": "Race Loser", "patient_age": 41,
    }
    sessions_a.set(hospital_id, PHONE, "AWAITING_CONFIRMATION", dict(shared_context))
    sessions_b.set(hospital_id, OTHER_PHONE, "AWAITING_CONFIRMATION", dict(shared_context))

    # A confirms first and wins the contested slot.
    await handle_incoming(wa, sessions_a, PHONE, hospital_id, tap("confirm"))
    assert "booked successfully" in wa.sent[-1][1]["body_text"].lower()

    # B confirms next -> loses the race, is shown alternate times for the
    # SAME doctor/date (not sent back to department/doctor/date selection).
    await handle_incoming(wa, sessions_b, OTHER_PHONE, hospital_id, tap("confirm"))
    session_b = sessions_b.get(hospital_id, OTHER_PHONE)
    assert session_b["state"] == "AWAITING_TIME_SLOT"
    assert session_b["context"]["patient_name"] == "Race Loser"
    assert session_b["context"]["patient_age"] == 41
    offered_ids = _row_ids(_list_sends(wa)[-1])
    assert contested["id"] not in offered_ids
    assert same_day_alternate["id"] in offered_ids

    # B picks one of the alternate slots -- must go STRAIGHT to a new
    # confirmation card (not AWAITING_PATIENT_NAME/AGE), and the card must
    # still show B's own name/age, not blank/re-collected values.
    wa.sent.clear()
    await handle_incoming(wa, sessions_b, OTHER_PHONE, hospital_id, tap(same_day_alternate["id"]))
    session_b = sessions_b.get(hospital_id, OTHER_PHONE)
    assert session_b["state"] == "AWAITING_CONFIRMATION"
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "Race Loser" in kwargs["body_text"]
    assert "41" in kwargs["body_text"]

    # And confirming actually books it -- the DB-level upsert (deferred by
    # the earlier failed transaction) finally happens here, on the
    # successful booking.
    await handle_incoming(wa, sessions_b, OTHER_PHONE, hospital_id, tap("confirm"))
    assert "booked successfully" in wa.sent[-1][1]["body_text"].lower()
    booked = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    b_appt = next(a for a in booked if a.phone == OTHER_PHONE and a.doctor_id == doctor_id)
    assert b_appt.scheduled_at.isoformat() == f"{same_day_alternate['date']}T{same_day_alternate['time']}:00"


# --- 2. Stale session resumption enforced everywhere a state is read ---

@pytest.mark.parametrize("state,context", [
    ("AWAITING_DEPARTMENT", {}),
    ("AWAITING_DOCTOR", {"department_id": "cardiology", "department_name": "Cardiology"}),
    ("AWAITING_DATE", {"department_id": "cardiology", "department_name": "Cardiology",
                        "doctor_id": "doc_card_1", "doctor_name": "Dr. Anjali Rao"}),
    ("AWAITING_TIME_SLOT", {"department_id": "cardiology", "department_name": "Cardiology",
                             "doctor_id": "doc_card_1", "doctor_name": "Dr. Anjali Rao", "date": "2026-08-08"}),
    ("AWAITING_PATIENT_NAME", {"department_name": "Cardiology", "doctor_name": "Dr. Anjali Rao"}),
    ("AWAITING_PATIENT_AGE", {"department_name": "Cardiology", "doctor_name": "Dr. Anjali Rao", "patient_name": "x"}),
    ("AWAITING_CONFIRMATION", {"department_name": "Cardiology", "doctor_name": "Dr. Anjali Rao", "date_label": "x",
                                "slot_time": "x", "patient_name": "x", "patient_age": 30}),
    ("AWAITING_CANCEL_SELECTION", {}),
    ("AWAITING_CANCEL_CONFIRM", {"appointment_id": 1}),
    ("AWAITING_RESCHEDULE_SELECTION", {}),
    ("AWAITING_RESCHEDULE_SLOT", {"doctor_id": "doc_card_1", "doctor_name": "Dr. Anjali Rao", "reschedule_appointment_id": 1}),
    ("AWAITING_RESCHEDULE_CONFIRM", {"doctor_name": "Dr. Anjali Rao", "slot_label": "x", "reschedule_appointment_id": 1}),
])
@pytest.mark.asyncio
async def test_stale_session_in_every_state_resets_to_idle_and_shows_main_menu(hospital_id, state, context):
    """The 30-min timeout check lives in a single place (core/history.py's
    session store .get()), called from a single place (booking_flow.handle_incoming).
    This proves that centralization actually covers every state name the state
    machine can be in — not just the one state a single hand-picked test might use."""
    import time

    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore(timeout_seconds=0)
    sessions.set(hospital_id, PHONE, state, context)
    time.sleep(0.01)  # ensure the 0-second timeout has definitely elapsed

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("anything"), hospital_name="City Hospital")

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert "City Hospital" in kwargs["body_text"]  # got the main menu, not a resumed stale flow
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


# --- 5. Empty department/doctor/slot lists ---

@pytest.mark.asyncio
async def test_department_with_zero_doctors_shows_graceful_message(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    conn = db_connection.get_connection()
    conn.execute("INSERT INTO departments (id, hospital_id, name) VALUES (?, ?, ?)", ("empty_dept", hospital_id, "Empty Department"))
    conn.commit()
    sessions.set(hospital_id, PHONE, "AWAITING_DEPARTMENT", {})

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("empty_dept"))

    # Item 9: the graceful message is now followed by the main menu, so the
    # patient has a way forward instead of a dead end.
    text_kind, text_kwargs = wa.sent[-2]
    assert text_kind == "text"
    assert "no doctors available" in text_kwargs["text"].lower()
    assert wa.sent[-1][0] == "list"
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_doctor_with_zero_available_slots_shows_graceful_message(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    doctor_id = "doc_card_1"
    for slot in db.get_slots(hospital_id, doctor_id):
        db.create_appointment(hospital_id, "000", "cardiology", doctor_id, datetime.fromisoformat(f"{slot['date']}T{slot['time']}:00"))
    assert db.get_slots(hospital_id, doctor_id) == []

    sessions.set(hospital_id, PHONE, "AWAITING_DOCTOR", {"department_id": "cardiology", "department_name": "Cardiology"})
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id))

    text_kind, text_kwargs = wa.sent[-2]
    assert text_kind == "text"
    assert "no available slots" in text_kwargs["text"].lower()
    assert wa.sent[-1][0] == "list"
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_reschedule_selection_doctor_with_zero_slots_shows_graceful_message(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    doctor_id = "doc_card_1"
    appt = db.create_appointment(hospital_id, PHONE, "cardiology", doctor_id, datetime.now() + timedelta(hours=72))
    for slot in db.get_slots(hospital_id, doctor_id):
        db.create_appointment(hospital_id, "000", "cardiology", doctor_id, datetime.fromisoformat(f"{slot['date']}T{slot['time']}:00"))
    assert db.get_slots(hospital_id, doctor_id) == []

    sessions.set(hospital_id, PHONE, "AWAITING_RESCHEDULE_SELECTION", {})
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"appt_{appt.id}"))

    text_kind, text_kwargs = wa.sent[-2]
    assert text_kind == "text"
    assert "no available slots" in text_kwargs["text"].lower()
    assert wa.sent[-1][0] == "list"
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_awaiting_slot_fallback_rechecks_availability_if_slots_emptied_mid_flow(hospital_id):
    """Slots are dynamic — another patient can take the last one while this
    patient is still typing free text instead of tapping. The re-prompt path
    must recheck, not blindly resend a now-empty list."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    doctor_id = "doc_card_1"
    for slot in db.get_slots(hospital_id, doctor_id):
        db.create_appointment(hospital_id, "000", "cardiology", doctor_id, datetime.fromisoformat(f"{slot['date']}T{slot['time']}:00"))
    sessions.set(hospital_id, PHONE, "AWAITING_DATE", {
        "department_id": "cardiology", "department_name": "Cardiology",
        "doctor_id": doctor_id, "doctor_name": "Dr. Anjali Rao",
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("whatever"))

    text_kind, text_kwargs = wa.sent[-2]
    assert text_kind == "text"
    assert "no available slots" in text_kwargs["text"].lower()
    assert wa.sent[-1][0] == "list"
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_duplicate_booking_with_same_doctor_and_age_is_blocked_with_quick_actions(hospital_id):
    """Item 5 (Spec.md Section 0): confirming a booking with the same doctor
    + same age as an existing active appointment on this phone is blocked --
    the patient is shown a clear message with Cancel/Reschedule/Main Menu
    quick actions for the EXISTING appointment, not a generic error."""
    from core.booking_flow import GOTO_MAIN_MENU, MANAGE_CANCEL_PREFIX, MANAGE_RESCHEDULE_PREFIX

    doctor_id = "doc_card_1"
    slots = db.get_slots(hospital_id, doctor_id)
    existing = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slots[0]['date']}T{slots[0]['time']}"),
        patient_name="Ravi Kumar", patient_age=34,
    )

    wa2 = FakeWhatsAppClient()
    sessions2 = InMemorySessionStore()
    sessions2.set(hospital_id, PHONE, "AWAITING_CONFIRMATION", {
        "department_id": "cardiology", "department_name": "Cardiology",
        "doctor_id": doctor_id, "doctor_name": "Dr. Anjali Rao",
        "date": slots[1]["date"], "date_label": "Sat, Aug 8",
        "slot_id": slots[1]["id"], "slot_date": slots[1]["date"], "slot_time": slots[1]["time"],
        "patient_name": "Ravi Kumar", "patient_age": 34,
    })

    await handle_incoming(wa2, sessions2, PHONE, hospital_id, tap("confirm"))

    kind, kwargs = wa2.sent[-1]
    assert kind == "buttons"
    assert "already have an appointment" in kwargs["body_text"].lower()
    button_ids = {b["id"] for b in kwargs["buttons"]}
    assert GOTO_MAIN_MENU in button_ids
    assert f"{MANAGE_CANCEL_PREFIX}{existing.id}" in button_ids
    assert f"{MANAGE_RESCHEDULE_PREFIX}{existing.id}" in button_ids

    # No second appointment was actually created.
    due = db.get_upcoming_appointments_for_phone(hospital_id, PHONE)
    assert len(due) == 1
    assert due[0].id == existing.id

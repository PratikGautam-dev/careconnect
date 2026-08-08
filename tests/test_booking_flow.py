from datetime import datetime, timedelta

import pytest

import db.repository as db
from core.booking_flow import _MAX_LIST_ROWS, handle_incoming
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


def _seed_appointment(hospital_id, phone=PHONE, hours_from_now=24, department_id="cardiology", doctor_id="doc_card_1"):
    scheduled_at = datetime.now() + timedelta(hours=hours_from_now)
    return db.create_appointment(hospital_id, phone, department_id, doctor_id, scheduled_at)


def _row_ids(kind_kwargs):
    return {row["id"] for section in kind_kwargs["sections"] for row in section["rows"]}


@pytest.mark.asyncio
async def test_idle_any_message_sends_welcome_and_main_menu(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), hospital_name="City Hospital")

    assert len(wa.sent) == 1
    kind, kwargs = wa.sent[0]
    assert kind == "list"
    assert "City Hospital" in kwargs["body_text"]
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert row_ids == {"menu_book", "menu_reschedule", "menu_cancel", "menu_faq"}
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_idle_book_tap_advances_to_awaiting_department(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))

    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert row_ids == {d["id"] for d in db.get_departments(hospital_id)}


@pytest.mark.asyncio
async def test_idle_reschedule_tap_with_no_appointments_replies_and_stays_idle(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reschedule"))

    assert wa.sent == [("text", {"to": PHONE, "text": "You don't have any upcoming appointments to reschedule."})]
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_idle_cancel_tap_with_no_appointments_replies_and_stays_idle(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_cancel"))

    assert wa.sent == [("text", {"to": PHONE, "text": "You don't have any upcoming appointments to cancel."})]
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_idle_faq_tap_replies_with_faq_text(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_faq"))

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "Hours" in kwargs["text"]
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_date_and_time_menus_capped_to_whatsapp_list_limit(hospital_id):
    """Live-found bug: a doctor whose working hours/slot duration generate
    more than Meta's 10-row WhatsApp list limit (e.g. a wide shift with a
    short slot duration -- easily 100+ slots over the 14-day window) used to
    make send_list() silently fail end to end (Meta rejects the >10-row
    request, core/whatsapp.py logs and swallows it) -- the patient saw
    nothing at all after tapping the doctor. core/booking_flow.py's
    _cap_rows() now caps every send_list() call site to the soonest
    _MAX_LIST_ROWS rows instead of sending the full (potentially huge) list --
    Section 12.12 split this doctor's overflow into TWO caps to verify: the
    date list (this doctor works every weekday across the 14-day window, so
    easily >10 distinct dates) and, independently, the time list for any
    single one of those dates (8 hours at a 10-minute slot duration is 48
    times in one day alone)."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    department = db.get_departments(hospital_id)[0]
    doctor = db.create_doctor(
        hospital_id, department["id"], "Dr. Overbooked",
        # All 7 days, not just weekdays: _SLOT_DAYS_AHEAD's 14-day window is
        # EXACTLY 10 weekdays (two full weeks), which wouldn't exceed the cap
        # being tested here at all -- every day of the week guarantees >10
        # distinct dates.
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-17:00"],
        slot_duration_minutes=10,
    )
    all_slots = db.get_slots(hospital_id, doctor["id"])
    distinct_dates = []
    for s in all_slots:
        if s["date"] not in distinct_dates:
            distinct_dates.append(s["date"])
    assert len(distinct_dates) > _MAX_LIST_ROWS  # sanity check the date-cap precondition
    first_date_slots = [s for s in all_slots if s["date"] == distinct_dates[0]]
    assert len(first_date_slots) > _MAX_LIST_ROWS  # sanity check the time-cap precondition

    sessions.set(hospital_id, PHONE, "AWAITING_DOCTOR", {"department_id": department["id"], "department_name": department["name"]})
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor["id"]))

    # Date list: capped to the soonest 10 distinct dates.
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    date_rows = kwargs["sections"][0]["rows"]
    assert len(date_rows) == _MAX_LIST_ROWS
    assert {r["id"] for r in date_rows} == set(distinct_dates[:_MAX_LIST_ROWS])

    # Time list for the soonest date: independently capped to 10.
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(distinct_dates[0]))
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    time_rows = kwargs["sections"][0]["rows"]
    assert len(time_rows) == _MAX_LIST_ROWS
    assert {r["id"] for r in time_rows} == {s["id"] for s in first_date_slots[:_MAX_LIST_ROWS]}


@pytest.mark.asyncio
async def test_reset_keyword_escapes_a_stuck_mid_flow_state(hospital_id):
    """A patient stuck mid-flow (e.g. from the list-limit bug above, or just
    confusion) must be able to type a common greeting/reset word and get back
    to the main menu immediately -- not stay stuck re-prompted with "please
    choose from the list" until the 30-minute session timeout."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_DATE", {
        "department_id": "cardiology", "department_name": "Cardiology",
        "doctor_id": "doc_card_1", "doctor_name": "Dr. Anjali Rao",
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Hi"), hospital_name="City Hospital")

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert "City Hospital" in kwargs["body_text"]
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert row_ids == {"menu_book", "menu_reschedule", "menu_cancel", "menu_faq"}
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_non_reset_text_mid_flow_still_reprompts_the_same_state(hospital_id):
    """Only the recognized reset keywords escape a mid-flow state -- ordinary
    free text (not a valid list tap) still gets the existing "please choose
    from the list" re-prompt, unchanged."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_DATE", {
        "department_id": "cardiology", "department_name": "Cardiology",
        "doctor_id": "doc_card_1", "doctor_name": "Dr. Anjali Rao",
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("whatever"))

    assert wa.sent[0] == ("text", {"to": PHONE, "text": "Please choose an option from the list above"})
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DATE"


@pytest.mark.asyncio
async def test_full_happy_path_through_confirmation(hospital_id):
    """Section 12.12's exact reference-screenshot sequence: department ->
    doctor (inline "You have selected Dr. X" + date list) -> date -> time ->
    patient name (first-time patient, no age step) -> structured confirmation
    card -> success message with a generated reference_id."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    # Main menu -> Book
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"

    # Pick a department
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DOCTOR"
    assert session["context"]["department_id"] == "cardiology"
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]

    # Pick a doctor -> inline confirmation line + date list
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DATE"
    assert session["context"]["doctor_id"] == doctor_id
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert kwargs["body_text"].startswith("You have selected Dr. ")
    assert "consulting date" in kwargs["body_text"]
    all_slots = db.get_slots(hospital_id, doctor_id)
    date_str = all_slots[0]["date"]

    # Pick a date -> time list
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_TIME_SLOT"
    assert session["context"]["date"] == date_str
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert kwargs["body_text"] == "Please select a preferred consulting time slot:"

    # Pick a time -- a first-time patient (no name on file) is asked for a
    # name before confirmation (no age step, Section 12.12).
    slot = [s for s in all_slots if s["date"] == date_str][0]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_PATIENT_NAME"
    assert session["context"]["slot_id"] == slot["id"]
    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "full name" in kwargs["text"].lower()

    # Give a name -> structured confirmation card
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Ravi Kumar"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_CONFIRMATION"
    assert session["context"]["patient_name"] == "Ravi Kumar"
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"confirm", "cancel"}
    assert "*Confirm Booking Details:*" in kwargs["body_text"]
    assert "🏥 *Dept:* Cardiology" in kwargs["body_text"]
    assert "👤 *Patient:* Ravi Kumar" in kwargs["body_text"]

    # Confirm -> booked, resets to IDLE, structured success message with a
    # generated reference_id.
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))
    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "booked successfully" in kwargs["text"].lower()
    assert "Reference ID: *apt_" in kwargs["text"]
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}

    # And it should have written an appointment record (db/repository.py)
    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    assert len(due) == 1
    appt = due[0]
    assert appt.phone == PHONE
    assert appt.department_id == "cardiology"
    assert appt.doctor_id == doctor_id
    assert appt.scheduled_at.isoformat() == f"{slot['date']}T{slot['time']}:00"
    assert appt.reference_id is not None and appt.reference_id.startswith("apt_")
    assert f"Reference ID: *{appt.reference_id}*" in kwargs["text"]

    # ...and saved the patient's name (Section 12.11's other half; age is no
    # longer collected via WhatsApp as of Section 12.12).
    patient = db.get_patient_by_phone(hospital_id, PHONE)
    assert patient["name"] == "Ravi Kumar"


@pytest.mark.asyncio
async def test_returning_patient_with_name_on_file_skips_straight_to_confirmation(hospital_id):
    """A patient who's already booked once (name on file) is never re-asked
    on a later booking -- their existing name is still shown on the
    confirmation card, even though they weren't asked for it this time."""
    import db.connection as db_connection
    from db.repository import _upsert_patient
    _upsert_patient(db_connection.get_connection(), hospital_id, PHONE, "Priya Shah", 29)
    db_connection.get_connection().commit()

    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    department = db.get_departments(hospital_id)[0]
    doctor_id = db.get_doctors(hospital_id, department["id"])[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    sessions.set(hospital_id, PHONE, "AWAITING_TIME_SLOT", {
        "department_id": department["id"], "department_name": department["name"],
        "doctor_id": doctor_id, "doctor_name": "Dr. X",
        "date": slot["date"], "date_label": "Sat, Aug 8",
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]))

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_CONFIRMATION"  # not AWAITING_PATIENT_NAME
    assert session["context"]["patient_name"] == "Priya Shah"
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "👤 *Patient:* Priya Shah" in kwargs["body_text"]


@pytest.mark.asyncio
async def test_patient_name_free_text_validation(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_PATIENT_NAME", {"slot_id": "x"})

    # Empty/whitespace-only text re-prompts instead of accepting a blank name.
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("   "))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_NAME"
    assert "valid name" in wa.sent[0][1]["text"].lower()

    # A valid name proceeds straight to confirmation -- no age step
    # (Section 12.12 dropped the separate AWAITING_PATIENT_AGE state).
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Asha Rao"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_CONFIRMATION"
    assert session["context"]["patient_name"] == "Asha Rao"


@pytest.mark.asyncio
async def test_confirmation_cancel_resets_to_idle(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_CONFIRMATION", {
        "department_name": "Cardiology", "doctor_name": "Dr. Anjali Rao", "slot_label": "Mon 01 Jan 10:00",
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cancel"))

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "cancelled" in kwargs["text"].lower()
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_free_text_in_awaiting_department_reprompts_same_state(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_DEPARTMENT", {})

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Cardiology please"))

    assert wa.sent[0] == ("text", {"to": PHONE, "text": "Please choose an option from the list above"})
    assert wa.sent[1][0] == "list"
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"


@pytest.mark.asyncio
async def test_unrecognized_tap_id_in_awaiting_doctor_reprompts_same_state(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_DOCTOR", {"department_id": "cardiology", "department_name": "Cardiology"})

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("not_a_real_doctor_id"))

    assert wa.sent[0] == ("text", {"to": PHONE, "text": "Please choose an option from the list above"})
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DOCTOR"
    assert session["context"]["department_id"] == "cardiology"


@pytest.mark.asyncio
async def test_expired_session_resets_to_idle_instead_of_resuming(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore(timeout_seconds=0)
    sessions.set(hospital_id, PHONE, "AWAITING_DATE", {"doctor_id": "doc_card_1", "doctor_name": "Dr. Anjali Rao"})
    import time
    time.sleep(0.01)  # ensure the 0-second timeout has definitely elapsed

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("some_slot_id"), hospital_name="City Hospital")

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert "City Hospital" in kwargs["body_text"]  # got the main menu, not a slot reprompt
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_awaiting_doctor_with_missing_department_context_falls_back_to_main_menu(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_DOCTOR", {})  # corrupted/incomplete context

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("anything"))

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


# --- Cancel flow ---

@pytest.mark.asyncio
async def test_cancel_flow_one_appointment_happy_path(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    appt = _seed_appointment(hospital_id)

    # Main menu -> Cancel: shows the one appointment
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_cancel"))
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == {f"appt_{appt.id}"}
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_CANCEL_SELECTION"

    # Pick it -> confirm buttons
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"appt_{appt.id}"))
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"confirm", "cancel"}
    assert "Dr. Anjali Rao" in kwargs["body_text"]
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_CANCEL_CONFIRM"
    assert session["context"]["appointment_id"] == appt.id

    # Confirm -> cancelled, resets to IDLE
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))
    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "cancelled" in kwargs["text"].lower()
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}
    assert db.get_appointment(hospital_id, appt.id).status == db.STATUS_CANCELLED


@pytest.mark.asyncio
async def test_cancel_flow_multiple_appointments_cancels_only_the_selected_one(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    first = _seed_appointment(hospital_id, hours_from_now=5, doctor_id="doc_card_1")
    second = _seed_appointment(hospital_id, hours_from_now=10, doctor_id="doc_card_2")

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_cancel"))
    kind, kwargs = wa.sent[-1]
    assert _row_ids(kwargs) == {f"appt_{first.id}", f"appt_{second.id}"}

    # Pick the second one specifically
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"appt_{second.id}"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))

    assert db.get_appointment(hospital_id, second.id).status == db.STATUS_CANCELLED
    assert db.get_appointment(hospital_id, first.id).status == db.STATUS_BOOKED  # untouched


@pytest.mark.asyncio
async def test_cancel_flow_excludes_past_and_already_cancelled_appointments(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    _seed_appointment(hospital_id, hours_from_now=-5)  # past
    already_cancelled = _seed_appointment(hospital_id, hours_from_now=3, doctor_id="doc_card_2")
    db.cancel_appointment(hospital_id, already_cancelled.id)
    valid = _seed_appointment(hospital_id, hours_from_now=8, department_id="orthopedics", doctor_id="doc_ortho_1")

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_cancel"))

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == {f"appt_{valid.id}"}


@pytest.mark.asyncio
async def test_cancel_confirm_decline_leaves_appointment_booked(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    appt = _seed_appointment(hospital_id)
    sessions.set(hospital_id, PHONE, "AWAITING_CANCEL_CONFIRM", {"appointment_id": appt.id})

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cancel"))

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "not cancelled" in kwargs["text"].lower()
    assert db.get_appointment(hospital_id, appt.id).status == db.STATUS_BOOKED
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_cancel_selection_free_text_reprompts_same_state(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    appt = _seed_appointment(hospital_id)
    sessions.set(hospital_id, PHONE, "AWAITING_CANCEL_SELECTION", {})

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("the first one"))

    assert wa.sent[0] == ("text", {"to": PHONE, "text": "Please choose an option from the list above"})
    assert wa.sent[1][0] == "list"
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_CANCEL_SELECTION"
    assert db.get_appointment(hospital_id, appt.id).status == db.STATUS_BOOKED


# --- Reschedule flow ---

@pytest.mark.asyncio
async def test_reschedule_flow_happy_path_skips_department_and_doctor(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    appt = _seed_appointment(hospital_id)

    # Main menu -> Reschedule: shows the one appointment
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reschedule"))
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == {f"appt_{appt.id}"}
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_RESCHEDULE_SELECTION"

    # Pick it -> goes straight to slot menu (no department/doctor re-pick)
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"appt_{appt.id}"))
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    # Capped to Meta's 10-row WhatsApp list limit (core/booking_flow.py's
    # _cap_rows()) -- the soonest 10 of this doctor's available slots, not
    # necessarily all of them.
    slot_ids = _row_ids(kwargs)
    all_slot_ids = [s["id"] for s in db.get_slots(hospital_id, appt.doctor_id)]
    assert slot_ids == set(all_slot_ids[:10])
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_RESCHEDULE_SLOT"
    assert session["context"]["doctor_id"] == appt.doctor_id
    assert session["context"]["reschedule_appointment_id"] == appt.id

    # Pick a new slot -> confirm buttons
    new_slot_id = db.get_slots(hospital_id, appt.doctor_id)[1]["id"]  # a different slot than any default
    new_slot = db.find_slot(hospital_id, appt.doctor_id, new_slot_id)
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(new_slot_id))
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"confirm", "cancel"}
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_RESCHEDULE_CONFIRM"

    # Confirm -> old appointment rescheduled, new one created, resets to IDLE
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))
    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "rescheduled" in kwargs["text"].lower()
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}

    assert db.get_appointment(hospital_id, appt.id).status == db.STATUS_RESCHEDULED
    upcoming = db.get_upcoming_appointments_for_phone(hospital_id, PHONE)
    assert len(upcoming) == 1
    new_appt = upcoming[0]
    assert new_appt.id != appt.id
    assert new_appt.doctor_id == appt.doctor_id
    assert new_appt.department_id == appt.department_id
    assert new_appt.scheduled_at.isoformat() == f"{new_slot['date']}T{new_slot['time']}:00"


@pytest.mark.asyncio
async def test_reschedule_confirm_decline_leaves_appointment_untouched(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    appt = _seed_appointment(hospital_id)
    slot = db.get_slots(hospital_id, appt.doctor_id)[0]
    sessions.set(hospital_id, PHONE, "AWAITING_RESCHEDULE_CONFIRM", {
        "reschedule_appointment_id": appt.id,
        "department_id": appt.department_id,
        "department_name": appt.department_name,
        "doctor_id": appt.doctor_id,
        "doctor_name": appt.doctor_name,
        "slot_id": slot["id"],
        "slot_label": slot["label"],
        "slot_date": slot["date"],
        "slot_time": slot["time"],
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cancel"))

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "not rescheduled" in kwargs["text"].lower()
    assert db.get_appointment(hospital_id, appt.id).status == db.STATUS_BOOKED
    assert db.get_upcoming_appointments_for_phone(hospital_id, PHONE) == [db.get_appointment(hospital_id, appt.id)]
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_reschedule_flow_excludes_past_and_cancelled_appointments(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    _seed_appointment(hospital_id, hours_from_now=-2)  # past
    already_cancelled = _seed_appointment(hospital_id, hours_from_now=4, doctor_id="doc_card_2")
    db.cancel_appointment(hospital_id, already_cancelled.id)
    valid = _seed_appointment(hospital_id, hours_from_now=6, department_id="orthopedics", doctor_id="doc_ortho_1")

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reschedule"))

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == {f"appt_{valid.id}"}

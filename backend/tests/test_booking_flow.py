from datetime import datetime, timedelta

import pytest

import db.repository as db
from flows.booking import (
    BACK_ID, GOTO_MAIN_MENU, MANAGE_CANCEL_PREFIX, MANAGE_RESCHEDULE_PREFIX, _MAX_LIST_ROWS, handle_incoming,
)
from core.session_store import InMemorySessionStore


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


def _last_list(wa):
    """UX follow-up (Spec.md Section 0): "Back" moved out of the list itself
    into its own follow-up buttons message sent right after -- so the most
    recently sent message for a Back-eligible menu is now that buttons
    message, not the list. This finds the list itself regardless of a
    trailing Back-button message."""
    for kind, kwargs in reversed(wa.sent):
        if kind == "list":
            return kwargs
    raise AssertionError("no list message was sent")


@pytest.mark.asyncio
async def test_idle_any_message_sends_welcome_and_main_menu(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), hospital_name="City Hospital")

    assert len(wa.sent) == 1
    kind, kwargs = wa.sent[0]
    assert kind == "list"
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert row_ids == {"menu_book", "menu_reschedule", "menu_cancel", "menu_faq"}
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_idle_book_tap_advances_to_awaiting_patient_name(hospital_id):
    """Patient identity/UX follow-up (Spec.md Section 0), confirmed with the
    user: a first-time patient (no name/age on file) is now asked for their
    name FIRST, before department selection."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))

    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_NAME"
    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "full name" in kwargs["text"].lower()

    # Name -> age -> appointment type -> NOW department selection.
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Ravi Kumar"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("34"))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_APPOINTMENT_TYPE"
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"
    kwargs = _last_list(wa)
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert row_ids == {d["id"] for d in db.get_departments(hospital_id)}
    # "Go back" navigation now sends its own follow-up buttons message,
    # separate from the list (Spec.md Section 0's UX follow-up).
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {BACK_ID}


@pytest.mark.asyncio
async def test_idle_reschedule_tap_with_no_appointments_replies_and_stays_idle(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reschedule"))

    # Item 9: the "nothing to reschedule" message is now followed by the
    # main menu, so the patient has a way forward.
    assert wa.sent[0] == ("text", {"to": PHONE, "text": "You don't have any upcoming appointments to reschedule."})
    assert wa.sent[1][0] == "list"
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_idle_cancel_tap_with_no_appointments_replies_and_stays_idle(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_cancel"))

    # Item 9: the "nothing to cancel" message is now followed by the main
    # menu, so the patient has a way forward.
    assert wa.sent[0] == ("text", {"to": PHONE, "text": "You don't have any upcoming appointments to cancel."})
    assert wa.sent[1][0] == "list"
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

    # Date list: capped to the soonest _MAX_LIST_ROWS distinct dates -- "Go
    # back" (Section 3.3 follow-up) no longer occupies a row of its own
    # (UX follow-up, Spec.md Section 0: it's now a separate follow-up
    # buttons message instead), so the list itself uses the full cap.
    date_kwargs = _last_list(wa)
    date_rows = date_kwargs["sections"][0]["rows"]
    assert len(date_rows) == _MAX_LIST_ROWS
    assert {r["id"] for r in date_rows} == set(distinct_dates[:_MAX_LIST_ROWS])
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {BACK_ID}

    # Time list for the soonest date: independently capped the same way.
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(distinct_dates[0]))
    time_kwargs = _last_list(wa)
    time_rows = time_kwargs["sections"][0]["rows"]
    assert len(time_rows) == _MAX_LIST_ROWS
    assert {r["id"] for r in time_rows} == {s["id"] for s in first_date_slots[:_MAX_LIST_ROWS]}
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {BACK_ID}


@pytest.mark.asyncio
async def test_select_date_menu_never_offers_a_stale_past_only_date(hospital_id):
    """get_slots() (db/repositories/slots.py) filters out already-past slots,
    but generate_slots_for_doctor() never deletes old rows once their date
    has passed -- a manually-seeded past-only date must not appear as a row
    in the Select Date list, since _send_date_menu derives its rows purely
    from get_available_slots()'s own output (no separate date query)."""
    import db.connection as db_connection

    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    department = db.get_departments(hospital_id)[0]
    doctor = db.create_doctor(
        hospital_id, department["id"], "Dr. Stale Date",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=60,
    )
    yesterday = (datetime.now() - timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    conn = db_connection.get_connection()
    conn.execute(
        "INSERT INTO doctor_slots (hospital_id, doctor_id, scheduled_at) VALUES (?, ?, ?)",
        (hospital_id, doctor["id"], yesterday.isoformat()),
    )
    conn.commit()

    sessions.set(hospital_id, PHONE, "AWAITING_DOCTOR", {"department_id": department["id"], "department_name": department["name"]})
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor["id"]))

    date_kwargs = _last_list(wa)
    date_rows = date_kwargs["sections"][0]["rows"]
    assert yesterday.date().isoformat() not in {r["id"] for r in date_rows}


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
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert row_ids == {"menu_book", "menu_reschedule", "menu_cancel", "menu_faq"}
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_cancel_free_text_is_a_recognized_reset_keyword(hospital_id):
    """Reset-keyword follow-up (Spec.md Section 0): "cancel" (free text) now
    escapes a stuck mid-flow state the same way "hi"/"menu" already did --
    it was reported missing and confirmed genuinely absent from
    RESET_KEYWORDS before this fix."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_DATE", {
        "department_id": "cardiology", "department_name": "Cardiology",
        "doctor_id": "doc_card_1", "doctor_name": "Dr. Anjali Rao",
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("cancel"), hospital_name="City Hospital")

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert row_ids == {"menu_book", "menu_reschedule", "menu_cancel", "menu_faq"}
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_cancel_button_at_confirmation_still_declines_not_resets_to_menu(hospital_id):
    """Composability check (Spec.md Section 0): the explicit button-based
    cancel at booking confirmation (CONFIRM_NO, interactive_reply id
    "cancel") is a DECLINE of this specific booking, not the free-text
    reset-keyword escape hatch -- is_reset_keyword() only ever matches
    reply["type"] == "text", so an interactive_reply tap can never collide
    with the "cancel" keyword just added to RESET_KEYWORDS."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    department = db.get_departments(hospital_id)[0]
    doctor_id = db.get_doctors(hospital_id, department["id"])[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    sessions.set(hospital_id, PHONE, "AWAITING_CONFIRMATION", {
        "department_id": department["id"], "department_name": department["name"],
        "doctor_id": doctor_id, "doctor_name": "Dr. X",
        "date_label": "Sat, Aug 8", "slot_date": slot["date"], "slot_time": slot["time"],
        "patient_name": "Ravi Kumar", "patient_age": 34,
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cancel"))

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "cancelled this booking" in kwargs["text"].lower()
    # Resets to IDLE (booking declined), same end state a free-text "cancel"
    # keyword would reach too -- but via the decline path, not the
    # reset-keyword short-circuit (which never even runs for an
    # interactive_reply).
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_non_reset_text_mid_flow_still_reprompts_the_same_state(hospital_id):
    """Only the recognized reset keywords escape a mid-flow state -- ordinary
    free text (not a valid list tap) re-prompts the same state. Item 8: this
    re-sends the actual real interactive menu directly, not a separate
    generic "please choose" text message first."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_DATE", {
        "department_id": "cardiology", "department_name": "Cardiology",
        "doctor_id": "doc_card_1", "doctor_name": "Dr. Anjali Rao",
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("whatever"))

    # The list itself, plus its own follow-up Back-button message (Spec.md
    # Section 0's UX follow-up).
    assert len(wa.sent) == 2
    assert wa.sent[0][0] == "list"
    assert "Dr. Anjali Rao" in wa.sent[0][1]["body_text"]
    assert wa.sent[1][0] == "buttons"
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DATE"


@pytest.mark.asyncio
async def test_free_text_in_awaiting_time_slot_resends_the_real_time_list(hospital_id):
    """Item 8's own example scenario: free text during AWAITING_TIME_SLOT
    must re-send the actual times-available list for that date, not a
    generic scolding text -- and item 8 also requires this NOT to break the
    reset-keyword escape hatch, checked in the second half of this test."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    date_str = db.get_slots(hospital_id, doctor_id)[0]["date"]
    sessions.set(hospital_id, PHONE, "AWAITING_TIME_SLOT", {
        "department_id": "cardiology", "department_name": "Cardiology",
        "doctor_id": doctor_id, "doctor_name": "Dr. Anjali Rao",
        "date": date_str, "date_label": "Sat, Aug 8",
    })

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("umm what times"))

    # The list itself, plus its own follow-up Back-button message.
    assert len(wa.sent) == 2
    assert wa.sent[0][0] == "list"
    assert wa.sent[1][0] == "buttons"
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_TIME_SLOT"

    # Reset keywords must still escape from here, unaffected by the above.
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("menu"), hospital_name="City Hospital")
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert row_ids == {"menu_book", "menu_reschedule", "menu_cancel", "menu_faq"}
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_full_happy_path_through_confirmation(hospital_id):
    """Patient identity/UX follow-up (Spec.md Section 0), confirmed with the
    user: name/age is now asked FIRST -- "Book Appointment" tap -> patient
    name -> patient age -> department -> doctor (inline "Dr. X selected ✅"
    + date list) -> date -> time -> structured confirmation card ->
    success message with a generated reference_id."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    # Main menu -> Book -- a first-time patient (no name/age on file) is
    # asked for a name before anything else now.
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_PATIENT_NAME"
    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "full name" in kwargs["text"].lower()

    # Give a name -> asked for age
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Ravi Kumar"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_PATIENT_AGE"
    assert session["context"]["patient_name"] == "Ravi Kumar"
    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "age" in kwargs["text"].lower()

    # Give an age -> NOW appointment type selection starts.
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("34"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_APPOINTMENT_TYPE"
    assert session["context"]["patient_name"] == "Ravi Kumar"
    assert session["context"]["patient_age"] == 34

    # Pick an appointment type -> department selection.
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DEPARTMENT"
    assert session["context"]["appointment_type_id"] == "new"

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
    kwargs = _last_list(wa)
    assert kwargs["body_text"].startswith("Dr. ")
    assert "selected" in kwargs["body_text"]
    assert "appointment date" in kwargs["body_text"]
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"  # the follow-up Back button (Spec.md Section 0)
    all_slots = db.get_slots(hospital_id, doctor_id)
    date_str = all_slots[0]["date"]

    # Pick a date -> time list
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_TIME_SLOT"
    assert session["context"]["date"] == date_str
    kwargs = _last_list(wa)
    assert kwargs["body_text"] == "Please select a preferred consulting time slot:"

    # Pick a time -- name/age were already collected up front, so this goes
    # straight to the structured confirmation card.
    slot = [s for s in all_slots if s["date"] == date_str][0]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_CONFIRMATION"
    assert session["context"]["slot_id"] == slot["id"]
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"confirm", "cancel", BACK_ID}
    assert "*Confirm Booking Details:*" in kwargs["body_text"]
    assert "🏥 Department: Cardiology" in kwargs["body_text"]
    assert "👤 Patient: Ravi Kumar" in kwargs["body_text"]
    assert "🎂 Age: 34" in kwargs["body_text"]
    assert "🆔 Patient Code:" in kwargs["body_text"]

    # Confirm -> booked, resets to IDLE, structured success message with a
    # generated reference_id. Item 3 (Spec.md Section 0): now sent as
    # buttons (Main Menu/Cancel/Reschedule quick actions), not plain text.
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "appointment confirmed" in kwargs["body_text"].lower()
    # Item 8 (Spec.md Section 0): reference_id format is now APT-<DDMMYY>-<NNN>.
    assert "Appointment ID: APT-" in kwargs["body_text"]
    button_ids = {b["id"] for b in kwargs["buttons"]}
    assert GOTO_MAIN_MENU in button_ids
    assert any(bid.startswith(MANAGE_CANCEL_PREFIX) for bid in button_ids)
    assert any(bid.startswith(MANAGE_RESCHEDULE_PREFIX) for bid in button_ids)
    assert sessions.get(hospital_id, PHONE) == {"state": "IDLE", "context": {}}

    # And it should have written an appointment record (db/repository.py)
    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    assert len(due) == 1
    appt = due[0]
    assert appt.phone == PHONE
    assert appt.department_id == "cardiology"
    assert appt.doctor_id == doctor_id
    assert appt.scheduled_at.isoformat() == f"{slot['date']}T{slot['time']}:00"
    assert appt.reference_id is not None and appt.reference_id.startswith("APT-")
    assert f"Appointment ID: {appt.reference_id}" in kwargs["body_text"]

    # ...and saved the patient's name/age (Section 12.11's other half).
    patient = db.get_patient_by_phone(hospital_id, PHONE)
    assert patient["name"] == "Ravi Kumar"
    assert patient["age"] == 34


@pytest.mark.asyncio
async def test_returning_patient_is_still_asked_name_and_age_every_time(hospital_id):
    """UX follow-up (Spec.md Section 0), per the user's own explicit request
    ("I want it to take name every time"): the earlier "skip a returning
    patient" behavior (Section 12.11's original design, still correct for
    this exact scenario one round ago) is now deliberately gone for THIS
    step -- even a patient with both a name AND an age already on file is
    asked again, every single booking."""
    import db.connection as db_connection
    from db.repository import _upsert_patient
    _upsert_patient(db_connection.get_connection(), hospital_id, PHONE, "Priya Shah", 29)
    db_connection.get_connection().commit()

    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_PATIENT_NAME"
    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "full name" in kwargs["text"].lower()


@pytest.mark.asyncio
async def test_patient_name_matching_a_reset_keyword_is_accepted_as_the_name(hospital_id):
    """Live-found bug: AWAITING_PATIENT_NAME/AWAITING_PATIENT_AGE are the two
    states in this whole flow that accept arbitrary free text as a real
    value, not a menu choice -- someone testing the bot (or, in principle, a
    real patient literally named "Hi") typing "hi" as the patient name used
    to trip the GLOBAL reset-keyword short-circuit before this state's own
    handler ever ran, silently bouncing them back to the main menu instead
    of accepting the name and proceeding to the next step."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    # Patient identity/UX follow-up (Spec.md Section 0): AWAITING_PATIENT_NAME
    # is now the very first interactive state (before department), so its
    # context is empty at this point in real usage -- no doctor/slot fields
    # to carry.
    sessions.set(hospital_id, PHONE, "AWAITING_PATIENT_NAME", {})

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"))

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_PATIENT_AGE"  # not bounced to IDLE
    assert session["context"]["patient_name"] == "hi"


@pytest.mark.asyncio
async def test_reset_keyword_shaped_age_input_fails_validation_instead_of_resetting(hospital_id):
    """Same protection, AWAITING_PATIENT_AGE side: "hi" isn't a valid age
    either way, but it must fail through the normal invalid-age re-prompt,
    not get intercepted as a reset keyword first."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_PATIENT_AGE", {"patient_name": "Test Patient"})

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"))

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_PATIENT_AGE"  # re-prompted, not reset to IDLE
    assert "valid age" in wa.sent[0][1]["text"].lower()


@pytest.mark.asyncio
async def test_patient_name_and_age_free_text_validation(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_PATIENT_NAME", {})

    # Empty/whitespace-only text re-prompts instead of accepting a blank name.
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("   "))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_NAME"
    assert "valid name" in wa.sent[0][1]["text"].lower()

    # A valid name proceeds to the age question.
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Asha Rao"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_PATIENT_AGE"
    assert session["context"]["patient_name"] == "Asha Rao"

    # Non-numeric and out-of-range ages both re-prompt with the specific error.
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("not a number"))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_AGE"
    assert "valid age" in wa.sent[-2][1]["text"].lower()

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("200"))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_AGE"

    # A valid age proceeds to appointment type selection (Spec.md Section 0's
    # reorder -- name/age now come before department, not confirmation; the
    # appointment type step, added later, comes right after).
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("41"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_APPOINTMENT_TYPE"
    assert session["context"]["patient_age"] == 41

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DEPARTMENT"


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
    """Item 8: re-sends the real department list directly -- no separate
    generic "please choose" text first."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_DEPARTMENT", {})

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Cardiology please"))

    assert len(wa.sent) == 2  # the list, plus its own follow-up Back button
    assert wa.sent[0][0] == "list"
    assert wa.sent[1][0] == "buttons"
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"


@pytest.mark.asyncio
async def test_unrecognized_tap_id_in_awaiting_doctor_reprompts_same_state(hospital_id):
    """Item 8: re-sends the real doctor list directly -- no separate generic
    "please choose" text first."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_DOCTOR", {"department_id": "cardiology", "department_name": "Cardiology"})

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("not_a_real_doctor_id"))

    assert len(wa.sent) == 2  # the list, plus its own follow-up Back button
    assert wa.sent[0][0] == "list"
    assert wa.sent[1][0] == "buttons"
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
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert row_ids == {"menu_book", "menu_reschedule", "menu_cancel", "menu_faq"}  # got the main menu, not a slot reprompt
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
    assert _row_ids(kwargs) == {f"appt_{appt.id}", "goto_main_menu"}
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
    kind, kwargs = wa.sent[-2]
    assert kind == "text"
    assert "cancelled" in kwargs["text"].lower()
    # A generic (not appointment-scoped) Main Menu/Cancel/Reschedule
    # follow-up menu is sent right after -- see _send_post_action_menu.
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"goto_main_menu", "menu_cancel", "menu_reschedule"}
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
    assert _row_ids(kwargs) == {f"appt_{first.id}", f"appt_{second.id}", "goto_main_menu"}

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
    assert _row_ids(kwargs) == {f"appt_{valid.id}", "goto_main_menu"}


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
    """Item 8: re-sends the real appointment-selection list directly -- no
    separate generic "please choose" text first."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    appt = _seed_appointment(hospital_id)
    sessions.set(hospital_id, PHONE, "AWAITING_CANCEL_SELECTION", {})

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("the first one"))

    assert len(wa.sent) == 1
    assert wa.sent[0][0] == "list"
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_CANCEL_SELECTION"
    assert db.get_appointment(hospital_id, appt.id).status == db.STATUS_BOOKED


# --- Reschedule flow ---

@pytest.mark.asyncio
async def test_reschedule_flow_happy_path_skips_department_and_doctor(hospital_id):
    """Item 3 (Spec.md Section 0): reschedule now goes through a genuine
    date-then-time picker, same as booking's own AWAITING_DATE ->
    AWAITING_TIME_SLOT split, instead of a single combined list capped to
    10 rows across the doctor's WHOLE availability window (which silently
    hid later dates for a doctor with many slots/day)."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    appt = _seed_appointment(hospital_id)

    # Main menu -> Reschedule: shows the one appointment
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reschedule"))
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == {f"appt_{appt.id}", "goto_main_menu"}
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_RESCHEDULE_SELECTION"

    # Pick it -> goes straight to a DATE list (no department/doctor re-pick)
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"appt_{appt.id}"))
    kwargs = _last_list(wa)
    all_slots = db.get_slots(hospital_id, appt.doctor_id)
    dates_seen = []
    for s in all_slots:
        if s["date"] not in dates_seen:
            dates_seen.append(s["date"])
    # A doctor generates up to 14 days ahead -- capped to Meta's 10-row list
    # limit (Back is its own follow-up buttons message now, Spec.md Section
    # 0's UX follow-up, so it no longer reserves a row here), so this can
    # legitimately be fewer distinct dates than the doctor actually has, but
    # every date shown is a REAL date, not an arbitrary slice of the
    # combined list.
    date_row_ids = _row_ids(kwargs)
    assert date_row_ids == set(dates_seen[:_MAX_LIST_ROWS])
    assert wa.sent[-1][0] == "buttons"  # the follow-up Back button
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_RESCHEDULE_DATE"
    assert session["context"]["doctor_id"] == appt.doctor_id
    assert session["context"]["reschedule_appointment_id"] == appt.id

    # Pick a date -> a TIME list scoped to just that date
    date_str = dates_seen[0]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str))
    kwargs = _last_list(wa)
    time_ids = _row_ids(kwargs)
    assert time_ids == {s["id"] for s in all_slots if s["date"] == date_str}
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_RESCHEDULE_SLOT"
    assert session["context"]["date"] == date_str

    # Pick a new slot (on the SAME date just picked, since the time list is
    # now scoped to it) -> confirm buttons
    same_date_slots = [s for s in all_slots if s["date"] == date_str]
    new_slot_id = same_date_slots[0]["id"]
    new_slot = db.find_slot(hospital_id, appt.doctor_id, new_slot_id)
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(new_slot_id))
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"confirm", "cancel"}
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_RESCHEDULE_CONFIRM"

    # Confirm -> old appointment rescheduled, new one created, resets to IDLE
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))
    kind, kwargs = wa.sent[-2]
    assert kind == "text"
    assert "rescheduled" in kwargs["text"].lower()
    # A generic (not appointment-scoped) Main Menu/Cancel/Reschedule
    # follow-up menu is sent right after -- see _send_post_action_menu.
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"goto_main_menu", "menu_cancel", "menu_reschedule"}
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
async def test_reschedule_can_reach_a_date_the_old_combined_list_would_have_hidden(hospital_id):
    """Item 3's actual reported bug, reproduced directly (Spec.md Section 0):
    doc_card_1 has 2 slots/day (db/seed.py's _DEFAULT_WORKING_HOURS) across
    14 days. The OLD combined _send_slot_menu capped at 10 rows TOTAL, so
    only the first 5 days' slots were ever reachable -- day 6 onward was
    completely hidden, with no way to pick them at all. The new date-first
    picker offers dates independently of how many times each one has, so a
    date the old list could never have shown (the 8th distinct date, index 7)
    is reachable and its own times are all correctly offered."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    appt = _seed_appointment(hospital_id)

    all_slots = db.get_slots(hospital_id, appt.doctor_id)
    dates_seen = []
    for s in all_slots:
        if s["date"] not in dates_seen:
            dates_seen.append(s["date"])
    assert len(dates_seen) >= 8  # otherwise this doctor's seed no longer proves the point
    far_date = dates_seen[7]

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reschedule"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"appt_{appt.id}"))
    kwargs = _last_list(wa)
    assert far_date in _row_ids(kwargs)  # reachable on the very first date page

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(far_date))
    kwargs = _last_list(wa)
    time_ids = _row_ids(kwargs)
    assert time_ids == {s["id"] for s in all_slots if s["date"] == far_date}
    assert sessions.get(hospital_id, PHONE)["context"]["date"] == far_date


@pytest.mark.asyncio
async def test_reschedule_back_from_time_list_returns_to_date_list(hospital_id):
    """The date/time menus reschedule now reuses (_send_date_menu/
    _send_time_menu) always send their own follow-up Back-button message
    (_send_back_button, Spec.md Section 0's UX follow-up) -- confirms it's
    wired up to something rather than silently no-oping, since reschedule
    doesn't use the booking flow's full history stack."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    appt = _seed_appointment(hospital_id)

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reschedule"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"appt_{appt.id}"))
    date_str = db.get_slots(hospital_id, appt.doctor_id)[0]["date"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_RESCHEDULE_SLOT"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    _last_list(wa)  # confirms a list was actually sent
    assert wa.sent[-1][0] == "buttons"  # the follow-up Back button
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_RESCHEDULE_DATE"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == {f"appt_{appt.id}", "goto_main_menu"}
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_RESCHEDULE_SELECTION"


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
    assert _row_ids(kwargs) == {f"appt_{valid.id}", "goto_main_menu"}


@pytest.mark.asyncio
async def test_new_consultation_blocks_rebooking_in_same_department(hospital_id):
    """Shared department-selection rule (base.existing_department_appointment,
    confirmed with the user): a patient with an existing ACTIVE (non-cancelled)
    appointment in a department cannot book that same department again until
    it's cancelled -- blocked immediately on department selection, before
    doctor/date/slot are ever asked, dropping straight to the main menu with
    Cancel/Reschedule for the CONFLICTING appointment (not a re-prompt of the
    department list)."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    existing = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, datetime.fromisoformat(f"{slot['date']}T{slot['time']}"),
        patient_id=patient["id"], appointment_type_id="new",
    )

    # Same patient (auto-selected, only one linked), same department -- blocked
    # immediately on department selection, before doctor/date/slot are ever asked.
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"))

    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "cardiology" in kwargs["body_text"].lower()
    assert existing.doctor_name.lower() in kwargs["body_text"].lower()
    button_ids = {b["id"] for b in kwargs["buttons"]}
    assert "goto_main_menu" in button_ids
    assert any(b.startswith("manage_cancel_") for b in button_ids)
    assert any(b.startswith("manage_reschedule_") for b in button_ids)
    # Dropped to the main menu, not left mid-flow.
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"
    # No second appointment was created.
    assert len(db.get_active_appointments_for_patient(hospital_id, patient["id"])) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("appointment_type_id", ["tele", "second_opinion", "daycare"])
async def test_other_full_flow_types_also_block_rebooking_in_same_department(hospital_id, appointment_type_id):
    """The department-selection conflict check (base.existing_department_
    appointment) isn't New-Consultation-only -- confirmed with the user it
    should cover every type that lets the patient pick a department
    themselves."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, datetime.fromisoformat(f"{slot['date']}T{slot['time']}"),
        patient_id=patient["id"], appointment_type_id="new",
    )

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(appointment_type_id))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"))

    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "cardiology" in kwargs["body_text"].lower()
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"
    assert len(db.get_active_appointments_for_patient(hospital_id, patient["id"])) == 1


@pytest.mark.asyncio
async def test_a_followup_appointment_also_blocks_a_new_pick_in_that_department(hospital_id):
    """An appointment booked as "followup" still counts as "already in that
    department" for the shared check -- get_active_appointments_for_patient()
    doesn't distinguish by appointment_type_id."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, datetime.fromisoformat(f"{slot['date']}T{slot['time']}"),
        patient_id=patient["id"], appointment_type_id="followup",
    )

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"))

    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "cardiology" in kwargs["body_text"].lower()
    assert len(db.get_active_appointments_for_patient(hospital_id, patient["id"])) == 1


@pytest.mark.asyncio
async def test_new_consultation_blocks_other_department_same_day(hospital_id):
    """Rule 2: a patient with an active booking on a given day cannot book a
    DIFFERENT department that same day."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    card_doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    card_slot = db.get_slots(hospital_id, card_doctor_id)[0]
    db.create_appointment(
        hospital_id, PHONE, "cardiology", card_doctor_id, datetime.fromisoformat(f"{card_slot['date']}T{card_slot['time']}"),
        patient_id=patient["id"], appointment_type_id="new",
    )
    ortho_doctor_id = db.get_doctors(hospital_id, "orthopedics")[0]["id"]
    ortho_slots = db.get_slots(hospital_id, ortho_doctor_id)
    same_day_slot = next((s for s in ortho_slots if s["date"] == card_slot["date"]), None)
    assert same_day_slot is not None, "test setup assumes both doctors share at least one working date"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("orthopedics"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(ortho_doctor_id))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(same_day_slot["date"]))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(same_day_slot["id"]))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "already have an appointment booked on this day" in kwargs["text"].lower()
    assert len(db.get_active_appointments_for_patient(hospital_id, patient["id"])) == 1


@pytest.mark.asyncio
async def test_new_consultation_allows_other_department_on_a_different_day(hospital_id):
    """Sanity check: the same patient CAN book a different department on a
    day they don't already have a booking -- rules 1/2 shouldn't over-block."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    card_doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    card_slot = db.get_slots(hospital_id, card_doctor_id)[0]
    db.create_appointment(
        hospital_id, PHONE, "cardiology", card_doctor_id, datetime.fromisoformat(f"{card_slot['date']}T{card_slot['time']}"),
        patient_id=patient["id"], appointment_type_id="new",
    )
    ortho_doctor_id = db.get_doctors(hospital_id, "orthopedics")[0]["id"]
    ortho_slots = db.get_slots(hospital_id, ortho_doctor_id)
    different_day_slot = next(s for s in ortho_slots if s["date"] != card_slot["date"])

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("orthopedics"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(ortho_doctor_id))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(different_day_slot["date"]))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(different_day_slot["id"]))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))

    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "appointment confirmed" in kwargs["body_text"].lower()
    assert len(db.get_active_appointments_for_patient(hospital_id, patient["id"])) == 2


@pytest.mark.asyncio
async def test_followup_with_no_previous_visit_sends_back_to_appointment_type(hospital_id):
    """docs/per-appointment-type-flow-plan.md Phase 2 Step 2: a patient with
    no attended appointment at all can't Follow-up -- told so, and sent back
    to appointment-type selection rather than left stuck."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    sessions.set(hospital_id, PHONE, "AWAITING_APPOINTMENT_TYPE", {"patient_name": "Ravi Kumar", "patient_age": 34})

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("followup"))

    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_APPOINTMENT_TYPE"
    # A single buttons message: the "no previous visit" text plus Back/Main
    # Menu -- both exit to the main menu, there's no earlier booking step.
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "no previous consultation found" in kwargs["body_text"].lower()
    assert "ravi kumar" in kwargs["body_text"].lower()
    button_ids = {b["id"] for b in kwargs["buttons"]}
    assert button_ids == {"nav_back", "goto_main_menu"}


@pytest.mark.asyncio
async def test_followup_confirm_screen_then_straight_to_date_selection(hospital_id):
    """The core Follow-up behavior: auto-selects the SAME doctor/department
    as the patient's last attended appointment, shows a confirm screen (with
    a Back button), then on confirm jumps straight to date selection -- no
    department/doctor prompt at all."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    past_appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.now() - timedelta(days=10), patient_id=patient["id"],
    )
    db.mark_attendance(hospital_id, past_appt.id, True)
    sessions.set(hospital_id, PHONE, "AWAITING_APPOINTMENT_TYPE", {"active_patient_id": patient["id"], "patient_name": "Ravi Kumar", "patient_age": 34})

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("followup"))

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_FOLLOWUP_CONFIRM"
    assert session["context"]["doctor_id"] == doctor_id
    assert session["context"]["department_id"] == "cardiology"
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"confirm", BACK_ID}

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DATE"
    assert session["context"]["doctor_id"] == doctor_id
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"  # the date list's own follow-up Back button


@pytest.mark.asyncio
async def test_followup_back_from_date_returns_to_followup_confirm_screen(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    past_appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.now() - timedelta(days=10), patient_id=patient["id"],
    )
    db.mark_attendance(hospital_id, past_appt.id, True)
    sessions.set(hospital_id, PHONE, "AWAITING_APPOINTMENT_TYPE", {"active_patient_id": patient["id"], "patient_name": "Ravi Kumar", "patient_age": 34})
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("followup"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DATE"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_FOLLOWUP_CONFIRM"
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"confirm", BACK_ID}

    # And Back from THERE returns to appointment-type selection.
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_APPOINTMENT_TYPE"


@pytest.mark.asyncio
async def test_diagnostic_appointment_type_skips_department_and_doctor_selection(hospital_id):
    """docs/per-appointment-type-flow-plan.md Phase 1: 'diagnostic' (and
    'lab') have requires_doctor_selection=False and no department/doctor step
    in their TypeFlow (flows/booking/types/diagnostic.py) -- picking this
    type should jump straight to date selection, with a department/doctor
    auto-resolved behind the scenes (_first_available_resource) rather than
    asked for."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_APPOINTMENT_TYPE", {"patient_name": "Ravi Kumar", "patient_age": 34})

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("diagnostic"))

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DATE"
    assert session["context"]["appointment_type_id"] == "diagnostic"
    assert session["context"]["department_id"]
    assert session["context"]["doctor_id"]
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"  # the date list's own follow-up Back button


@pytest.mark.asyncio
async def test_diagnostic_back_from_date_returns_to_appointment_type_selection(hospital_id):
    """No STATE_AWAITING_DEPARTMENT/DOCTOR history frame is ever pushed for a
    type with no department/doctor step, so a Back tap from the date list
    should land straight back on appointment-type selection, not doctor."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_APPOINTMENT_TYPE", {"patient_name": "Ravi Kumar", "patient_age": 34})
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("diagnostic"))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DATE"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_APPOINTMENT_TYPE"
    kwargs = _last_list(wa)
    assert "appointment type" in kwargs["body_text"].lower() or "diagnostic" in {
        r["id"] for s in kwargs["sections"] for r in s["rows"]
    }


@pytest.mark.asyncio
async def test_diagnostic_change_selection_menu_omits_department_and_doctor(hospital_id):
    """Confirmation's "what would you like to change?" sub-menu should not
    offer Change Department/Change Doctor for a type whose flow never asked
    for either -- there'd be no history frame to jump back to."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_APPOINTMENT_TYPE", {"patient_name": "Ravi Kumar", "patient_age": 34})
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("diagnostic"))
    doctor_id = sessions.get(hospital_id, PHONE)["context"]["doctor_id"]
    all_slots = db.get_slots(hospital_id, doctor_id)
    date_str = all_slots[0]["date"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str))
    slot = [s for s in all_slots if s["date"] == date_str][0]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_CONFIRMATION"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))

    kwargs = _last_list(wa)
    row_ids = _row_ids(kwargs)
    assert "change_department" not in row_ids
    assert "change_doctor" not in row_ids
    assert "change_date" in row_ids
    assert "change_time" in row_ids


# --- docs/per-appointment-type-flow-plan.md Phase 2 Step 3: Tele-consultation
# video-link generation (TypeFlow.on_booking_confirmed) ---

async def _book_through_confirmation(wa, sessions, hospital_id, appointment_type_id):
    """Shared setup for the video-link regression tests below: drives a full
    booking up to (and past) the confirmation tap for the given type, using
    the same cardiology/doc_card_1 fixture data test_full_happy_path_through_
    confirmation itself uses. requires_consent types (tele, second_opinion)
    get their extra consent tap; every other type goes straight from
    "confirm" to the success message."""
    from db.repositories.appointment_types import DEFAULT_APPOINTMENT_TYPES

    sessions.set(hospital_id, PHONE, "AWAITING_APPOINTMENT_TYPE", {"patient_name": "Ravi Kumar", "patient_age": 34})
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(appointment_type_id))
    session = sessions.get(hospital_id, PHONE)

    if session["state"] == "AWAITING_DEPARTMENT":
        await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"))
        doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
        await handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id))
    doctor_id = sessions.get(hospital_id, PHONE)["context"]["doctor_id"]
    all_slots = db.get_slots(hospital_id, doctor_id)
    date_str = all_slots[0]["date"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str))
    slot = [s for s in all_slots if s["date"] == date_str][0]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]))
    if sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DAYCARE_DURATION":
        # Daycare Phase 2's one extra step: pick any duration option before
        # confirmation shows up.
        option = db.get_daycare_duration_options(hospital_id)[0]
        await handle_incoming(wa, sessions, PHONE, hospital_id, tap(str(option["id"])))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_CONFIRMATION"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))

    requires_consent = next(t for t in DEFAULT_APPOINTMENT_TYPES if t["id"] == appointment_type_id)["requires_consent"]
    if requires_consent:
        assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_CONSENT"
        await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))


@pytest.mark.asyncio
async def test_tele_consultation_booking_generates_and_stores_a_video_link(hospital_id):
    """Confirmed with the user directly, after real-world testing raised the
    question of when the doctor/patient actually get to use this link: the
    video link is generated and persisted right at booking time, but
    deliberately WITHHELD from this immediate confirmation -- a patient
    shouldn't be able to join (or casually forward) a "live" room hours or
    days before the actual slot. It's surfaced later instead, close to the
    appointment, via the reminder message (see test_reminders.py) -- and to
    the doctor any time via the staff portal (portal/routes/bookings.py's
    _appointment_json)."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await _book_through_confirmation(wa, sessions, hospital_id, "tele")

    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "appointment confirmed" in kwargs["body_text"].lower()
    assert "🎥" not in kwargs["body_text"]
    assert "meet.jit.si" not in kwargs["body_text"]

    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    appt = next(a for a in due if a.phone == PHONE)
    stored = db.get_appointment(hospital_id, appt.id)
    assert stored.video_link is not None
    assert stored.video_link.startswith("https://meet.jit.si/CareConnect-")


@pytest.mark.asyncio
async def test_tele_consultation_video_link_token_is_not_predictable(hospital_id):
    """Not a full cryptographic audit -- just confirms the token isn't
    sequential/derived from the appointment id or timestamp (which would be
    trivially guessable), by generating several bookings back to back and
    checking every token is unique and long enough to not be brute-forceable
    in any practical sense."""
    tokens = []
    for _ in range(5):
        wa = FakeWhatsAppClient()
        sessions = InMemorySessionStore()
        await _book_through_confirmation(wa, sessions, hospital_id, "tele")
        due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
        appt = next(a for a in due if a.phone == PHONE and a.video_link)
        token = appt.video_link.removeprefix("https://meet.jit.si/CareConnect-")
        tokens.append(token)
        db.cancel_appointment(hospital_id, appt.id)  # keep get_upcoming_appointments' set small

    assert len(set(tokens)) == len(tokens)  # every token unique
    for token in tokens:
        assert len(token) >= 32  # secrets.token_urlsafe(24) -> 32 chars
        assert not token.isdigit()  # not a bare counter/timestamp


@pytest.mark.asyncio
@pytest.mark.parametrize("appointment_type_id", ["new", "followup", "second_opinion", "diagnostic", "lab", "daycare"])
async def test_non_tele_types_get_no_video_link_in_their_confirmation(hospital_id, appointment_type_id):
    """The one thing that must not regress (docs/per-appointment-type-flow-plan.md's
    own discipline): every OTHER type's confirmation notification is exactly
    what it was before tele's on_booking_confirmed hook existed -- no video
    link field, no stray blank line, nothing conditional on this hook at all
    (their TypeFlow.on_booking_confirmed is still None)."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    if appointment_type_id == "followup":
        # Follow-up has no department/doctor step of its own -- it needs a
        # prior ATTENDED appointment to auto-select from (see this file's
        # own test_followup_confirm_screen_then_straight_to_date_selection).
        patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
        doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
        past_appt = db.create_appointment(
            hospital_id, PHONE, "cardiology", doctor_id, datetime.now() - timedelta(days=10), patient_id=patient["id"],
        )
        db.mark_attendance(hospital_id, past_appt.id, True)
        sessions.set(hospital_id, PHONE, "AWAITING_APPOINTMENT_TYPE", {"active_patient_id": patient["id"], "patient_name": "Ravi Kumar", "patient_age": 34})
        await handle_incoming(wa, sessions, PHONE, hospital_id, tap("followup"))
        await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))  # followup's own "use this doctor?" confirm
        doctor_id = sessions.get(hospital_id, PHONE)["context"]["doctor_id"]
        all_slots = db.get_slots(hospital_id, doctor_id)
        date_str = all_slots[0]["date"]
        await handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str))
        slot = [s for s in all_slots if s["date"] == date_str][0]
        await handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]))
        await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))
    else:
        await _book_through_confirmation(wa, sessions, hospital_id, appointment_type_id)

    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "appointment confirmed" in kwargs["body_text"].lower()
    assert "🎥" not in kwargs["body_text"]
    assert "meet.jit.si" not in kwargs["body_text"]
    assert "Video Consultation" not in kwargs["body_text"]

    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    appt = next(a for a in due if a.phone == PHONE)
    stored = db.get_appointment(hospital_id, appt.id)
    assert stored.video_link is None


@pytest.mark.asyncio
async def test_rescheduling_a_tele_consultation_generates_a_fresh_video_link(hospital_id):
    """Real-world testing gap (confirmed with the user directly):
    reschedule_booking() creates a genuinely NEW appointment row that
    inherits the OLD row's appointment_type_id, so a rescheduled
    tele-consultation stays type "tele" -- but the new row starts with
    video_link unset (create_appointment() never copies it forward, since
    the room is tied to a specific slot). flows/booking/reschedule.py's own
    confirm handler must regenerate one, same on_booking_confirmed hook
    book.py uses for a fresh booking, so the reminder sent for the NEW slot
    has a real link."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    original = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, datetime.now() + timedelta(hours=24),
        appointment_type_id="tele",
    )
    db.set_appointment_video_link(hospital_id, original.id, "https://meet.jit.si/CareConnect-original")
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reschedule"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"appt_{original.id}"))
    all_slots = db.get_slots(hospital_id, doctor_id)
    date_str = all_slots[0]["date"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str))
    slot = [s for s in all_slots if s["date"] == date_str][0]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_RESCHEDULE_CONFIRM"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))

    kind, kwargs = wa.sent[-2]
    assert kind == "text"
    assert "rescheduled" in kwargs["text"].lower()
    # Same "don't show it in the notification" rule as a fresh booking.
    assert "🎥" not in kwargs["text"]
    assert "meet.jit.si" not in kwargs["text"]

    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    new_appt = next(a for a in due if a.phone == PHONE and a.id != original.id)
    assert new_appt.appointment_type_id == "tele"
    assert new_appt.video_link is not None
    assert new_appt.video_link.startswith("https://meet.jit.si/CareConnect-")
    # A genuinely NEW link, not the old one carried forward unchanged.
    assert new_appt.video_link != "https://meet.jit.si/CareConnect-original"


@pytest.mark.asyncio
async def test_daycare_booking_asks_for_duration_and_stores_it(hospital_id):
    """Daycare Phase 2 (docs/per-appointment-type-flow-plan.md): the one
    extra step after time-slot selection -- picking how long the stay is
    from the hospital's configured options (db/repositories/
    daycare_duration_options.py's seeded defaults). Shown in the immediate
    confirmation too (unlike tele's video link, there's no "don't reveal
    early" concern here)."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    sessions.set(hospital_id, PHONE, "AWAITING_APPOINTMENT_TYPE", {"patient_name": "Ravi Kumar", "patient_age": 34})
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("daycare"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"))
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id))
    all_slots = db.get_slots(hospital_id, doctor_id)
    date_str = all_slots[0]["date"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str))
    slot = [s for s in all_slots if s["date"] == date_str][0]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DAYCARE_DURATION"

    option = db.get_daycare_duration_options(hospital_id)[0]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(str(option["id"])))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_CONFIRMATION"
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert option["label"] in kwargs["body_text"]

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))
    kind, kwargs = wa.sent[-1]
    assert "appointment confirmed" in kwargs["body_text"].lower()

    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    appt = next(a for a in due if a.phone == PHONE)
    stored = db.get_appointment(hospital_id, appt.id)
    assert stored.duration_hours == option["hours"]


@pytest.mark.asyncio
async def test_rescheduling_a_daycare_appointment_carries_the_same_duration_forward(hospital_id):
    """Unlike tele's video link (regenerated fresh per slot), daycare's
    duration isn't slot-specific and the reschedule flow never re-asks it --
    the new row must keep the ORIGINAL duration, not lose it (see
    connectors.tier1.Tier1Connector.reschedule_booking's own duration_hours
    carry-forward)."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    original = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, datetime.now() + timedelta(hours=24),
        appointment_type_id="daycare",
    )
    db.set_appointment_duration(hospital_id, original.id, 24)
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reschedule"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"appt_{original.id}"))
    all_slots = db.get_slots(hospital_id, doctor_id)
    date_str = all_slots[0]["date"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str))
    slot = [s for s in all_slots if s["date"] == date_str][0]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_RESCHEDULE_CONFIRM"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))

    due = db.get_upcoming_appointments(hospital_id, offset_hours=999999)
    new_appt = next(a for a in due if a.phone == PHONE and a.id != original.id)
    assert new_appt.appointment_type_id == "daycare"
    assert new_appt.duration_hours == 24

# tests/test_booking_back_navigation.py
"""
Section 3.3 follow-up: "Go back" navigation at each of the booking flow's 5
interactive states (department, doctor, date, time slot, confirmation).

Covers, per the task's own request:
  - Back from each state returns to the right prior state with the right
    data preserved (name/age never re-collected).
  - Back-then-forward-again produces a consistent, non-broken flow.
  - Back doesn't leak stale data into a fresh path forward (a different
    doctor picked after Back correctly re-queries that doctor's own slots).
  - Composability with the reset-keyword escape hatch and the
    free-text-resends-current-message behavior.
"""
import db.repository as db
from flows.booking import BACK_ID, CHANGE_DATE, CHANGE_DEPARTMENT, CHANGE_DOCTOR, CHANGE_TIME, handle_incoming
from core.session_store import InMemorySessionStore

PHONE = "5491112345678"


class FakeWhatsAppClient:
    def __init__(self):
        self.sent = []

    async def send_text(self, to, text):
        self.sent.append(("text", {"to": to, "text": text}))

    async def send_list(self, to, body_text, button_text, sections, header_text=None, footer_text=None):
        self.sent.append(("list", {"to": to, "body_text": body_text, "sections": sections}))

    async def send_buttons(self, to, body_text, buttons, header_text=None, footer_text=None):
        self.sent.append(("buttons", {"to": to, "body_text": body_text, "buttons": buttons}))


def tap(option_id):
    return {"type": "interactive_reply", "id": option_id, "title": ""}


def text_reply(text):
    return {"type": "text", "text": text}


def _row_ids(kwargs):
    return {row["id"] for section in kwargs["sections"] for row in section["rows"]}


def _last_list(wa):
    """UX follow-up (Spec.md Section 0): "Back" moved out of the list itself
    into its own follow-up buttons message sent right after -- this finds
    the list itself regardless of a trailing Back-button message."""
    for kind, kwargs in reversed(wa.sent):
        if kind == "list":
            return kwargs
    raise AssertionError("no list message was sent")


async def _start_booking(wa, sessions, hospital_id, name="Ravi Kumar", age="34"):
    """Patient identity/UX follow-up (Spec.md Section 0), confirmed with the
    user: name/age is now collected FIRST, right after "Book Appointment" is
    tapped -- before department selection. Drives through both, landing on
    AWAITING_DEPARTMENT."""
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply(name))
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply(age))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"


async def _book_to_time_slot(wa, sessions, hospital_id):
    """Drives a fresh session through name/age -> department -> doctor ->
    date, landing on AWAITING_TIME_SLOT. Returns (doctor_id, date_str)."""
    await _start_booking(wa, sessions, hospital_id)
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"))
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id))
    date_str = db.get_slots(hospital_id, doctor_id)[0]["date"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_TIME_SLOT"
    return doctor_id, date_str


async def _book_to_confirmation(wa, sessions, hospital_id):
    """Name/age were already collected up front by _book_to_time_slot ->
    picking a slot now goes straight to AWAITING_CONFIRMATION."""
    doctor_id, date_str = await _book_to_time_slot(wa, sessions, hospital_id)
    slot_id = [s for s in db.get_slots(hospital_id, doctor_id) if s["date"] == date_str][0]["id"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot_id))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_CONFIRMATION"
    return doctor_id, date_str, slot_id


async def test_back_from_doctor_returns_to_department_list(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await _start_booking(wa, sessions, hospital_id)
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DOCTOR"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DEPARTMENT"
    kwargs = _last_list(wa)
    assert _row_ids(kwargs) == {d["id"] for d in db.get_departments(hospital_id)}
    assert wa.sent[-1][0] == "buttons"  # the follow-up Back button


async def test_back_from_date_returns_to_doctor_list_same_department(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await _start_booking(wa, sessions, hospital_id)
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"))
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DATE"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DOCTOR"
    assert session["context"]["department_id"] == "cardiology"
    kwargs = _last_list(wa)
    assert _row_ids(kwargs) == {d["id"] for d in db.get_doctors(hospital_id, "cardiology")}
    assert wa.sent[-1][0] == "buttons"  # the follow-up Back button


async def test_back_from_time_slot_returns_to_date_list_same_doctor(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    doctor_id, date_str = await _book_to_time_slot(wa, sessions, hospital_id)

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DATE"
    assert session["context"]["doctor_id"] == doctor_id
    assert "date" not in session["context"]
    _last_list(wa)  # confirms a list was actually sent
    assert wa.sent[-1][0] == "buttons"  # the follow-up Back button


async def test_back_from_confirmation_offers_change_submenu(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await _book_to_confirmation(wa, sessions, hospital_id)

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_CHANGE_SELECTION"
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    row_ids = _row_ids(kwargs)
    assert row_ids == {CHANGE_DEPARTMENT, CHANGE_DOCTOR, CHANGE_DATE, CHANGE_TIME}


async def test_change_time_from_submenu_returns_to_time_list_preserving_name_age(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    doctor_id, date_str, _slot_id = await _book_to_confirmation(wa, sessions, hospital_id)

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(CHANGE_TIME))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_TIME_SLOT"
    assert session["context"]["doctor_id"] == doctor_id
    assert session["context"]["date"] == date_str
    # Back must never re-trigger name/age collection.
    assert session["context"]["patient_name"] == "Ravi Kumar"
    assert session["context"]["patient_age"] == 34


async def test_change_department_from_submenu_returns_to_department_list_preserving_name_age(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await _book_to_confirmation(wa, sessions, hospital_id)

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(CHANGE_DEPARTMENT))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DEPARTMENT"
    assert session["context"]["patient_name"] == "Ravi Kumar"
    assert session["context"]["patient_age"] == 34
    kwargs = _last_list(wa)
    assert _row_ids(kwargs) == {d["id"] for d in db.get_departments(hospital_id)}
    assert wa.sent[-1][0] == "buttons"  # the follow-up Back button


async def test_back_then_forward_again_is_consistent(hospital_id):
    """Back from date to doctor, then re-pick the SAME doctor again -> lands
    back on a working date list, not a broken/duplicated state."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await _start_booking(wa, sessions, hospital_id)
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"))
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id))

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DOCTOR"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DATE"
    assert session["context"]["doctor_id"] == doctor_id
    kwargs = _last_list(wa)
    date_str = db.get_slots(hospital_id, doctor_id)[0]["date"]
    assert date_str in _row_ids(kwargs)


async def test_back_does_not_leak_stale_slots_when_picking_a_different_doctor(hospital_id):
    """Back from time-slot to date, then back again to doctor, then pick a
    DIFFERENT doctor -> the resulting date list must be that new doctor's
    own availability, not a stale copy of the first doctor's dates."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    doctors = db.get_doctors(hospital_id, "cardiology")
    assert len(doctors) >= 1
    first_doctor_id = doctors[0]["id"]
    # A second doctor in the same department, so the comparison is
    # apples-to-apples (department unchanged, only the doctor differs).
    second_doctor = db.create_doctor(
        hospital_id, "cardiology", "Dr. Second Opinion",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
        working_hours=["09:00-17:00"],
        slot_duration_minutes=30,
    )
    second_doctor_id = second_doctor["id"]

    await _start_booking(wa, sessions, hospital_id)
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(first_doctor_id))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DATE"

    # Back to doctor list, then pick the DIFFERENT doctor.
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DOCTOR"
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(second_doctor_id))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DATE"
    assert session["context"]["doctor_id"] == second_doctor_id

    kwargs = _last_list(wa)
    expected_dates = {s["date"] for s in db.get_slots(hospital_id, second_doctor_id)}
    assert _row_ids(kwargs) <= expected_dates


async def test_back_at_department_with_no_history_falls_back_to_main_menu(hospital_id):
    """Back tapped at the very first interactive step (department) has
    nowhere earlier to return to -- falls back to the main menu instead of
    erroring or looping."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await _start_booking(wa, sessions, hospital_id)

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "IDLE"
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    row_ids = _row_ids(kwargs)
    assert row_ids == {"menu_book", "menu_reschedule", "menu_cancel", "menu_faq"}


async def test_reset_keyword_still_works_after_back_navigation(hospital_id):
    """Composability: the reset-keyword escape hatch (e.g. "menu"/"hi") must
    still short-circuit correctly even mid-way through a Back-modified
    session, not conflict with the history stack."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await _book_to_time_slot(wa, sessions, hospital_id)
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DATE"

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("menu"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "IDLE"
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == {"menu_book", "menu_reschedule", "menu_cancel", "menu_faq"}


async def test_free_text_resend_includes_back_option_after_back_navigation(hospital_id):
    """Composability with the free-text-resends-current-message behavior
    (prior round's item 8): an unrecognized tap/text at a Back-reachable
    state re-sends THAT state's own menu -- the Back option is now its own
    follow-up buttons message (Spec.md Section 0's UX follow-up), not a row
    inside the list, but it's still re-sent every time, not a separate
    generic scolding message."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await _book_to_time_slot(wa, sessions, hospital_id)
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DATE"

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("blah"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DATE"
    _last_list(wa)  # confirms a list was actually sent
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {BACK_ID}

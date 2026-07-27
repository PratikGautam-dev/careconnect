import pytest

import mock_data
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


@pytest.mark.asyncio
async def test_idle_any_message_sends_welcome_and_main_menu():
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, text_reply("hi"), hospital_name="City Hospital")

    assert len(wa.sent) == 1
    kind, kwargs = wa.sent[0]
    assert kind == "list"
    assert "City Hospital" in kwargs["body_text"]
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert row_ids == {"menu_book", "menu_reschedule", "menu_cancel", "menu_faq"}
    assert sessions.get(PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_idle_book_tap_advances_to_awaiting_department():
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, tap("menu_book"))

    assert sessions.get(PHONE)["state"] == "AWAITING_DEPARTMENT"
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert row_ids == {d["id"] for d in mock_data.get_departments()}


@pytest.mark.asyncio
async def test_idle_reschedule_tap_replies_coming_soon_and_stays_idle():
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, tap("menu_reschedule"))

    assert wa.sent == [("text", {"to": PHONE, "text": "This feature is coming soon."})]
    assert sessions.get(PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_idle_cancel_tap_replies_coming_soon_and_stays_idle():
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, tap("menu_cancel"))

    assert wa.sent == [("text", {"to": PHONE, "text": "This feature is coming soon."})]
    assert sessions.get(PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_idle_faq_tap_replies_with_faq_text():
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, tap("menu_faq"))

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "Hours" in kwargs["text"]
    assert sessions.get(PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_full_happy_path_through_confirmation():
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    # Main menu -> Book
    await handle_incoming(wa, sessions, PHONE, tap("menu_book"))
    assert sessions.get(PHONE)["state"] == "AWAITING_DEPARTMENT"

    # Pick a department
    await handle_incoming(wa, sessions, PHONE, tap("cardiology"))
    session = sessions.get(PHONE)
    assert session["state"] == "AWAITING_DOCTOR"
    assert session["context"]["department_id"] == "cardiology"
    doctor_id = mock_data.get_doctors("cardiology")[0]["id"]

    # Pick a doctor
    await handle_incoming(wa, sessions, PHONE, tap(doctor_id))
    session = sessions.get(PHONE)
    assert session["state"] == "AWAITING_SLOT"
    assert session["context"]["doctor_id"] == doctor_id
    slot_id = mock_data.get_slots(doctor_id)[0]["id"]

    # Pick a slot
    await handle_incoming(wa, sessions, PHONE, tap(slot_id))
    session = sessions.get(PHONE)
    assert session["state"] == "AWAITING_CONFIRMATION"
    assert session["context"]["slot_id"] == slot_id
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"confirm", "cancel"}

    # Confirm -> booked, resets to IDLE
    await handle_incoming(wa, sessions, PHONE, tap("confirm"))
    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "confirmed" in kwargs["text"].lower()
    assert sessions.get(PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_confirmation_cancel_resets_to_idle():
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(PHONE, "AWAITING_CONFIRMATION", {
        "department_name": "Cardiology", "doctor_name": "Dr. Anjali Rao", "slot_label": "Mon 01 Jan 10:00",
    })

    await handle_incoming(wa, sessions, PHONE, tap("cancel"))

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "cancelled" in kwargs["text"].lower()
    assert sessions.get(PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_free_text_in_awaiting_department_reprompts_same_state():
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(PHONE, "AWAITING_DEPARTMENT", {})

    await handle_incoming(wa, sessions, PHONE, text_reply("Cardiology please"))

    assert wa.sent[0] == ("text", {"to": PHONE, "text": "Please choose an option from the list above"})
    assert wa.sent[1][0] == "list"
    assert sessions.get(PHONE)["state"] == "AWAITING_DEPARTMENT"


@pytest.mark.asyncio
async def test_unrecognized_tap_id_in_awaiting_doctor_reprompts_same_state():
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(PHONE, "AWAITING_DOCTOR", {"department_id": "cardiology", "department_name": "Cardiology"})

    await handle_incoming(wa, sessions, PHONE, tap("not_a_real_doctor_id"))

    assert wa.sent[0] == ("text", {"to": PHONE, "text": "Please choose an option from the list above"})
    session = sessions.get(PHONE)
    assert session["state"] == "AWAITING_DOCTOR"
    assert session["context"]["department_id"] == "cardiology"


@pytest.mark.asyncio
async def test_expired_session_resets_to_idle_instead_of_resuming():
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore(timeout_seconds=0)
    sessions.set(PHONE, "AWAITING_SLOT", {"doctor_id": "doc_card_1", "doctor_name": "Dr. Anjali Rao"})
    import time
    time.sleep(0.01)  # ensure the 0-second timeout has definitely elapsed

    await handle_incoming(wa, sessions, PHONE, tap("some_slot_id"), hospital_name="City Hospital")

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert "City Hospital" in kwargs["body_text"]  # got the main menu, not a slot reprompt
    assert sessions.get(PHONE) == {"state": "IDLE", "context": {}}


@pytest.mark.asyncio
async def test_awaiting_doctor_with_missing_department_context_falls_back_to_main_menu():
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(PHONE, "AWAITING_DOCTOR", {})  # corrupted/incomplete context

    await handle_incoming(wa, sessions, PHONE, tap("anything"))

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert sessions.get(PHONE) == {"state": "IDLE", "context": {}}

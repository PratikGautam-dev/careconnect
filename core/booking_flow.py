# core/booking_flow.py
"""
Menu-based appointment booking state machine (SPEC Section 3.3).

No AI/LLM anywhere in this file. Every state sends a fixed WhatsApp interactive
list or button message with a closed set of options; a patient's reply is
either a tapped selection (interactive_reply) or free text/unsupported input,
which is treated as "didn't tap anything" and re-prompts the current menu.

Session (state + context) lives in whatever store core/history.get_session_store()
returns (Redis or in-memory) — this module takes it as a parameter so it stays a
plain function library with no platform-specific dependency (portability rule,
SPEC Section 6).
"""
import logging

import mock_data
from core.whatsapp import WhatsAppClient

logger = logging.getLogger(__name__)

STATE_IDLE = "IDLE"
STATE_AWAITING_DEPARTMENT = "AWAITING_DEPARTMENT"
STATE_AWAITING_DOCTOR = "AWAITING_DOCTOR"
STATE_AWAITING_SLOT = "AWAITING_SLOT"
STATE_AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
STATE_BOOKED = "BOOKED"  # momentary only — never persisted, see _handle_awaiting_confirmation

MAIN_MENU_BOOK = "menu_book"
MAIN_MENU_RESCHEDULE = "menu_reschedule"
MAIN_MENU_CANCEL = "menu_cancel"
MAIN_MENU_FAQ = "menu_faq"

CONFIRM_YES = "confirm"
CONFIRM_NO = "cancel"

_PLEASE_CHOOSE = "Please choose an option from the list above"

_FAQ_TEXT = (
    "Frequently Asked Questions:\n\n"
    "- Hours: Mon-Sat, 9:00 AM - 6:00 PM\n"
    "- To book, reschedule or cancel an appointment, just send us any message.\n"
    "- For emergencies, please call the hospital directly instead of messaging here.\n\n"
    "Send any message to return to the main menu."
)


# --- Outgoing menu builders ---

async def _send_main_menu(wa: WhatsAppClient, phone: str, hospital_name: str) -> None:
    rows = [
        {"id": MAIN_MENU_BOOK, "title": "Book Appointment"},
        {"id": MAIN_MENU_RESCHEDULE, "title": "Reschedule"},
        {"id": MAIN_MENU_CANCEL, "title": "Cancel"},
        {"id": MAIN_MENU_FAQ, "title": "FAQ"},
    ]
    await wa.send_list(
        to=phone,
        body_text=f"Welcome to {hospital_name}! How can we help you today?",
        button_text="Main Menu",
        sections=[{"title": "Main Menu", "rows": rows}],
    )


async def _send_department_menu(wa: WhatsAppClient, phone: str) -> None:
    rows = [{"id": d["id"], "title": d["name"]} for d in mock_data.get_departments()]
    await wa.send_list(
        to=phone,
        body_text="Please select a department:",
        button_text="View Departments",
        sections=[{"title": "Departments", "rows": rows}],
    )


async def _send_doctor_menu(wa: WhatsAppClient, phone: str, department_id: str, department_name: str) -> None:
    rows = [{"id": d["id"], "title": d["name"]} for d in mock_data.get_doctors(department_id)]
    await wa.send_list(
        to=phone,
        body_text=f"Please select a doctor in {department_name}:",
        button_text="View Doctors",
        sections=[{"title": department_name, "rows": rows}],
    )


async def _send_slot_menu(wa: WhatsAppClient, phone: str, doctor_id: str, doctor_name: str) -> None:
    rows = [{"id": s["id"], "title": s["label"]} for s in mock_data.get_slots(doctor_id)]
    await wa.send_list(
        to=phone,
        body_text=f"Please select a time slot with {doctor_name}:",
        button_text="View Slots",
        sections=[{"title": "Available Slots", "rows": rows}],
    )


async def _send_confirmation(wa: WhatsAppClient, phone: str, context: dict) -> None:
    summary = (
        "Please confirm your appointment:\n\n"
        f"Department: {context.get('department_name')}\n"
        f"Doctor: {context.get('doctor_name')}\n"
        f"Slot: {context.get('slot_label')}"
    )
    await wa.send_buttons(
        to=phone,
        body_text=summary,
        buttons=[
            {"id": CONFIRM_YES, "title": "Confirm"},
            {"id": CONFIRM_NO, "title": "Cancel"},
        ],
    )


# --- State handlers ---
# Each handler either advances the session to the next state (on a valid tap)
# or refreshes the session at the *same* state (on free text/unsupported input,
# which also resets the 30-min inactivity clock since the patient did respond).

async def _handle_idle(wa: WhatsAppClient, sessions, phone: str, reply: dict, hospital_name: str) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == MAIN_MENU_BOOK:
            sessions.set(phone, STATE_AWAITING_DEPARTMENT, {})
            await _send_department_menu(wa, phone)
            return
        if rid == MAIN_MENU_RESCHEDULE:
            sessions.reset(phone)
            await wa.send_text(phone, "This feature is coming soon.")
            return
        if rid == MAIN_MENU_CANCEL:
            sessions.reset(phone)
            await wa.send_text(phone, "This feature is coming soon.")
            return
        if rid == MAIN_MENU_FAQ:
            sessions.reset(phone)
            await wa.send_text(phone, _FAQ_TEXT)
            return
    # Any other message while IDLE (first contact, free text, stale/unknown id):
    # per spec, IDLE always responds with the welcome message + main menu.
    sessions.reset(phone)
    await _send_main_menu(wa, phone, hospital_name)


async def _handle_awaiting_department(wa: WhatsAppClient, sessions, phone: str, reply: dict, context: dict) -> None:
    if reply["type"] == "interactive_reply":
        dept = mock_data.find_department(reply["id"])
        if dept:
            new_context = {"department_id": dept["id"], "department_name": dept["name"]}
            sessions.set(phone, STATE_AWAITING_DOCTOR, new_context)
            await _send_doctor_menu(wa, phone, dept["id"], dept["name"])
            return
    sessions.set(phone, STATE_AWAITING_DEPARTMENT, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_department_menu(wa, phone)


async def _handle_awaiting_doctor(wa: WhatsAppClient, sessions, phone: str, reply: dict, context: dict) -> None:
    department_id = context.get("department_id")
    department_name = context.get("department_name", "")
    if not department_id:
        # Corrupted/incomplete session context — fail safe back to the main menu.
        sessions.reset(phone)
        await _send_main_menu(wa, phone, "the hospital")
        return

    if reply["type"] == "interactive_reply":
        doctor = mock_data.find_doctor(department_id, reply["id"])
        if doctor:
            new_context = {**context, "doctor_id": doctor["id"], "doctor_name": doctor["name"]}
            sessions.set(phone, STATE_AWAITING_SLOT, new_context)
            await _send_slot_menu(wa, phone, doctor["id"], doctor["name"])
            return
    sessions.set(phone, STATE_AWAITING_DOCTOR, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_doctor_menu(wa, phone, department_id, department_name)


async def _handle_awaiting_slot(wa: WhatsAppClient, sessions, phone: str, reply: dict, context: dict) -> None:
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    if not doctor_id:
        sessions.reset(phone)
        await _send_main_menu(wa, phone, "the hospital")
        return

    if reply["type"] == "interactive_reply":
        slot = mock_data.find_slot(doctor_id, reply["id"])
        if slot:
            new_context = {**context, "slot_id": slot["id"], "slot_label": slot["label"]}
            sessions.set(phone, STATE_AWAITING_CONFIRMATION, new_context)
            await _send_confirmation(wa, phone, new_context)
            return
    sessions.set(phone, STATE_AWAITING_SLOT, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_slot_menu(wa, phone, doctor_id, doctor_name)


async def _handle_awaiting_confirmation(wa: WhatsAppClient, sessions, phone: str, reply: dict, context: dict) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            summary = (
                "Your appointment is confirmed!\n\n"
                f"Department: {context.get('department_name')}\n"
                f"Doctor: {context.get('doctor_name')}\n"
                f"Slot: {context.get('slot_label')}\n\n"
                "We look forward to seeing you."
            )
            await wa.send_text(phone, summary)
            # STATE_BOOKED is terminal and resets to IDLE immediately — there's no
            # separate incoming message that moves it out of BOOKED, so it's never
            # actually written to the session store.
            sessions.reset(phone)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, "Okay, I've cancelled this booking. Send any message to start over.")
            sessions.reset(phone)
            return
    sessions.set(phone, STATE_AWAITING_CONFIRMATION, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_confirmation(wa, phone, context)


_HANDLERS = {
    STATE_AWAITING_DEPARTMENT: _handle_awaiting_department,
    STATE_AWAITING_DOCTOR: _handle_awaiting_doctor,
    STATE_AWAITING_SLOT: _handle_awaiting_slot,
    STATE_AWAITING_CONFIRMATION: _handle_awaiting_confirmation,
}


async def handle_incoming(
    wa: WhatsAppClient,
    sessions,
    phone: str,
    reply: dict,
    hospital_name: str = "the hospital",
) -> None:
    """
    Entry point: look up the patient's current session (sessions.get already
    resets stale/timed-out sessions to IDLE) and dispatch to the matching
    state handler.
    """
    session = sessions.get(phone)
    state = session["state"]
    context = session["context"]

    handler = _HANDLERS.get(state)
    if handler is None:
        # IDLE, or any unrecognized/stale state value -> treat as IDLE.
        await _handle_idle(wa, sessions, phone, reply, hospital_name)
        return

    await handler(wa, sessions, phone, reply, context)

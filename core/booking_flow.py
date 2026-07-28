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

Department/doctor/appointment data lives in db/repository.py (SPEC Section
12.6 Tier 1 — a real Postgres/Neon database, per Section 6). Every db call and every session store
call here is scoped by hospital_id (SPEC Section 12.2, Phase 9), resolved
per-message in core/main.py from the incoming webhook's phone_number_id —
not a single value fixed at startup, so this module never assumes there's
only one hospital.
"""
import logging
from datetime import datetime

import db.repository as db
from core.whatsapp import WhatsAppClient
from db.connection import IntegrityError

logger = logging.getLogger(__name__)

STATE_IDLE = "IDLE"
STATE_AWAITING_DEPARTMENT = "AWAITING_DEPARTMENT"
STATE_AWAITING_DOCTOR = "AWAITING_DOCTOR"
STATE_AWAITING_SLOT = "AWAITING_SLOT"
STATE_AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
STATE_BOOKED = "BOOKED"  # momentary only — never persisted, see _handle_awaiting_confirmation

# Cancel flow (SPEC Section 3.3/5)
STATE_AWAITING_CANCEL_SELECTION = "AWAITING_CANCEL_SELECTION"
STATE_AWAITING_CANCEL_CONFIRM = "AWAITING_CANCEL_CONFIRM"

# Reschedule flow (SPEC Section 3.3/5) — selection reuses the same
# "pick which appointment" pattern as cancel; slot/confirm reuse the booking
# flow's slot menu, scoped to the appointment's existing doctor.
STATE_AWAITING_RESCHEDULE_SELECTION = "AWAITING_RESCHEDULE_SELECTION"
STATE_AWAITING_RESCHEDULE_SLOT = "AWAITING_RESCHEDULE_SLOT"
STATE_AWAITING_RESCHEDULE_CONFIRM = "AWAITING_RESCHEDULE_CONFIRM"

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


async def _send_department_menu(wa: WhatsAppClient, phone: str, hospital_id: int) -> None:
    rows = [{"id": d["id"], "title": d["name"]} for d in db.get_departments(hospital_id)]
    await wa.send_list(
        to=phone,
        body_text="Please select a department:",
        button_text="View Departments",
        sections=[{"title": "Departments", "rows": rows}],
    )


async def _send_doctor_menu(wa: WhatsAppClient, phone: str, hospital_id: int, department_id: str, department_name: str) -> None:
    rows = [{"id": d["id"], "title": d["name"]} for d in db.get_doctors(hospital_id, department_id)]
    await wa.send_list(
        to=phone,
        body_text=f"Please select a doctor in {department_name}:",
        button_text="View Doctors",
        sections=[{"title": department_name, "rows": rows}],
    )


async def _send_slot_menu(wa: WhatsAppClient, phone: str, hospital_id: int, doctor_id: str, doctor_name: str) -> None:
    rows = [{"id": s["id"], "title": s["label"]} for s in db.get_slots(hospital_id, doctor_id)]
    await wa.send_list(
        to=phone,
        body_text=f"Please select a time slot with {doctor_name}:",
        button_text="View Slots",
        sections=[{"title": "Available Slots", "rows": rows}],
    )


async def _notify_no_doctors_available(wa: WhatsAppClient, sessions, hospital_id: int, phone: str, department_name: str) -> None:
    sessions.reset(hospital_id, phone)
    await wa.send_text(phone, f"Sorry, there are no doctors available in {department_name} right now. Please check back later.")


async def _notify_no_slots_available(wa: WhatsAppClient, sessions, hospital_id: int, phone: str, doctor_name: str) -> None:
    sessions.reset(hospital_id, phone)
    await wa.send_text(phone, f"Sorry, there are no available slots for {doctor_name} right now. Please check back later.")


async def _handle_slot_taken(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, target_state: str) -> None:
    """Shared recovery path for a double-booking race hit during booking OR
    reschedule confirmation (SPEC Phase 8): tell the patient, then either
    re-show the doctor's now-current slot list (freshly queried, so the just-
    taken slot is already gone) or, if that emptied the list out entirely,
    the same "no slots available" fallback used elsewhere."""
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    logger.info("Double-booking race: hospital=%s doctor=%s slot=%s already taken", hospital_id, doctor_id, context.get("slot_id"))
    if not db.get_slots(hospital_id, doctor_id):
        sessions.reset(hospital_id, phone)
        await wa.send_text(
            phone,
            f"Sorry, that slot was just taken and there are no other slots available "
            f"for {doctor_name} right now. Please check back later.",
        )
        return
    sessions.set(hospital_id, phone, target_state, context)
    await wa.send_text(phone, "Sorry, that slot was just taken. Please choose another time.")
    await _send_slot_menu(wa, phone, hospital_id, doctor_id, doctor_name)


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


def _appointment_row_id(appointment_id: int) -> str:
    return f"appt_{appointment_id}"


def _parse_appointment_row_id(row_id: str) -> int | None:
    if not row_id.startswith("appt_"):
        return None
    try:
        return int(row_id[len("appt_"):])
    except ValueError:
        return None


async def _send_appointment_selection_menu(wa: WhatsAppClient, phone: str, appointments: list, body_text: str) -> None:
    rows = [
        {
            "id": _appointment_row_id(a.id),
            "title": a.doctor_name,
            "description": a.scheduled_at.strftime("%a %d %b %Y, %H:%M"),
        }
        for a in appointments
    ]
    await wa.send_list(
        to=phone,
        body_text=body_text,
        button_text="View Appointments",
        sections=[{"title": "Your Appointments", "rows": rows}],
    )


async def _send_cancel_confirm(wa: WhatsAppClient, phone: str, appointment) -> None:
    when = appointment.scheduled_at.strftime("%A, %d %B at %H:%M")
    await wa.send_buttons(
        to=phone,
        body_text=f"Are you sure you want to cancel your appointment with {appointment.doctor_name} on {when}?",
        buttons=[
            {"id": CONFIRM_YES, "title": "Confirm"},
            {"id": CONFIRM_NO, "title": "Cancel"},
        ],
    )


async def _send_reschedule_confirm(wa: WhatsAppClient, phone: str, context: dict) -> None:
    summary = (
        "Please confirm your new appointment time:\n\n"
        f"Doctor: {context.get('doctor_name')}\n"
        f"New Slot: {context.get('slot_label')}"
    )
    await wa.send_buttons(
        to=phone,
        body_text=summary,
        buttons=[
            {"id": CONFIRM_YES, "title": "Confirm"},
            {"id": CONFIRM_NO, "title": "Cancel"},
        ],
    )


def _find_selected_appointment(hospital_id: int, phone: str, reply: dict):
    """Resolve a tapped appointment-selection row id to a live Appointment,
    re-validated against the database (not trusted from stale context) — same
    "re-check against the source of truth" pattern as db.find_slot. Scoped by
    hospital_id, so a row id guessed/replayed from a different hospital's
    conversation can never resolve here (SPEC Section 12.2)."""
    if reply["type"] != "interactive_reply":
        return None
    appt_id = _parse_appointment_row_id(reply["id"])
    if appt_id is None:
        return None
    appt = db.get_appointment(hospital_id, appt_id)
    if appt and appt.phone == phone and appt.status == db.STATUS_BOOKED and appt.scheduled_at > datetime.now():
        return appt
    return None


# --- State handlers ---
# Each handler either advances the session to the next state (on a valid tap)
# or refreshes the session at the *same* state (on free text/unsupported input,
# which also resets the 30-min inactivity clock since the patient did respond).

async def _handle_idle(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, hospital_name: str) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == MAIN_MENU_BOOK:
            sessions.set(hospital_id, phone, STATE_AWAITING_DEPARTMENT, {})
            await _send_department_menu(wa, phone, hospital_id)
            return
        if rid == MAIN_MENU_RESCHEDULE:
            await _start_reschedule_flow(wa, sessions, phone, hospital_id)
            return
        if rid == MAIN_MENU_CANCEL:
            await _start_cancel_flow(wa, sessions, phone, hospital_id)
            return
        if rid == MAIN_MENU_FAQ:
            sessions.reset(hospital_id, phone)
            await wa.send_text(phone, _FAQ_TEXT)
            return
    # Any other message while IDLE (first contact, free text, stale/unknown id):
    # per spec, IDLE always responds with the welcome message + main menu.
    sessions.reset(hospital_id, phone)
    await _send_main_menu(wa, phone, hospital_name)


async def _handle_awaiting_department(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict) -> None:
    if reply["type"] == "interactive_reply":
        dept = db.find_department(hospital_id, reply["id"])
        if dept:
            if not db.get_doctors(hospital_id, dept["id"]):
                await _notify_no_doctors_available(wa, sessions, hospital_id, phone, dept["name"])
                return
            new_context = {"department_id": dept["id"], "department_name": dept["name"]}
            sessions.set(hospital_id, phone, STATE_AWAITING_DOCTOR, new_context)
            await _send_doctor_menu(wa, phone, hospital_id, dept["id"], dept["name"])
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_DEPARTMENT, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_department_menu(wa, phone, hospital_id)


async def _handle_awaiting_doctor(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict) -> None:
    department_id = context.get("department_id")
    department_name = context.get("department_name", "")
    if not department_id:
        # Corrupted/incomplete session context — fail safe back to the main menu.
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital")
        return

    if reply["type"] == "interactive_reply":
        doctor = db.find_doctor(hospital_id, department_id, reply["id"])
        if doctor:
            if not db.get_slots(hospital_id, doctor["id"]):
                await _notify_no_slots_available(wa, sessions, hospital_id, phone, doctor["name"])
                return
            new_context = {**context, "doctor_id": doctor["id"], "doctor_name": doctor["name"]}
            sessions.set(hospital_id, phone, STATE_AWAITING_SLOT, new_context)
            await _send_slot_menu(wa, phone, hospital_id, doctor["id"], doctor["name"])
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_DOCTOR, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_doctor_menu(wa, phone, hospital_id, department_id, department_name)


async def _handle_awaiting_slot(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict) -> None:
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    if not doctor_id:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital")
        return

    if reply["type"] == "interactive_reply":
        slot = db.find_slot(hospital_id, doctor_id, reply["id"])
        if slot:
            new_context = {
                **context,
                "slot_id": slot["id"],
                "slot_label": slot["label"],
                "slot_date": slot["date"],
                "slot_time": slot["time"],
            }
            sessions.set(hospital_id, phone, STATE_AWAITING_CONFIRMATION, new_context)
            await _send_confirmation(wa, phone, new_context)
            return
    # Slots are dynamic (another patient's booking can take the last one between
    # this menu being sent and this reply) — recheck rather than blindly re-send.
    if not db.get_slots(hospital_id, doctor_id):
        await _notify_no_slots_available(wa, sessions, hospital_id, phone, doctor_name)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_SLOT, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_slot_menu(wa, phone, hospital_id, doctor_id, doctor_name)


async def _handle_awaiting_confirmation(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            try:
                db.create_appointment(
                    hospital_id=hospital_id,
                    phone=phone,
                    department_id=context.get("department_id"),
                    doctor_id=context.get("doctor_id"),
                    scheduled_at=datetime.fromisoformat(f"{context['slot_date']}T{context['slot_time']}"),
                )
            except IntegrityError:
                # Someone else booked this exact doctor+slot first (db/schema.sql's
                # partial unique index — the real double-booking guard, not this
                # try/except). Send the patient back to slot selection with a
                # freshly-queried list that no longer offers the taken slot.
                await _handle_slot_taken(wa, sessions, phone, hospital_id, context, STATE_AWAITING_SLOT)
                return
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
            sessions.reset(hospital_id, phone)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, "Okay, I've cancelled this booking. Send any message to start over.")
            sessions.reset(hospital_id, phone)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_CONFIRMATION, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_confirmation(wa, phone, context)


# --- Cancel flow (SPEC Section 3.3/5) ---

async def _start_cancel_flow(wa: WhatsAppClient, sessions, phone: str, hospital_id: int) -> None:
    appointments = db.get_upcoming_appointments_for_phone(hospital_id, phone)
    if not appointments:
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, "You don't have any upcoming appointments to cancel.")
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_SELECTION, {})
    await _send_appointment_selection_menu(wa, phone, appointments, "Which appointment would you like to cancel?")


async def _handle_awaiting_cancel_selection(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict) -> None:
    appt = _find_selected_appointment(hospital_id, phone, reply)
    if appt:
        sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_CONFIRM, {"appointment_id": appt.id})
        await _send_cancel_confirm(wa, phone, appt)
        return

    appointments = db.get_upcoming_appointments_for_phone(hospital_id, phone)
    if not appointments:
        # Went stale between menu-send and reply (e.g. the appointment's time passed).
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, "You don't have any upcoming appointments to cancel.")
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_SELECTION, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_appointment_selection_menu(wa, phone, appointments, "Which appointment would you like to cancel?")


async def _handle_awaiting_cancel_confirm(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict) -> None:
    appointment_id = context.get("appointment_id")
    appt = db.get_appointment(hospital_id, appointment_id) if appointment_id is not None else None
    if not appt:
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, "Something went wrong finding that appointment. Please start over.")
        return

    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            db.cancel_appointment(hospital_id, appt.id)
            when = appt.scheduled_at.strftime("%A, %d %B at %H:%M")
            await wa.send_text(phone, f"Your appointment with {appt.doctor_name} on {when} has been cancelled.")
            sessions.reset(hospital_id, phone)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, "Okay, your appointment was not cancelled.")
            sessions.reset(hospital_id, phone)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_CONFIRM, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_cancel_confirm(wa, phone, appt)


# --- Reschedule flow (SPEC Section 3.3/5) ---
# Selection reuses the cancel flow's "pick which appointment" pattern; the new
# slot step reuses _send_slot_menu/db.find_slot from the booking flow, scoped
# to the appointment's existing doctor (no re-picking department/doctor).

async def _start_reschedule_flow(wa: WhatsAppClient, sessions, phone: str, hospital_id: int) -> None:
    appointments = db.get_upcoming_appointments_for_phone(hospital_id, phone)
    if not appointments:
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, "You don't have any upcoming appointments to reschedule.")
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SELECTION, {})
    await _send_appointment_selection_menu(wa, phone, appointments, "Which appointment would you like to reschedule?")


async def _handle_awaiting_reschedule_selection(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict) -> None:
    appt = _find_selected_appointment(hospital_id, phone, reply)
    if appt:
        if not db.get_slots(hospital_id, appt.doctor_id):
            await _notify_no_slots_available(wa, sessions, hospital_id, phone, appt.doctor_name)
            return
        new_context = {
            "reschedule_appointment_id": appt.id,
            "department_id": appt.department_id,
            "department_name": appt.department_name,
            "doctor_id": appt.doctor_id,
            "doctor_name": appt.doctor_name,
        }
        sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SLOT, new_context)
        await _send_slot_menu(wa, phone, hospital_id, appt.doctor_id, appt.doctor_name)
        return

    appointments = db.get_upcoming_appointments_for_phone(hospital_id, phone)
    if not appointments:
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, "You don't have any upcoming appointments to reschedule.")
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SELECTION, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_appointment_selection_menu(wa, phone, appointments, "Which appointment would you like to reschedule?")


async def _handle_awaiting_reschedule_slot(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict) -> None:
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    if not doctor_id or context.get("reschedule_appointment_id") is None:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital")
        return

    if reply["type"] == "interactive_reply":
        slot = db.find_slot(hospital_id, doctor_id, reply["id"])
        if slot:
            new_context = {
                **context,
                "slot_id": slot["id"],
                "slot_label": slot["label"],
                "slot_date": slot["date"],
                "slot_time": slot["time"],
            }
            sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_CONFIRM, new_context)
            await _send_reschedule_confirm(wa, phone, new_context)
            return
    if not db.get_slots(hospital_id, doctor_id):
        await _notify_no_slots_available(wa, sessions, hospital_id, phone, doctor_name)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SLOT, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_slot_menu(wa, phone, hospital_id, doctor_id, doctor_name)


async def _handle_awaiting_reschedule_confirm(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            # Book the new slot BEFORE marking the old appointment rescheduled: if
            # someone else grabbed this exact doctor+slot first (IntegrityError),
            # the patient must keep their original appointment rather than being
            # left with neither (a bug this fix caught — mark_rescheduled() used
            # to run first, unconditionally).
            try:
                db.create_appointment(
                    hospital_id=hospital_id,
                    phone=phone,
                    department_id=context.get("department_id"),
                    doctor_id=context.get("doctor_id"),
                    scheduled_at=datetime.fromisoformat(f"{context['slot_date']}T{context['slot_time']}"),
                )
            except IntegrityError:
                await _handle_slot_taken(wa, sessions, phone, hospital_id, context, STATE_AWAITING_RESCHEDULE_SLOT)
                return
            db.mark_rescheduled(hospital_id, context["reschedule_appointment_id"])
            summary = (
                "Your appointment has been rescheduled!\n\n"
                f"Doctor: {context.get('doctor_name')}\n"
                f"New Slot: {context.get('slot_label')}\n\n"
                "We look forward to seeing you."
            )
            await wa.send_text(phone, summary)
            sessions.reset(hospital_id, phone)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, "Okay, your appointment was not rescheduled.")
            sessions.reset(hospital_id, phone)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_CONFIRM, context)
    await wa.send_text(phone, _PLEASE_CHOOSE)
    await _send_reschedule_confirm(wa, phone, context)


_HANDLERS = {
    STATE_AWAITING_DEPARTMENT: _handle_awaiting_department,
    STATE_AWAITING_DOCTOR: _handle_awaiting_doctor,
    STATE_AWAITING_SLOT: _handle_awaiting_slot,
    STATE_AWAITING_CONFIRMATION: _handle_awaiting_confirmation,
    STATE_AWAITING_CANCEL_SELECTION: _handle_awaiting_cancel_selection,
    STATE_AWAITING_CANCEL_CONFIRM: _handle_awaiting_cancel_confirm,
    STATE_AWAITING_RESCHEDULE_SELECTION: _handle_awaiting_reschedule_selection,
    STATE_AWAITING_RESCHEDULE_SLOT: _handle_awaiting_reschedule_slot,
    STATE_AWAITING_RESCHEDULE_CONFIRM: _handle_awaiting_reschedule_confirm,
}


async def handle_incoming(
    wa: WhatsAppClient,
    sessions,
    phone: str,
    hospital_id: int,
    reply: dict,
    hospital_name: str = "the hospital",
) -> None:
    """
    Entry point: look up the patient's current session (sessions.get already
    resets stale/timed-out sessions to IDLE) and dispatch to the matching
    state handler. hospital_id scopes every database read/write AND every
    session store read/write this message triggers (SPEC Section 12.2) —
    resolved per-message in core/main.py from the incoming webhook's
    phone_number_id (Phase 9), not a value fixed once at startup.
    """
    session = sessions.get(hospital_id, phone)
    state = session["state"]
    context = session["context"]

    handler = _HANDLERS.get(state)
    if handler is None:
        # IDLE, or any unrecognized/stale state value -> treat as IDLE.
        await _handle_idle(wa, sessions, phone, hospital_id, reply, hospital_name)
        return

    await handler(wa, sessions, phone, hospital_id, reply, context)

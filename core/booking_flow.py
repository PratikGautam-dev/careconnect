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

Department/doctor/appointment data is reached ONLY through the connector
interface (SPEC Section 12.6.2, connectors.py) — this module never imports
db/repository.py directly. Every handler takes a `connector` parameter; the
concrete connector (Tier 1/2/3) is resolved once by core/main.py, right after
it resolves which hospital a message is for, and threaded down from there —
this file has no idea which tier it's talking to. `connector` defaults to a
Tier 1 connector so every existing call site (and every existing test) keeps
working unchanged for Tier 1 hospitals without needing to pass one explicitly.

Every db call and every session store call here is scoped by hospital_id
(SPEC Section 12.2, Phase 9), resolved per-message in core/main.py from the
incoming webhook's phone_number_id — not a single value fixed at startup, so
this module never assumes there's only one hospital.

Section 12.11 (language selection + patient name/age during booking): every
function that sends a patient-facing message now takes a `language: str =
"en"` keyword parameter and looks strings up via core/translations.t()
instead of hardcoding English -- defaulted so every pre-existing call site
(including every existing test) keeps working unchanged if it doesn't pass
one. flows.py's router is what actually resolves a session's chosen language
and passes it down; this module doesn't own language SELECTION (that's the
top-level menu's job, flows.py), only respects whichever one it's given.

Also Section 12.11: two new states, AWAITING_PATIENT_NAME and
AWAITING_PATIENT_AGE, inserted between slot selection and confirmation. A
first-time WhatsApp patient (no name on file yet, checked via
connector.get_patient_info()) is asked for both before confirming; a
returning patient with a name already on file skips straight to confirmation
exactly as before Section 12.11 -- the bot should feel like it "remembers"
them, not re-interrogate on every booking.
"""
import logging
from datetime import datetime

from connectors import Connector, Tier1Connector
from core.flow_common import MAX_LIST_ROWS, RESET_KEYWORDS, cap_rows, is_reset_keyword
from core.translations import t
from core.whatsapp import WhatsAppClient
from db.connection import IntegrityError

logger = logging.getLogger(__name__)

_DEFAULT_CONNECTOR = Tier1Connector()

STATE_IDLE = "IDLE"
STATE_AWAITING_DEPARTMENT = "AWAITING_DEPARTMENT"
STATE_AWAITING_DOCTOR = "AWAITING_DOCTOR"
STATE_AWAITING_SLOT = "AWAITING_SLOT"
STATE_AWAITING_PATIENT_NAME = "AWAITING_PATIENT_NAME"
STATE_AWAITING_PATIENT_AGE = "AWAITING_PATIENT_AGE"
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

MIN_PATIENT_AGE = 0
MAX_PATIENT_AGE = 120

# Row-count cap (Meta's 10-row WhatsApp list limit) and reset-keyword handling
# both now live in core/flow_common.py, shared with every other flow_type
# handler (Section 14.1) -- re-exported under their old names here so nothing
# else in this file (or tests importing them from this module) needed to change.
_MAX_LIST_ROWS = MAX_LIST_ROWS
_cap_rows = cap_rows
_RESET_KEYWORDS = RESET_KEYWORDS


def _find_by_id(items: list[dict], item_id: str) -> dict | None:
    """Local replacement for db/repository.py's old find_department()/
    find_doctor()/find_slot() — the connector interface (Section 12.6.2) only
    exposes the plural get_*() forms, so validating a tapped id against the
    full list is done here instead. Department/doctor/slot counts per hospital
    are always small, so filtering client-side costs nothing meaningful."""
    return next((item for item in items if item["id"] == item_id), None)


def _parse_patient_age(text: str) -> int | None:
    """Deliberately permissive parsing, strict range check: strips whitespace,
    requires plain digits (rejects "34.5", "-5", "thirty", empty) -- a
    WhatsApp patient typing an age is realistically always going to type
    plain digits, so no need for a fancier parser. Returns None for anything
    that isn't a whole number in [MIN_PATIENT_AGE, MAX_PATIENT_AGE]."""
    text = text.strip()
    if not text.isdigit():
        return None
    age = int(text)
    if age < MIN_PATIENT_AGE or age > MAX_PATIENT_AGE:
        return None
    return age


# --- Outgoing menu builders ---

async def _send_main_menu(wa: WhatsAppClient, phone: str, hospital_name: str, language: str = "en") -> None:
    rows = [
        {"id": MAIN_MENU_BOOK, "title": t("book_appointment_short", language)},
        {"id": MAIN_MENU_RESCHEDULE, "title": t("reschedule_short", language)},
        {"id": MAIN_MENU_CANCEL, "title": t("cancel_short", language)},
        {"id": MAIN_MENU_FAQ, "title": t("faq_short", language)},
    ]
    await wa.send_list(
        to=phone,
        body_text=t("welcome_menu", language, hospital_name=hospital_name),
        button_text=t("main_menu_button", language),
        sections=[{"title": t("main_menu_section_title", language), "rows": rows}],
    )


async def _send_department_menu(wa: WhatsAppClient, phone: str, hospital_id: int, connector: Connector, language: str = "en") -> None:
    rows = [{"id": d["id"], "title": d["name"]} for d in connector.get_departments(hospital_id)]
    rows = _cap_rows(rows, "department menu")
    await wa.send_list(
        to=phone,
        body_text=t("select_department", language),
        button_text=t("view_departments_button", language),
        sections=[{"title": t("departments_section_title", language), "rows": rows}],
    )


async def _send_doctor_menu(
    wa: WhatsAppClient, phone: str, hospital_id: int, department_id: str, department_name: str, connector: Connector,
    language: str = "en",
) -> None:
    rows = [{"id": d["id"], "title": d["name"]} for d in connector.get_doctors(hospital_id, department_id)]
    rows = _cap_rows(rows, "doctor menu")
    await wa.send_list(
        to=phone,
        body_text=t("select_doctor", language, department_name=department_name),
        button_text=t("view_doctors_button", language),
        sections=[{"title": department_name, "rows": rows}],
    )


async def _send_slot_menu(
    wa: WhatsAppClient, phone: str, hospital_id: int, doctor_id: str, doctor_name: str, connector: Connector,
    language: str = "en",
) -> None:
    # get_available_slots() returns soonest-first (db.get_slots()'s ORDER BY
    # scheduled_at) -- capping to _MAX_LIST_ROWS keeps the soonest bookable
    # times, not an arbitrary/later slice.
    rows = [{"id": s["id"], "title": s["label"]} for s in connector.get_available_slots(hospital_id, doctor_id)]
    rows = _cap_rows(rows, f"slot menu for doctor {doctor_id}")
    await wa.send_list(
        to=phone,
        body_text=t("select_slot", language, doctor_name=doctor_name),
        button_text=t("view_slots_button", language),
        sections=[{"title": t("available_slots_section_title", language), "rows": rows}],
    )


async def _notify_no_doctors_available(
    wa: WhatsAppClient, sessions, hospital_id: int, phone: str, department_name: str, language: str = "en",
) -> None:
    sessions.reset(hospital_id, phone)
    await wa.send_text(phone, t("no_doctors_available", language, department_name=department_name))


async def _notify_no_slots_available(
    wa: WhatsAppClient, sessions, hospital_id: int, phone: str, doctor_name: str, language: str = "en",
) -> None:
    sessions.reset(hospital_id, phone)
    await wa.send_text(phone, t("no_slots_available", language, doctor_name=doctor_name))


async def _handle_slot_taken(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, target_state: str, connector: Connector,
    language: str = "en",
) -> None:
    """Shared recovery path for a double-booking race hit during booking OR
    reschedule confirmation (SPEC Phase 8): tell the patient, then either
    re-show the doctor's now-current slot list (freshly queried, so the just-
    taken slot is already gone) or, if that emptied the list out entirely,
    the same "no slots available" fallback used elsewhere."""
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    logger.info("Double-booking race: hospital=%s doctor=%s slot=%s already taken", hospital_id, doctor_id, context.get("slot_id"))
    if not connector.get_available_slots(hospital_id, doctor_id):
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("slot_taken_no_alternatives", language, doctor_name=doctor_name))
        return
    sessions.set(hospital_id, phone, target_state, context)
    await wa.send_text(phone, t("slot_taken_choose_another", language))
    await _send_slot_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)


async def _send_confirmation(wa: WhatsAppClient, phone: str, context: dict, language: str = "en") -> None:
    summary = t(
        "confirm_booking_summary", language,
        department_name=context.get("department_name"), doctor_name=context.get("doctor_name"),
        slot_label=context.get("slot_label"),
    )
    await wa.send_buttons(
        to=phone,
        body_text=summary,
        buttons=[
            {"id": CONFIRM_YES, "title": t("confirm_button", language)},
            {"id": CONFIRM_NO, "title": t("cancel_button", language)},
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


async def _send_appointment_selection_menu(
    wa: WhatsAppClient, phone: str, appointments: list, body_key: str, language: str = "en",
) -> None:
    rows = [
        {
            "id": _appointment_row_id(a.id),
            "title": a.doctor_name,
            "description": a.scheduled_at.strftime("%a %d %b %Y, %H:%M"),
        }
        for a in appointments
    ]
    rows = _cap_rows(rows, "appointment selection menu")
    await wa.send_list(
        to=phone,
        body_text=t(body_key, language),
        button_text=t("view_appointments_button", language),
        sections=[{"title": t("your_appointments_section_title", language), "rows": rows}],
    )


async def _send_cancel_confirm(wa: WhatsAppClient, phone: str, appointment, language: str = "en") -> None:
    when = appointment.scheduled_at.strftime("%A, %d %B at %H:%M")
    await wa.send_buttons(
        to=phone,
        body_text=t("cancel_confirm_question", language, doctor_name=appointment.doctor_name, when=when),
        buttons=[
            {"id": CONFIRM_YES, "title": t("confirm_button", language)},
            {"id": CONFIRM_NO, "title": t("cancel_button", language)},
        ],
    )


async def _send_reschedule_confirm(wa: WhatsAppClient, phone: str, context: dict, language: str = "en") -> None:
    summary = t(
        "reschedule_confirm_summary", language,
        doctor_name=context.get("doctor_name"), slot_label=context.get("slot_label"),
    )
    await wa.send_buttons(
        to=phone,
        body_text=summary,
        buttons=[
            {"id": CONFIRM_YES, "title": t("confirm_button", language)},
            {"id": CONFIRM_NO, "title": t("cancel_button", language)},
        ],
    )


def _find_selected_appointment(hospital_id: int, phone: str, reply: dict, connector: Connector):
    """Resolve a tapped appointment-selection row id to a live Appointment,
    re-validated against the patient's own current upcoming appointments (not
    trusted from stale context) — same "re-check against the source of truth"
    pattern as slot selection. connector.get_upcoming_appointments(phone=...)
    already only returns booked, future, phone-owned appointments, so a row id
    guessed/replayed from a different hospital's conversation (or a different
    patient's) can never resolve here (SPEC Section 12.2)."""
    if reply["type"] != "interactive_reply":
        return None
    appt_id = _parse_appointment_row_id(reply["id"])
    if appt_id is None:
        return None
    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    return next((a for a in appointments if a.id == appt_id), None)


# --- State handlers ---
# Each handler either advances the session to the next state (on a valid tap)
# or refreshes the session at the *same* state (on free text/unsupported input,
# which also resets the 30-min inactivity clock since the patient did respond).

async def _handle_idle(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, hospital_name: str, connector: Connector,
    language: str = "en",
) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == MAIN_MENU_BOOK:
            sessions.set(hospital_id, phone, STATE_AWAITING_DEPARTMENT, {})
            await _send_department_menu(wa, phone, hospital_id, connector, language=language)
            return
        if rid == MAIN_MENU_RESCHEDULE:
            await _start_reschedule_flow(wa, sessions, phone, hospital_id, connector, language=language)
            return
        if rid == MAIN_MENU_CANCEL:
            await _start_cancel_flow(wa, sessions, phone, hospital_id, connector, language=language)
            return
        if rid == MAIN_MENU_FAQ:
            sessions.reset(hospital_id, phone)
            await wa.send_text(phone, t("hospital_info_text", language))
            return
    # Any other message while IDLE (first contact, free text, stale/unknown id):
    # per spec, IDLE always responds with the welcome message + main menu.
    sessions.reset(hospital_id, phone)
    await _send_main_menu(wa, phone, hospital_name, language=language)


async def _handle_awaiting_department(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    if reply["type"] == "interactive_reply":
        dept = _find_by_id(connector.get_departments(hospital_id), reply["id"])
        if dept:
            if not connector.get_doctors(hospital_id, dept["id"]):
                await _notify_no_doctors_available(wa, sessions, hospital_id, phone, dept["name"], language=language)
                return
            new_context = {"department_id": dept["id"], "department_name": dept["name"]}
            sessions.set(hospital_id, phone, STATE_AWAITING_DOCTOR, new_context)
            await _send_doctor_menu(wa, phone, hospital_id, dept["id"], dept["name"], connector, language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_DEPARTMENT, context)
    await wa.send_text(phone, t("please_choose", language))
    await _send_department_menu(wa, phone, hospital_id, connector, language=language)


async def _handle_awaiting_doctor(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    department_id = context.get("department_id")
    department_name = context.get("department_name", "")
    if not department_id:
        # Corrupted/incomplete session context — fail safe back to the main menu.
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        doctor = _find_by_id(connector.get_doctors(hospital_id, department_id), reply["id"])
        if doctor:
            if not connector.get_available_slots(hospital_id, doctor["id"]):
                await _notify_no_slots_available(wa, sessions, hospital_id, phone, doctor["name"], language=language)
                return
            new_context = {**context, "doctor_id": doctor["id"], "doctor_name": doctor["name"]}
            sessions.set(hospital_id, phone, STATE_AWAITING_SLOT, new_context)
            await _send_slot_menu(wa, phone, hospital_id, doctor["id"], doctor["name"], connector, language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_DOCTOR, context)
    await wa.send_text(phone, t("please_choose", language))
    await _send_doctor_menu(wa, phone, hospital_id, department_id, department_name, connector, language=language)


async def _handle_awaiting_slot(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    if not doctor_id:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        slot = _find_by_id(connector.get_available_slots(hospital_id, doctor_id), reply["id"])
        if slot:
            new_context = {
                **context,
                "slot_id": slot["id"],
                "slot_label": slot["label"],
                "slot_date": slot["date"],
                "slot_time": slot["time"],
            }
            # Section 12.11: a first-time patient (no name on file) is asked
            # for name+age before confirming; a returning patient skips
            # straight to confirmation exactly as before this section.
            patient_info = connector.get_patient_info(hospital_id, phone)
            if patient_info and patient_info.get("name"):
                sessions.set(hospital_id, phone, STATE_AWAITING_CONFIRMATION, new_context)
                await _send_confirmation(wa, phone, new_context, language=language)
                return
            sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, new_context)
            await wa.send_text(phone, t("ask_patient_name", language))
            return
    # Slots are dynamic (another patient's booking can take the last one between
    # this menu being sent and this reply) — recheck rather than blindly re-send.
    if not connector.get_available_slots(hospital_id, doctor_id):
        await _notify_no_slots_available(wa, sessions, hospital_id, phone, doctor_name, language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_SLOT, context)
    await wa.send_text(phone, t("please_choose", language))
    await _send_slot_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)


async def _handle_awaiting_patient_name(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    """Section 12.11. Free text only, same "unsupported input re-prompts the
    same state" pattern as every tap-driven state above, just keyed on
    non-empty text instead of a valid interactive_reply id."""
    if reply["type"] == "text" and reply["text"].strip():
        name = reply["text"].strip()
        new_context = {**context, "patient_name": name}
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, new_context)
        await wa.send_text(phone, t("ask_patient_age", language, patient_name=name))
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, context)
    await wa.send_text(phone, t("invalid_patient_name", language))
    await wa.send_text(phone, t("ask_patient_name", language))


async def _handle_awaiting_patient_age(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    """Section 12.11. Validates a whole number in [MIN_PATIENT_AGE,
    MAX_PATIENT_AGE] (_parse_patient_age) -- non-numeric or out-of-range
    input re-prompts with a specific error, same pattern as every other
    validation failure in this codebase (e.g. db.is_valid_phone() at the
    staff new-booking form)."""
    age = _parse_patient_age(reply["text"]) if reply["type"] == "text" else None
    if age is not None:
        new_context = {**context, "patient_age": age}
        sessions.set(hospital_id, phone, STATE_AWAITING_CONFIRMATION, new_context)
        await _send_confirmation(wa, phone, new_context, language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, context)
    await wa.send_text(phone, t("invalid_patient_age", language))
    await wa.send_text(phone, t("ask_patient_age", language, patient_name=context.get("patient_name", "")))


async def _handle_awaiting_confirmation(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            try:
                connector.create_booking(
                    hospital_id=hospital_id,
                    phone=phone,
                    department_id=context.get("department_id"),
                    doctor_id=context.get("doctor_id"),
                    scheduled_at=datetime.fromisoformat(f"{context['slot_date']}T{context['slot_time']}"),
                    patient_name=context.get("patient_name"),
                    patient_age=context.get("patient_age"),
                )
            except IntegrityError:
                # Someone else booked this exact doctor+slot first (db/schema.sql's
                # partial unique index — the real double-booking guard, not this
                # try/except). Send the patient back to slot selection with a
                # freshly-queried list that no longer offers the taken slot.
                await _handle_slot_taken(wa, sessions, phone, hospital_id, context, STATE_AWAITING_SLOT, connector, language=language)
                return
            summary = t(
                "booking_confirmed", language,
                department_name=context.get("department_name"), doctor_name=context.get("doctor_name"),
                slot_label=context.get("slot_label"),
            )
            await wa.send_text(phone, summary)
            # STATE_BOOKED is terminal and resets to IDLE immediately — there's no
            # separate incoming message that moves it out of BOOKED, so it's never
            # actually written to the session store.
            sessions.reset(hospital_id, phone)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, t("booking_not_confirmed", language))
            sessions.reset(hospital_id, phone)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_CONFIRMATION, context)
    await wa.send_text(phone, t("please_choose", language))
    await _send_confirmation(wa, phone, context, language=language)


# --- Cancel flow (SPEC Section 3.3/5) ---

async def _start_cancel_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    if not appointments:
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("no_upcoming_to_cancel", language))
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_SELECTION, {})
    await _send_appointment_selection_menu(wa, phone, appointments, "which_appointment_cancel", language=language)


async def _handle_awaiting_cancel_selection(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    appt = _find_selected_appointment(hospital_id, phone, reply, connector)
    if appt:
        sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_CONFIRM, {"appointment_id": appt.id})
        await _send_cancel_confirm(wa, phone, appt, language=language)
        return

    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    if not appointments:
        # Went stale between menu-send and reply (e.g. the appointment's time passed).
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("no_upcoming_to_cancel", language))
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_SELECTION, context)
    await wa.send_text(phone, t("please_choose", language))
    await _send_appointment_selection_menu(wa, phone, appointments, "which_appointment_cancel", language=language)


async def _handle_awaiting_cancel_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    appointment_id = context.get("appointment_id")
    appt = None
    if appointment_id is not None:
        appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
        appt = next((a for a in appointments if a.id == appointment_id), None)
    if not appt:
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("appointment_lookup_error", language))
        return

    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            connector.cancel_booking(hospital_id, appt.id)
            when = appt.scheduled_at.strftime("%A, %d %B at %H:%M")
            await wa.send_text(phone, t("appointment_cancelled", language, doctor_name=appt.doctor_name, when=when))
            sessions.reset(hospital_id, phone)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, t("cancellation_aborted", language))
            sessions.reset(hospital_id, phone)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_CONFIRM, context)
    await wa.send_text(phone, t("please_choose", language))
    await _send_cancel_confirm(wa, phone, appt, language=language)


# --- Reschedule flow (SPEC Section 3.3/5) ---
# Selection reuses the cancel flow's "pick which appointment" pattern; the new
# slot step reuses _send_slot_menu/the connector's slot lookup from the
# booking flow, scoped to the appointment's existing doctor (no re-picking
# department/doctor).

async def _start_reschedule_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    if not appointments:
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("no_upcoming_to_reschedule", language))
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SELECTION, {})
    await _send_appointment_selection_menu(wa, phone, appointments, "which_appointment_reschedule", language=language)


async def _handle_awaiting_reschedule_selection(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    appt = _find_selected_appointment(hospital_id, phone, reply, connector)
    if appt:
        if not connector.get_available_slots(hospital_id, appt.doctor_id):
            await _notify_no_slots_available(wa, sessions, hospital_id, phone, appt.doctor_name, language=language)
            return
        new_context = {
            "reschedule_appointment_id": appt.id,
            "department_id": appt.department_id,
            "department_name": appt.department_name,
            "doctor_id": appt.doctor_id,
            "doctor_name": appt.doctor_name,
        }
        sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SLOT, new_context)
        await _send_slot_menu(wa, phone, hospital_id, appt.doctor_id, appt.doctor_name, connector, language=language)
        return

    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    if not appointments:
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("no_upcoming_to_reschedule", language))
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SELECTION, context)
    await wa.send_text(phone, t("please_choose", language))
    await _send_appointment_selection_menu(wa, phone, appointments, "which_appointment_reschedule", language=language)


async def _handle_awaiting_reschedule_slot(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    if not doctor_id or context.get("reschedule_appointment_id") is None:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        slot = _find_by_id(connector.get_available_slots(hospital_id, doctor_id), reply["id"])
        if slot:
            new_context = {
                **context,
                "slot_id": slot["id"],
                "slot_label": slot["label"],
                "slot_date": slot["date"],
                "slot_time": slot["time"],
            }
            sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_CONFIRM, new_context)
            await _send_reschedule_confirm(wa, phone, new_context, language=language)
            return
    if not connector.get_available_slots(hospital_id, doctor_id):
        await _notify_no_slots_available(wa, sessions, hospital_id, phone, doctor_name, language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SLOT, context)
    await wa.send_text(phone, t("please_choose", language))
    await _send_slot_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)


async def _handle_awaiting_reschedule_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            try:
                connector.reschedule_booking(
                    hospital_id=hospital_id,
                    old_appointment_id=context["reschedule_appointment_id"],
                    phone=phone,
                    department_id=context.get("department_id"),
                    doctor_id=context.get("doctor_id"),
                    scheduled_at=datetime.fromisoformat(f"{context['slot_date']}T{context['slot_time']}"),
                )
            except IntegrityError:
                # Someone else grabbed this exact doctor+slot first -- the connector's
                # reschedule_booking() (Tier1Connector) books the new slot before
                # touching the old appointment, so a losing race here leaves the
                # patient's original appointment intact rather than with neither.
                await _handle_slot_taken(wa, sessions, phone, hospital_id, context, STATE_AWAITING_RESCHEDULE_SLOT, connector, language=language)
                return
            summary = t(
                "appointment_rescheduled", language,
                doctor_name=context.get("doctor_name"), slot_label=context.get("slot_label"),
            )
            await wa.send_text(phone, summary)
            sessions.reset(hospital_id, phone)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, t("reschedule_aborted", language))
            sessions.reset(hospital_id, phone)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_CONFIRM, context)
    await wa.send_text(phone, t("please_choose", language))
    await _send_reschedule_confirm(wa, phone, context, language=language)


_HANDLERS = {
    STATE_AWAITING_DEPARTMENT: _handle_awaiting_department,
    STATE_AWAITING_DOCTOR: _handle_awaiting_doctor,
    STATE_AWAITING_SLOT: _handle_awaiting_slot,
    STATE_AWAITING_PATIENT_NAME: _handle_awaiting_patient_name,
    STATE_AWAITING_PATIENT_AGE: _handle_awaiting_patient_age,
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
    connector: Connector | None = None,
) -> None:
    """
    Entry point: look up the patient's current session (sessions.get already
    resets stale/timed-out sessions to IDLE) and dispatch to the matching
    state handler. hospital_id scopes every database read/write AND every
    session store read/write this message triggers (SPEC Section 12.2) —
    resolved per-message in core/main.py from the incoming webhook's
    phone_number_id (Phase 9), not a value fixed once at startup.

    connector (SPEC Section 12.6.2) is resolved once by core/main.py from the
    hospital's stored data_tier and passed in here; defaults to a Tier 1
    connector so every pre-existing caller (including the whole test suite)
    keeps working unchanged for Tier 1 hospitals without passing one.

    This module's OWN entry point (superseded for real traffic by flows.py's
    router, see the module docstring) doesn't own language SELECTION -- it
    just respects whatever's already on the session, defaulting to English,
    so its own standalone tests stay meaningful for language too without
    duplicating flows.py's language-picker logic in a dead code path.
    """
    connector = connector or _DEFAULT_CONNECTOR
    session = sessions.get(hospital_id, phone)
    state = session["state"]
    context = session["context"]
    language = session.get("language") or "en"

    if state != STATE_IDLE and is_reset_keyword(reply):
        sessions.reset(hospital_id, phone)
        await _handle_idle(wa, sessions, phone, hospital_id, reply, hospital_name, connector, language=language)
        return

    handler = _HANDLERS.get(state)
    if handler is None:
        # IDLE, or any unrecognized/stale state value -> treat as IDLE.
        await _handle_idle(wa, sessions, phone, hospital_id, reply, hospital_name, connector, language=language)
        return

    await handler(wa, sessions, phone, hospital_id, reply, context, connector, language=language)

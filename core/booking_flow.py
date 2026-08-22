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

Section 12.11 also added a patient-name/age collection step; Section 12.12
split slot selection into two steps (date, then time) to match a reference
screenshot's exact flow/wording and briefly dropped the age step to match
it exactly, then a Section 12.13 follow-up restored age (confirmed wanted
after all) -- see the state constants' own comment for the full history.
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

# Section 12.12: restructured to match a reference screenshot's exact flow --
# department -> doctor (now with an inline "You have selected Dr. X" line) ->
# DATE (new, was folded into a single combined slot list before this) -> TIME
# (new) -> patient name -> confirmation (restyled as a structured
# *bold*-markdown card) -> a success message with a generated reference_id.
# Section 12.12 originally dropped Section 12.11's separate age step to match
# the reference screenshot exactly (it had no age field) -- a Section 12.13
# follow-up restored it (confirmed wanted after all) with age now also shown
# on the confirmation card, which the original reference screenshot didn't
# have either but was explicitly requested this time. Reschedule keeps its
# own separate, unchanged single combined slot-list step
# (_send_slot_menu/STATE_AWAITING_RESCHEDULE_SLOT) -- none of this ever
# applied to it.
STATE_IDLE = "IDLE"
STATE_AWAITING_DEPARTMENT = "AWAITING_DEPARTMENT"
STATE_AWAITING_DOCTOR = "AWAITING_DOCTOR"
STATE_AWAITING_DATE = "AWAITING_DATE"
STATE_AWAITING_TIME_SLOT = "AWAITING_TIME_SLOT"
STATE_AWAITING_PATIENT_NAME = "AWAITING_PATIENT_NAME"
STATE_AWAITING_PATIENT_AGE = "AWAITING_PATIENT_AGE"
STATE_AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
STATE_BOOKED = "BOOKED"  # momentary only — never persisted, see _handle_awaiting_confirmation

MIN_PATIENT_AGE = 0
MAX_PATIENT_AGE = 120

# Live-found bug: a patient's actual typed input can collide with a reset
# keyword purely by coincidence (a real patient named "Hi", or -- far more
# commonly hit in practice -- someone testing the bot who types "hi"/"test"
# as a throwaway name/age) at the two states in this whole flow that accept
# arbitrary free text as a real value, not a menu choice. The global
# reset-keyword short-circuit in both this module's own handle_incoming()
# below AND flows.py's router-level one must skip states in this set, so
# free text typed there is always taken as the actual value, never
# misread as an escape-to-menu command.
FREE_TEXT_INPUT_STATES = {STATE_AWAITING_PATIENT_NAME, STATE_AWAITING_PATIENT_AGE}

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


def _date_label(date_str: str) -> str:
    """"Sat, Aug 8" style day+date label (Section 12.12, reference screenshot).
    Built manually rather than via a single strftime format string because the
    day-of-month-without-a-leading-zero directive isn't portable (%-d is
    Linux/macOS only, Windows needs %#d) -- this avoids the platform split
    entirely. Deliberately not translated for Hindi (see core/translations.py
    module docstring's "computed value, not fixed UI chrome" precedent --
    slot_label was never translated either)."""
    dt = datetime.fromisoformat(date_str)
    return f"{dt.strftime('%a')}, {dt.strftime('%b')} {dt.day}"


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


def _append_closing_message(text: str, closing_message_text: str | None) -> str:
    """Section 12.13: a hospital's own custom closing/thank-you text is
    APPENDED after the standard success message (booking confirmed, cancelled,
    rescheduled), never replacing it -- e.g. "Thank you for choosing City
    Hospital. For emergencies, call 102." NULL/blank (the default -- most
    hospitals never set this) leaves the standard message untouched."""
    if not closing_message_text:
        return text
    return f"{text}\n\n{closing_message_text}"


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
    """RESCHEDULE flow's own step only, as of Section 12.12 -- see the module
    docstring/state-constants comment for why booking itself now uses the
    date/time-split _send_date_menu/_send_time_menu below instead."""
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


async def _send_date_menu(
    wa: WhatsAppClient, phone: str, hospital_id: int, doctor_id: str, doctor_name: str, connector: Connector,
    language: str = "en",
) -> None:
    """Section 12.12, booking flow's step 1 of the date/time split: the
    distinct dates (soonest first, since get_available_slots() is already
    sorted that way) this doctor has ANY bookable slot on, capped to Meta's
    10-row limit -- a doctor generates up to 14 days ahead
    (db/repository.py's _SLOT_DAYS_AHEAD), so this can legitimately exceed 10
    distinct dates for a doctor who works every day."""
    slots = connector.get_available_slots(hospital_id, doctor_id)
    dates_seen: list[str] = []
    for s in slots:
        if s["date"] not in dates_seen:
            dates_seen.append(s["date"])
    rows = [{"id": d, "title": _date_label(d)} for d in dates_seen]
    rows = _cap_rows(rows, f"date menu for doctor {doctor_id}")
    await wa.send_list(
        to=phone,
        body_text=t("doctor_selected_ask_date", language, doctor_name=doctor_name),
        button_text=t("view_dates_button", language),
        sections=[{"title": t("available_dates_section_title", language), "rows": rows}],
    )


async def _send_time_menu(
    wa: WhatsAppClient, phone: str, hospital_id: int, doctor_id: str, date_str: str, connector: Connector,
    language: str = "en",
) -> None:
    """Section 12.12, step 2 of the date/time split: just this doctor's slots
    ON date_str, row title is the bare time (the date's already been picked,
    showing it again in every row would be redundant) -- e.g. a doctor with
    two shifts and a short slot duration can easily have 20+ times in one day,
    so this is capped independently of the date list above, not just
    inheriting whatever headroom the date cap left."""
    rows = [
        {"id": s["id"], "title": s["time"]}
        for s in connector.get_available_slots(hospital_id, doctor_id)
        if s["date"] == date_str
    ]
    rows = _cap_rows(rows, f"time menu for doctor {doctor_id} on {date_str}")
    await wa.send_list(
        to=phone,
        body_text=t("select_time_slot", language),
        button_text=t("view_times_button", language),
        sections=[{"title": t("available_times_section_title", language), "rows": rows}],
    )


async def _notify_no_doctors_available(
    wa: WhatsAppClient, sessions, hospital_id: int, phone: str, department_name: str, language: str = "en",
) -> None:
    sessions.reset(hospital_id, phone)
    await wa.send_text(phone, t("no_doctors_available", language, department_name=department_name))
    # Item 9 (Spec.md Section 0): a genuine dead end (this department has no
    # doctors) previously left the patient with nothing to do next but
    # message again from scratch -- the main menu is the recovery path for
    # every negative-outcome case that ISN'T specifically "pick another
    # slot" (that's item 1's own alternate-slot recovery, _handle_slot_taken
    # above). "the hospital" matches this file's own existing fallback
    # wording at every other deep-handler-bails-to-main-menu site (e.g.
    # _handle_awaiting_doctor's corrupted-context guard) -- none of these
    # state handlers carry the real hospital_name down this far.
    await _send_main_menu(wa, phone, "the hospital", language=language)


async def _notify_no_slots_available(
    wa: WhatsAppClient, sessions, hospital_id: int, phone: str, doctor_name: str, language: str = "en",
) -> None:
    sessions.reset(hospital_id, phone)
    await wa.send_text(phone, t("no_slots_available", language, doctor_name=doctor_name))
    await _send_main_menu(wa, phone, "the hospital", language=language)


async def _handle_slot_taken(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, target_state: str, connector: Connector,
    language: str = "en",
) -> None:
    """Shared recovery path for a double-booking race hit during booking OR
    reschedule confirmation (SPEC Phase 8): tell the patient, then either
    re-show a fresh list that no longer offers the just-taken slot, or, if
    that emptied the doctor's availability out entirely, the same "no slots
    available" fallback used elsewhere.

    Section 12.12: target_state tells this which flow is recovering --
    STATE_AWAITING_TIME_SLOT (booking, date/time-split) re-shows just that
    date's times via _send_time_menu; anything else (reschedule's
    STATE_AWAITING_RESCHEDULE_SLOT) re-shows the older combined _send_slot_menu,
    unchanged from before this section."""
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    logger.info("Double-booking race: hospital=%s doctor=%s slot=%s already taken", hospital_id, doctor_id, context.get("slot_id"))
    if not connector.get_available_slots(hospital_id, doctor_id):
        # Item 9: a genuine dead end, not the "pick another slot" case item 1
        # covers (there's nothing left to pick) -- same recovery as
        # _notify_no_slots_available above.
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("slot_taken_no_alternatives", language, doctor_name=doctor_name))
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    sessions.set(hospital_id, phone, target_state, context)
    await wa.send_text(phone, t("slot_taken_choose_another", language))
    if target_state == STATE_AWAITING_TIME_SLOT:
        date_str = context.get("date") or context.get("slot_date")
        await _send_time_menu(wa, phone, hospital_id, doctor_id, date_str, connector, language=language)
        return
    await _send_slot_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)


async def _send_confirmation(wa: WhatsAppClient, phone: str, context: dict, language: str = "en") -> None:
    """Section 12.12: structured *bold*-markdown card matching the reference
    screenshot -- see core/translations.py's confirm_booking_summary. Age
    (Section 12.13 follow-up) is included too, even though the original
    reference screenshot didn't have it -- explicitly requested."""
    summary = t(
        "confirm_booking_summary", language,
        department_name=context.get("department_name"), doctor_name=context.get("doctor_name"),
        date_label=context.get("date_label"), time_label=context.get("slot_time"),
        patient_name=context.get("patient_name"), patient_age=context.get("patient_age"),
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
    language: str = "en", closing_message_text: str | None = None,
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
    await _send_department_menu(wa, phone, hospital_id, connector, language=language)


async def _handle_awaiting_doctor(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
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
            sessions.set(hospital_id, phone, STATE_AWAITING_DATE, new_context)
            await _send_date_menu(wa, phone, hospital_id, doctor["id"], doctor["name"], connector, language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_DOCTOR, context)
    await _send_doctor_menu(wa, phone, hospital_id, department_id, department_name, connector, language=language)


async def _handle_awaiting_date(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Section 12.12, step 1 of the date/time split (was _handle_awaiting_slot
    before this section)."""
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    if not doctor_id:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        available_dates = {s["date"] for s in connector.get_available_slots(hospital_id, doctor_id)}
        if reply["id"] in available_dates:
            new_context = {**context, "date": reply["id"], "date_label": _date_label(reply["id"])}
            sessions.set(hospital_id, phone, STATE_AWAITING_TIME_SLOT, new_context)
            await _send_time_menu(wa, phone, hospital_id, doctor_id, reply["id"], connector, language=language)
            return
    # Dates are dynamic (another patient's booking can take the doctor's only
    # slot on a given date between this menu being sent and this reply) --
    # recheck rather than blindly re-send, same discipline as every other
    # dynamic-availability step in this file.
    if not connector.get_available_slots(hospital_id, doctor_id):
        await _notify_no_slots_available(wa, sessions, hospital_id, phone, doctor_name, language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_DATE, context)
    await _send_date_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)


async def _handle_awaiting_time_slot(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Section 12.12, step 2 of the date/time split."""
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    date_str = context.get("date")
    if not doctor_id or not date_str:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        slot = _find_by_id(connector.get_available_slots(hospital_id, doctor_id), reply["id"])
        if slot and slot["date"] == date_str:
            new_context = {
                **context,
                "slot_id": slot["id"],
                "slot_date": slot["date"],
                "slot_time": slot["time"],
            }
            # Re-picking a slot after a double-booking race (_handle_slot_taken
            # re-enters this exact state, context unchanged): this session
            # already collected name/age earlier THIS booking attempt, but
            # create_appointment()'s failed transaction never reached
            # _upsert_patient() (it runs after the INSERT that raised the
            # race error, and the whole transaction rolled back) -- so the DB
            # genuinely doesn't have it yet even though context does. Trust
            # context over a DB re-query here, or the patient gets asked for
            # name/age a second time for no reason.
            if context.get("patient_name") and context.get("patient_age") is not None:
                sessions.set(hospital_id, phone, STATE_AWAITING_CONFIRMATION, new_context)
                await _send_confirmation(wa, phone, new_context, language=language)
                return
            # Section 12.11 (patient-info skip), age restored by a Section
            # 12.13 follow-up: a patient with BOTH a name and an age already
            # on file skips straight to confirmation; one with a name but no
            # age (e.g. booked once back when this flow only collected a
            # name) skips just the name question and is asked for age only;
            # a genuinely first-time patient is asked for both.
            patient_info = connector.get_patient_info(hospital_id, phone)
            has_name = bool(patient_info and patient_info.get("name"))
            has_age = bool(patient_info and patient_info.get("age") is not None)
            if has_name and has_age:
                new_context["patient_name"] = patient_info["name"]
                new_context["patient_age"] = patient_info["age"]
                sessions.set(hospital_id, phone, STATE_AWAITING_CONFIRMATION, new_context)
                await _send_confirmation(wa, phone, new_context, language=language)
                return
            if has_name:
                new_context["patient_name"] = patient_info["name"]
                sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, new_context)
                await wa.send_text(phone, t("ask_patient_age", language, patient_name=patient_info["name"]))
                return
            sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, new_context)
            await wa.send_text(phone, t("ask_patient_name", language))
            return
    # Times are dynamic for the same reason dates are above -- recheck this
    # exact date's availability rather than blindly re-sending a stale list.
    if not any(s["date"] == date_str for s in connector.get_available_slots(hospital_id, doctor_id)):
        # This date specifically emptied out (not necessarily the whole
        # doctor) -- step back to date selection rather than a full reset,
        # so the patient picks a different date instead of starting over.
        sessions.set(hospital_id, phone, STATE_AWAITING_DATE, context)
        await _send_date_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_TIME_SLOT, context)
    await _send_time_menu(wa, phone, hospital_id, doctor_id, date_str, connector, language=language)


async def _handle_awaiting_patient_name(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Section 12.11, target state restored to AWAITING_PATIENT_AGE by a
    Section 12.13 follow-up (Section 12.12 had briefly sent this straight to
    confirmation instead). Free text only, same "unsupported input
    re-prompts the same state" pattern as every tap-driven state above, just
    keyed on non-empty text instead of a valid interactive_reply id."""
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
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Section 12.11, restored by a Section 12.13 follow-up. Validates a
    whole number in [MIN_PATIENT_AGE, MAX_PATIENT_AGE] (_parse_patient_age)
    -- non-numeric or out-of-range input re-prompts with a specific error,
    same pattern as every other validation failure in this codebase (e.g.
    db.is_valid_phone() at the staff new-booking form)."""
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
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            try:
                appointment = connector.create_booking(
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
                # try/except). Send the patient back to time selection with a
                # freshly-queried list that no longer offers the taken slot.
                await _handle_slot_taken(wa, sessions, phone, hospital_id, context, STATE_AWAITING_TIME_SLOT, connector, language=language)
                return
            # Section 12.12: reference_id is generated once, inside
            # create_appointment() itself (db/repository.py) -- read back off
            # the returned Appointment rather than regenerated here, so the
            # id shown to the patient is the exact one actually stored.
            summary = t("booking_confirmed", language, reference_id=appointment.reference_id)
            await wa.send_text(phone, _append_closing_message(summary, closing_message_text))
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
    await _send_confirmation(wa, phone, context, language=language)


# --- Cancel flow (SPEC Section 3.3/5) ---

async def _start_cancel_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    if not appointments:
        # Item 9: nothing to cancel is a dead end without a menu offered.
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("no_upcoming_to_cancel", language))
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_SELECTION, {})
    await _send_appointment_selection_menu(wa, phone, appointments, "which_appointment_cancel", language=language)


async def _handle_awaiting_cancel_selection(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    appt = _find_selected_appointment(hospital_id, phone, reply, connector)
    if appt:
        sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_CONFIRM, {"appointment_id": appt.id})
        await _send_cancel_confirm(wa, phone, appt, language=language)
        return

    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    if not appointments:
        # Went stale between menu-send and reply (e.g. the appointment's time
        # passed) -- item 9: dead end, offer the main menu.
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("no_upcoming_to_cancel", language))
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_SELECTION, context)
    await _send_appointment_selection_menu(wa, phone, appointments, "which_appointment_cancel", language=language)


async def _handle_awaiting_cancel_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    appointment_id = context.get("appointment_id")
    appt = None
    if appointment_id is not None:
        appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
        appt = next((a for a in appointments if a.id == appointment_id), None)
    if not appt:
        # Item 9: an unexpected failure mid-flow -- exactly the "give the
        # patient a way forward" case, not item 1's alternate-slot recovery.
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("appointment_lookup_error", language))
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            connector.cancel_booking(hospital_id, appt.id)
            when = appt.scheduled_at.strftime("%A, %d %B at %H:%M")
            cancelled_text = t("appointment_cancelled", language, doctor_name=appt.doctor_name, when=when)
            await wa.send_text(phone, _append_closing_message(cancelled_text, closing_message_text))
            sessions.reset(hospital_id, phone)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, t("cancellation_aborted", language))
            sessions.reset(hospital_id, phone)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_CONFIRM, context)
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
        # Item 9: nothing to reschedule is a dead end without a menu offered.
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("no_upcoming_to_reschedule", language))
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SELECTION, {})
    await _send_appointment_selection_menu(wa, phone, appointments, "which_appointment_reschedule", language=language)


async def _handle_awaiting_reschedule_selection(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
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
        # Went stale between menu-send and reply -- item 9: dead end, offer
        # the main menu.
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("no_upcoming_to_reschedule", language))
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SELECTION, context)
    await _send_appointment_selection_menu(wa, phone, appointments, "which_appointment_reschedule", language=language)


async def _handle_awaiting_reschedule_slot(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
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
    await _send_slot_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)


async def _handle_awaiting_reschedule_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
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
            await wa.send_text(phone, _append_closing_message(summary, closing_message_text))
            sessions.reset(hospital_id, phone)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, t("reschedule_aborted", language))
            sessions.reset(hospital_id, phone)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_CONFIRM, context)
    await _send_reschedule_confirm(wa, phone, context, language=language)


_HANDLERS = {
    STATE_AWAITING_DEPARTMENT: _handle_awaiting_department,
    STATE_AWAITING_DOCTOR: _handle_awaiting_doctor,
    STATE_AWAITING_DATE: _handle_awaiting_date,
    STATE_AWAITING_TIME_SLOT: _handle_awaiting_time_slot,
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
    closing_message_text: str | None = None,
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

    if state != STATE_IDLE and state not in FREE_TEXT_INPUT_STATES and is_reset_keyword(reply):
        sessions.reset(hospital_id, phone)
        await _handle_idle(wa, sessions, phone, hospital_id, reply, hospital_name, connector, language=language)
        return

    handler = _HANDLERS.get(state)
    if handler is None:
        # IDLE, or any unrecognized/stale state value -> treat as IDLE.
        await _handle_idle(wa, sessions, phone, hospital_id, reply, hospital_name, connector, language=language)
        return

    await handler(
        wa, sessions, phone, hospital_id, reply, context, connector,
        language=language, closing_message_text=closing_message_text,
    )

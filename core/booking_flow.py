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

from connectors import (
    Connector, DuplicateBookingError, MAX_ACTIVE_PATIENT_LINKS, Tier1Connector, TooManyLinkedPatientsError,
)
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
# have either but was explicitly requested this time. Reschedule originally
# kept its own separate single combined slot-list step
# (_send_slot_menu/STATE_AWAITING_RESCHEDULE_SLOT) -- Item 3 (Spec.md
# Section 0) later gave it the same date+time split as booking above, via
# its own STATE_AWAITING_RESCHEDULE_DATE + a repurposed
# STATE_AWAITING_RESCHEDULE_SLOT (now meaning "pick a time").
#
# Patient identity/UX follow-up (Spec.md Section 0), confirmed with the
# user: name/age moved to the FRONT of this sequence -- "Book Appointment"
# tap -> patient name -> patient age -> department -> doctor -> date -> time
# -> confirmation. STATE_AWAITING_PATIENT_NAME/AGE below are unchanged
# states, just entered first now (via _start_booking_flow) instead of last
# (via the old post-time-slot check, now removed from
# _handle_awaiting_time_slot -- see that function's own comment).
STATE_IDLE = "IDLE"
STATE_AWAITING_DEPARTMENT = "AWAITING_DEPARTMENT"
STATE_AWAITING_DOCTOR = "AWAITING_DOCTOR"
STATE_AWAITING_DATE = "AWAITING_DATE"
STATE_AWAITING_TIME_SLOT = "AWAITING_TIME_SLOT"
STATE_AWAITING_PATIENT_NAME = "AWAITING_PATIENT_NAME"
STATE_AWAITING_PATIENT_AGE = "AWAITING_PATIENT_AGE"
STATE_AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
STATE_BOOKED = "BOOKED"  # momentary only — never persisted, see _handle_awaiting_confirmation

# "Go back" navigation: deliberately scoped to exactly the 5 interactive
# (list/button) booking states explicitly requested -- department, doctor,
# date, time slot, confirmation -- not the free-text name/age states (a
# typed "back" there would be indistinguishable from a patient's real
# input, same reasoning FREE_TEXT_INPUT_STATES already exists for), and not
# cancel/reschedule (their own separate, unrequested flows).
STATE_AWAITING_CHANGE_SELECTION = "AWAITING_CHANGE_SELECTION"
BACK_ID = "nav_back"
CHANGE_DEPARTMENT = "change_department"
CHANGE_DOCTOR = "change_doctor"
CHANGE_DATE = "change_date"
CHANGE_TIME = "change_time"
# Confirmation's own Back doesn't pop one step -- there's no single "the"
# field a patient wants to fix -- it routes to this sub-menu instead (no
# existing UX convention in this codebase for "which field do you want to
# change" to follow instead, so this is a new, deliberately minimal one).
_CHANGE_TARGETS = {
    CHANGE_DEPARTMENT: STATE_AWAITING_DEPARTMENT,
    CHANGE_DOCTOR: STATE_AWAITING_DOCTOR,
    CHANGE_DATE: STATE_AWAITING_DATE,
    CHANGE_TIME: STATE_AWAITING_TIME_SLOT,
}
# Context key holding the step-history stack (Section 3.3 follow-up): a list
# of {"state": ..., "context": {...}} frames, one pushed every time a step is
# LEFT (advanced past), each capturing that step's own context as it stood
# at that point -- not nested inside itself, so restoring one frame doesn't
# carry along the frames captured after it. A leading underscore keeps it
# visually distinct from the real booking fields (department_id etc.) this
# context dict otherwise holds, though it's a completely ordinary dict key,
# not a Python-private attribute.
_HISTORY_KEY = "_history"
# Carried forward across ANY back/change-target restore regardless of which
# frame is being restored -- once collected, the patient's own name/age
# doesn't depend on which department/doctor/date/time they end up with, and
# older frames (captured before name/age were ever asked) never have them.
_PRESERVE_ACROSS_BACK = ("patient_name", "patient_age")

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
# "pick which appointment" pattern as cancel; date/slot/confirm reuse the
# booking flow's own date+time-split menus (_send_date_menu/_send_time_menu,
# Section 12.12), scoped to the appointment's existing doctor. Item 3
# (Spec.md Section 0): reschedule used to jump straight to a single combined
# date+time list capped at 10 rows across the doctor's WHOLE availability
# window, silently hiding later dates for a doctor with many slots/day --
# STATE_AWAITING_RESCHEDULE_SLOT now means "pick a TIME for context['date']",
# matching STATE_AWAITING_TIME_SLOT's own meaning in the booking flow, with
# STATE_AWAITING_RESCHEDULE_DATE as the new date-picking step ahead of it.
STATE_AWAITING_RESCHEDULE_SELECTION = "AWAITING_RESCHEDULE_SELECTION"
STATE_AWAITING_RESCHEDULE_DATE = "AWAITING_RESCHEDULE_DATE"
STATE_AWAITING_RESCHEDULE_SLOT = "AWAITING_RESCHEDULE_SLOT"
STATE_AWAITING_RESCHEDULE_CONFIRM = "AWAITING_RESCHEDULE_CONFIRM"

# Patient identity SEPARATION (Spec.md Section 0, plan reviewed with the user
# before this touched production data): one WhatsApp phone can link up to 5
# patient profiles -- STATE_AWAITING_PATIENT_SELECTION is the shared "who is
# this for" step, reused by booking, cancel, reschedule, and (via flows.py's
# import) view_appointments, parameterized by context["patient_flow_next"].
# Only ever shown when >1 active patient is linked -- a single-patient phone
# (every phone that existed before this section, via the migration backfill,
# plus every genuinely new phone's first patient) sees ZERO added friction,
# auto-selected exactly like before this section.
#
# STATE_AWAITING_PATIENT_NAME/AGE (already existed, Section 12.11) are REUSED
# for "add a patient" rather than duplicated -- collecting a name then an age
# is the exact same two-step ask either way; what changes is what happens on
# completion (create_patient_profile() + route via patient_flow_next, not the
# old "stash in context, ask again next booking" behavior this section
# replaces entirely, confirmed with the user).
STATE_AWAITING_PATIENT_SELECTION = "AWAITING_PATIENT_SELECTION"
STATE_AWAITING_MANAGE_PATIENTS_ACTION = "AWAITING_MANAGE_PATIENTS_ACTION"
STATE_AWAITING_UNLINK_CONFIRM = "AWAITING_UNLINK_CONFIRM"

ADD_PATIENT_ROW_ID = "add_patient"
ALL_PATIENTS_ROW_ID = "all_patients"
MANAGE_PATIENTS_ADD_ROW_ID = "manage_add_patient"
_PATIENT_ROW_PREFIX = "patient_"
_UNLINK_ROW_PREFIX = "unlink_"

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


async def _send_back_button(wa: WhatsAppClient, phone: str, language: str = "en") -> None:
    """UX follow-up (Spec.md Section 0), confirmed with the user: "Back" used
    to be the last ROW inside the department/doctor/date/time list itself
    (_cap_rows_with_back, now removed) -- WhatsApp's `list` message type has
    no way to attach a separate button to the SAME message, so showing Back
    visually apart from the real options means sending it as its own
    follow-up buttons message immediately after the list, not folding it
    into one. Same BACK_ID either way -- every handler's `if reply["id"] ==
    BACK_ID` check is unchanged, since core/whatsapp.py's parser normalizes
    a tapped list row and a tapped button to the exact same
    {"type": "interactive_reply", "id": ...} shape regardless of which
    message it came from. Confirmed with the user: no "◀" arrow, and the
    body text showing "Back" a second time (right above a button ALSO
    labeled "Back") read as visibly duplicated -- Meta's button-message
    type requires a non-empty body (a true empty string isn't accepted), so
    a zero-width space is used instead of reusing the word "Back" -- renders
    as a blank line, satisfies the API, and leaves only the button itself
    visibly saying "Back"."""
    await wa.send_buttons(to=phone, body_text="​", buttons=[{"id": BACK_ID, "title": t("back_option", language)}])


def _push_history(context: dict, state: str) -> list[dict]:
    """Returns a NEW history list (the existing one, plus one more frame) --
    called by every handler right before advancing to a new state, so a
    later Back/change-target tap knows exactly where to return to. The
    frame's own context snapshot excludes _HISTORY_KEY itself, so restoring
    a frame later doesn't drag along the frames captured after it."""
    history = list(context.get(_HISTORY_KEY, []))
    snapshot = {k: v for k, v in context.items() if k != _HISTORY_KEY}
    history.append({"state": state, "context": snapshot})
    return history


def _carry_forward_preserved_fields(current_context: dict, restored_context: dict) -> dict:
    for key in _PRESERVE_ACROSS_BACK:
        if key in current_context and key not in restored_context:
            restored_context[key] = current_context[key]
    return restored_context


def _history_pop(context: dict) -> tuple[str, dict] | None:
    """Single-step Back: pops the most recent frame and returns
    (state, restored_context) to resume there, or None if there's nothing
    to go back to (e.g. Back tapped at the very first interactive step)."""
    history = list(context.get(_HISTORY_KEY, []))
    if not history:
        return None
    frame = history.pop()
    restored = dict(frame["context"])
    restored[_HISTORY_KEY] = history
    return frame["state"], _carry_forward_preserved_fields(context, restored)


def _history_pop_to(context: dict, target_state: str) -> dict | None:
    """Multi-step jump (confirmation's "what would you like to change?"
    sub-menu): finds the frame for target_state and restores it, truncating
    history to everything BEFORE that frame -- so a further single-step Back
    from the restored state still walks back correctly one more step."""
    history = context.get(_HISTORY_KEY, [])
    for i, frame in enumerate(history):
        if frame["state"] == target_state:
            restored = dict(frame["context"])
            restored[_HISTORY_KEY] = list(history[:i])
            return _carry_forward_preserved_fields(context, restored)
    return None


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
    await _send_back_button(wa, phone, language=language)


async def _start_booking_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    """Patient identity/UX follow-up (Spec.md Section 0): name/age collection
    moved to the FRONT of the booking flow -- asked immediately after "Book
    Appointment" is tapped, before department selection -- instead of the
    back (after date/time selection, Section 12.11's original placement,
    kept unchanged through Sections 12.12/12.13). Confirmed with the user
    directly (not assumed) before making this change.

    Patient identity SEPARATION (Spec.md Section 0), superseding the
    immediately-prior "ask name every time" behavior (confirmed with the
    user this was a workaround for having no real profile concept yet, now
    replaced): a phone with ZERO linked patients is asked for a name (the
    implicit first/"Self" profile, mirroring the migration backfill's own
    convention); a phone with exactly ONE linked patient auto-selects it and
    proceeds straight to department selection, zero added friction -- the
    same single-patient UX this app has always had; a phone with MORE THAN
    ONE linked patient sees STATE_AWAITING_PATIENT_SELECTION first. Name/age
    is never re-asked for an already-linked patient -- it's captured once,
    at profile creation, then just selected.

    Shared by flows.py's real dispatch (_start_feature) AND this module's
    own standalone _handle_idle() below (superseded for real traffic, but
    still exercised directly by tests/test_booking_flow.py as a standalone
    unit of the state machine -- see this module's docstring) so both entry
    points stay behaviorally identical rather than drifting apart."""
    patients = connector.list_active_patients(hospital_id, phone)
    if not patients:
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, {"patient_flow_next": "booking"})
        await wa.send_text(phone, t("ask_patient_name", language))
        return
    if len(patients) == 1:
        await _select_patient_and_continue(wa, sessions, phone, hospital_id, connector, patients[0], "booking", language=language)
        return
    await _send_patient_selector(wa, sessions, phone, hospital_id, connector, "booking", language=language)


async def _select_patient_and_continue(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, patient: dict,
    next_action: str, language: str = "en",
) -> None:
    """The shared "a patient is now active, what happens next" router --
    reached either via auto-select (exactly one linked patient, zero added
    friction) or an explicit tap in _handle_awaiting_patient_selection."""
    if next_action == "booking":
        context = {
            "active_patient_id": patient["id"], "patient_name": patient["name"], "patient_age": patient["age"],
        }
        sessions.set(hospital_id, phone, STATE_AWAITING_DEPARTMENT, context)
        await _send_department_menu(wa, phone, hospital_id, connector, language=language)
    elif next_action == "cancel":
        await _start_cancel_flow_for_patient(wa, sessions, phone, hospital_id, connector, patient["id"], language=language)
    elif next_action == "reschedule":
        await _start_reschedule_flow_for_patient(wa, sessions, phone, hospital_id, connector, patient["id"], language=language)
    elif next_action == "view_appointments":
        await _send_view_appointments(wa, sessions, phone, hospital_id, connector, language=language, active_patient_id=patient["id"])
    elif next_action == "manage_patients":
        await wa.send_text(phone, t("patient_added", language, patient_name=patient["name"]))
        await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)
    else:
        logger.warning("No _select_patient_and_continue branch for next_action %r -- falling back to main menu", next_action)
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)


async def _send_patient_selector(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, next_action: str,
    language: str = "en",
) -> None:
    """The shared "who is this for" list -- department/doctor/cancel/
    reschedule/view_appointments all reach this the same way, only ever when
    this phone has MORE THAN ONE active linked patient. `next_action` decides
    what happens once a patient is picked (_select_patient_and_continue) and
    whether an "All" row (view_appointments/cancel/reschedule -- there's no
    "book for everyone" equivalent, so booking never offers it) and/or an
    "+ Add Patient" row (booking only, per the user's own spec) are shown."""
    patients = connector.list_active_patients(hospital_id, phone)
    rows = [{"id": _patient_row_id(p["id"]), "title": _patient_row_title(p)} for p in patients]
    if next_action != "booking":
        rows.append({"id": ALL_PATIENTS_ROW_ID, "title": t("all_patients_option", language)})
    if next_action == "booking" and len(patients) < MAX_ACTIVE_PATIENT_LINKS:
        rows.append({"id": ADD_PATIENT_ROW_ID, "title": t("add_patient_option", language)})
    rows = _cap_rows(rows, "patient selector")
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_SELECTION, {"patient_flow_next": next_action})
    await wa.send_list(
        to=phone,
        body_text=t(f"patient_selector_prompt_{next_action}", language),
        button_text=t("patient_selector_button", language),
        sections=[{"title": t("patient_selector_section_title", language), "rows": rows}],
    )


async def _handle_awaiting_patient_selection(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    next_action = context.get("patient_flow_next", "booking")
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == ADD_PATIENT_ROW_ID and next_action == "booking":
            sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, {"patient_flow_next": next_action})
            await wa.send_text(phone, t("ask_patient_name", language))
            return
        if rid == ALL_PATIENTS_ROW_ID and next_action != "booking":
            await _select_patient_and_continue(
                wa, sessions, phone, hospital_id, connector, {"id": None, "name": None, "age": None},
                next_action, language=language,
            )
            return
        patient_id = _parse_patient_row_id(rid)
        if patient_id is not None:
            patients = connector.list_active_patients(hospital_id, phone)
            match = next((p for p in patients if p["id"] == patient_id), None)
            if match:
                await _select_patient_and_continue(wa, sessions, phone, hospital_id, connector, match, next_action, language=language)
                return
    # Stale/unrecognized tap, or the list went stale between send and reply
    # (a patient was unlinked meanwhile) -- re-fetch and re-show fresh rather
    # than acting on a stale id (Phase 8's established "recheck dynamic
    # data" discipline).
    patients = connector.list_active_patients(hospital_id, phone)
    if len(patients) <= 1 and next_action != "booking":
        # Down to (at most) one patient since this selector was sent --
        # nothing left to disambiguate, just proceed.
        if patients:
            await _select_patient_and_continue(wa, sessions, phone, hospital_id, connector, patients[0], next_action, language=language)
        else:
            await _select_patient_and_continue(
                wa, sessions, phone, hospital_id, connector, {"id": None, "name": None, "age": None},
                next_action, language=language,
            )
        return
    await _send_patient_selector(wa, sessions, phone, hospital_id, connector, next_action, language=language)


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
    await _send_back_button(wa, phone, language=language)


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
    await _send_back_button(wa, phone, language=language)


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
    await _send_back_button(wa, phone, language=language)


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

    Section 12.12, extended by Item 3 (Spec.md Section 0): target_state tells
    this which flow is recovering -- STATE_AWAITING_TIME_SLOT (booking) and
    STATE_AWAITING_RESCHEDULE_SLOT (reschedule, since its own date/time split)
    both now mean "pick a time for context['date']", so both re-show just
    that date's times via _send_time_menu."""
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
    if target_state in (STATE_AWAITING_TIME_SLOT, STATE_AWAITING_RESCHEDULE_SLOT):
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
            {"id": BACK_ID, "title": t("back_option", language)},
        ],
    )


async def _send_change_selection_menu(wa: WhatsAppClient, phone: str, language: str = "en") -> None:
    """Confirmation's own Back: there's no single "the" field to pop back to,
    so this asks which one instead (see the module-level comment by
    _CHANGE_TARGETS for why)."""
    rows = [
        {"id": CHANGE_DEPARTMENT, "title": t("change_department_option", language)},
        {"id": CHANGE_DOCTOR, "title": t("change_doctor_option", language)},
        {"id": CHANGE_DATE, "title": t("change_date_option", language)},
        {"id": CHANGE_TIME, "title": t("change_time_option", language)},
    ]
    await wa.send_list(
        to=phone,
        body_text=t("what_would_you_like_to_change", language),
        button_text=t("view_change_options_button", language),
        sections=[{"title": t("change_options_section_title", language), "rows": rows}],
    )


async def _resend_menu_for_state(
    wa: WhatsAppClient, phone: str, hospital_id: int, state: str, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    """Dispatches to whichever menu builder matches a restored state -- used
    after both a single-step Back (_history_pop) and a change-target jump
    (_history_pop_to) land on one of the 4 list states, so the patient
    actually sees the list to pick from again, not just a silent state change."""
    if state == STATE_AWAITING_DEPARTMENT:
        await _send_department_menu(wa, phone, hospital_id, connector, language=language)
    elif state == STATE_AWAITING_DOCTOR:
        await _send_doctor_menu(
            wa, phone, hospital_id, context["department_id"], context["department_name"], connector,
            language=language,
        )
    elif state == STATE_AWAITING_DATE:
        await _send_date_menu(
            wa, phone, hospital_id, context["doctor_id"], context["doctor_name"], connector, language=language,
        )
    elif state == STATE_AWAITING_TIME_SLOT:
        await _send_time_menu(
            wa, phone, hospital_id, context["doctor_id"], context["date"], connector, language=language,
        )


async def _handle_back_navigation(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    """Shared BACK_ID handler for the 4 list states (confirmation's Back is
    handled separately in _handle_awaiting_confirmation -- it jumps to the
    change-selection sub-menu, not a single popped frame). Popping with
    nothing left in the history (Back tapped at the very first interactive
    step, department) falls back to the main menu -- there's nowhere earlier
    in the booking flow to return to."""
    popped = _history_pop(context)
    if popped is None:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    state, restored_context = popped
    sessions.set(hospital_id, phone, state, restored_context)
    await _resend_menu_for_state(wa, phone, hospital_id, state, restored_context, connector, language=language)


def _appointment_row_id(appointment_id: int) -> str:
    return f"appt_{appointment_id}"


def _parse_appointment_row_id(row_id: str) -> int | None:
    if not row_id.startswith("appt_"):
        return None
    try:
        return int(row_id[len("appt_"):])
    except ValueError:
        return None


def _patient_row_id(patient_id: int) -> str:
    return f"{_PATIENT_ROW_PREFIX}{patient_id}"


def _parse_patient_row_id(row_id: str) -> int | None:
    if not row_id.startswith(_PATIENT_ROW_PREFIX):
        return None
    try:
        return int(row_id[len(_PATIENT_ROW_PREFIX):])
    except ValueError:
        return None


def _unlink_row_id(patient_id: int) -> str:
    return f"{_UNLINK_ROW_PREFIX}{patient_id}"


def _parse_unlink_row_id(row_id: str) -> int | None:
    if not row_id.startswith(_UNLINK_ROW_PREFIX):
        return None
    try:
        return int(row_id[len(_UNLINK_ROW_PREFIX):])
    except ValueError:
        return None


def _patient_row_title(patient: dict) -> str:
    label = patient.get("relationship_label")
    return f"{patient['name']} ({label})" if label else patient["name"]


# Items 3/5/6 (Spec.md Section 0): quick-action ids embedding a SPECIFIC
# appointment id, attached to the booking-success message, the
# duplicate-booking block message, and My Appointments' per-appointment
# actions -- tapping one routes straight into that appointment's own cancel/
# reschedule confirm step, skipping the "which appointment" re-identification
# a generic Cancel/Reschedule menu tap would otherwise require. Recognized
# from ANY session state (flows.py checks for these before normal state
# dispatch), since the message carrying them may be tapped long after the
# session that sent it has expired.
MANAGE_CANCEL_PREFIX = "manage_cancel_"
MANAGE_RESCHEDULE_PREFIX = "manage_reschedule_"
GOTO_MAIN_MENU = "goto_main_menu"


def _manage_cancel_id(appointment_id: int) -> str:
    return f"{MANAGE_CANCEL_PREFIX}{appointment_id}"


def _manage_reschedule_id(appointment_id: int) -> str:
    return f"{MANAGE_RESCHEDULE_PREFIX}{appointment_id}"


def _parse_manage_id(row_id: str, prefix: str) -> int | None:
    if not row_id.startswith(prefix):
        return None
    try:
        return int(row_id[len(prefix):])
    except ValueError:
        return None


async def _start_cancel_flow_for_appointment(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, appt, language: str = "en",
) -> None:
    """Jumps straight to THIS appointment's own cancel-confirm step, skipping
    the "which appointment" selection list -- the shared target for the
    booking-success/duplicate-booking quick-action buttons and My
    Appointments' inline actions."""
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_CONFIRM, {"appointment_id": appt.id})
    await _send_cancel_confirm(wa, phone, appt, language=language)


async def _start_reschedule_flow_for_appointment(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, appt, connector: Connector, language: str = "en",
) -> None:
    """Same as _start_cancel_flow_for_appointment above, for reschedule --
    jumps straight to this appointment's doctor's date list (Item 3, Spec.md
    Section 0), scoped to the appointment's existing doctor (no re-picking
    department/doctor)."""
    if not connector.get_available_slots(hospital_id, appt.doctor_id):
        await _notify_no_slots_available(wa, sessions, hospital_id, phone, appt.doctor_name, language=language)
        return
    new_context = {
        "reschedule_appointment_id": appt.id,
        "department_id": appt.department_id,
        "department_name": appt.department_name,
        "doctor_id": appt.doctor_id,
        "doctor_name": appt.doctor_name,
        # Patient identity SEPARATION (Spec.md Section 0): carries the
        # ORIGINAL appointment's own patient through the reschedule -- without
        # this, a multi-patient phone rescheduling would have no way to know
        # which linked family member's appointment is being moved.
        "active_patient_id": appt.patient_id,
    }
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_DATE, new_context)
    await _send_date_menu(wa, phone, hospital_id, appt.doctor_id, appt.doctor_name, connector, language=language)


async def _send_appointment_selection_menu(
    wa: WhatsAppClient, phone: str, appointments: list, body_key: str, language: str = "en",
    patient_names: dict[int, str] | None = None,
) -> None:
    """Patient identity SEPARATION (Spec.md Section 0): `patient_names`, when
    given (a multi-patient phone viewing an unfiltered "All" list), prefixes
    each row with that appointment's own patient name so it's unambiguous
    whose appointment is whose -- omitted entirely for the common
    single-patient case, unchanged from before this section."""
    rows = []
    for a in appointments:
        title = a.doctor_name
        if patient_names and a.patient_id in patient_names:
            title = f"{patient_names[a.patient_id]} — {a.doctor_name}"
        rows.append({
            "id": _appointment_row_id(a.id),
            "title": title,
            "description": a.scheduled_at.strftime("%a %d %b %Y, %H:%M"),
        })
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
            await _start_booking_flow(wa, sessions, phone, hospital_id, connector, language=language)
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
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        dept = _find_by_id(connector.get_departments(hospital_id), reply["id"])
        if dept:
            if not connector.get_doctors(hospital_id, dept["id"]):
                await _notify_no_doctors_available(wa, sessions, hospital_id, phone, dept["name"], language=language)
                return
            # Bug fix (Section 3.3 "Go back" follow-up): this branch used to
            # build new_context from scratch with no **context spread, unlike
            # every other handler below -- silently dropping _history/
            # patient_name/patient_age if a patient reached here via the
            # confirmation screen's "change department" path. Explicit
            # carry-forward instead of a blanket spread, since department_id/
            # name from the OLD pick must NOT survive a fresh department pick.
            history = _push_history(context, STATE_AWAITING_DEPARTMENT)
            new_context = {"department_id": dept["id"], "department_name": dept["name"], _HISTORY_KEY: history}
            new_context = _carry_forward_preserved_fields(context, new_context)
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
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        doctor = _find_by_id(connector.get_doctors(hospital_id, department_id), reply["id"])
        if doctor:
            if not connector.get_available_slots(hospital_id, doctor["id"]):
                await _notify_no_slots_available(wa, sessions, hospital_id, phone, doctor["name"], language=language)
                return
            history = _push_history(context, STATE_AWAITING_DOCTOR)
            new_context = {**context, "doctor_id": doctor["id"], "doctor_name": doctor["name"], _HISTORY_KEY: history}
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
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        available_dates = {s["date"] for s in connector.get_available_slots(hospital_id, doctor_id)}
        if reply["id"] in available_dates:
            history = _push_history(context, STATE_AWAITING_DATE)
            new_context = {**context, "date": reply["id"], "date_label": _date_label(reply["id"]), _HISTORY_KEY: history}
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
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        slot = _find_by_id(connector.get_available_slots(hospital_id, doctor_id), reply["id"])
        if slot and slot["date"] == date_str:
            new_context = {
                **context,
                "slot_id": slot["id"],
                "slot_date": slot["date"],
                "slot_time": slot["time"],
                _HISTORY_KEY: _push_history(context, STATE_AWAITING_TIME_SLOT),
            }
            # Patient identity/UX follow-up (Spec.md Section 0): name/age is
            # now collected BEFORE department selection (_start_booking_flow),
            # so context always already has both by the time a slot is
            # picked -- including on a double-booking-race re-entry into this
            # exact state (_handle_slot_taken re-sets STATE_AWAITING_TIME_SLOT
            # with context unchanged) -- straight to confirmation, no mid-flow
            # name/age ask needed anymore.
            sessions.set(hospital_id, phone, STATE_AWAITING_CONFIRMATION, new_context)
            await _send_confirmation(wa, phone, new_context, language=language)
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
    db.is_valid_phone() at the staff new-booking form).

    Patient identity SEPARATION (Spec.md Section 0): a valid age now creates
    a real `patients` row + `patient_links` link (connector.create_patient_profile)
    instead of just stashing name/age in context -- this is the ONE place a
    new patient profile is ever created from the WhatsApp chat itself (both
    the implicit-first-profile path and "+ Add Patient" from the selector
    funnel through here, distinguished only by `patient_flow_next`). Routes
    onward via _select_patient_and_continue using whatever next_action was
    stashed when this state was entered, so "Add Patient" tapped mid-cancel/
    reschedule/view_appointments returns to that flow, not always booking."""
    age = _parse_patient_age(reply["text"]) if reply["type"] == "text" else None
    if age is None:
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, context)
        await wa.send_text(phone, t("invalid_patient_age", language))
        await wa.send_text(phone, t("ask_patient_age", language, patient_name=context.get("patient_name", "")))
        return
    next_action = context.get("patient_flow_next", "booking")
    try:
        patient = connector.create_patient_profile(hospital_id, phone, context["patient_name"], age)
    except TooManyLinkedPatientsError:
        await wa.send_text(phone, t("too_many_linked_patients", language))
        if next_action == "manage_patients":
            await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)
        else:
            sessions.reset(hospital_id, phone)
            await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    await _select_patient_and_continue(wa, sessions, phone, hospital_id, connector, patient, next_action, language=language)


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
                    patient_id=context.get("active_patient_id"),
                )
            except DuplicateBookingError as exc:
                # Item 5: must be checked BEFORE the generic IntegrityError
                # catch below -- DuplicateBookingError IS an IntegrityError
                # (same subclassing pattern as QuotaExceededError), so the
                # more specific except has to come first or this branch is
                # unreachable. Offer the SAME quick-action pattern the
                # booking-success message uses (item 3), scoped to the
                # already-existing appointment, not a generic error.
                sessions.reset(hospital_id, phone)
                existing = next(
                    (a for a in connector.get_upcoming_appointments(hospital_id, phone=phone)
                     if a.id == exc.existing_appointment_id),
                    None,
                )
                doctor_name = existing.doctor_name if existing else context.get("doctor_name", "")
                await wa.send_buttons(
                    to=phone,
                    body_text=t("duplicate_booking_text", language, doctor_name=doctor_name),
                    buttons=[
                        {"id": GOTO_MAIN_MENU, "title": t("main_menu_button", language)},
                        {"id": _manage_cancel_id(exc.existing_appointment_id), "title": t("cancel_button", language)},
                        {"id": _manage_reschedule_id(exc.existing_appointment_id), "title": t("reschedule_short", language)},
                    ],
                )
                return
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
            summary = _append_closing_message(summary, closing_message_text)
            # Item 3: quick-action buttons attached to the success message --
            # tapping any of them, even long after this session has expired,
            # routes straight into that flow for THIS specific appointment
            # (flows.py checks for these ids before normal session dispatch).
            await wa.send_buttons(
                to=phone,
                body_text=summary,
                buttons=[
                    {"id": GOTO_MAIN_MENU, "title": t("main_menu_button", language)},
                    {"id": _manage_cancel_id(appointment.id), "title": t("cancel_button", language)},
                    {"id": _manage_reschedule_id(appointment.id), "title": t("reschedule_short", language)},
                ],
            )
            # STATE_BOOKED is terminal and resets to IDLE immediately — there's no
            # separate incoming message that moves it out of BOOKED, so it's never
            # actually written to the session store.
            #
            # Language-reset follow-up (Spec.md Section 0): a FULLY COMPLETED
            # booking specifically clears the chosen language too
            # (keep_language=False) -- the next fresh conversation from this
            # patient shows the language picker again, rather than assuming
            # the last-used language forever. Every OTHER reset() call site
            # in this file (decline, cancel flow, reschedule, stale-session
            # cleanup, ...) is deliberately untouched and keeps preserving
            # language, per Section 12.11's original "only ask once per
            # fresh conversation" reasoning -- this is a narrow, deliberate
            # exception for the one specific event requested, not a general
            # policy change.
            sessions.reset(hospital_id, phone, keep_language=False)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, t("booking_not_confirmed", language))
            sessions.reset(hospital_id, phone)
            return
        if rid == BACK_ID:
            sessions.set(hospital_id, phone, STATE_AWAITING_CHANGE_SELECTION, context)
            await _send_change_selection_menu(wa, phone, language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_CONFIRMATION, context)
    await _send_confirmation(wa, phone, context, language=language)


async def _handle_awaiting_change_selection(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Confirmation's "what would you like to change?" sub-menu -- jumps
    (multi-step, via _history_pop_to) straight to the chosen field's own
    list state rather than a single popped frame, since the patient may be
    fixing a field several steps back (e.g. department) from confirmation."""
    if reply["type"] == "interactive_reply":
        target_state = _CHANGE_TARGETS.get(reply["id"])
        if target_state:
            restored_context = _history_pop_to(context, target_state)
            if restored_context is not None:
                sessions.set(hospital_id, phone, target_state, restored_context)
                await _resend_menu_for_state(wa, phone, hospital_id, target_state, restored_context, connector, language=language)
                return
            # No matching frame in history (shouldn't normally happen --
            # every state on the path to confirmation pushes one) -- fail
            # safe back to the main menu rather than getting stuck.
            sessions.reset(hospital_id, phone)
            await _send_main_menu(wa, phone, "the hospital", language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_CHANGE_SELECTION, context)
    await _send_change_selection_menu(wa, phone, language=language)


# --- Cancel flow (SPEC Section 3.3/5) ---

async def _start_cancel_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    """Patient identity SEPARATION (Spec.md Section 0): a "whose
    appointments" pre-step, only shown when this phone has more than one
    active linked patient -- the single-patient case (every phone before
    this section, and any phone with just one linked patient) goes straight
    to _start_cancel_flow_for_patient() below, zero added friction."""
    patients = connector.list_active_patients(hospital_id, phone)
    if len(patients) > 1:
        await _send_patient_selector(wa, sessions, phone, hospital_id, connector, "cancel", language=language)
        return
    await _start_cancel_flow_for_patient(wa, sessions, phone, hospital_id, connector, None, language=language)


async def _start_cancel_flow_for_patient(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector,
    active_patient_id: int | None, language: str = "en",
) -> None:
    """The actual "which appointment" list, scoped to `active_patient_id`
    when given -- None means "show everyone linked to this phone" (the
    natural single-patient case, or the explicit "All" choice from the
    patient selector), with each row prefixed by its own patient's name
    whenever more than one patient could plausibly be shown."""
    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    patient_names = None
    if active_patient_id is not None:
        appointments = [a for a in appointments if a.patient_id == active_patient_id]
    else:
        patients = connector.list_active_patients(hospital_id, phone)
        if len(patients) > 1:
            patient_names = {p["id"]: p["name"] for p in patients}
    if not appointments:
        # Item 9: nothing to cancel is a dead end without a menu offered.
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("no_upcoming_to_cancel", language))
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_SELECTION, {"active_patient_id": active_patient_id})
    await _send_appointment_selection_menu(
        wa, phone, appointments, "which_appointment_cancel", language=language, patient_names=patient_names,
    )


async def _handle_awaiting_cancel_selection(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    appt = _find_selected_appointment(hospital_id, phone, reply, connector)
    if appt:
        await _start_cancel_flow_for_appointment(wa, sessions, phone, hospital_id, appt, language=language)
        return
    # Went stale between menu-send and reply, or an unrecognized tap --
    # re-show the same (patient-scoped) list rather than a dead end.
    await _start_cancel_flow_for_patient(
        wa, sessions, phone, hospital_id, connector, context.get("active_patient_id"), language=language,
    )


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
# Selection reuses the cancel flow's "pick which appointment" pattern; the
# date/slot(time) steps reuse the booking flow's own _send_date_menu/
# _send_time_menu (Item 3, Spec.md Section 0), scoped to the appointment's
# existing doctor (no re-picking department/doctor).

async def _start_reschedule_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    """Patient identity SEPARATION (Spec.md Section 0): same "whose
    appointments" pre-step as cancel above, only shown when >1 active
    patient is linked."""
    patients = connector.list_active_patients(hospital_id, phone)
    if len(patients) > 1:
        await _send_patient_selector(wa, sessions, phone, hospital_id, connector, "reschedule", language=language)
        return
    await _start_reschedule_flow_for_patient(wa, sessions, phone, hospital_id, connector, None, language=language)


async def _start_reschedule_flow_for_patient(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector,
    active_patient_id: int | None, language: str = "en",
) -> None:
    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    patient_names = None
    if active_patient_id is not None:
        appointments = [a for a in appointments if a.patient_id == active_patient_id]
    else:
        patients = connector.list_active_patients(hospital_id, phone)
        if len(patients) > 1:
            patient_names = {p["id"]: p["name"] for p in patients}
    if not appointments:
        # Item 9: nothing to reschedule is a dead end without a menu offered.
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("no_upcoming_to_reschedule", language))
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SELECTION, {"active_patient_id": active_patient_id})
    await _send_appointment_selection_menu(
        wa, phone, appointments, "which_appointment_reschedule", language=language, patient_names=patient_names,
    )


async def _handle_awaiting_reschedule_selection(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    appt = _find_selected_appointment(hospital_id, phone, reply, connector)
    if appt:
        await _start_reschedule_flow_for_appointment(wa, sessions, phone, hospital_id, appt, connector, language=language)
        return
    # Went stale between menu-send and reply, or an unrecognized tap --
    # re-show the same (patient-scoped) list rather than a dead end.
    await _start_reschedule_flow_for_patient(
        wa, sessions, phone, hospital_id, connector, context.get("active_patient_id"), language=language,
    )


async def _handle_awaiting_reschedule_date(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Item 3 (Spec.md Section 0), reschedule's own date-picking step, mirrors
    the booking flow's _handle_awaiting_date -- no name/age involved here, so
    it's simpler: a picked date just moves on to that date's time list.
    Reschedule doesn't use the booking flow's full history-stack Back
    mechanism (it never had one), but reusing _send_date_menu means a Back
    button is now shown here too (_send_back_button, sent as a follow-up
    message after the list) -- a single linear step back to appointment
    selection is enough to make that button do something rather than
    silently no-op."""
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    if not doctor_id or context.get("reschedule_appointment_id") is None:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _start_reschedule_flow(wa, sessions, phone, hospital_id, connector, language=language)
            return
        available_dates = {s["date"] for s in connector.get_available_slots(hospital_id, doctor_id)}
        if reply["id"] in available_dates:
            new_context = {**context, "date": reply["id"], "date_label": _date_label(reply["id"])}
            sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SLOT, new_context)
            await _send_time_menu(wa, phone, hospital_id, doctor_id, reply["id"], connector, language=language)
            return
    if not connector.get_available_slots(hospital_id, doctor_id):
        await _notify_no_slots_available(wa, sessions, hospital_id, phone, doctor_name, language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_DATE, context)
    await _send_date_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)


async def _handle_awaiting_reschedule_slot(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Item 3 (Spec.md Section 0): now the TIME step for context['date'],
    mirroring the booking flow's _handle_awaiting_time_slot -- no name/age
    involved here either, so a picked time goes straight to reschedule
    confirm."""
    doctor_id = context.get("doctor_id")
    doctor_name = context.get("doctor_name", "")
    date_str = context.get("date")
    if not doctor_id or not date_str or context.get("reschedule_appointment_id") is None:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_DATE, context)
            await _send_date_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)
            return
        slot = _find_by_id(connector.get_available_slots(hospital_id, doctor_id), reply["id"])
        if slot and slot["date"] == date_str:
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
    if not any(s["date"] == date_str for s in connector.get_available_slots(hospital_id, doctor_id)):
        # This date specifically emptied out (not necessarily the whole
        # doctor) -- step back to date selection, same as the booking flow's
        # own _handle_awaiting_time_slot.
        sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_DATE, context)
        await _send_date_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_RESCHEDULE_SLOT, context)
    await _send_time_menu(wa, phone, hospital_id, doctor_id, date_str, connector, language=language)


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
                    patient_id=context.get("active_patient_id"),
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


STATE_AWAITING_VIEW_APPOINTMENT_ACTION = "AWAITING_VIEW_APPOINTMENT_ACTION"


async def _start_view_appointments_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    """Patient identity SEPARATION (Spec.md Section 0): same "whose
    appointments" pre-step as cancel/reschedule above, only shown when >1
    active patient is linked. Relocated here from flows.py (was
    _send_view_appointments, called directly) so the shared patient
    selector can reach it without a circular import -- this module never
    imports flows.py, but the selector needs to route booking, cancel,
    reschedule, AND view_appointments, so all four now live here."""
    patients = connector.list_active_patients(hospital_id, phone)
    if len(patients) > 1:
        await _send_patient_selector(wa, sessions, phone, hospital_id, connector, "view_appointments", language=language)
        return
    await _send_view_appointments(wa, sessions, phone, hospital_id, connector, language=language)


async def _send_view_appointments(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
    active_patient_id: int | None = None,
) -> None:
    """Item 6 (Spec.md Section 0): each listed appointment is now a tappable
    row (not just a plain-text summary) -- picking one shows THAT
    appointment's own Cancel/Reschedule quick actions directly. Patient
    identity SEPARATION: scoped to `active_patient_id` when given (a
    specific family member was selected); None means "show everyone linked
    to this phone" (the natural single-patient case, or the explicit "All"
    choice from the patient selector), with each row prefixed by its own
    patient's name whenever more than one patient could plausibly be
    shown."""
    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    patient_names = None
    if active_patient_id is not None:
        appointments = [a for a in appointments if a.patient_id == active_patient_id]
    else:
        patients = connector.list_active_patients(hospital_id, phone)
        if len(patients) > 1:
            patient_names = {p["id"]: p["name"] for p in patients}
    if not appointments:
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t("view_appointments_list", language))
        return
    rows = []
    for a in appointments:
        title = a.doctor_name
        if patient_names and a.patient_id in patient_names:
            title = f"{patient_names[a.patient_id]} — {a.doctor_name}"
        rows.append({
            "id": _appointment_row_id(a.id),
            "title": title,
            "description": f"{a.department_name} — {a.scheduled_at.strftime('%a %d %b %Y, %H:%M')}",
        })
    rows = _cap_rows(rows, "view appointments menu")
    sessions.set(hospital_id, phone, STATE_AWAITING_VIEW_APPOINTMENT_ACTION, {"active_patient_id": active_patient_id})
    await wa.send_list(
        to=phone,
        body_text=t("view_appointments_header", language),
        button_text=t("view_appointments_button", language),
        sections=[{"title": t("your_appointments_section_title", language), "rows": rows}],
    )


async def _handle_awaiting_view_appointment_action(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    appt_id = _parse_appointment_row_id(reply["id"]) if reply["type"] == "interactive_reply" else None
    appt = None
    if appt_id is not None:
        appt = next(
            (a for a in connector.get_upcoming_appointments(hospital_id, phone=phone) if a.id == appt_id), None,
        )
    if appt is None:
        # Stale/unrecognized tap, or the list went stale between send and
        # reply -- re-show the current (patient-scoped) list rather than a
        # dead end.
        await _send_view_appointments(
            wa, sessions, phone, hospital_id, connector, language=language,
            active_patient_id=context.get("active_patient_id"),
        )
        return
    sessions.reset(hospital_id, phone)
    await wa.send_buttons(
        to=phone,
        body_text=t("manage_appointment_prompt", language, doctor_name=appt.doctor_name),
        buttons=[
            {"id": GOTO_MAIN_MENU, "title": t("main_menu_button", language)},
            {"id": _manage_cancel_id(appt.id), "title": t("cancel_button", language)},
            {"id": _manage_reschedule_id(appt.id), "title": t("reschedule_short", language)},
        ],
    )


# --- Manage Patients (Spec.md Section 0) ---
# View/add/unlink the patients linked to this phone. Add reuses
# STATE_AWAITING_PATIENT_NAME/AGE (patient_flow_next="manage_patients"),
# same as booking's implicit-first-profile and selector "+ Add Patient"
# paths -- see _handle_awaiting_patient_age.

async def _start_manage_patients_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    patients = connector.list_active_patients(hospital_id, phone)
    rows = [{"id": _patient_row_id(p["id"]), "title": _patient_row_title(p)} for p in patients]
    if len(patients) < MAX_ACTIVE_PATIENT_LINKS:
        rows.append({"id": MANAGE_PATIENTS_ADD_ROW_ID, "title": t("add_patient_option", language)})
    rows = _cap_rows(rows, "manage patients list")
    sessions.set(hospital_id, phone, STATE_AWAITING_MANAGE_PATIENTS_ACTION, {})
    await wa.send_list(
        to=phone,
        body_text=t("manage_patients_header", language),
        button_text=t("manage_patients_button", language),
        sections=[{"title": t("manage_patients_section_title", language), "rows": rows}],
    )


async def _handle_awaiting_manage_patients_action(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == MANAGE_PATIENTS_ADD_ROW_ID:
            patients = connector.list_active_patients(hospital_id, phone)
            if len(patients) >= MAX_ACTIVE_PATIENT_LINKS:
                await wa.send_text(phone, t("too_many_linked_patients", language))
                await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)
                return
            sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, {"patient_flow_next": "manage_patients"})
            await wa.send_text(phone, t("ask_patient_name", language))
            return
        patient_id = _parse_patient_row_id(rid)
        if patient_id is not None:
            patients = connector.list_active_patients(hospital_id, phone)
            match = next((p for p in patients if p["id"] == patient_id), None)
            if match:
                sessions.set(
                    hospital_id, phone, STATE_AWAITING_UNLINK_CONFIRM,
                    {"unlink_patient_id": patient_id, "unlink_patient_name": match["name"]},
                )
                await wa.send_buttons(
                    to=phone,
                    body_text=t("unlink_patient_confirm", language, patient_name=match["name"]),
                    buttons=[
                        {"id": CONFIRM_YES, "title": t("confirm_button", language)},
                        {"id": CONFIRM_NO, "title": t("cancel_button", language)},
                    ],
                )
                return
    # Stale/unrecognized tap, or the list went stale between send and reply
    # -- re-fetch and re-show fresh rather than acting on a stale id.
    await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)


async def _handle_awaiting_unlink_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    patient_id = context.get("unlink_patient_id")
    patient_name = context.get("unlink_patient_name", "")
    if reply["type"] == "interactive_reply" and patient_id is not None:
        if reply["id"] == CONFIRM_YES:
            # Soft-unlink only -- unlink_patient() sets patient_links.unlinked_at
            # and never touches `patients`/`appointments`, so this patient's
            # booking history and Patient ID are completely unaffected.
            connector.unlink_patient(hospital_id, phone, patient_id)
            await wa.send_text(phone, t("patient_unlinked", language, patient_name=patient_name))
            await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)
            return
        if reply["id"] == CONFIRM_NO:
            await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_UNLINK_CONFIRM, context)
    await wa.send_buttons(
        to=phone,
        body_text=t("unlink_patient_confirm", language, patient_name=patient_name),
        buttons=[
            {"id": CONFIRM_YES, "title": t("confirm_button", language)},
            {"id": CONFIRM_NO, "title": t("cancel_button", language)},
        ],
    )


_HANDLERS = {
    STATE_AWAITING_DEPARTMENT: _handle_awaiting_department,
    STATE_AWAITING_DOCTOR: _handle_awaiting_doctor,
    STATE_AWAITING_DATE: _handle_awaiting_date,
    STATE_AWAITING_TIME_SLOT: _handle_awaiting_time_slot,
    STATE_AWAITING_PATIENT_NAME: _handle_awaiting_patient_name,
    STATE_AWAITING_PATIENT_AGE: _handle_awaiting_patient_age,
    STATE_AWAITING_CONFIRMATION: _handle_awaiting_confirmation,
    STATE_AWAITING_CHANGE_SELECTION: _handle_awaiting_change_selection,
    STATE_AWAITING_CANCEL_SELECTION: _handle_awaiting_cancel_selection,
    STATE_AWAITING_CANCEL_CONFIRM: _handle_awaiting_cancel_confirm,
    STATE_AWAITING_RESCHEDULE_SELECTION: _handle_awaiting_reschedule_selection,
    STATE_AWAITING_RESCHEDULE_DATE: _handle_awaiting_reschedule_date,
    STATE_AWAITING_RESCHEDULE_SLOT: _handle_awaiting_reschedule_slot,
    STATE_AWAITING_RESCHEDULE_CONFIRM: _handle_awaiting_reschedule_confirm,
    STATE_AWAITING_VIEW_APPOINTMENT_ACTION: _handle_awaiting_view_appointment_action,
    STATE_AWAITING_PATIENT_SELECTION: _handle_awaiting_patient_selection,
    STATE_AWAITING_MANAGE_PATIENTS_ACTION: _handle_awaiting_manage_patients_action,
    STATE_AWAITING_UNLINK_CONFIRM: _handle_awaiting_unlink_confirm,
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

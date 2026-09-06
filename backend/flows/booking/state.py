# flows/booking/state.py
"""
ARCHITECTURE_PLAN.md Phase 3b: session-state constants, the step-history
stack, and row-id encode/decode helpers for the booking/cancel/reschedule/
view-appointments/manage-patients state machine. Pure functions and
constants only -- no WhatsApp/connector/db dependency -- split out of the
former single core/booking_flow.py module.
"""
from datetime import datetime

from flows.common import MAX_LIST_ROWS, RESET_KEYWORDS, cap_rows

STATE_IDLE = "IDLE"


STATE_AWAITING_APPOINTMENT_TYPE = "AWAITING_APPOINTMENT_TYPE"


# docs/per-appointment-type-flow-plan.md Phase 2 Step 2 follow-up: the
# eligible-consultations LIST step (one row per department's most recent
# ATTENDED appointment still within the hospital's eligibility window) --
# replaces the earlier single-visit auto-select + confirm-before-date screen.
STATE_AWAITING_FOLLOWUP_SELECTION = "AWAITING_FOLLOWUP_SELECTION"


STATE_AWAITING_CONSENT = "AWAITING_CONSENT"


STATE_AWAITING_DEPARTMENT = "AWAITING_DEPARTMENT"


STATE_AWAITING_DOCTOR = "AWAITING_DOCTOR"


STATE_AWAITING_DATE = "AWAITING_DATE"


STATE_AWAITING_TIME_SLOT = "AWAITING_TIME_SLOT"


# Daycare/Procedure rebuild: Step 1 picks a procedure from its own catalog
# (category + booking mode), replacing the old duration-picker flow entirely
# -- see flows/booking/types/procedure.py.
STATE_AWAITING_PROCEDURE = "AWAITING_PROCEDURE"


# Approval-required procedures' own pre-send review screen (spec Step 3) --
# reached instead of date/time, no slot is ever asked until hospital approval.
STATE_AWAITING_PROCEDURE_REQUEST_CONFIRM = "AWAITING_PROCEDURE_REQUEST_CONFIRM"


# "Request Reschedule" for an approval-required procedure's own date/time
# pick (own split date/then/time steps, same shape as every other date/time
# pair in this app) -- writes the desired slot onto the appointment for
# staff to approve, never calls the normal instant reschedule path. See
# flows/booking/reschedule.py.
STATE_AWAITING_PROCEDURE_RESCHEDULE_DATE = "AWAITING_PROCEDURE_RESCHEDULE_DATE"
STATE_AWAITING_PROCEDURE_RESCHEDULE_SLOT = "AWAITING_PROCEDURE_RESCHEDULE_SLOT"


# Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5):
# picking which test, then which variant, before date/time -- see
# flows/booking/types/_diagnostic_shared.py.
STATE_AWAITING_DIAGNOSTIC_TEST = "AWAITING_DIAGNOSTIC_TEST"


STATE_AWAITING_DIAGNOSTIC_VARIANT = "AWAITING_DIAGNOSTIC_VARIANT"


# Lab Test Phase 2 follow-up (business spec Sections 4.1-4.4): unlike
# Diagnostic Test above, Lab Test is a multi-test BASKET (this state repeats,
# once per test added) with its own collection-method/home-collection steps
# before date/time -- see flows/booking/types/lab.py.
STATE_AWAITING_LAB_TEST = "AWAITING_LAB_TEST"


# A dedicated state, not a reuse of STATE_AWAITING_DIAGNOSTIC_VARIANT -- that
# one's handler (_handle_awaiting_diagnostic_variant) assigns a SINGLE
# variant onto context and proceeds straight to date selection; Lab Test's
# own variant pick instead appends to the growing basket and loops back to
# "add another?", a genuinely different behavior that can't share one state.
STATE_AWAITING_LAB_TEST_VARIANT = "AWAITING_LAB_TEST_VARIANT"


STATE_AWAITING_COLLECTION_METHOD = "AWAITING_COLLECTION_METHOD"


STATE_AWAITING_COLLECTION_PINCODE = "AWAITING_COLLECTION_PINCODE"


STATE_AWAITING_COLLECTION_ADDRESS = "AWAITING_COLLECTION_ADDRESS"


STATE_AWAITING_PATIENT_NAME = "AWAITING_PATIENT_NAME"


STATE_AWAITING_PATIENT_AGE = "AWAITING_PATIENT_AGE"


STATE_AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"


STATE_BOOKED = "BOOKED"  # momentary only — never persisted, see _handle_awaiting_confirmation


STATE_AWAITING_CHANGE_SELECTION = "AWAITING_CHANGE_SELECTION"


BACK_ID = "nav_back"


CHANGE_APPOINTMENT_TYPE = "change_appointment_type"


CHANGE_DEPARTMENT = "change_department"


CHANGE_DOCTOR = "change_doctor"


CHANGE_DATE = "change_date"


CHANGE_TIME = "change_time"


CHANGE_DIAGNOSTIC_TEST = "change_diagnostic_test"


CHANGE_DIAGNOSTIC_VARIANT = "change_diagnostic_variant"


# Lab Test Phase 2 follow-up: jumps back to the collection-method step only
# -- there's no single "change test" target for a basket (which of N items?),
# so re-picking the basket from confirmation isn't offered; a patient who
# wants a different set of tests uses "Change Appointment Type" instead
# (restarts test selection from scratch).
CHANGE_COLLECTION_METHOD = "change_collection_method"


_CHANGE_TARGETS = {
    CHANGE_APPOINTMENT_TYPE: STATE_AWAITING_APPOINTMENT_TYPE,
    CHANGE_DEPARTMENT: STATE_AWAITING_DEPARTMENT,
    CHANGE_DOCTOR: STATE_AWAITING_DOCTOR,
    CHANGE_DATE: STATE_AWAITING_DATE,
    CHANGE_TIME: STATE_AWAITING_TIME_SLOT,
    CHANGE_DIAGNOSTIC_TEST: STATE_AWAITING_DIAGNOSTIC_TEST,
    CHANGE_DIAGNOSTIC_VARIANT: STATE_AWAITING_DIAGNOSTIC_VARIANT,
    CHANGE_COLLECTION_METHOD: STATE_AWAITING_COLLECTION_METHOD,
}


_HISTORY_KEY = "_history"


_PRESERVE_ACROSS_BACK = (
    "patient_name", "patient_age", "active_patient_id",
    "appointment_type_id", "appointment_type_label", "appointment_type_requires_consent",
)


MIN_PATIENT_AGE = 0


MAX_PATIENT_AGE = 120


FREE_TEXT_INPUT_STATES = {
    STATE_AWAITING_PATIENT_NAME, STATE_AWAITING_PATIENT_AGE,
    # Lab Test Phase 2 follow-up: PIN code and address are free-text replies,
    # same reset-keyword-exemption reasoning as patient name/age above (a
    # PIN code or a street address could itself start with a word this app
    # treats as a reset keyword).
    STATE_AWAITING_COLLECTION_PINCODE, STATE_AWAITING_COLLECTION_ADDRESS,
}


STATE_AWAITING_CANCEL_SELECTION = "AWAITING_CANCEL_SELECTION"


STATE_AWAITING_CANCEL_CONFIRM = "AWAITING_CANCEL_CONFIRM"


STATE_AWAITING_RESCHEDULE_SELECTION = "AWAITING_RESCHEDULE_SELECTION"


STATE_AWAITING_RESCHEDULE_DATE = "AWAITING_RESCHEDULE_DATE"


STATE_AWAITING_RESCHEDULE_SLOT = "AWAITING_RESCHEDULE_SLOT"


STATE_AWAITING_RESCHEDULE_CONFIRM = "AWAITING_RESCHEDULE_CONFIRM"


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


_MAX_LIST_ROWS = MAX_LIST_ROWS


_cap_rows = cap_rows


_RESET_KEYWORDS = RESET_KEYWORDS


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


STATE_AWAITING_VIEW_APPOINTMENT_ACTION = "AWAITING_VIEW_APPOINTMENT_ACTION"


STATE_AWAITING_VIEW_APPOINTMENTS_RANGE = "AWAITING_VIEW_APPOINTMENTS_RANGE"


VIEW_APPOINTMENTS_RANGE_PREVIOUS_ID = "view_appointments_range_previous"


VIEW_APPOINTMENTS_RANGE_UPCOMING_ID = "view_appointments_range_upcoming"

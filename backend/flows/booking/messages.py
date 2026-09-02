# flows/booking/messages.py
"""
ARCHITECTURE_PLAN.md Phase 3b: WA message/menu builders shared across the
booking/cancel/reschedule/view-appointments/manage-patients sub-flows
(patient selector, slot-taken recovery, back-navigation, appointment
selection, confirmation cards, ...), split out of the former single
core/booking_flow.py module.

_select_patient_and_continue routes onward into cancel.py/reschedule.py/
manage_patients.py/view_appointments.py -- imported LAZILY inside that one
function body, not at module top level, since those sibling modules import
back from this one (_send_patient_selector, _send_main_menu, etc.); a
top-level import here would be circular.
"""
import logging

import db.repository as db
from connectors import Connector
from core.translations import t
from core.translations.menu import (
    BOOK_APPOINTMENT_SHORT,
    CANCEL_SHORT,
    FAQ_SHORT,
    MAIN_MENU_BUTTON,
    MAIN_MENU_SECTION_TITLE,
    RESCHEDULE_SHORT,
    WELCOME_MENU,
)
from core.translations.common import BACK_OPTION
from core.translations.patient_identity import (
    ADD_PATIENT_OPTION,
    ALL_PATIENTS_OPTION,
    BACK_TO_MENU_OPTION,
    PATIENT_CONTEXT_INVALID,
    PATIENT_SELECTOR_BUTTON,
    PATIENT_SELECTOR_SECTION_TITLE,
)
from core.translations.booking import (
    APPOINTMENT_TYPES_SECTION_TITLE,
    ASK_PATIENT_NAME,
    AVAILABLE_DATES_SECTION_TITLE,
    AVAILABLE_SLOTS_SECTION_TITLE,
    AVAILABLE_TIMES_SECTION_TITLE,
    CANCEL_BUTTON,
    CHANGE_APPOINTMENT_TYPE_OPTION,
    CHANGE_DATE_OPTION,
    CHANGE_DEPARTMENT_OPTION,
    CHANGE_DOCTOR_OPTION,
    CHANGE_DURATION_OPTION,
    CHANGE_OPTIONS_SECTION_TITLE,
    CHANGE_TIME_OPTION,
    CONFIRM_BOOKING_SUMMARY,
    CONFIRM_BUTTON,
    CONFIRM_DAYCARE_DURATION_LINE,
    CONSENT_AGREE_BUTTON,
    CONSENT_PROMPT,
    CONSULTATION_FEE_LINE,
    DEPARTMENTS_SECTION_TITLE,
    DOCTOR_SELECTED_ASK_DATE,
    NO_DOCTORS_AVAILABLE,
    NO_SLOTS_AVAILABLE,
    SELECT_APPOINTMENT_TYPE,
    SELECT_DEPARTMENT,
    SELECT_DOCTOR,
    SELECT_SLOT,
    SELECT_TIME_SLOT,
    SLOT_TAKEN_CHOOSE_ANOTHER,
    SLOT_TAKEN_NO_ALTERNATIVES,
    VIEW_APPOINTMENT_TYPES_BUTTON,
    VIEW_CHANGE_OPTIONS_BUTTON,
    VIEW_DATES_BUTTON,
    VIEW_DEPARTMENTS_BUTTON,
    VIEW_DOCTORS_BUTTON,
    VIEW_SLOTS_BUTTON,
    VIEW_TIMES_BUTTON,
    WHAT_WOULD_YOU_LIKE_TO_CHANGE,
)
from core.translations.manage_patients import PATIENT_ADDED
from core.translations.cancel_reschedule import (
    CANCEL_CONFIRM_QUESTION,
    RESCHEDULE_CONFIRM_SUMMARY,
    VIEW_APPOINTMENTS_BUTTON,
    YOUR_APPOINTMENTS_SECTION_TITLE,
)
from core.whatsapp import WhatsAppClient

from flows.booking.state import (
    ADD_PATIENT_ROW_ID, ALL_PATIENTS_ROW_ID, BACK_ID, CHANGE_APPOINTMENT_TYPE, CHANGE_DATE, CHANGE_DEPARTMENT, GOTO_MAIN_MENU,
    CHANGE_DOCTOR, CHANGE_DURATION, CHANGE_TIME, CONFIRM_NO, CONFIRM_YES, MAIN_MENU_BOOK, MAIN_MENU_CANCEL, MAIN_MENU_FAQ,
    MAIN_MENU_RESCHEDULE, STATE_AWAITING_APPOINTMENT_TYPE, STATE_AWAITING_DATE, STATE_AWAITING_DAYCARE_DURATION,
    STATE_AWAITING_DEPARTMENT,
    STATE_AWAITING_FOLLOWUP_SELECTION,
    STATE_AWAITING_DOCTOR, STATE_AWAITING_PATIENT_NAME, STATE_AWAITING_PATIENT_SELECTION,
    STATE_AWAITING_RESCHEDULE_SLOT, STATE_AWAITING_TIME_SLOT,
    _CHANGE_TARGETS, _MAX_LIST_ROWS, _appointment_row_id, _cap_rows, _date_label, _history_pop, _history_pop_to,
    _parse_appointment_row_id, _parse_patient_row_id, _patient_row_id, _patient_row_title,
)
from flows.booking.types.registry import get_type_flow

logger = logging.getLogger(__name__)

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
    await wa.send_buttons(to=phone, body_text="​", buttons=[{"id": BACK_ID, "title": t(BACK_OPTION, language)}])


async def _reject_if_patient_link_invalid(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, patient_id: int | None, connector: Connector,
    language: str = "en",
) -> bool:
    """CareConnect architecture doc alignment (Spec.md Section 0), Section
    14's patient-context validation -- re-checked here, right before the
    actual WRITE, not just at selection time: a link resolved several
    messages ago in a multi-step flow could have been unlinked (or the
    patient blocked) in between.

    Deliberately called ONLY at booking confirmation (context["active_patient_id"],
    always freshly resolved THIS session by core/patient_identity.py) --
    NOT at cancel/reschedule confirmation, even though those also
    conceptually touch a patient_id: their context/`appt.patient_id`
    predates this feature for any appointment created before a hospital's
    patient-linking migration ran, or created via the staff portal (which
    never creates a patient_links row at all, only a bare `patients` row via
    _upsert_patient()) -- re-validating THAT patient_id here would
    incorrectly block a patient from cancelling/rescheduling their own
    completely legitimate, pre-existing appointment. Booking confirmation
    has no such legacy-data ambiguity: active_patient_id there is only ever
    set by a resolution that just happened in this exact conversation.

    Returns True (and has already reset the session + replied) if the check
    fails and the caller should stop; False if there's nothing to check
    (patient_id is None) or the link is still genuinely valid."""
    if patient_id is None:
        return False
    if connector.validate_active_patient_link(hospital_id, phone, patient_id):
        return False
    sessions.clear_active_patient(hospital_id, phone)
    sessions.reset(hospital_id, phone)
    await wa.send_text(phone, t(PATIENT_CONTEXT_INVALID, language))
    return True


async def _send_post_action_menu(wa: WhatsAppClient, phone: str, language: str = "en") -> None:
    """Generic follow-up quick-menu sent after cancel/reschedule confirms and
    after the My Appointments list -- NOT scoped to any one appointment
    (unlike book.py's own booking-confirmed buttons, which target the
    appointment just booked): Cancel/Reschedule here are the same row ids
    the real dynamic main menu uses (MAIN_MENU_CANCEL/MAIN_MENU_RESCHEDULE),
    so router.py's own IDLE dispatch (_ROW_ID_TO_FEATURE) picks them up and
    starts that feature fresh, scoped to whichever patient is active, same
    as tapping it from the main menu itself."""
    await wa.send_buttons(
        to=phone,
        body_text="​",
        buttons=[
            {"id": GOTO_MAIN_MENU, "title": t(MAIN_MENU_BUTTON, language)},
            {"id": MAIN_MENU_CANCEL, "title": t(CANCEL_BUTTON, language)},
            {"id": MAIN_MENU_RESCHEDULE, "title": t(RESCHEDULE_SHORT, language)},
        ],
    )


async def _send_main_menu(wa: WhatsAppClient, phone: str, hospital_name: str, language: str = "en") -> None:
    rows = [
        {"id": MAIN_MENU_BOOK, "title": t(BOOK_APPOINTMENT_SHORT, language)},
        {"id": MAIN_MENU_RESCHEDULE, "title": t(RESCHEDULE_SHORT, language)},
        {"id": MAIN_MENU_CANCEL, "title": t(CANCEL_SHORT, language)},
        {"id": MAIN_MENU_FAQ, "title": t(FAQ_SHORT, language)},
    ]
    await wa.send_list(
        to=phone,
        body_text=t(WELCOME_MENU, language, hospital_name=hospital_name),
        button_text=t(MAIN_MENU_BUTTON, language),
        sections=[{"title": t(MAIN_MENU_SECTION_TITLE, language), "rows": rows}],
    )


async def _send_appointment_type_menu(
    wa: WhatsAppClient, phone: str, hospital_id: int, connector: Connector, language: str = "en",
    category: "frozenset[str] | list[str] | None" = None,
) -> None:
    """The APPOINTMENT TYPE step -- shown right after patient resolution,
    before department selection (see _select_patient_and_continue's booking
    branch). Row ids are the appointment_types.id values themselves (e.g.
    "new", "tele") -- same "use the real id directly as the WA row id, no
    extra prefix" convention _send_department_menu already uses.

    category (WhatsApp menu restructuring): when given, only types whose id
    is in this set are shown -- Book Doctor Appointment/Tests & Diagnostics
    each pass their own fixed id set (db.BOOK_DOCTOR_APPOINTMENT_CATEGORY/
    TESTS_DIAGNOSTICS_CATEGORY) so the same underlying type list powers both
    category submenus without duplicating this function."""
    types = connector.get_appointment_types(hospital_id)
    if category is not None:
        types = [t_ for t_ in types if t_["id"] in category]
    rows = [{"id": t_["id"], "title": t_["label"]} for t_ in types]
    rows = _cap_rows(rows, "appointment type menu")
    await wa.send_list(
        to=phone,
        body_text=t(SELECT_APPOINTMENT_TYPE, language),
        button_text=t(VIEW_APPOINTMENT_TYPES_BUTTON, language),
        sections=[{"title": t(APPOINTMENT_TYPES_SECTION_TITLE, language), "rows": rows}],
    )
    # Booking's own first step -- a separate follow-up button (same pattern
    # as _send_back_button), but GOTO_MAIN_MENU not BACK_ID: intercepted
    # globally in flows/router.py's handle_incoming, BEFORE any state
    # dispatch, so it correctly re-shows the REAL dynamic menu (patient
    # header, actual hospital name, actual enabled features) rather than
    # this module's own fixed 4-row _send_main_menu stand-in.
    await wa.send_buttons(
        to=phone, body_text="​", buttons=[{"id": GOTO_MAIN_MENU, "title": t(BACK_TO_MENU_OPTION, language)}],
    )


async def _send_consent_prompt(wa: WhatsAppClient, phone: str, appointment_type_label: str, language: str = "en") -> None:
    """Shown between confirmation and actually creating the booking, only
    for an appointment type whose requires_consent is TRUE (e.g.
    tele-consultation, second opinion) -- see db/schema.sql's own comment on
    appointment_types.requires_consent."""
    await wa.send_buttons(
        to=phone,
        body_text=t(CONSENT_PROMPT, language, appointment_type_label=appointment_type_label),
        buttons=[
            {"id": CONFIRM_YES, "title": t(CONSENT_AGREE_BUTTON, language)},
            {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
        ],
    )


async def _send_department_menu(wa: WhatsAppClient, phone: str, hospital_id: int, connector: Connector, language: str = "en") -> None:
    rows = [{"id": d["id"], "title": d["name"]} for d in connector.get_departments(hospital_id)]
    rows = _cap_rows(rows, "department menu")
    await wa.send_list(
        to=phone,
        body_text=t(SELECT_DEPARTMENT, language),
        button_text=t(VIEW_DEPARTMENTS_BUTTON, language),
        sections=[{"title": t(DEPARTMENTS_SECTION_TITLE, language), "rows": rows}],
    )
    await _send_back_button(wa, phone, language=language)


async def _select_patient_and_continue(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, patient: dict,
    next_action: str, language: str = "en", booking_category: "list[str] | None" = None,
) -> None:
    """The shared "a patient is now active, what happens next" router --
    reached either via auto-select (exactly one linked patient, zero added
    friction) or an explicit tap in _handle_awaiting_patient_selection.

    Imports the other sub-flow modules' own entry points LAZILY, right here,
    rather than at module top level -- this module's docstring explains why
    (cancel.py/reschedule.py/manage_patients.py/view_appointments.py all
    import FROM this module, so a top-level import in the other direction
    would be circular)."""
    from flows.booking.book import _start_booking_for_preselected_type
    from flows.booking.cancel import _start_cancel_flow_for_patient
    from flows.booking.manage_patients import _start_manage_patients_flow
    from flows.booking.reschedule import _start_reschedule_flow_for_patient
    from flows.booking.view_appointments import _send_view_appointments

    if next_action == "booking":
        context = {
            "active_patient_id": patient["id"], "patient_name": patient["name"], "patient_age": patient["age"],
        }
        if booking_category is not None:
            context["appointment_type_category"] = list(booking_category)
        sessions.set(hospital_id, phone, STATE_AWAITING_APPOINTMENT_TYPE, context)
        await _send_appointment_type_menu(wa, phone, hospital_id, connector, language=language, category=booking_category)
    elif next_action == "book_report_review":
        # Reports & Prescriptions' single-type category -- no list is ever
        # shown, so it skips straight past the type-list step (see
        # _start_booking_for_preselected_type's own docstring).
        await _start_booking_for_preselected_type(
            wa, sessions, phone, hospital_id, connector, db.REPORT_REVIEW_TYPE_ID, patient, language=language,
        )
    elif next_action == "cancel":
        await _start_cancel_flow_for_patient(wa, sessions, phone, hospital_id, connector, patient["id"], language=language)
    elif next_action == "reschedule":
        await _start_reschedule_flow_for_patient(wa, sessions, phone, hospital_id, connector, patient["id"], language=language)
    elif next_action.startswith("view_appointments_"):
        range_ = next_action[len("view_appointments_"):]
        await _send_view_appointments(
            wa, sessions, phone, hospital_id, connector, language=language, active_patient_id=patient["id"], range_=range_,
        )
    elif next_action == "manage_patients":
        await wa.send_text(phone, t(PATIENT_ADDED, language, patient_name=patient["name"]))
        await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)
    else:
        logger.warning("No _select_patient_and_continue branch for next_action %r -- falling back to main menu", next_action)
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)


async def _send_patient_selector(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, next_action: str,
    language: str = "en", booking_category: "list[str] | None" = None,
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
        rows.append({"id": ALL_PATIENTS_ROW_ID, "title": t(ALL_PATIENTS_OPTION, language)})
    if next_action == "booking" and len(patients) < connector.get_max_active_patient_links():
        rows.append({"id": ADD_PATIENT_ROW_ID, "title": t(ADD_PATIENT_OPTION, language)})
    # Reached right from the main menu (Book/Cancel/Reschedule/View
    # Appointments) -- unlike core/patient_identity.py's own patient
    # selector (shown BEFORE the main menu exists at all, so it has nothing
    # to go back to), this one always has a real main menu behind it.
    rows.append({"id": GOTO_MAIN_MENU, "title": t(BACK_TO_MENU_OPTION, language)})
    rows = _cap_rows(rows, "patient selector")
    sessions.set(
        hospital_id, phone, STATE_AWAITING_PATIENT_SELECTION,
        {"patient_flow_next": next_action, "patient_flow_category": booking_category},
    )
    await wa.send_list(
        to=phone,
        body_text=t(f"patient_selector_prompt_{next_action}", language),
        button_text=t(PATIENT_SELECTOR_BUTTON, language),
        sections=[{"title": t(PATIENT_SELECTOR_SECTION_TITLE, language), "rows": rows}],
    )


async def _handle_awaiting_patient_selection(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    next_action = context.get("patient_flow_next", "booking")
    booking_category = context.get("patient_flow_category")
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == ADD_PATIENT_ROW_ID and next_action == "booking":
            sessions.set(
                hospital_id, phone, STATE_AWAITING_PATIENT_NAME,
                {"patient_flow_next": next_action, "patient_flow_category": booking_category},
            )
            await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
            return
        if rid == ALL_PATIENTS_ROW_ID and next_action != "booking":
            await _select_patient_and_continue(
                wa, sessions, phone, hospital_id, connector, {"id": None, "name": None, "age": None},
                next_action, language=language, booking_category=booking_category,
            )
            return
        patient_id = _parse_patient_row_id(rid)
        if patient_id is not None:
            patients = connector.list_active_patients(hospital_id, phone)
            match = next((p for p in patients if p["id"] == patient_id), None)
            if match:
                await _select_patient_and_continue(
                    wa, sessions, phone, hospital_id, connector, match, next_action, language=language,
                    booking_category=booking_category,
                )
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
            await _select_patient_and_continue(
                wa, sessions, phone, hospital_id, connector, patients[0], next_action, language=language,
                booking_category=booking_category,
            )
        else:
            await _select_patient_and_continue(
                wa, sessions, phone, hospital_id, connector, {"id": None, "name": None, "age": None},
                next_action, language=language, booking_category=booking_category,
            )
        return
    await _send_patient_selector(
        wa, sessions, phone, hospital_id, connector, next_action, language=language, booking_category=booking_category,
    )


async def _send_doctor_menu(
    wa: WhatsAppClient, phone: str, hospital_id: int, department_id: str, department_name: str, connector: Connector,
    language: str = "en",
) -> None:
    rows = [{"id": d["id"], "title": d["name"]} for d in connector.get_doctors(hospital_id, department_id)]
    rows = _cap_rows(rows, "doctor menu")
    await wa.send_list(
        to=phone,
        body_text=t(SELECT_DOCTOR, language, department_name=department_name),
        button_text=t(VIEW_DOCTORS_BUTTON, language),
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
        body_text=t(SELECT_SLOT, language, doctor_name=doctor_name),
        button_text=t(VIEW_SLOTS_BUTTON, language),
        sections=[{"title": t(AVAILABLE_SLOTS_SECTION_TITLE, language), "rows": rows}],
    )


async def _send_date_menu(
    wa: WhatsAppClient, phone: str, hospital_id: int, doctor_id: str, doctor_name: str, connector: Connector,
    language: str = "en", min_date: str | None = None,
) -> None:
    """Section 12.12, booking flow's step 1 of the date/time split: the
    distinct dates (soonest first, since get_available_slots() is already
    sorted that way) this doctor has ANY bookable slot on, capped to Meta's
    10-row limit -- a doctor generates up to 14 days ahead
    (db/repository.py's _SLOT_DAYS_AHEAD), so this can legitimately exceed 10
    distinct dates for a doctor who works every day.

    min_date (Follow-up only, docs/per-appointment-type-flow-plan.md Phase 2
    Step 2 follow-up): dates strictly AFTER this "YYYY-MM-DD" string are kept
    -- a follow-up must be booked after the visit it follows, never on the
    same day or earlier. String comparison is safe since dates are always
    this ISO shape. None (every other type) means no floor at all."""
    slots = connector.get_available_slots(hospital_id, doctor_id)
    dates_seen: list[str] = []
    for s in slots:
        if s["date"] not in dates_seen and (min_date is None or s["date"] > min_date):
            dates_seen.append(s["date"])
    rows = [{"id": d, "title": _date_label(d)} for d in dates_seen]
    rows = _cap_rows(rows, f"date menu for doctor {doctor_id}")
    await wa.send_list(
        to=phone,
        body_text=t(DOCTOR_SELECTED_ASK_DATE, language, doctor_name=doctor_name),
        button_text=t(VIEW_DATES_BUTTON, language),
        sections=[{"title": t(AVAILABLE_DATES_SECTION_TITLE, language), "rows": rows}],
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
        body_text=t(SELECT_TIME_SLOT, language),
        button_text=t(VIEW_TIMES_BUTTON, language),
        sections=[{"title": t(AVAILABLE_TIMES_SECTION_TITLE, language), "rows": rows}],
    )
    await _send_back_button(wa, phone, language=language)


async def _notify_no_doctors_available(
    wa: WhatsAppClient, sessions, hospital_id: int, phone: str, department_name: str, language: str = "en",
) -> None:
    sessions.reset(hospital_id, phone)
    await wa.send_text(phone, t(NO_DOCTORS_AVAILABLE, language, department_name=department_name))
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
    await wa.send_text(phone, t(NO_SLOTS_AVAILABLE, language, doctor_name=doctor_name))
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
    if doctor_id is None:
        # Corrupted/stale context -- nothing to recover a slot list for.
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    logger.info("Double-booking race: hospital=%s doctor=%s slot=%s already taken", hospital_id, doctor_id, context.get("slot_id"))
    if not connector.get_available_slots(hospital_id, doctor_id):
        # Item 9: a genuine dead end, not the "pick another slot" case item 1
        # covers (there's nothing left to pick) -- same recovery as
        # _notify_no_slots_available above.
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t(SLOT_TAKEN_NO_ALTERNATIVES, language, doctor_name=doctor_name))
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    sessions.set(hospital_id, phone, target_state, context)
    await wa.send_text(phone, t(SLOT_TAKEN_CHOOSE_ANOTHER, language))
    if target_state in (STATE_AWAITING_TIME_SLOT, STATE_AWAITING_RESCHEDULE_SLOT):
        date_str = context.get("date") or context.get("slot_date")
        if date_str is None:
            # Corrupted/stale context -- nothing to recover a time list for.
            sessions.reset(hospital_id, phone)
            await _send_main_menu(wa, phone, "the hospital", language=language)
            return
        await _send_time_menu(wa, phone, hospital_id, doctor_id, date_str, connector, language=language)
        return
    await _send_slot_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)


async def _send_confirmation(wa: WhatsAppClient, phone: str, hospital_id: int, context: dict, language: str = "en") -> None:
    """Section 12.12: structured card matching the reference screenshot --
    see core/translations.py's confirm_booking_summary. Age (Section 12.13
    follow-up) is included too, even though the original reference
    screenshot didn't have it -- explicitly requested.

    patient_code (Patient Code line, confirmed with the user) is the same
    patient_display_id shown everywhere else in the app -- fetched fresh
    here via active_patient_id rather than threaded through context, since
    nothing upstream of this call currently stashes it there.

    flow.build_confirmation_summary (Follow-up's own card shape) fully
    replaces the generic summary text below when set -- the Confirm/Cancel/
    Back buttons at the end are unaffected either way."""
    flow = get_type_flow(context.get("appointment_type_id"))
    if flow.build_confirmation_summary is not None:
        summary = flow.build_confirmation_summary(context, hospital_id)
        await wa.send_buttons(
            to=phone,
            body_text=summary,
            buttons=[
                {"id": CONFIRM_YES, "title": t(CONFIRM_BUTTON, language)},
                {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
                {"id": BACK_ID, "title": t(BACK_OPTION, language)},
            ],
        )
        return
    patient = db.get_patient(hospital_id, context.get("active_patient_id"))
    # Fee line: only for "new" (New Consultation) bookings, and only when the
    # hospital has actually configured a fee -- omitted entirely otherwise,
    # not shown as a fake ₹0. Was a static "₹800 (if applicable)" placeholder
    # before hospital_settings.new_consultation_fee existed as a real field.
    fee_line = ""
    if context.get("appointment_type_id") == "new":
        new_consultation_fee = db.get_hospital_settings(hospital_id)["new_consultation_fee"]
        if new_consultation_fee is not None:
            amount = int(new_consultation_fee) if new_consultation_fee == int(new_consultation_fee) else new_consultation_fee
            fee_line = t(CONSULTATION_FEE_LINE, language, amount=amount)
    summary = t(CONFIRM_BOOKING_SUMMARY, language,
        appointment_type_label=context.get("appointment_type_label"),
        department_name=context.get("department_name"), doctor_name=context.get("doctor_name"),
        date_label=context.get("date_label"), time_label=context.get("slot_time"),
        patient_name=context.get("patient_name"), patient_age=context.get("patient_age"),
        patient_code=(patient.get("patient_display_id") if patient else None) or "—",
        fee_line=fee_line,
    )
    # Daycare Phase 2: the chosen stay length, appended after the fixed
    # template above rather than folded into confirm_booking_summary itself
    # -- every other type has nothing to show here, and confirm_booking_
    # summary's placeholders are all unconditional fields every type has.
    if context.get("daycare_duration_label"):
        summary += "\n" + t(CONFIRM_DAYCARE_DURATION_LINE, language, duration_label=context["daycare_duration_label"])
    await wa.send_buttons(
        to=phone,
        body_text=summary,
        buttons=[
            {"id": CONFIRM_YES, "title": t(CONFIRM_BUTTON, language)},
            {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
            {"id": BACK_ID, "title": t(BACK_OPTION, language)},
        ],
    )


async def _send_change_selection_menu(
    wa: WhatsAppClient, phone: str, hospital_id: int, connector: Connector, language: str = "en",
    context: dict | None = None,
) -> None:
    """Confirmation's own Back: there's no single "the" field to pop back to,
    so this asks which one instead (see the module-level comment by
    _CHANGE_TARGETS for why).

    "Change Department"/"Change Doctor" are omitted for a single-department,
    single-doctor tenant (a clinic) -- there's nothing else to change TO, and
    offering them would be a dead end anyway: _handle_awaiting_appointment_
    type's clinic auto-skip never pushes a STATE_AWAITING_DEPARTMENT/DOCTOR
    history frame to jump back to, so _history_pop_to would find none and
    fail safe to a full reset -- confusing for a tap that looked like a
    normal menu option. Same applies to any type with no department/doctor
    step at all (diagnostic, lab, followup) via `context`'s TypeFlow."""
    departments = connector.get_departments(hospital_id)
    single_choice = len(departments) == 1 and len(connector.get_doctors(hospital_id, departments[0]["id"])) == 1
    flow = get_type_flow((context or {}).get("appointment_type_id"))
    single_choice = single_choice or not flow.has_step(STATE_AWAITING_DEPARTMENT)
    rows = [{"id": CHANGE_APPOINTMENT_TYPE, "title": t(CHANGE_APPOINTMENT_TYPE_OPTION, language)}]
    if not single_choice:
        rows.append({"id": CHANGE_DEPARTMENT, "title": t(CHANGE_DEPARTMENT_OPTION, language)})
        rows.append({"id": CHANGE_DOCTOR, "title": t(CHANGE_DOCTOR_OPTION, language)})
    rows.append({"id": CHANGE_DATE, "title": t(CHANGE_DATE_OPTION, language)})
    rows.append({"id": CHANGE_TIME, "title": t(CHANGE_TIME_OPTION, language)})
    if flow.has_step(STATE_AWAITING_DAYCARE_DURATION):
        rows.append({"id": CHANGE_DURATION, "title": t(CHANGE_DURATION_OPTION, language)})
    # Previously a dead end -- every row here picked a field to change, with
    # no way out except actually picking one. GOTO_MAIN_MENU is intercepted
    # globally (flows/router.py's handle_incoming, before any state
    # dispatch), so this abandons the in-progress booking rather than
    # returning to the confirmation card underneath -- same trade-off
    # _send_patient_selector's own back row above makes.
    rows.append({"id": GOTO_MAIN_MENU, "title": t(BACK_TO_MENU_OPTION, language)})
    await wa.send_list(
        to=phone,
        body_text=t(WHAT_WOULD_YOU_LIKE_TO_CHANGE, language),
        button_text=t(VIEW_CHANGE_OPTIONS_BUTTON, language),
        sections=[{"title": t(CHANGE_OPTIONS_SECTION_TITLE, language), "rows": rows}],
    )


async def _resend_menu_for_state(
    wa: WhatsAppClient, phone: str, hospital_id: int, state: str, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    """Dispatches to whichever menu builder matches a restored state -- used
    after both a single-step Back (_history_pop) and a change-target jump
    (_history_pop_to) land on one of the 4 list states, so the patient
    actually sees the list to pick from again, not just a silent state change."""
    if state == STATE_AWAITING_APPOINTMENT_TYPE:
        await _send_appointment_type_menu(
            wa, phone, hospital_id, connector, language=language, category=context.get("appointment_type_category"),
        )
    elif state == STATE_AWAITING_FOLLOWUP_SELECTION:
        # Lazy import: avoids this module -> types.registry -> followup cycle.
        from flows.booking.types.followup import _resend_followup_eligible_list
        await _resend_followup_eligible_list(wa, phone, hospital_id, context, connector, language=language)
    elif state == STATE_AWAITING_DEPARTMENT:
        await _send_department_menu(wa, phone, hospital_id, connector, language=language)
    elif state == STATE_AWAITING_DOCTOR:
        await _send_doctor_menu(
            wa, phone, hospital_id, context["department_id"], context["department_name"], connector,
            language=language,
        )
    elif state == STATE_AWAITING_DATE:
        await _send_date_menu(
            wa, phone, hospital_id, context["doctor_id"], context["doctor_name"], connector, language=language,
            min_date=context.get("followup_previous_visit_date"),
        )
    elif state == STATE_AWAITING_TIME_SLOT:
        await _send_time_menu(
            wa, phone, hospital_id, context["doctor_id"], context["date"], connector, language=language,
        )
    elif state == STATE_AWAITING_DAYCARE_DURATION:
        # Lazy import: avoids this module -> types.registry -> daycare cycle,
        # same reason STATE_AWAITING_FOLLOWUP_CONFIRM's case above does.
        from flows.booking.types.daycare import _send_daycare_duration_menu
        await _send_daycare_duration_menu(wa, phone, hospital_id, connector, language=language)


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
    # Cancel/reschedule's own first screen (right from the main menu, or
    # after the patient selector above for a multi-patient phone) -- a real
    # main menu always exists behind it, unlike identity's pre-resolution
    # screens.
    rows.append({"id": GOTO_MAIN_MENU, "title": t(BACK_TO_MENU_OPTION, language)})
    rows = _cap_rows(rows, "appointment selection menu")
    await wa.send_list(
        to=phone,
        body_text=t(body_key, language),
        button_text=t(VIEW_APPOINTMENTS_BUTTON, language),
        sections=[{"title": t(YOUR_APPOINTMENTS_SECTION_TITLE, language), "rows": rows}],
    )


async def _send_cancel_confirm(wa: WhatsAppClient, phone: str, appointment, language: str = "en") -> None:
    when = appointment.scheduled_at.strftime("%A, %d %B at %H:%M")
    await wa.send_buttons(
        to=phone,
        body_text=t(CANCEL_CONFIRM_QUESTION, language, doctor_name=appointment.doctor_name, when=when),
        buttons=[
            {"id": CONFIRM_YES, "title": t(CONFIRM_BUTTON, language)},
            {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
        ],
    )


async def _send_reschedule_confirm(wa: WhatsAppClient, phone: str, context: dict, language: str = "en") -> None:
    summary = t(RESCHEDULE_CONFIRM_SUMMARY, language,
        doctor_name=context.get("doctor_name"), slot_label=context.get("slot_label"),
    )
    await wa.send_buttons(
        to=phone,
        body_text=summary,
        buttons=[
            {"id": CONFIRM_YES, "title": t(CONFIRM_BUTTON, language)},
            {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
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

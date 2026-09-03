# flows/booking/book.py
"""
ARCHITECTURE_PLAN.md Phase 3b: the booking sub-flow's own state handlers
(department/doctor/date/time/patient-name/age/confirmation/change-selection),
split out of the former single core/booking_flow.py module.
"""
from datetime import datetime

from connectors import Connector, DuplicateBookingError, TooManyLinkedPatientsError
from core.translations import t
from core.translations.menu import MAIN_MENU_BUTTON, RESCHEDULE_SHORT
from core.translations.booking import (
    ASK_PATIENT_AGE,
    ASK_PATIENT_NAME,
    BOOKING_CONFIRMED,
    BOOKING_NOT_CONFIRMED,
    CANCEL_BUTTON,
    CONSENT_DECLINED,
    DEPARTMENT_APPOINTMENT_CONFLICT,
    DUPLICATE_BOOKING_TEXT,
    INVALID_PATIENT_AGE,
    INVALID_PATIENT_NAME,
)
from core.translations.patient_identity import TOO_MANY_LINKED_PATIENTS
from core.whatsapp import WhatsAppClient
from db.connection import IntegrityError

from flows.booking.manage_patients import _start_manage_patients_flow
from flows.booking.messages import (
    _handle_back_navigation, _handle_slot_taken, _notify_no_doctors_available, _notify_no_slots_available,
    _reject_if_patient_link_invalid, _resend_menu_for_state, _select_patient_and_continue, _send_appointment_type_menu,
    _send_change_selection_menu, _send_confirmation, _send_consent_prompt, _send_date_menu, _send_department_menu,
    _send_doctor_menu, _send_main_menu, _send_patient_selector, _send_time_menu,
)
from flows.booking.state import (
    BACK_ID, CONFIRM_NO, CONFIRM_YES, GOTO_MAIN_MENU, MAX_PATIENT_AGE, MIN_PATIENT_AGE, STATE_AWAITING_APPOINTMENT_TYPE,
    STATE_AWAITING_CHANGE_SELECTION, STATE_AWAITING_CONFIRMATION, STATE_AWAITING_CONSENT, STATE_AWAITING_DATE,
    STATE_AWAITING_DEPARTMENT, STATE_AWAITING_DOCTOR, STATE_AWAITING_PATIENT_AGE, STATE_AWAITING_PATIENT_NAME,
    STATE_AWAITING_PATIENT_SELECTION, STATE_AWAITING_TIME_SLOT,
    STATE_BOOKED, _CHANGE_TARGETS, _HISTORY_KEY, _append_closing_message, _carry_forward_preserved_fields,
    _date_label, _find_by_id, _history_pop_to, _manage_cancel_id, _manage_reschedule_id, _parse_patient_age,
    _push_history,
)
from flows.booking.types.registry import get_type_flow


def _get_slots(connector: Connector, hospital_id: int, doctor_id: str | None, resource_id: str | None) -> list[dict]:
    """Diagnostic/Lab Phase 2: the one place _handle_awaiting_date/
    _handle_awaiting_time_slot read slot availability from -- resource_id
    (when set) takes priority, same "exactly one of the two is ever set"
    invariant create_appointment() enforces at the DB level."""
    if resource_id is not None:
        return connector.get_available_resource_slots(hospital_id, resource_id)
    assert doctor_id is not None  # caller already checked not (doctor_id or resource_id) -> reset
    return connector.get_available_slots(hospital_id, doctor_id)


def _first_available_resource(connector: Connector, hospital_id: int) -> tuple[dict, dict] | None:
    """Picks the first department's first doctor with open slots -- the
    internal resource used for types with no department/doctor step
    (diagnostic, lab). Returns None if nothing has any open slot."""
    for dept in connector.get_departments(hospital_id):
        for doctor in connector.get_doctors(hospital_id, dept["id"]):
            if connector.get_available_slots(hospital_id, doctor["id"]):
                return dept, doctor
    return None

async def _start_booking_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
    active_patient_id: int | None = None, category: "frozenset[str] | None" = None, next_action: str = "booking",
) -> None:
    """CareConnect architecture doc alignment (Spec.md Section 0): when
    `active_patient_id` is given (flows.py's real-traffic path, resolved
    ONCE up front by core/patient_identity.py before the main menu is ever
    shown -- Section 13's "Active Patient Context"), skip straight to
    department selection using it, bypassing every branch below entirely --
    this module no longer owns patient resolution for real traffic. Left
    None (every existing call site/test), the full 0/1/2+ resolution below
    runs exactly as before -- see the "known scope decision" in
    core/patient_identity.py's own module docstring for why this module's
    own selector logic below is kept rather than deleted.

    Patient identity/UX follow-up (Spec.md Section 0): name/age collection
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
    booking_category = list(category) if category else None
    if active_patient_id is not None:
        patients = connector.list_active_patients(hospital_id, phone)
        match = next((p for p in patients if p["id"] == active_patient_id), None)
        if match is not None:
            await _select_patient_and_continue(
                wa, sessions, phone, hospital_id, connector, match, next_action, language=language,
                booking_category=booking_category,
            )
            return
        # Defensive only -- shouldn't happen, since flows.py only ever
        # passes an active_patient_id it just validated. Fall through to
        # the normal resolution below rather than silently failing.
    patients = connector.list_active_patients(hospital_id, phone)
    if not patients:
        sessions.set(
            hospital_id, phone, STATE_AWAITING_PATIENT_NAME,
            {"patient_flow_next": next_action, "patient_flow_category": booking_category},
        )
        await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
        return
    if len(patients) == 1:
        await _select_patient_and_continue(
            wa, sessions, phone, hospital_id, connector, patients[0], next_action, language=language,
            booking_category=booking_category,
        )
        return
    await _send_patient_selector(
        wa, sessions, phone, hospital_id, connector, next_action, language=language, booking_category=booking_category,
    )


async def _proceed_with_appointment_type(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, appt_type: dict, new_context: dict,
    connector: Connector, language: str = "en",
) -> None:
    """Everything that happens once an appointment type is settled --
    factored out of _handle_awaiting_appointment_type so
    _start_booking_for_preselected_type (Book Report Review, which never
    shows a type list at all) can reuse it too. Callers build `new_context`
    themselves (with or without a _HISTORY_KEY frame, per their own
    situation) and pass it in already-formed."""
    # A type with its own on_selected hook (e.g. followup.py) fully
    # owns what happens next -- checked before the skip branch below.
    flow = get_type_flow(appt_type["id"])
    if flow.on_selected is not None:
        await flow.on_selected(wa, sessions, phone, hospital_id, connector, new_context, language)
        return
    # No department/doctor step at all (diagnostic, lab): auto-resolve
    # a resource instead of asking, regardless of tenant shape.
    if STATE_AWAITING_DEPARTMENT not in flow.steps:
        resource = _first_available_resource(connector, hospital_id)
        if resource is None:
            await _notify_no_doctors_available(wa, sessions, hospital_id, phone, appt_type["label"], language=language)
            return
        dept, doctor = resource
        new_context = {
            **new_context,
            "department_id": dept["id"], "department_name": dept["name"],
            "doctor_id": doctor["id"], "doctor_name": doctor["name"],
        }
        sessions.set(hospital_id, phone, flow.first_step(), new_context)
        await _send_date_menu(wa, phone, hospital_id, doctor["id"], doctor["name"], connector, language=language)
        return
    # Single-doctor tenant (a clinic, per tenant-capability-gating-
    # plan.md -- onboarded with exactly one department and one
    # doctor): asking a clinic's patient to pick a department then a
    # doctor when there's only ever one of each is pure friction, so
    # skip straight to date selection with both auto-selected. Not
    # gated on tenant_type directly -- this module only ever talks to
    # `connector`, never db/repository.py or Hospital -- so it's
    # phrased as "there's only one real choice," which happens to be
    # exactly the clinic case and degrades safely if a hospital ever
    # legitimately has one department with one doctor too. Back
    # navigation needs no special-casing: since STATE_AWAITING_
    # DEPARTMENT/DOCTOR frames are simply never pushed here, popping
    # history naturally returns straight to appointment type.
    departments = connector.get_departments(hospital_id)
    if len(departments) == 1:
        only_dept = departments[0]
        doctors = connector.get_doctors(hospital_id, only_dept["id"])
        if len(doctors) == 1:
            only_doctor = doctors[0]
            if not connector.get_available_slots(hospital_id, only_doctor["id"]):
                await _notify_no_slots_available(wa, sessions, hospital_id, phone, only_doctor["name"], language=language)
                return
            new_context = {
                **new_context,
                "department_id": only_dept["id"], "department_name": only_dept["name"],
                "doctor_id": only_doctor["id"], "doctor_name": only_doctor["name"],
            }
            sessions.set(hospital_id, phone, STATE_AWAITING_DATE, new_context)
            await _send_date_menu(wa, phone, hospital_id, only_doctor["id"], only_doctor["name"], connector, language=language)
            return
        if not doctors:
            await _notify_no_doctors_available(wa, sessions, hospital_id, phone, only_dept["name"], language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_DEPARTMENT, new_context)
    await _send_department_menu(wa, phone, hospital_id, connector, language=language)


async def _start_booking_for_preselected_type(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, appointment_type_id: str,
    active_patient: dict, language: str = "en",
) -> None:
    """Reports & Prescriptions' "Book Report Review" row: its category has
    exactly one type (db.REPORT_REVIEW_TYPE_ID), so showing a 1-row type
    list would be pure friction -- this skips straight past the type-LIST
    step into whatever picking that type normally does next
    (_proceed_with_appointment_type). No _HISTORY_KEY frame is pushed: no
    list screen was ever shown, so there's nothing for Back to pop to (same
    "frames simply never pushed" precedent the clinic single-doctor
    auto-skip above already established)."""
    appt_type = _find_by_id(connector.get_appointment_types(hospital_id), appointment_type_id)
    if appt_type is None:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    new_context = {
        "active_patient_id": active_patient["id"], "patient_name": active_patient["name"],
        "patient_age": active_patient["age"],
        "appointment_type_id": appt_type["id"],
        "appointment_type_label": appt_type["label"],
        "appointment_type_requires_consent": appt_type["requires_consent"],
    }
    await _proceed_with_appointment_type(wa, sessions, phone, hospital_id, appt_type, new_context, connector, language=language)


async def _handle_awaiting_appointment_type(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Appointment type step (WhatsApp flow alignment) -- the first booking
    step after patient resolution (_select_patient_and_continue's booking
    branch), same position Back navigation returns to first (there's no
    earlier booking-specific step for Back to fall through to; a Back tap
    here falls all the way out to the main menu, same as department's Back
    used to before this step existed)."""
    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            sessions.reset(hospital_id, phone)
            await _send_main_menu(wa, phone, "the hospital", language=language)
            return
        appt_type = _find_by_id(connector.get_appointment_types(hospital_id), reply["id"])
        if appt_type:
            history = _push_history(context, STATE_AWAITING_APPOINTMENT_TYPE)
            new_context = {
                **context,
                "appointment_type_id": appt_type["id"],
                "appointment_type_label": appt_type["label"],
                "appointment_type_requires_consent": appt_type["requires_consent"],
                _HISTORY_KEY: history,
            }
            await _proceed_with_appointment_type(wa, sessions, phone, hospital_id, appt_type, new_context, connector, language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_APPOINTMENT_TYPE, context)
    await _send_appointment_type_menu(
        wa, phone, hospital_id, connector, language=language, category=context.get("appointment_type_category"),
    )


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
            flow = get_type_flow(context.get("appointment_type_id"))
            if flow.validate_department is not None:
                conflict = flow.validate_department(
                    connector, hospital_id, context.get("active_patient_id"), dept["id"],
                )
                if conflict is not None:
                    # Confirmed with the user: instead of re-showing the
                    # department list, drop straight to the main menu (same
                    # Main Menu/Cancel/Reschedule quick-action shape as
                    # DuplicateBookingError below), showing the CONFLICTING
                    # appointment's own doctor/date so the patient knows
                    # exactly what to manage.
                    sessions.reset(hospital_id, phone)
                    when = conflict.scheduled_at.strftime("%A, %d %B at %H:%M")
                    await wa.send_buttons(
                        to=phone,
                        body_text=t(
                            DEPARTMENT_APPOINTMENT_CONFLICT, language,
                            department_name=conflict.department_name, doctor_name=conflict.doctor_name, when=when,
                        ),
                        buttons=[
                            {"id": GOTO_MAIN_MENU, "title": t(MAIN_MENU_BUTTON, language)},
                            {"id": _manage_cancel_id(conflict.id), "title": t(CANCEL_BUTTON, language)},
                            {"id": _manage_reschedule_id(conflict.id), "title": t(RESCHEDULE_SHORT, language)},
                        ],
                    )
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
    before this section).

    Diagnostic/Lab Phase 2: context["resource_id"], when set, means this
    booking is resource-bound (not doctor-bound) -- slot lookups go through
    the resource-keyed connector methods instead, same "one small branch in
    shared code" shape used throughout this file."""
    doctor_id = context.get("doctor_id")
    resource_id = context.get("resource_id")
    doctor_name = context.get("doctor_name", "")
    if not doctor_id and not resource_id:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        available_dates = {s["date"] for s in _get_slots(connector, hospital_id, doctor_id, resource_id)}
        if reply["id"] in available_dates:
            history = _push_history(context, STATE_AWAITING_DATE)
            new_context = {**context, "date": reply["id"], "date_label": _date_label(reply["id"]), _HISTORY_KEY: history}
            sessions.set(hospital_id, phone, STATE_AWAITING_TIME_SLOT, new_context)
            await _send_time_menu(wa, phone, hospital_id, doctor_id, reply["id"], connector, language=language, resource_id=resource_id)
            return
    # Dates are dynamic (another patient's booking can take the doctor's only
    # slot on a given date between this menu being sent and this reply) --
    # recheck rather than blindly re-send, same discipline as every other
    # dynamic-availability step in this file.
    if not _get_slots(connector, hospital_id, doctor_id, resource_id):
        await _notify_no_slots_available(wa, sessions, hospital_id, phone, doctor_name, language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_DATE, context)
    await _send_date_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language, resource_id=resource_id)


async def _handle_awaiting_time_slot(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Section 12.12, step 2 of the date/time split.

    Diagnostic/Lab Phase 2: same context["resource_id"] branch as
    _handle_awaiting_date above."""
    doctor_id = context.get("doctor_id")
    resource_id = context.get("resource_id")
    doctor_name = context.get("doctor_name", "")
    date_str = context.get("date")
    if (not doctor_id and not resource_id) or not date_str:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        slot = _find_by_id(_get_slots(connector, hospital_id, doctor_id, resource_id), reply["id"])
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
            #
            # Daycare Phase 2: the one type with a step after time-slot
            # (STATE_AWAITING_DAYCARE_DURATION) -- flow.next_step() resolves
            # to STATE_AWAITING_CONFIRMATION for every other type, unchanged.
            flow = get_type_flow(context.get("appointment_type_id"))
            next_state = flow.next_step(STATE_AWAITING_TIME_SLOT)
            sessions.set(hospital_id, phone, next_state, new_context)
            if next_state == STATE_AWAITING_CONFIRMATION:
                await _send_confirmation(wa, phone, hospital_id, new_context, language=language)
            else:
                from flows.booking.types.daycare import _send_daycare_duration_menu
                await _send_daycare_duration_menu(wa, phone, hospital_id, connector, language=language)
            return
    # Times are dynamic for the same reason dates are above -- recheck this
    # exact date's availability rather than blindly re-sending a stale list.
    if not any(s["date"] == date_str for s in _get_slots(connector, hospital_id, doctor_id, resource_id)):
        # This date specifically emptied out (not necessarily the whole
        # doctor) -- step back to date selection rather than a full reset,
        # so the patient picks a different date instead of starting over.
        sessions.set(hospital_id, phone, STATE_AWAITING_DATE, context)
        await _send_date_menu(
            wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language,
            min_date=context.get("followup_previous_visit_date"), resource_id=resource_id,
        )
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_TIME_SLOT, context)
    await _send_time_menu(wa, phone, hospital_id, doctor_id, date_str, connector, language=language, resource_id=resource_id)


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
        await wa.send_text(phone, t(ASK_PATIENT_AGE, language, patient_name=name))
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, context)
    await wa.send_text(phone, t(INVALID_PATIENT_NAME, language))
    await wa.send_text(phone, t(ASK_PATIENT_NAME, language))


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
        await wa.send_text(phone, t(INVALID_PATIENT_AGE, language))
        await wa.send_text(phone, t(ASK_PATIENT_AGE, language, patient_name=context.get("patient_name", "")))
        return
    next_action = context.get("patient_flow_next", "booking")
    booking_category = context.get("patient_flow_category")
    try:
        patient = connector.create_patient_profile(hospital_id, phone, context["patient_name"], age)
    except TooManyLinkedPatientsError:
        await wa.send_text(phone, t(TOO_MANY_LINKED_PATIENTS, language))
        if next_action == "manage_patients":
            await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)
        else:
            sessions.reset(hospital_id, phone)
            await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    await _select_patient_and_continue(
        wa, sessions, phone, hospital_id, connector, patient, next_action, language=language,
        booking_category=booking_category,
    )


async def _create_booking_and_notify(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None, consent_given_at: str | None = None,
) -> None:
    """The actual "create the appointment and tell the patient" sequence --
    shared by _handle_awaiting_confirmation's CONFIRM_YES branch (an
    appointment type with no consent requirement) and
    _handle_awaiting_consent's own CONFIRM_YES branch (consent just given),
    so this isn't duplicated across the two entry points."""
    if await _reject_if_patient_link_invalid(
        wa, sessions, phone, hospital_id, context.get("active_patient_id"), connector, language=language,
    ):
        return
    scheduled_at = datetime.fromisoformat(f"{context['slot_date']}T{context['slot_time']}")
    # Checked right before create_booking, not earlier -- context can still
    # change via "change selection" up to this exact point.
    flow = get_type_flow(context.get("appointment_type_id"))
    if flow.validate_booking is not None:
        conflict = flow.validate_booking(
            connector, hospital_id, context.get("active_patient_id"), context.get("department_id"), scheduled_at,
        )
        if conflict is not None:
            await wa.send_text(phone, t(conflict, language))
            sessions.reset(hospital_id, phone)
            return
    try:
        appointment = connector.create_booking(
            hospital_id=hospital_id,
            phone=phone,
            department_id=context.get("department_id"),
            doctor_id=context.get("doctor_id"),
            scheduled_at=scheduled_at,
            patient_name=context.get("patient_name"),
            patient_age=context.get("patient_age"),
            patient_id=context.get("active_patient_id"),
            appointment_type_id=context.get("appointment_type_id"),
            consent_given_at=consent_given_at,
            resource_id=context.get("resource_id"),
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
            body_text=t(DUPLICATE_BOOKING_TEXT, language, doctor_name=doctor_name),
            buttons=[
                {"id": GOTO_MAIN_MENU, "title": t(MAIN_MENU_BUTTON, language)},
                {"id": _manage_cancel_id(exc.existing_appointment_id), "title": t(CANCEL_BUTTON, language)},
                {"id": _manage_reschedule_id(exc.existing_appointment_id), "title": t(RESCHEDULE_SHORT, language)},
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
    # flow.build_success_summary (Follow-up's own card shape) fully replaces
    # the generic text below when set -- the Reschedule/Cancel/Main-Menu
    # buttons further down are unaffected either way.
    if flow.build_success_summary is not None:
        summary = flow.build_success_summary(appointment, context, hospital_id)
    else:
        summary = t(
            BOOKING_CONFIRMED, language,
            reference_id=appointment.reference_id,
            patient_name=context.get("patient_name"),
            department_name=appointment.department_name,
            doctor_name=appointment.doctor_name,
            date_label=appointment.scheduled_at.strftime("%A, %d %B %Y"),
            time_label=appointment.scheduled_at.strftime("%I:%M %p"),
        )
    # Tele-consultation Phase 2, revised per the user's own explicit
    # "soft-gate" call: the video link is generated and persisted right here
    # (needs appointment.id to attach it to), but deliberately NOT shown in
    # this immediate confirmation -- it's sent later, close to the actual
    # slot, via the reminder message (reminders/scheduler.py) instead, so a
    # patient can't casually share/join a "live" room hours or days before
    # the appointment. None for every other type, so their notification is
    # untouched -- the hook's return value is no longer consulted by either
    # call site (this one, or reschedule.py's own) now that neither
    # notification shows the link directly.
    if flow.on_booking_confirmed is not None:
        await flow.on_booking_confirmed(appointment, connector, context)
    summary = _append_closing_message(summary, closing_message_text)
    # Item 3: quick-action buttons attached to the success message --
    # tapping any of them, even long after this session has expired,
    # routes straight into that flow for THIS specific appointment
    # (flows.py checks for these ids before normal session dispatch).
    await wa.send_buttons(
        to=phone,
        body_text=summary,
        buttons=[
            {"id": _manage_reschedule_id(appointment.id), "title": t(RESCHEDULE_SHORT, language)},
            {"id": _manage_cancel_id(appointment.id), "title": t(CANCEL_BUTTON, language)},
            {"id": GOTO_MAIN_MENU, "title": t(MAIN_MENU_BUTTON, language)},
        ],
    )
    # STATE_BOOKED is terminal and resets to IDLE immediately, never written
    # to the session store. A fully completed booking also clears language
    # and active_patient_id -- next conversation re-picks language and
    # re-resolves patient identity fresh. Every other reset() call site
    # keeps preserving both.
    sessions.reset(hospital_id, phone, keep_language=False, keep_active_patient=False)


async def _handle_awaiting_confirmation(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            # Appointment type step (WhatsApp flow alignment): a type whose
            # requires_consent is TRUE (e.g. tele-consultation, second
            # opinion) needs an explicit consent step BEFORE the appointment
            # is actually created -- everything else (department/doctor/
            # date/time review, patient-link validity) is already settled by
            # the time confirmation is reached, so this only gates the final
            # create_booking() call, not re-asking anything already answered.
            if context.get("appointment_type_requires_consent"):
                sessions.set(hospital_id, phone, STATE_AWAITING_CONSENT, context)
                await _send_consent_prompt(
                    wa, phone, context.get("appointment_type_label", ""), language=language,
                )
                return
            await _create_booking_and_notify(
                wa, sessions, phone, hospital_id, context, connector,
                language=language, closing_message_text=closing_message_text,
            )
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, t(BOOKING_NOT_CONFIRMED, language))
            sessions.reset(hospital_id, phone)
            return
        if rid == BACK_ID:
            sessions.set(hospital_id, phone, STATE_AWAITING_CHANGE_SELECTION, context)
            await _send_change_selection_menu(wa, phone, hospital_id, connector, language=language, context=context)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_CONFIRMATION, context)
    await _send_confirmation(wa, phone, hospital_id, context, language=language)


async def _handle_awaiting_consent(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Reached only for an appointment type with requires_consent=TRUE, right
    after confirmation -- see _handle_awaiting_confirmation's own CONFIRM_YES
    branch. Declining does NOT go back to confirmation (there's nothing to
    change that would make consent unnecessary for this type -- the patient
    would need to pick a different appointment type instead, i.e. start
    over), so this ends the flow with an explanatory message rather than
    looping."""
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            await _create_booking_and_notify(
                wa, sessions, phone, hospital_id, context, connector,
                language=language, closing_message_text=closing_message_text,
                consent_given_at=datetime.now().isoformat(),
            )
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, t(CONSENT_DECLINED, language))
            sessions.reset(hospital_id, phone)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_CONSENT, context)
    await _send_consent_prompt(wa, phone, context.get("appointment_type_label", ""), language=language)


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
    await _send_change_selection_menu(wa, phone, hospital_id, connector, language=language, context=context)

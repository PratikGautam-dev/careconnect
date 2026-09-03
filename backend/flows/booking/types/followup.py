# flows/booking/types/followup.py
"""Follow-up: shows every department's most recent ATTENDED appointment
still within the hospital's eligibility window (hospital_settings.
followup_validity_days, docs/per-appointment-type-flow-plan.md Phase 2 Step
2 follow-up), lets the patient pick one, then skips department/doctor
selection entirely and jumps straight to date selection -- floored to
strictly after that previous visit's own date, since a follow-up can't
predate the visit it follows. Confirmation and success then show Follow-up's
own card text (build_confirmation_summary/build_success_summary hooks), not
the generic cards every other type shares; the Confirm/Cancel/Back and
Reschedule/Cancel/Main-Menu buttons underneath are unchanged either way.

messages.py imports are lazy (inside functions) to avoid a circular import:
this module -> types.registry -> this module."""

import db.repository as db
from flows.booking.state import (
    BACK_ID, GOTO_MAIN_MENU, STATE_AWAITING_APPOINTMENT_TYPE, STATE_AWAITING_DATE,
    STATE_AWAITING_FOLLOWUP_SELECTION, _HISTORY_KEY, _appointment_row_id, _parse_appointment_row_id, _push_history,
)
from flows.booking.types.base import NO_DOCTOR_FLOW, TypeFlow
from core.translations import t
from core.translations.booking import (
    CONSULTATION_FEE_LINE,
    FOLLOWUP_APPOINTMENT_CONFIRMED,
    FOLLOWUP_CONFIRMATION_SUMMARY,
    FOLLOWUP_ELIGIBLE_LIST_PROMPT,
    FOLLOWUP_ELIGIBLE_SECTION_TITLE,
    NO_PREVIOUS_APPOINTMENT_FOR_FOLLOWUP,
    VIEW_FOLLOWUP_OPTIONS_BUTTON,
)
from core.translations.common import BACK_OPTION
from core.translations.menu import MAIN_MENU_BUTTON


def _followup_row_title(appt) -> str:
    return f"{appt.department_name} - {appt.doctor_name} ({appt.scheduled_at.strftime('%d %b %Y')})"


def _fee_line(hospital_id: int, language: str) -> str:
    fee = db.get_hospital_settings(hospital_id)["followup_fee"]
    if fee is None:
        return ""
    amount = int(fee) if fee == int(fee) else fee
    return t(CONSULTATION_FEE_LINE, language, amount=amount)


async def _fetch_eligible(hospital_id: int, connector, context: dict) -> list:
    patient_id = context.get("active_patient_id")
    if patient_id is None:
        return []
    validity_days = db.get_followup_validity_days(hospital_id)
    return connector.get_followup_eligible_appointments(hospital_id, patient_id, validity_days)


async def _send_no_eligible_screen(wa, phone: str, hospital_id: int, sessions, context: dict, connector, language: str) -> None:
    """Back and Main Menu both just exit to the main menu here -- there's no
    earlier booking step before appointment-type selection for Back to
    meaningfully return to (BACK_ID's own handler at
    STATE_AWAITING_APPOINTMENT_TYPE already does exactly this). Covers both
    "never had an attended visit" and "every attended visit has aged out of
    the eligibility window" -- same message either way.

    Sends the appointment-type list itself first (same category this came
    from), with the "no previous appointment" text as its body instead of
    the list's own generic prompt, followed by the separate Back/Main Menu
    buttons message -- so the patient can pick a different type directly
    instead of only being able to back out entirely."""
    from flows.booking.messages import _send_appointment_type_menu

    sessions.set(hospital_id, phone, STATE_AWAITING_APPOINTMENT_TYPE, context)
    await _send_appointment_type_menu(
        wa, phone, hospital_id, connector, language=language, category=context.get("appointment_type_category"),
        body_text_override=t(NO_PREVIOUS_APPOINTMENT_FOR_FOLLOWUP, language, name=context.get("patient_name")),
    )
    await wa.send_buttons(
        to=phone,
        body_text="​",
        buttons=[
            {"id": BACK_ID, "title": t(BACK_OPTION, language)},
            {"id": GOTO_MAIN_MENU, "title": t(MAIN_MENU_BUTTON, language)},
        ],
    )


async def _send_followup_eligible_list(wa, phone: str, eligible: list, patient_name, language: str = "en") -> None:
    from flows.booking.messages import _send_back_button

    rows = [{"id": _appointment_row_id(a.id), "title": _followup_row_title(a)} for a in eligible]
    await wa.send_list(
        to=phone,
        body_text=t(FOLLOWUP_ELIGIBLE_LIST_PROMPT, language, patient_name=patient_name),
        button_text=t(VIEW_FOLLOWUP_OPTIONS_BUTTON, language),
        sections=[{"title": t(FOLLOWUP_ELIGIBLE_SECTION_TITLE, language), "rows": rows}],
    )
    await _send_back_button(wa, phone, language=language)


async def _resend_followup_eligible_list(wa, phone: str, hospital_id: int, context: dict, connector, language: str = "en") -> None:
    """Re-queries rather than trusting a stashed list in context -- eligibility
    can genuinely change between showing this screen and a Back/stale-tap
    landing back on it (a visit aging out of the window, mid-conversation)."""
    eligible = await _fetch_eligible(hospital_id, connector, context)
    await _send_followup_eligible_list(wa, phone, eligible, context.get("patient_name"), language=language)


async def _on_followup_selected(
    wa, sessions, phone: str, hospital_id: int, connector, context: dict, language: str = "en",
) -> None:
    """TypeFlow.on_selected hook: replaces the normal "go to steps[0]"
    behavior for Follow-up."""
    eligible = await _fetch_eligible(hospital_id, connector, context)
    if not eligible:
        await _send_no_eligible_screen(wa, phone, hospital_id, sessions, context, connector, language)
        return
    history = _push_history(context, STATE_AWAITING_APPOINTMENT_TYPE)
    new_context = {**context, _HISTORY_KEY: history}
    sessions.set(hospital_id, phone, STATE_AWAITING_FOLLOWUP_SELECTION, new_context)
    await _send_followup_eligible_list(wa, phone, eligible, context.get("patient_name"), language=language)


async def _handle_awaiting_followup_selection(
    wa, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    from flows.booking.messages import _handle_back_navigation, _notify_no_slots_available, _send_date_menu

    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        appt_id = _parse_appointment_row_id(reply["id"])
        if appt_id is not None:
            eligible = await _fetch_eligible(hospital_id, connector, context)
            match = next((a for a in eligible if a.id == appt_id), None)
            if match is not None:
                previous_visit_date = match.scheduled_at.strftime("%Y-%m-%d")
                slots = connector.get_available_slots(hospital_id, match.doctor_id)
                if not any(s["date"] > previous_visit_date for s in slots):
                    await _notify_no_slots_available(wa, sessions, hospital_id, phone, match.doctor_name, language=language)
                    return
                history = _push_history(context, STATE_AWAITING_FOLLOWUP_SELECTION)
                new_context = {
                    **context,
                    "department_id": match.department_id, "department_name": match.department_name,
                    "doctor_id": match.doctor_id, "doctor_name": match.doctor_name,
                    "followup_previous_appointment_id": match.id,
                    "followup_previous_visit_date": previous_visit_date,
                    "followup_previous_visit_label": match.scheduled_at.strftime("%d %b %Y"),
                    _HISTORY_KEY: history,
                }
                sessions.set(hospital_id, phone, STATE_AWAITING_DATE, new_context)
                await _send_date_menu(
                    wa, phone, hospital_id, match.doctor_id, match.doctor_name, connector,
                    language=language, min_date=previous_visit_date,
                )
                return
    # Stale/unrecognized tap -- re-show the same list.
    await _resend_followup_eligible_list(wa, phone, hospital_id, context, connector, language=language)


def _build_followup_confirmation_summary(context: dict, hospital_id: int) -> str:
    """TypeFlow.build_confirmation_summary hook -- see flows/booking/messages.py's
    _send_confirmation, which calls this instead of building the generic
    CONFIRM_BOOKING_SUMMARY card for a Follow-up booking."""
    language = context.get("language", "en")
    patient = db.get_patient(hospital_id, context.get("active_patient_id"))
    return t(
        FOLLOWUP_CONFIRMATION_SUMMARY, language,
        patient_name=context.get("patient_name"),
        patient_code=(patient.get("patient_display_id") if patient else None) or "—",
        appointment_type_label=context.get("appointment_type_label"),
        department_name=context.get("department_name"), doctor_name=context.get("doctor_name"),
        previous_visit_label=context.get("followup_previous_visit_label"),
        date_label=context.get("date_label"), time_label=context.get("slot_time"),
        fee_line=_fee_line(hospital_id, language),
    )


def _build_followup_success_summary(appointment, context: dict, hospital_id: int) -> str:
    """TypeFlow.build_success_summary hook -- see flows/booking/book.py's
    _create_booking_and_notify, which calls this instead of building the
    generic BOOKING_CONFIRMED text for a Follow-up booking."""
    language = context.get("language", "en")
    return t(
        FOLLOWUP_APPOINTMENT_CONFIRMED, language,
        reference_id=appointment.reference_id,
        patient_name=context.get("patient_name"),
        doctor_name=appointment.doctor_name,
        department_name=appointment.department_name,
        date_label=appointment.scheduled_at.strftime("%d %b %Y"),
        time_label=appointment.scheduled_at.strftime("%I:%M %p"),
    )


# steps=NO_DOCTOR_FLOW (not FULL_FLOW): purely so messages.py's
# change-selection menu hides "Change Department"/"Change Doctor" here too,
# same as diagnostic/lab. book.py checks on_selected before ever consulting
# `steps` for this type's own entry/transition logic.
FLOW = TypeFlow(
    type_id="followup",
    steps=NO_DOCTOR_FLOW,
    on_selected=_on_followup_selected,
    build_confirmation_summary=_build_followup_confirmation_summary,
    build_success_summary=_build_followup_success_summary,
)

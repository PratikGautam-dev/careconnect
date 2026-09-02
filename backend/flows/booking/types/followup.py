# flows/booking/types/followup.py
"""Follow-up: skips department/doctor selection, auto-using the same doctor
as the patient's last ATTENDED appointment. Shows a confirm screen, then
goes straight to date selection. No prior attended visit -> back to
appointment-type selection.

messages.py imports are lazy (inside functions) to avoid a circular import:
this module -> types.registry -> this module."""
from flows.booking.state import (
    BACK_ID, CONFIRM_YES, GOTO_MAIN_MENU, STATE_AWAITING_APPOINTMENT_TYPE, STATE_AWAITING_DATE,
    STATE_AWAITING_FOLLOWUP_CONFIRM, _HISTORY_KEY, _push_history,
)
from flows.booking.types.base import NO_DOCTOR_FLOW, TypeFlow
from core.translations import t
from core.translations.booking import (
    CONFIRM_BUTTON,
    FOLLOWUP_CONFIRM_PROMPT,
    NO_PREVIOUS_APPOINTMENT_FOR_FOLLOWUP,
)
from core.translations.common import BACK_OPTION
from core.translations.menu import MAIN_MENU_BUTTON


async def _send_followup_confirm_prompt(wa, phone: str, context: dict, language: str = "en") -> None:
    """Built entirely from `context` -- never re-queried, so a re-prompt
    (stale tap, Back-navigation) needs no DB round-trip."""
    body = t(FOLLOWUP_CONFIRM_PROMPT, language,
        doctor_name=context.get("doctor_name"), department_name=context.get("department_name"),
        last_visit_label=context.get("followup_last_visit_label"),
    )
    await wa.send_buttons(
        to=phone,
        body_text=body,
        buttons=[
            {"id": CONFIRM_YES, "title": t(CONFIRM_BUTTON, language)},
            {"id": BACK_ID, "title": t(BACK_OPTION, language)},
        ],
    )


async def _on_followup_selected(
    wa, sessions, phone: str, hospital_id: int, connector, context: dict, language: str = "en",
) -> None:
    """TypeFlow.on_selected hook: replaces the normal "go to steps[0]"
    behavior for Follow-up."""
    patient_id = context.get("active_patient_id")
    last = connector.get_last_attended_appointment(hospital_id, patient_id) if patient_id is not None else None
    if last is None:
        # Back and Main Menu both just exit to the main menu here -- there's
        # no earlier booking step before appointment-type selection for Back
        # to meaningfully return to (BACK_ID's own handler at
        # STATE_AWAITING_APPOINTMENT_TYPE already does exactly this).
        sessions.set(hospital_id, phone, STATE_AWAITING_APPOINTMENT_TYPE, context)
        await wa.send_buttons(
            to=phone,
            body_text=t(NO_PREVIOUS_APPOINTMENT_FOR_FOLLOWUP, language, name=context.get("patient_name")),
            buttons=[
                {"id": BACK_ID, "title": t(BACK_OPTION, language)},
                {"id": GOTO_MAIN_MENU, "title": t(MAIN_MENU_BUTTON, language)},
            ],
        )
        return
    new_context = {
        **context,
        "department_id": last.department_id, "department_name": last.department_name,
        "doctor_id": last.doctor_id, "doctor_name": last.doctor_name,
        "followup_last_appointment_id": last.id,
        "followup_last_visit_label": last.scheduled_at.strftime("%d %b %Y"),
    }
    sessions.set(hospital_id, phone, STATE_AWAITING_FOLLOWUP_CONFIRM, new_context)
    await _send_followup_confirm_prompt(wa, phone, new_context, language=language)


async def _handle_awaiting_followup_confirm(
    wa, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    from flows.booking.messages import _handle_back_navigation, _notify_no_slots_available, _send_date_menu, _send_main_menu

    doctor_id: str | None = context.get("doctor_id")
    if not doctor_id:
        # Corrupted/incomplete session context -- fail safe, same convention
        # as _handle_awaiting_doctor/_handle_awaiting_date in book.py.
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        if reply["id"] == CONFIRM_YES:
            doctor_name = context.get("doctor_name", "")
            if not connector.get_available_slots(hospital_id, doctor_id):
                await _notify_no_slots_available(wa, sessions, hospital_id, phone, doctor_name, language=language)
                return
            new_context = {**context, _HISTORY_KEY: _push_history(context, STATE_AWAITING_FOLLOWUP_CONFIRM)}
            sessions.set(hospital_id, phone, STATE_AWAITING_DATE, new_context)
            await _send_date_menu(wa, phone, hospital_id, doctor_id, doctor_name, connector, language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_FOLLOWUP_CONFIRM, context)
    await _send_followup_confirm_prompt(wa, phone, context, language=language)


# steps=NO_DOCTOR_FLOW (not FULL_FLOW): purely so messages.py's
# change-selection menu hides "Change Department"/"Change Doctor" here too,
# same as diagnostic/lab. book.py checks on_selected before ever consulting
# `steps` for this type's own entry/transition logic.
FLOW = TypeFlow(
    type_id="followup",
    steps=NO_DOCTOR_FLOW,
    on_selected=_on_followup_selected,
)

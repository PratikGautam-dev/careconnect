# flows/booking/cancel.py
"""ARCHITECTURE_PLAN.md Phase 3b: the cancel sub-flow (SPEC Section 3.3/5),
split out of the former single core/booking_flow.py module."""
from connectors import Connector
from core.translations import t
from core.translations.cancel_reschedule import (
    APPOINTMENT_CANCELLED,
    APPOINTMENT_LOOKUP_ERROR,
    CANCELLATION_ABORTED,
    NO_UPCOMING_TO_CANCEL,
)
from core.whatsapp import WhatsAppClient

from flows.booking.messages import (
    _find_selected_appointment, _send_appointment_selection_menu, _send_cancel_confirm, _send_main_menu,
    _send_patient_selector, _send_post_action_menu,
)
from flows.booking.state import (
    CONFIRM_NO, CONFIRM_YES, STATE_AWAITING_CANCEL_CONFIRM, STATE_AWAITING_CANCEL_SELECTION, _append_closing_message,
)

async def _start_cancel_flow_for_appointment(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, appt, language: str = "en",
) -> None:
    """Jumps straight to THIS appointment's own cancel-confirm step, skipping
    the "which appointment" selection list -- the shared target for the
    booking-success/duplicate-booking quick-action buttons and My
    Appointments' inline actions."""
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_CONFIRM, {"appointment_id": appt.id})
    await _send_cancel_confirm(wa, phone, appt, language=language)


async def _start_cancel_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
    active_patient_id: int | None = None,
) -> None:
    """Patient identity SEPARATION (Spec.md Section 0): a "whose
    appointments" pre-step, only shown when this phone has more than one
    active linked patient -- the single-patient case (every phone before
    this section, and any phone with just one linked patient) goes straight
    to _start_cancel_flow_for_patient() below, zero added friction.

    CareConnect architecture doc alignment (Spec.md Section 0): when
    `active_patient_id` is given (flows.py's real-traffic path, already
    resolved up front), skip this module's own per-feature selector
    entirely -- see _start_booking_flow()'s own docstring for the full
    reasoning, identical here."""
    if active_patient_id is not None:
        await _start_cancel_flow_for_patient(wa, sessions, phone, hospital_id, connector, active_patient_id, language=language)
        return
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
        await wa.send_text(phone, t(NO_UPCOMING_TO_CANCEL, language))
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
        await wa.send_text(phone, t(APPOINTMENT_LOOKUP_ERROR, language))
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return

    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == CONFIRM_YES:
            connector.cancel_booking(hospital_id, appt.id)
            when = appt.scheduled_at.strftime("%A, %d %B at %H:%M")
            cancelled_text = t(APPOINTMENT_CANCELLED, language, doctor_name=appt.doctor_name, when=when)
            await wa.send_text(phone, _append_closing_message(cancelled_text, closing_message_text))
            sessions.reset(hospital_id, phone)
            await _send_post_action_menu(wa, phone, language=language)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, t(CANCELLATION_ABORTED, language))
            sessions.reset(hospital_id, phone)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_CANCEL_CONFIRM, context)
    await _send_cancel_confirm(wa, phone, appt, language=language)

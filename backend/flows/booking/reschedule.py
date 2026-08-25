# flows/booking/reschedule.py
"""ARCHITECTURE_PLAN.md Phase 3b: the reschedule sub-flow (SPEC Section
3.3/5) -- date/time steps reuse the booking flow's own _send_date_menu/
_send_time_menu, scoped to the appointment's existing doctor. Split out of
the former single core/booking_flow.py module."""
from datetime import datetime

from connectors import Connector
from core.translations import t
from core.whatsapp import WhatsAppClient
from db.connection import IntegrityError

from flows.booking.messages import (
    _find_selected_appointment, _handle_slot_taken, _notify_no_slots_available, _send_appointment_selection_menu,
    _send_back_button, _send_date_menu, _send_main_menu, _send_patient_selector, _send_reschedule_confirm,
    _send_time_menu,
)
from flows.booking.state import (
    BACK_ID, CONFIRM_NO, CONFIRM_YES, STATE_AWAITING_RESCHEDULE_CONFIRM, STATE_AWAITING_RESCHEDULE_DATE,
    STATE_AWAITING_RESCHEDULE_SELECTION, STATE_AWAITING_RESCHEDULE_SLOT, _append_closing_message, _date_label,
    _find_by_id,
)

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


async def _start_reschedule_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
    active_patient_id: int | None = None,
) -> None:
    """Patient identity SEPARATION (Spec.md Section 0): same "whose
    appointments" pre-step as cancel above, only shown when >1 active
    patient is linked.

    CareConnect architecture doc alignment (Spec.md Section 0): see
    _start_cancel_flow()'s own docstring -- identical `active_patient_id`
    short-circuit for flows.py's real-traffic path."""
    if active_patient_id is not None:
        await _start_reschedule_flow_for_patient(wa, sessions, phone, hospital_id, connector, active_patient_id, language=language)
        return
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

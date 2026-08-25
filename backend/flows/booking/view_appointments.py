# flows/booking/view_appointments.py
"""ARCHITECTURE_PLAN.md Phase 3b: the "My Appointments" view/manage
sub-flow, split out of the former single core/booking_flow.py module."""
from connectors import Connector
from core.translations import t
from core.whatsapp import WhatsAppClient

from flows.booking.messages import _send_patient_selector
from flows.booking.state import (
    GOTO_MAIN_MENU, STATE_AWAITING_VIEW_APPOINTMENT_ACTION, _appointment_row_id, _cap_rows, _manage_cancel_id,
    _manage_reschedule_id, _parse_appointment_row_id,
)

async def _start_view_appointments_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
    active_patient_id: int | None = None,
) -> None:
    """Patient identity SEPARATION (Spec.md Section 0): same "whose
    appointments" pre-step as cancel/reschedule above, only shown when >1
    active patient is linked. Relocated here from flows.py (was
    _send_view_appointments, called directly) so the shared patient
    selector can reach it without a circular import -- this module never
    imports flows.py, but the selector needs to route booking, cancel,
    reschedule, AND view_appointments, so all four now live here.

    CareConnect architecture doc alignment (Spec.md Section 0): see
    _start_cancel_flow()'s own docstring -- identical `active_patient_id`
    short-circuit for flows.py's real-traffic path."""
    if active_patient_id is not None:
        await _send_view_appointments(wa, sessions, phone, hospital_id, connector, language=language, active_patient_id=active_patient_id)
        return
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

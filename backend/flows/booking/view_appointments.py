# flows/booking/view_appointments.py
"""ARCHITECTURE_PLAN.md Phase 3b: the "My Appointments" view/manage
sub-flow, split out of the former single core/booking_flow.py module."""
from datetime import datetime, timedelta

from connectors import Connector
from core.translations import t
from core.translations.menu import (
    MAIN_MENU_BUTTON,
    RESCHEDULE_SHORT,
    VIEW_APPOINTMENTS_HEADER,
    VIEW_APPOINTMENTS_HEADER_PREVIOUS,
    VIEW_APPOINTMENTS_LIST,
    VIEW_APPOINTMENTS_LIST_PREVIOUS,
    VIEW_APPOINTMENTS_RANGE_PREVIOUS_BUTTON,
    VIEW_APPOINTMENTS_RANGE_PROMPT,
    VIEW_APPOINTMENTS_RANGE_UPCOMING_BUTTON,
)
from core.translations.patient_identity import BACK_TO_MENU_OPTION
from core.translations.cancel_reschedule import (
    VIEW_APPOINTMENTS_BUTTON,
    YOUR_APPOINTMENTS_SECTION_TITLE,
)
from core.translations.booking import (
    CANCEL_BUTTON,
    MANAGE_APPOINTMENT_PROMPT,
)
from core.whatsapp import WhatsAppClient
from db.models import STATUS_BOOKED

from flows.booking.messages import _send_patient_selector, _send_post_action_menu
from flows.booking.state import (
    GOTO_MAIN_MENU, MAIN_MENU_CANCEL, MAIN_MENU_RESCHEDULE, STATE_AWAITING_VIEW_APPOINTMENT_ACTION,
    STATE_AWAITING_VIEW_APPOINTMENTS_RANGE, VIEW_APPOINTMENTS_RANGE_PREVIOUS_ID, VIEW_APPOINTMENTS_RANGE_UPCOMING_ID,
    _appointment_row_id, _cap_rows, _manage_cancel_id, _manage_reschedule_id, _parse_appointment_row_id,
)

_RANGE_WINDOW_DAYS = 30


async def _start_view_appointments_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
    active_patient_id: int | None = None,
) -> None:
    """"My Appointments" -> Previous/Upcoming 1 Month range choice, shown
    FIRST -- before the "whose appointments" patient pre-step below, which
    only makes sense once we know which range is being asked for (its own
    prompt/next_action string is range-specific, see
    _handle_awaiting_view_appointments_range)."""
    sessions.set(hospital_id, phone, STATE_AWAITING_VIEW_APPOINTMENTS_RANGE, {"active_patient_id": active_patient_id})
    await wa.send_buttons(
        to=phone,
        body_text=t(VIEW_APPOINTMENTS_RANGE_PROMPT, language),
        buttons=[
            {"id": VIEW_APPOINTMENTS_RANGE_PREVIOUS_ID, "title": t(VIEW_APPOINTMENTS_RANGE_PREVIOUS_BUTTON, language)},
            {"id": VIEW_APPOINTMENTS_RANGE_UPCOMING_ID, "title": t(VIEW_APPOINTMENTS_RANGE_UPCOMING_BUTTON, language)},
        ],
    )


async def _handle_awaiting_view_appointments_range(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    active_patient_id = context.get("active_patient_id")
    if reply["type"] != "interactive_reply" or reply["id"] not in (
        VIEW_APPOINTMENTS_RANGE_PREVIOUS_ID, VIEW_APPOINTMENTS_RANGE_UPCOMING_ID,
    ):
        # Stale/unrecognized tap -- re-show the range choice rather than a
        # dead end (same discipline as every other stale-tap branch in this
        # state machine).
        await _start_view_appointments_flow(
            wa, sessions, phone, hospital_id, connector, language=language, active_patient_id=active_patient_id,
        )
        return
    range_ = "previous" if reply["id"] == VIEW_APPOINTMENTS_RANGE_PREVIOUS_ID else "upcoming"
    if active_patient_id is not None:
        await _send_view_appointments(
            wa, sessions, phone, hospital_id, connector, language=language, active_patient_id=active_patient_id,
            range_=range_,
        )
        return
    patients = connector.list_active_patients(hospital_id, phone)
    if len(patients) > 1:
        await _send_patient_selector(wa, sessions, phone, hospital_id, connector, f"view_appointments_{range_}", language=language)
        return
    await _send_view_appointments(wa, sessions, phone, hospital_id, connector, language=language, range_=range_)


async def _send_view_appointments(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
    active_patient_id: int | None = None, range_: str = "upcoming",
) -> None:
    """Item 6 (Spec.md Section 0): each listed appointment is now a tappable
    row (not just a plain-text summary) -- picking one shows THAT
    appointment's own Cancel/Reschedule quick actions directly. Patient
    identity SEPARATION: scoped to `active_patient_id` when given (a
    specific family member was selected); None means "show everyone linked
    to this phone" (the natural single-patient case, or the explicit "All"
    choice from the patient selector), with each row prefixed by its own
    patient's name whenever more than one patient could plausibly be
    shown.

    Account, not phone, scoped (confirmed with the user): appointments are
    fetched for every patient CURRENTLY linked to this phone's
    care_connect_account at this hospital -- see
    db/repositories/appointments.py's get_appointments_for_account_in_range
    for why appointments.phone alone isn't the right key (a WhatsApp number
    can change while the account persists). `range_` picks a 30-day window:
    "upcoming" is [now, now+30d] and booked-only (a cancelled future-dated
    appointment isn't "upcoming"); "previous" is [now-30d, now) and any
    status (a true history view, cancellations included)."""
    account = connector.identify_contact(phone, phone_number=phone)
    now = datetime.now()
    if range_ == "previous":
        appointments = connector.get_appointments_in_range(hospital_id, account["id"], now - timedelta(days=_RANGE_WINDOW_DAYS), now)
    else:
        appointments = connector.get_appointments_in_range(
            hospital_id, account["id"], now, now + timedelta(days=_RANGE_WINDOW_DAYS), statuses=[STATUS_BOOKED],
        )
    patient_names = None
    if active_patient_id is not None:
        appointments = [a for a in appointments if a.patient_id == active_patient_id]
    else:
        patients = connector.list_active_patients(hospital_id, phone)
        if len(patients) > 1:
            patient_names = {p["id"]: p["name"] for p in patients}
    if not appointments:
        sessions.reset(hospital_id, phone)
        empty_text = VIEW_APPOINTMENTS_LIST_PREVIOUS if range_ == "previous" else VIEW_APPOINTMENTS_LIST
        await wa.send_text(phone, t(empty_text, language))
        await _send_post_action_menu(wa, phone, language=language)
        return
    rows = []
    for a in appointments:
        title = a.doctor_name
        if patient_names and a.patient_id in patient_names:
            title = f"{patient_names[a.patient_id]} — {a.doctor_name}"
        description = f"{a.department_name} — {a.scheduled_at.strftime('%a %d %b %Y, %H:%M')}"
        if range_ == "previous":
            # Mixed statuses in this view (unlike upcoming, which is always
            # booked) -- call out cancelled/rescheduled rows so a patient
            # doesn't read a past cancellation as an attended visit.
            description = f"{description} — {a.status.title()}"
        rows.append({"id": _appointment_row_id(a.id), "title": title, "description": description})
    rows.append({"id": GOTO_MAIN_MENU, "title": t(BACK_TO_MENU_OPTION, language)})
    rows = _cap_rows(rows, "view appointments menu")
    sessions.set(hospital_id, phone, STATE_AWAITING_VIEW_APPOINTMENT_ACTION, {"active_patient_id": active_patient_id, "range": range_})
    header = VIEW_APPOINTMENTS_HEADER_PREVIOUS if range_ == "previous" else VIEW_APPOINTMENTS_HEADER
    await wa.send_list(
        to=phone,
        body_text=t(header, language),
        button_text=t(VIEW_APPOINTMENTS_BUTTON, language),
        sections=[{"title": t(YOUR_APPOINTMENTS_SECTION_TITLE, language), "rows": rows}],
    )
    await _send_post_action_menu(wa, phone, language=language)


async def _handle_awaiting_view_appointment_action(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    range_ = context.get("range", "upcoming")
    if reply["type"] == "interactive_reply":
        # The generic post-action buttons sent right under the list
        # (_send_post_action_menu) -- NOT one of the per-appointment rows
        # above them, so handled here rather than falling through to the
        # "stale/unrecognized tap" branch below. Imported lazily (see
        # flows/booking/messages.py's own module docstring on why cancel.py/
        # reschedule.py import back from here, making a top-level import
        # circular).
        if reply["id"] == MAIN_MENU_CANCEL:
            from flows.booking.cancel import _start_cancel_flow
            await _start_cancel_flow(
                wa, sessions, phone, hospital_id, connector, language=language,
                active_patient_id=context.get("active_patient_id"),
            )
            return
        if reply["id"] == MAIN_MENU_RESCHEDULE:
            from flows.booking.reschedule import _start_reschedule_flow
            await _start_reschedule_flow(
                wa, sessions, phone, hospital_id, connector, language=language,
                active_patient_id=context.get("active_patient_id"),
            )
            return
    appt_id = _parse_appointment_row_id(reply["id"]) if reply["type"] == "interactive_reply" else None
    appt = None
    if appt_id is not None:
        appt = next(
            (a for a in connector.get_upcoming_appointments(hospital_id, phone=phone) if a.id == appt_id), None,
        )
    if appt is None:
        # Stale/unrecognized tap, the list went stale between send and
        # reply, OR a tap on a "previous" row -- cancel/reschedule only ever
        # apply to a still-upcoming, still-booked appointment (looked up
        # above via get_upcoming_appointments, which is booked-only), so a
        # past row can never resolve here. Re-showing the current
        # (patient- and range-scoped) list rather than a dead end covers
        # all three cases the same way.
        await _send_view_appointments(
            wa, sessions, phone, hospital_id, connector, language=language,
            active_patient_id=context.get("active_patient_id"), range_=range_,
        )
        return
    sessions.reset(hospital_id, phone)
    await wa.send_buttons(
        to=phone,
        body_text=t(MANAGE_APPOINTMENT_PROMPT, language, doctor_name=appt.doctor_name),
        buttons=[
            {"id": GOTO_MAIN_MENU, "title": t(MAIN_MENU_BUTTON, language)},
            {"id": _manage_cancel_id(appt.id), "title": t(CANCEL_BUTTON, language)},
            {"id": _manage_reschedule_id(appt.id), "title": t(RESCHEDULE_SHORT, language)},
        ],
    )

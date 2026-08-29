# flows/booking/dispatch.py
"""ARCHITECTURE_PLAN.md Phase 3b: the _HANDLERS state-dispatch table and
handle_incoming(), the module's own standalone entry point -- superseded
for real traffic by flows/router.py (see that module's docstring), but
still exercised directly by tests/test_booking_flow.py and friends as a
standalone unit of the state machine. Split out of the former single
core/booking_flow.py module; this is the one file that imports every
sub-flow module, by design (everything else stays one-directional)."""
import logging

from connectors import Connector, Tier1Connector
from core.translations import t
from core.translations.menu import HOSPITAL_INFO_TEXT
from core.whatsapp import WhatsAppClient

from flows.common import is_reset_keyword
from flows.booking.book import (
    _handle_awaiting_appointment_type, _handle_awaiting_change_selection, _handle_awaiting_confirmation,
    _handle_awaiting_consent, _handle_awaiting_date, _handle_awaiting_department, _handle_awaiting_doctor,
    _handle_awaiting_patient_age, _handle_awaiting_patient_name, _handle_awaiting_time_slot, _start_booking_flow,
)
from flows.booking.cancel import _handle_awaiting_cancel_confirm, _handle_awaiting_cancel_selection, _start_cancel_flow
from flows.booking.manage_patients import _handle_awaiting_manage_patients_action, _handle_awaiting_unlink_confirm
from flows.booking.messages import _handle_awaiting_patient_selection, _send_main_menu
from flows.booking.types.daycare import _handle_awaiting_daycare_duration
from flows.booking.types.followup import _handle_awaiting_followup_confirm
from flows.booking.reschedule import (
    _handle_awaiting_reschedule_confirm, _handle_awaiting_reschedule_date, _handle_awaiting_reschedule_selection,
    _handle_awaiting_reschedule_slot, _start_reschedule_flow,
)
from flows.booking.state import (
    FREE_TEXT_INPUT_STATES, MAIN_MENU_BOOK, MAIN_MENU_CANCEL, MAIN_MENU_FAQ, MAIN_MENU_RESCHEDULE,
    STATE_AWAITING_APPOINTMENT_TYPE, STATE_AWAITING_CANCEL_CONFIRM, STATE_AWAITING_CANCEL_SELECTION,
    STATE_AWAITING_CHANGE_SELECTION, STATE_AWAITING_CONFIRMATION, STATE_AWAITING_CONSENT, STATE_AWAITING_DATE,
    STATE_AWAITING_DAYCARE_DURATION,
    STATE_AWAITING_DEPARTMENT, STATE_AWAITING_DOCTOR, STATE_AWAITING_FOLLOWUP_CONFIRM,
    STATE_AWAITING_MANAGE_PATIENTS_ACTION, STATE_AWAITING_PATIENT_AGE, STATE_AWAITING_PATIENT_NAME,
    STATE_AWAITING_PATIENT_SELECTION, STATE_AWAITING_RESCHEDULE_CONFIRM, STATE_AWAITING_RESCHEDULE_DATE,
    STATE_AWAITING_RESCHEDULE_SELECTION, STATE_AWAITING_RESCHEDULE_SLOT, STATE_AWAITING_TIME_SLOT,
    STATE_AWAITING_UNLINK_CONFIRM, STATE_AWAITING_VIEW_APPOINTMENT_ACTION, STATE_AWAITING_VIEW_APPOINTMENTS_RANGE,
    STATE_IDLE,
)
from flows.booking.view_appointments import (
    _handle_awaiting_view_appointment_action, _handle_awaiting_view_appointments_range,
)

logger = logging.getLogger(__name__)

_DEFAULT_CONNECTOR = Tier1Connector()

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
            await wa.send_text(phone, t(HOSPITAL_INFO_TEXT, language))
            return
    # Any other message while IDLE (first contact, free text, stale/unknown id):
    # per spec, IDLE always responds with the welcome message + main menu.
    sessions.reset(hospital_id, phone)
    await _send_main_menu(wa, phone, hospital_name, language=language)


_HANDLERS = {
    STATE_AWAITING_APPOINTMENT_TYPE: _handle_awaiting_appointment_type,
    STATE_AWAITING_FOLLOWUP_CONFIRM: _handle_awaiting_followup_confirm,
    STATE_AWAITING_CONSENT: _handle_awaiting_consent,
    STATE_AWAITING_DEPARTMENT: _handle_awaiting_department,
    STATE_AWAITING_DOCTOR: _handle_awaiting_doctor,
    STATE_AWAITING_DATE: _handle_awaiting_date,
    STATE_AWAITING_TIME_SLOT: _handle_awaiting_time_slot,
    STATE_AWAITING_DAYCARE_DURATION: _handle_awaiting_daycare_duration,
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
    STATE_AWAITING_VIEW_APPOINTMENTS_RANGE: _handle_awaiting_view_appointments_range,
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

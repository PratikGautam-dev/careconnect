# flows/booking/types/daycare.py
"""Daycare Phase 2 (docs/per-appointment-type-flow-plan.md): one extra step
after time-slot selection and before confirmation -- how long the stay is.
Confirmed with the user directly: the arrival date/time pickers stay exactly
as they are for every other FULL_FLOW type (a daycare patient still needs an
arrival slot), one new STATE_AWAITING_DAYCARE_DURATION step is inserted
right after it, offering a hospital-configurable list of duration options
(db/repositories/daycare_duration_options.py) -- this covers both a same-day
few-hour stay and a multi-night admission without a second date picker."""
from connectors import Connector
from core.translations import t
from core.translations.booking import (
    DAYCARE_DURATIONS_SECTION_TITLE,
    SELECT_DAYCARE_DURATION,
    VIEW_DURATIONS_BUTTON,
)
from core.whatsapp import WhatsAppClient

from flows.booking.state import (
    BACK_ID, STATE_AWAITING_CONFIRMATION, STATE_AWAITING_DATE, STATE_AWAITING_DAYCARE_DURATION,
    STATE_AWAITING_DEPARTMENT, STATE_AWAITING_DOCTOR, STATE_AWAITING_TIME_SLOT,
    _HISTORY_KEY, _push_history,
)
from flows.booking.types.base import TypeFlow, existing_department_appointment

# Same shape as base.py's FULL_FLOW, with STATE_AWAITING_DAYCARE_DURATION
# inserted before confirmation -- kept here, not in base.py, since this is
# the one type that needs it (base.py's shared constants are only for step
# lists genuinely reused by more than one type module).
_STEPS = (
    STATE_AWAITING_DEPARTMENT, STATE_AWAITING_DOCTOR, STATE_AWAITING_DATE, STATE_AWAITING_TIME_SLOT,
    STATE_AWAITING_DAYCARE_DURATION, STATE_AWAITING_CONFIRMATION,
)


async def _send_daycare_duration_menu(wa: WhatsAppClient, phone: str, hospital_id: int, connector: Connector, language: str = "en") -> None:
    rows = [{"id": str(o["id"]), "title": o["label"]} for o in connector.get_daycare_duration_options(hospital_id)]
    await wa.send_list(
        to=phone,
        body_text=t(SELECT_DAYCARE_DURATION, language),
        button_text=t(VIEW_DURATIONS_BUTTON, language),
        sections=[{"title": t(DAYCARE_DURATIONS_SECTION_TITLE, language), "rows": rows}],
    )


async def _handle_awaiting_daycare_duration(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    # Deferred imports: messages.py -> types.registry -> daycare would
    # otherwise cycle back through this module (same reason followup.py's
    # own handler lazy-imports _resend_menu_for_state's caller instead).
    from flows.booking.messages import _handle_back_navigation, _send_confirmation

    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        # Row ids sent to WhatsApp are the option's integer id, stringified
        # (_send_daycare_duration_menu above) -- str() both sides here rather
        # than reusing state.py's _find_by_id, which compares ids as-is and
        # would never match an int id against WhatsApp's always-string reply.
        option = next(
            (o for o in connector.get_daycare_duration_options(hospital_id) if str(o["id"]) == reply["id"]), None,
        )
        if option:
            new_context = {
                **context,
                "daycare_duration_hours": option["hours"],
                "daycare_duration_label": option["label"],
                _HISTORY_KEY: _push_history(context, STATE_AWAITING_DAYCARE_DURATION),
            }
            sessions.set(hospital_id, phone, STATE_AWAITING_CONFIRMATION, new_context)
            await _send_confirmation(wa, phone, hospital_id, new_context, language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_DAYCARE_DURATION, context)
    await _send_daycare_duration_menu(wa, phone, hospital_id, connector, language=language)


async def _on_daycare_duration_confirmed(
    appointment_id: int, hospital_id: int, patient_id: int | None, connector: Connector, context: dict,
) -> None:
    """Fresh booking only -- context["daycare_duration_hours"] is set by
    _handle_awaiting_daycare_duration above right before confirmation. A
    reschedule's context never has it (that flow only re-asks date/time, not
    duration): connectors.tier1.Tier1Connector.reschedule_booking() already
    carries the ORIGINAL appointment's duration_hours onto the new row at
    creation time, so this is correctly a no-op for that call site."""
    duration_hours = context.get("daycare_duration_hours")
    if duration_hours is not None:
        connector.set_appointment_duration(hospital_id, appointment_id, duration_hours)


FLOW = TypeFlow(
    type_id="daycare", steps=_STEPS, on_booking_confirmed=_on_daycare_duration_confirmed,
    validate_department=existing_department_appointment,
)

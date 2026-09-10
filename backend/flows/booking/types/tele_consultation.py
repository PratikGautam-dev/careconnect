# flows/booking/types/tele_consultation.py
"""Tele-consultation: FULL_FLOW (same department/doctor/date/slot pipeline
as new/second_opinion/daycare), except for one extra pre-step (confirmed
with the user): right after "tele" is picked, _on_tele_selected asks
whether this is a brand-new consultation or a follow-up to a previous
attended visit. "New Appointment" falls through to the normal pipeline
(_proceed_to_department_or_skip, same one every other FULL_FLOW type uses);
"Follow-up" reuses followup.py's own eligible-visit list/date-floor logic
directly. Either way the appointment is still created with
appointment_type_id="tele" (context["appointment_type_id"] is never
touched by either sub-path), so on_booking_confirmed below always fires --
a follow-up-style tele booking still gets a Meet link, same as a new one.

Phase 2: attach a video-call link to the booking notification via the
on_booking_confirmed hook -- book.py's shared _create_booking_and_notify
calls this right after connector.create_booking() succeeds, and merges
whatever dict it returns into the notification context. Every other type
leaves on_booking_confirmed unset (None), so their notifications are
untouched.

Google Meet integration (Spec.md Section 0): if this appointment's HOSPITAL
has an admin-connected Google account (modules/google_calendar.py,
auth/google_calendar_oauth.py -- one connection per hospital, used for every
doctor there, not a per-doctor connection), a real Calendar event with a
Meet link is created and used instead of a Jitsi room. Every hospital, until
the real GOOGLE_CALENDAR_CLIENT_ID/SECRET/CALENDAR_TOKEN_ENCRYPTION_KEY env
vars are set AND an admin explicitly connects, has no connection at all --
create_meet_event() returns None for that case (and for any Google API
failure) by design, never raising, so the Jitsi fallback below is the ONLY
path exercised until a hospital actually connects, unchanged from before
this feature existed.

Lazy imports (inside functions) of book.py/messages.py/followup.py avoid a
circular import: this module -> types.registry -> this module, same
precedent followup.py's own module docstring already established."""
import secrets

import db.repository as db
from core.translations import t
from core.translations.booking import TELE_SUB_TYPE_FOLLOWUP_BUTTON, TELE_SUB_TYPE_NEW_BUTTON, TELE_SUB_TYPE_PROMPT
from flows.booking.state import (
    BACK_ID, STATE_AWAITING_APPOINTMENT_TYPE, STATE_AWAITING_FOLLOWUP_SELECTION, STATE_AWAITING_TELE_SUB_TYPE,
    TELE_SUB_TYPE_FOLLOWUP, TELE_SUB_TYPE_NEW, _HISTORY_KEY, _find_by_id, _push_history,
)
from flows.booking.types.base import FULL_FLOW, TypeFlow, existing_department_appointment
from modules.google_calendar import create_meet_event

# Jitsi Meet: no API key, no OAuth, no external account needed -- anyone
# with the URL can join, so the room name IS the access control. Per the
# architecture doc's "never expose a permanent/public video URL"
# requirement, the token is generated fresh per booking with
# secrets.token_urlsafe (CSPRNG-backed), never anything derived from the
# appointment id, timestamp, or patient info -- none of which would be hard
# to guess or enumerate.
_JITSI_BASE_URL = "https://meet.jit.si/CareConnect-"
_TOKEN_BYTES = 24  # secrets.token_urlsafe(24) -> 32 URL-safe characters
_DEFAULT_DURATION_MINUTES = 30


async def _on_tele_booking_confirmed(appointment, connector, context: dict) -> dict:
    video_link = _try_create_meet_link(appointment)
    if video_link is None:
        video_link = f"{_JITSI_BASE_URL}{secrets.token_urlsafe(_TOKEN_BYTES)}"
    connector.set_appointment_video_link(appointment.hospital_id, appointment.id, video_link)
    return {"video_link": video_link}


def _try_create_meet_link(appointment) -> str | None:
    """None (never raises) for the overwhelming common case of "this
    hospital hasn't connected Google Calendar" -- modules/google_calendar.py's
    own functions already never raise for a misconfigured/unconnected/failed
    case, this is just the one extra step of looking up the doctor's own
    slot duration for the event length, with the same "fall back, don't
    fail the booking" discipline if that lookup itself comes back empty.
    The event is created on the HOSPITAL's connected calendar (one admin
    connection shared by every doctor there), not a per-doctor one -- the
    doctor's own name still appears in the event summary/title, just not as
    whose calendar it lives on."""
    doctor = db.get_doctor_full(appointment.hospital_id, appointment.doctor_id)
    duration_minutes = (doctor or {}).get("slot_duration_minutes") or _DEFAULT_DURATION_MINUTES
    summary = f"Tele-consultation: {appointment.doctor_name}"
    return create_meet_event(appointment.hospital_id, summary, appointment.scheduled_at, duration_minutes)


async def _send_tele_sub_type_prompt(wa, phone: str, language: str = "en") -> None:
    from flows.booking.messages import _send_back_button

    await wa.send_buttons(
        to=phone,
        body_text=t(TELE_SUB_TYPE_PROMPT, language),
        buttons=[
            {"id": TELE_SUB_TYPE_NEW, "title": t(TELE_SUB_TYPE_NEW_BUTTON, language)},
            {"id": TELE_SUB_TYPE_FOLLOWUP, "title": t(TELE_SUB_TYPE_FOLLOWUP_BUTTON, language)},
        ],
    )
    await _send_back_button(wa, phone, language=language)


async def _on_tele_selected(
    wa, sessions, phone: str, hospital_id: int, connector, context: dict, language: str = "en",
) -> None:
    """TypeFlow.on_selected hook: replaces the normal "go to steps[0]"
    behavior for tele-consultation with this New-Appointment-vs-Follow-up
    pre-step."""
    history = _push_history(context, STATE_AWAITING_APPOINTMENT_TYPE)
    new_context = {**context, _HISTORY_KEY: history}
    sessions.set(hospital_id, phone, STATE_AWAITING_TELE_SUB_TYPE, new_context)
    await _send_tele_sub_type_prompt(wa, phone, language=language)


async def _handle_awaiting_tele_sub_type(
    wa, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    from flows.booking.book import _proceed_to_department_or_skip
    from flows.booking.messages import _handle_back_navigation, _send_main_menu
    from flows.booking.types.followup import _fetch_eligible, _send_followup_eligible_list, _send_no_eligible_screen

    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        if reply["id"] == TELE_SUB_TYPE_NEW:
            appt_type = _find_by_id(connector.get_appointment_types(hospital_id), context.get("appointment_type_id"))
            if appt_type is None:
                sessions.reset(hospital_id, phone)
                await _send_main_menu(wa, phone, "the hospital", language=language)
                return
            history = _push_history(context, STATE_AWAITING_TELE_SUB_TYPE)
            new_context = {**context, _HISTORY_KEY: history}
            await _proceed_to_department_or_skip(
                wa, sessions, phone, hospital_id, appt_type, new_context, connector, language=language,
            )
            return
        if reply["id"] == TELE_SUB_TYPE_FOLLOWUP:
            eligible = await _fetch_eligible(hospital_id, connector, context)
            if not eligible:
                await _send_no_eligible_screen(wa, phone, hospital_id, sessions, context, connector, language)
                return
            history = _push_history(context, STATE_AWAITING_TELE_SUB_TYPE)
            new_context = {**context, _HISTORY_KEY: history}
            sessions.set(hospital_id, phone, STATE_AWAITING_FOLLOWUP_SELECTION, new_context)
            await _send_followup_eligible_list(wa, phone, eligible, context.get("patient_name"), language=language)
            return
    # Stale/unrecognized tap -- re-show the same prompt.
    sessions.set(hospital_id, phone, STATE_AWAITING_TELE_SUB_TYPE, context)
    await _send_tele_sub_type_prompt(wa, phone, language=language)


FLOW = TypeFlow(
    type_id="tele", steps=FULL_FLOW, on_selected=_on_tele_selected, on_booking_confirmed=_on_tele_booking_confirmed,
    validate_department=existing_department_appointment,
)

# flows/booking/types/tele_consultation.py
"""Tele-consultation: unchanged flow (FULL_FLOW, same department/doctor/
date/slot pipeline as new/followup/second_opinion/daycare). Phase 2: attach
a video-call link to the booking notification via the on_booking_confirmed
hook -- book.py's shared _create_booking_and_notify calls this right after
connector.create_booking() succeeds, and merges whatever dict it returns
into the notification context. Every other type leaves on_booking_confirmed
unset (None), so their notifications are untouched.

Google Meet integration (Spec.md Section 0): if this appointment's doctor
has connected their own Google account (modules/google_calendar.py,
auth/google_calendar_oauth.py), a real Calendar event with a Meet link is
created and used instead of a Jitsi room. Every doctor, until the real
GOOGLE_CALENDAR_CLIENT_ID/SECRET/CALENDAR_TOKEN_ENCRYPTION_KEY env vars are
set AND they explicitly connect, has no connection at all -- create_meet_event()
returns None for that case (and for any Google API failure) by design, never
raising, so the Jitsi fallback below is the ONLY path exercised until a
doctor actually connects, unchanged from before this feature existed."""
import secrets

import db.repository as db
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
    """None (never raises) for the overwhelming common case of "this doctor
    hasn't connected Google Calendar" -- modules/google_calendar.py's own
    functions already never raise for a misconfigured/unconnected/failed
    case, this is just the one extra step of looking up the doctor's own
    slot duration for the event length, with the same "fall back, don't
    fail the booking" discipline if that lookup itself comes back empty."""
    doctor = db.get_doctor_full(appointment.hospital_id, appointment.doctor_id)
    duration_minutes = (doctor or {}).get("slot_duration_minutes") or _DEFAULT_DURATION_MINUTES
    summary = f"Tele-consultation: {appointment.doctor_name}"
    return create_meet_event(appointment.doctor_id, summary, appointment.scheduled_at, duration_minutes)


FLOW = TypeFlow(
    type_id="tele", steps=FULL_FLOW, on_booking_confirmed=_on_tele_booking_confirmed,
    validate_department=existing_department_appointment,
)

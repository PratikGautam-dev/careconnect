# flows/booking/types/tele_consultation.py
"""Tele-consultation: unchanged flow (FULL_FLOW, same department/doctor/
date/slot pipeline as new/followup/second_opinion/daycare). Phase 2: attach
a video-call link to the booking notification via the on_booking_confirmed
hook -- book.py's shared _create_booking_and_notify calls this right after
connector.create_booking() succeeds, and merges whatever dict it returns
into the notification context. Every other type leaves on_booking_confirmed
unset (None), so their notifications are untouched."""
import secrets

from flows.booking.types.base import FULL_FLOW, TypeFlow, existing_department_appointment

# Jitsi Meet: no API key, no OAuth, no external account needed -- anyone
# with the URL can join, so the room name IS the access control. Per the
# architecture doc's "never expose a permanent/public video URL"
# requirement, the token is generated fresh per booking with
# secrets.token_urlsafe (CSPRNG-backed), never anything derived from the
# appointment id, timestamp, or patient info -- none of which would be hard
# to guess or enumerate.
_JITSI_BASE_URL = "https://meet.jit.si/CareConnect-"
_TOKEN_BYTES = 24  # secrets.token_urlsafe(24) -> 32 URL-safe characters


async def _on_tele_booking_confirmed(
    appointment_id: int, hospital_id: int, patient_id: int | None, connector, context: dict,
) -> dict:
    video_link = f"{_JITSI_BASE_URL}{secrets.token_urlsafe(_TOKEN_BYTES)}"
    connector.set_appointment_video_link(hospital_id, appointment_id, video_link)
    return {"video_link": video_link}


FLOW = TypeFlow(
    type_id="tele", steps=FULL_FLOW, on_booking_confirmed=_on_tele_booking_confirmed,
    validate_department=existing_department_appointment,
)

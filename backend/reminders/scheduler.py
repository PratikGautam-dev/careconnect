# reminders/scheduler.py
"""
Reminder scheduler (SPEC Section 3.5).

Designed to run on a fixed interval via an *external* trigger — POST
/internal/send-reminders in core/main.py, meant to be hit by a cron job — rather
than an in-process scheduler, matching SPEC Section 6's serverless-first infra
choice (no long-running worker process to babysit).

Reaches appointment data ONLY through the connector interface (SPEC Section
12.6.2, connectors.py), never db/repository.py directly — same rule as
core/booking_flow.py. `connector` defaults to a Tier 1 connector so every
pre-existing caller (including the test suite) keeps working unchanged.
"""
import logging

from connectors import Connector, Tier1Connector
from core.whatsapp import WhatsAppClient

logger = logging.getLogger(__name__)

_DEFAULT_CONNECTOR = Tier1Connector()


async def send_reminders(
    wa: WhatsAppClient, hospital_id: int, offsets_hours: list[float], connector: Connector | None = None
) -> int:
    """
    A hospital can configure multiple reminder offsets (SPEC Section 4's
    reminder_offsets_hours, e.g. [24, 1] for a 24h-before AND a 1h-before
    reminder) — each is its own independent pass: find appointments due for
    *that* offset that haven't had a reminder sent for it yet, message each
    patient, and record it (connector.mark_reminder_sent) so a repeat call
    (e.g. the next hourly cron tick, or this same offset appearing twice in a
    misconfigured list) doesn't double-send.

    connector (SPEC Section 12.6.2) is resolved once by core/main.py from the
    hospital's stored data_tier and passed in here; defaults to a Tier 1
    connector for backward compatibility with pre-existing callers/tests.

    Returns the total number of reminders sent across all offsets.
    """
    connector = connector or _DEFAULT_CONNECTOR
    sent = 0

    for offset_hours in offsets_hours:
        due = connector.get_upcoming_appointments(hospital_id, offset_hours=offset_hours)

        for appt in due:
            # NOTE: plain text reminder, for local dev/testing only. In production, any
            # outbound message sent outside the 24h customer-service window (i.e. more
            # than 24h since the patient's last inbound message — which a same-day
            # reminder often will be) MUST be an approved Meta template message, or
            # Meta will reject the send. Swap this for a template send (SPEC Section
            # 3.2/3.5) before this goes anywhere near production — we don't have an
            # approved template yet.
            message = (
                f"Reminder: you have an appointment with {appt.doctor_name} "
                f"({appt.department_name}) on {appt.scheduled_at.strftime('%A, %d %B at %H:%M')}. "
                f"Message us here if you need to reschedule or cancel."
            )
            # Tele-consultation Phase 2 (confirmed with the user directly):
            # the video link is deliberately withheld from the immediate
            # booking confirmation and only surfaces here, close to the
            # actual slot -- a patient can't casually share/join a "live"
            # room hours or days early. video_link is None for every other
            # type (and for a tele appointment predating this column), so
            # this is a no-op for them.
            if appt.appointment_type_id == "tele" and appt.video_link:
                message += f"\n\n🎥 Video Consultation Link: {appt.video_link}"
            await wa.send_text(appt.phone, message)
            connector.mark_reminder_sent(hospital_id, appt.id, offset_hours)
            sent += 1
            logger.info("Reminder sent to %s for appointment %s (offset=%sh)", appt.phone, appt.id, offset_hours)

    return sent

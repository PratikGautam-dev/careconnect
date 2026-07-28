# reminders/scheduler.py
"""
Reminder scheduler (SPEC Section 3.5).

Designed to run on a fixed interval via an *external* trigger — POST
/internal/send-reminders in core/main.py, meant to be hit by a cron job — rather
than an in-process scheduler, matching SPEC Section 6's serverless-first infra
choice (no long-running worker process to babysit).

Reads from db/repository.py (SPEC Section 12.6 Tier 1 — a real SQLite database),
scoped by hospital_id (Section 12.2) same as core/booking_flow.py.
"""
import logging

import db.repository as db
from core.whatsapp import WhatsAppClient

logger = logging.getLogger(__name__)


async def send_reminders(wa: WhatsAppClient, hospital_id: int, offsets_hours: list[float]) -> int:
    """
    A hospital can configure multiple reminder offsets (SPEC Section 4's
    reminder_offsets_hours, e.g. [24, 1] for a 24h-before AND a 1h-before
    reminder) — each is its own independent pass: find appointments due for
    *that* offset that haven't had a reminder sent for it yet, message each
    patient, and record it (db/repository.py:mark_reminded) so a repeat call
    (e.g. the next hourly cron tick, or this same offset appearing twice in a
    misconfigured list) doesn't double-send.
    Returns the total number of reminders sent across all offsets.
    """
    sent = 0

    for offset_hours in offsets_hours:
        due = db.get_upcoming_appointments(hospital_id, offset_hours)

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
            await wa.send_text(appt.phone, message)
            db.mark_reminded(hospital_id, appt.id, offset_hours)
            sent += 1
            logger.info("Reminder sent to %s for appointment %s (offset=%sh)", appt.phone, appt.id, offset_hours)

    return sent

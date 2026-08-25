from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

import db.repository as db
from reminders.scheduler import send_reminders


def _make(hospital_id, scheduled_at, phone="5491112345678", doctor_id="doc_card_1"):
    return db.create_appointment(hospital_id, phone, "cardiology", doctor_id, scheduled_at)


def _fake_wa():
    wa = MagicMock()
    wa.send_text = AsyncMock()
    return wa


@pytest.mark.asyncio
async def test_appointment_within_window_gets_reminder(hospital_id):
    now = datetime.now()
    _make(hospital_id, scheduled_at=now + timedelta(hours=5))
    wa = _fake_wa()

    sent = await send_reminders(wa, hospital_id, offsets_hours=[24])

    assert sent == 1
    wa.send_text.assert_called_once()
    call_phone = wa.send_text.call_args[0][0]
    assert call_phone == "5491112345678"


@pytest.mark.asyncio
async def test_appointment_outside_window_gets_no_reminder(hospital_id):
    now = datetime.now()
    _make(hospital_id, scheduled_at=now + timedelta(hours=48))  # outside a 24h window
    wa = _fake_wa()

    sent = await send_reminders(wa, hospital_id, offsets_hours=[24])

    assert sent == 0
    wa.send_text.assert_not_called()


@pytest.mark.asyncio
async def test_already_reminded_appointment_is_not_sent_twice(hospital_id):
    now = datetime.now()
    appt = _make(hospital_id, scheduled_at=now + timedelta(hours=5))
    wa = _fake_wa()

    first = await send_reminders(wa, hospital_id, offsets_hours=[24])
    second = await send_reminders(wa, hospital_id, offsets_hours=[24])

    assert first == 1
    assert second == 0
    wa.send_text.assert_called_once()
    assert db.get_reminded_offsets(hospital_id, appt.id) == [24]


@pytest.mark.asyncio
async def test_reminder_message_mentions_doctor_and_department(hospital_id):
    now = datetime.now()
    _make(hospital_id, scheduled_at=now + timedelta(hours=5))
    wa = _fake_wa()

    await send_reminders(wa, hospital_id, offsets_hours=[24])

    message = wa.send_text.call_args[0][1]
    assert "Dr. Anjali Rao" in message
    assert "Cardiology" in message


@pytest.mark.asyncio
async def test_multiple_due_appointments_all_get_reminded(hospital_id):
    now = datetime.now()
    _make(hospital_id, scheduled_at=now + timedelta(hours=1), phone="111", doctor_id="doc_card_1")
    _make(hospital_id, scheduled_at=now + timedelta(hours=2), phone="222", doctor_id="doc_card_2")
    wa = _fake_wa()

    sent = await send_reminders(wa, hospital_id, offsets_hours=[24])

    assert sent == 2
    assert wa.send_text.call_count == 2


@pytest.mark.asyncio
async def test_cancelled_appointment_gets_no_reminder(hospital_id):
    """Regression coverage: a cancelled appointment must never get a reminder sent."""
    now = datetime.now()
    appt = _make(hospital_id, scheduled_at=now + timedelta(hours=5))
    db.cancel_appointment(hospital_id, appt.id)
    wa = _fake_wa()

    sent = await send_reminders(wa, hospital_id, offsets_hours=[24])

    assert sent == 0
    wa.send_text.assert_not_called()


# --- Multiple reminder offsets per hospital (SPEC Section 4: reminder_offsets_hours) ---

@pytest.mark.asyncio
async def test_both_configured_offsets_fire_when_appointment_is_close(hospital_id):
    """A hospital configured for [24, 1] (24h-before AND 1h-before) must get
    BOTH reminders for an appointment that's already within the 1h window --
    each offset is tracked independently, so the 24h one firing must not
    suppress the 1h one."""
    appt = _make(hospital_id, scheduled_at=datetime.now() + timedelta(minutes=30))
    wa = _fake_wa()

    sent = await send_reminders(wa, hospital_id, offsets_hours=[24, 1])

    assert sent == 2
    assert wa.send_text.call_count == 2
    assert sorted(db.get_reminded_offsets(hospital_id, appt.id)) == [1, 24]


@pytest.mark.asyncio
async def test_only_the_offset_that_is_actually_due_fires(hospital_id):
    """An appointment 5h out with offsets [24, 1] configured should only get
    the 24h reminder now -- the 1h one isn't due yet, not sent, not marked."""
    appt = _make(hospital_id, scheduled_at=datetime.now() + timedelta(hours=5))
    wa = _fake_wa()

    sent = await send_reminders(wa, hospital_id, offsets_hours=[24, 1])

    assert sent == 1
    assert db.get_reminded_offsets(hospital_id, appt.id) == [24]


@pytest.mark.asyncio
async def test_second_cron_pass_does_not_resend_the_first_offset(hospital_id):
    """Simulates two separate cron runs against the same still-distant
    appointment: the 24h reminder fires once on the first pass; a second pass
    (nothing about the appointment changed) must not re-send it, and the 1h
    offset correctly stays not-yet-due on both passes."""
    appt = _make(hospital_id, scheduled_at=datetime.now() + timedelta(hours=5))
    wa = _fake_wa()

    first_pass = await send_reminders(wa, hospital_id, offsets_hours=[24, 1])
    second_pass = await send_reminders(wa, hospital_id, offsets_hours=[24, 1])

    assert first_pass == 1  # only the 24h one; not within the 1h window yet
    assert second_pass == 0  # 24h already sent, 1h still not due -- no re-send
    assert wa.send_text.call_count == 1
    assert db.get_reminded_offsets(hospital_id, appt.id) == [24]


@pytest.mark.asyncio
async def test_hospital_with_single_offset_still_works_as_before(hospital_id):
    """A hospital configured for just one offset (the common case, e.g. [24])
    must behave exactly as it did before multi-offset support existed."""
    _make(hospital_id, scheduled_at=datetime.now() + timedelta(hours=5))
    _make(hospital_id, scheduled_at=datetime.now() + timedelta(hours=48), phone="222")  # outside window
    wa = _fake_wa()

    sent = await send_reminders(wa, hospital_id, offsets_hours=[24])

    assert sent == 1
    wa.send_text.assert_called_once()

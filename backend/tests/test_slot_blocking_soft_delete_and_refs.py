# tests/test_slot_blocking_soft_delete_and_refs.py
"""
Second follow-up batch (Spec.md Section 0), DB-level coverage:
  - item 1: per-slot manual block/unblock, and refusing to block an
    already-booked slot.
  - item 3: soft-delete for appointments (guarded to non-'booked' rows only)
    and handoff_requests (no such guard), excluded from normal reads.
  - item 7: platform-wide lifetime total-bookings count, unaffected by
    status changes or soft-deletion.
  - item 8: reference_id format (APT-<DDMMYY>-<NNN>, numeric date part per
    the later Item 2 follow-up) and per-hospital-per-day sequencing (not
    globally sequential across tenants).
"""
from datetime import datetime

import db.repository as db

PHONE = "5491112345678"


def test_blocking_a_free_slot_hides_it_from_get_slots(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]

    ok = db.set_slot_blocked(hospital_id, doctor_id, slot["id"], True, reason="Doctor unavailable")
    assert ok is True

    remaining_ids = {s["id"] for s in db.get_slots(hospital_id, doctor_id)}
    assert slot["id"] not in remaining_ids

    # Unblocking makes it bookable again.
    ok2 = db.set_slot_blocked(hospital_id, doctor_id, slot["id"], False)
    assert ok2 is True
    assert slot["id"] in {s["id"] for s in db.get_slots(hospital_id, doctor_id)}


def test_cannot_block_a_slot_with_a_real_booking(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, datetime.fromisoformat(slot["id"]),
        patient_name="Ravi Kumar", patient_age=34,
    )

    ok = db.set_slot_blocked(hospital_id, doctor_id, slot["id"], True)
    assert ok is False

    # Still bookable-looking at the doctor_slots level -- not silently blocked.
    admin_view = db.get_doctor_slots_for_admin(hospital_id, doctor_id, slot["date"])
    row = next(r for r in admin_view if r["scheduled_at"] == slot["id"])
    assert row["blocked"] is False
    assert row["booked"] is True


def test_soft_delete_appointment_requires_non_booked_status(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, datetime.fromisoformat(slot["id"]),
        patient_name="Ravi Kumar", patient_age=34,
    )

    # Still 'booked' -- refused.
    assert db.soft_delete_appointment(hospital_id, appt.id) is False
    assert db.get_appointment(hospital_id, appt.id) is not None

    db.cancel_appointment(hospital_id, appt.id)
    assert db.soft_delete_appointment(hospital_id, appt.id) is True

    # Excluded from every normal read now (_APPOINTMENT_SELECT's own filter).
    assert db.get_appointment(hospital_id, appt.id) is None
    assert appt.id not in {a.id for a in db.get_all_appointments_for_hospital(hospital_id)}


def test_soft_delete_handoff_excludes_from_listings_and_open_check(hospital_id):
    handoff = db.create_handoff_request(hospital_id, PHONE, reason="patient_requested")
    assert db.has_open_handoff(hospital_id, PHONE) is True

    ok = db.soft_delete_handoff(hospital_id, handoff["id"])
    assert ok is True
    assert db.has_open_handoff(hospital_id, PHONE) is False
    assert handoff["id"] not in {h["id"] for h in db.get_handoff_requests(hospital_id, status=None)}

    # A second delete is a clean no-op-turned-404-signal, not an error.
    assert db.soft_delete_handoff(hospital_id, handoff["id"]) is False


def test_stale_open_handoff_no_longer_silences_the_bot(hospital_id):
    """"Bot stuck on Talk to Reception" follow-up (Spec.md Section 0): an
    open handoff older than _HANDOFF_STALE_MINUTES no longer counts as
    "open" for has_open_handoff()/get_open_handoff()'s purpose -- the bot
    resumes normal service for that phone -- but its real DB status is left
    completely untouched (still 'open'), so staff still see and can resolve
    it whenever they actually get to it."""
    from datetime import datetime, timedelta

    handoff = db.create_handoff_request(hospital_id, PHONE, reason="patient_requested")
    assert db.has_open_handoff(hospital_id, PHONE) is True

    # Backdate it well past the staleness window, directly -- same pattern
    # test_needs_attendance_review_lists_only_past_still_booked_appointments
    # (tests/test_portal_api.py) already uses for a similar "simulate an old
    # row" need.
    conn = db.get_connection()
    stale_at = datetime.now() - timedelta(minutes=90)
    conn.execute(
        "UPDATE handoff_requests SET created_at = ? WHERE id = ?",
        (stale_at.strftime("%Y-%m-%d %H:%M:%S"), handoff["id"]),
    )
    conn.commit()

    assert db.has_open_handoff(hospital_id, PHONE) is False
    assert db.get_open_handoff(hospital_id, PHONE) is None

    # The row itself is untouched -- still genuinely 'open' in the DB, still
    # visible to staff in the portal queue.
    still_open = [h for h in db.get_handoff_requests(hospital_id, status="open") if h["id"] == handoff["id"]]
    assert len(still_open) == 1
    assert still_open[0]["status"] == "open"


def test_recently_open_handoff_still_silences_the_bot(hospital_id):
    """The other half: a handoff well within the staleness window still
    behaves exactly as before -- this fix only affects genuinely
    forgotten/old requests, not normal, actively-pending ones."""
    handoff = db.create_handoff_request(hospital_id, PHONE, reason="patient_requested")
    assert db.has_open_handoff(hospital_id, PHONE) is True
    got = db.get_open_handoff(hospital_id, PHONE)
    assert got is not None and got["id"] == handoff["id"]


def test_total_bookings_count_unaffected_by_status_or_soft_delete(hospital_id, second_hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slots = db.get_slots(hospital_id, doctor_id)
    before = db.get_total_bookings_count()

    a = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, datetime.fromisoformat(slots[0]["id"]),
        patient_name="Ravi Kumar", patient_age=34,
    )
    b = db.create_appointment(
        hospital_id, "5490009999", "cardiology", doctor_id, datetime.fromisoformat(slots[1]["id"]),
        patient_name="Someone Else", patient_age=50,
    )
    assert db.get_total_bookings_count() == before + 2

    # Cancelling, then soft-deleting, never reduces the lifetime count.
    db.cancel_appointment(hospital_id, a.id)
    db.soft_delete_appointment(hospital_id, a.id)
    assert db.get_total_bookings_count() == before + 2

    # A booking under a DIFFERENT hospital still adds to the same platform-wide total.
    t2_doctor_id = db.get_doctors(second_hospital_id, "t2_neurology")[0]["id"]
    t2_slot = db.get_slots(second_hospital_id, t2_doctor_id)[0]
    db.create_appointment(
        second_hospital_id, PHONE, "t2_neurology", t2_doctor_id, datetime.fromisoformat(t2_slot["id"]),
        patient_name="Cross Tenant", patient_age=40,
    )
    assert db.get_total_bookings_count() == before + 3


def test_reference_id_format_and_per_hospital_daily_sequence(hospital_id, second_hospital_id):
    import re

    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slots = db.get_slots(hospital_id, doctor_id)

    first = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, datetime.fromisoformat(slots[0]["id"]),
        patient_name="Ravi Kumar", patient_age=34,
    )
    second = db.create_appointment(
        hospital_id, "5490009999", "cardiology", doctor_id, datetime.fromisoformat(slots[1]["id"]),
        patient_name="Someone Else", patient_age=50,
    )
    # Item 2 follow-up (Spec.md Section 0): date part switched from a
    # month-abbreviation (DDMMMYY) to fully numeric DDMMYY, confirmed with
    # the user directly.
    assert re.fullmatch(r"APT-\d{6}-\d{3}", first.reference_id)
    first_seq = int(first.reference_id.rsplit("-", 1)[1])
    second_seq = int(second.reference_id.rsplit("-", 1)[1])
    assert second_seq == first_seq + 1

    # A DIFFERENT hospital's sequence is independent -- not globally sequential.
    t2_doctor_id = db.get_doctors(second_hospital_id, "t2_neurology")[0]["id"]
    t2_slot = db.get_slots(second_hospital_id, t2_doctor_id)[0]
    t2_appt = db.create_appointment(
        second_hospital_id, PHONE, "t2_neurology", t2_doctor_id, datetime.fromisoformat(t2_slot["id"]),
        patient_name="Cross Tenant", patient_age=40,
    )
    t2_seq = int(t2_appt.reference_id.rsplit("-", 1)[1])
    assert t2_seq == 1

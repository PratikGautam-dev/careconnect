# tests/test_slot_blocking_soft_delete_and_refs.py
"""
Second follow-up batch (Spec.md Section 0), DB-level coverage:
  - item 1: per-slot manual block/unblock, and refusing to block an
    already-booked slot.
  - item 3: soft-delete for appointments (guarded to non-'booked' rows only)
    and handoff_requests (no such guard), excluded from normal reads.
  - item 7: platform-wide lifetime total-bookings count, unaffected by
    status changes or soft-deletion.
  - item 8: reference_id format (APT-<DDMMMYY>-<NNN>) and per-hospital-
    per-day sequencing (not globally sequential across tenants).
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
    assert re.fullmatch(r"APT-\d{2}[A-Z]{3}\d{2}-\d{3}", first.reference_id)
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

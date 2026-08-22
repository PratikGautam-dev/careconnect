# tests/test_duplicate_booking_and_denorm.py
"""
Items 5 and 8 (Spec.md Section 0):
  - item 5: create_appointment() blocks a second ACTIVE booking with the
    same doctor + same phone + same age on file, but allows a different
    doctor, and allows a different age (e.g. a sibling) on the same phone.
  - item 8: appointments.patient_id/patient_name/patient_phone are
    populated correctly by create_appointment() itself.
"""
from datetime import datetime

import pytest

import db.repository as db
from db.repository import DuplicateBookingError

PHONE = "5491112345678"


def _first_two_slots(hospital_id, doctor_id):
    slots = db.get_slots(hospital_id, doctor_id)
    return slots[0], slots[1]


def test_second_booking_same_doctor_same_age_is_blocked(hospital_id):
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot_a, slot_b = _first_two_slots(hospital_id, doctor_id)
    scheduled_a = datetime.fromisoformat(f"{slot_a['date']}T{slot_a['time']}")
    scheduled_b = datetime.fromisoformat(f"{slot_b['date']}T{slot_b['time']}")

    first = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, scheduled_a,
        patient_name="Ravi Kumar", patient_age=34,
    )

    with pytest.raises(DuplicateBookingError) as exc_info:
        db.create_appointment(
            hospital_id, PHONE, "cardiology", doctor_id, scheduled_b,
            patient_age=34,
        )
    assert exc_info.value.existing_appointment_id == first.id


def test_second_booking_different_doctor_is_allowed(hospital_id):
    """Scoped to the SAME doctor specifically -- a patient legitimately
    booking two different doctors must never be blocked."""
    doctors = db.get_doctors(hospital_id, "cardiology")
    doctor_a = doctors[0]["id"]
    doctor_b = db.create_doctor(
        hospital_id, "cardiology", "Dr. Second Opinion",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-17:00"],
        slot_duration_minutes=30,
    )["id"]
    slot_a = db.get_slots(hospital_id, doctor_a)[0]
    slot_b = db.get_slots(hospital_id, doctor_b)[0]

    db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_a,
        datetime.fromisoformat(f"{slot_a['date']}T{slot_a['time']}"),
        patient_name="Ravi Kumar", patient_age=34,
    )
    second = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_b,
        datetime.fromisoformat(f"{slot_b['date']}T{slot_b['time']}"),
        patient_age=34,
    )
    assert second.doctor_id == doctor_b


def test_second_booking_different_age_same_doctor_is_allowed(hospital_id):
    """A different age given for this attempt (the only way today's UI
    reflects a different family member on the same phone) is treated as a
    different patient, not blocked."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot_a, slot_b = _first_two_slots(hospital_id, doctor_id)

    db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_a['date']}T{slot_a['time']}"),
        patient_name="Ravi Kumar", patient_age=34,
    )
    # A DIFFERENT age is passed for this attempt -- e.g. a sibling.
    second = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_b['date']}T{slot_b['time']}"),
        patient_age=8,
    )
    assert second.doctor_id == doctor_id


def test_cancelling_the_first_appointment_allows_a_new_one(hospital_id):
    """Only an ACTIVE (status='booked') appointment blocks a duplicate --
    cancelling it clears the way."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot_a, slot_b = _first_two_slots(hospital_id, doctor_id)

    first = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_a['date']}T{slot_a['time']}"),
        patient_name="Ravi Kumar", patient_age=34,
    )
    db.cancel_appointment(hospital_id, first.id)

    second = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_b['date']}T{slot_b['time']}"),
        patient_age=34,
    )
    assert second.id != first.id


def test_appointment_gets_denormalized_patient_columns(hospital_id):
    """Item 8: patient_id/patient_name/patient_phone are populated directly
    on the appointments row, not requiring a join to patients."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]

    appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot['date']}T{slot['time']}"),
        patient_name="Ravi Kumar", patient_age=34,
    )

    conn = db.get_connection()
    row = conn.execute(
        "SELECT patient_id, patient_name, patient_phone FROM appointments WHERE id = ?",
        (appt.id,),
    ).fetchone()
    patient_row = conn.execute(
        "SELECT id FROM patients WHERE hospital_id = ? AND phone = ?", (hospital_id, PHONE),
    ).fetchone()
    assert row["patient_id"] == patient_row["id"]
    assert row["patient_name"] == "Ravi Kumar"
    assert row["patient_phone"] == PHONE

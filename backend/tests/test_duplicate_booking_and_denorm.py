# tests/test_duplicate_booking_and_denorm.py
"""
Items 5 and 8 (Spec.md Section 0):
  - item 5: create_appointment() blocks a second ACTIVE booking with the
    same doctor + same phone + same age on file, but allows a different
    doctor, and allows a different age (e.g. a sibling) on the same phone.
  - item 8: appointments.patient_id/patient_name/patient_phone are
    populated correctly by create_appointment() itself.
"""
from datetime import datetime, timedelta

import pytest

import db.repository as db
from db.repository import DuplicateBookingError, QuotaExceededError

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


def test_second_booking_same_age_different_name_same_doctor_is_allowed(hospital_id):
    """Family/multi-person-booking follow-up (Spec.md Section 0): the
    duplicate check now compares NAME too, not just age -- a coincidental
    same-age-different-family-member booking (e.g. twins) is correctly
    allowed through, which the age-only check would have incorrectly
    blocked before this fix."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot_a, slot_b = _first_two_slots(hospital_id, doctor_id)

    first = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_a['date']}T{slot_a['time']}"),
        patient_name="Ravi Kumar", patient_age=34,
    )
    second = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_b['date']}T{slot_b['time']}"),
        patient_name="Priya Kumar", patient_age=34,
    )
    assert second.id != first.id
    assert second.doctor_id == doctor_id


def test_second_booking_same_name_and_age_same_doctor_is_still_blocked(hospital_id):
    """Regression check: the name+age check is an AND, not a replacement for
    the age check -- truly the same patient (same name, same age) booking
    the same doctor twice is still blocked."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot_a, slot_b = _first_two_slots(hospital_id, doctor_id)

    first = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_a['date']}T{slot_a['time']}"),
        patient_name="Ravi Kumar", patient_age=34,
    )
    with pytest.raises(DuplicateBookingError) as exc_info:
        db.create_appointment(
            hospital_id, PHONE, "cardiology", doctor_id,
            datetime.fromisoformat(f"{slot_b['date']}T{slot_b['time']}"),
            patient_name="Ravi Kumar", patient_age=34,
        )
    assert exc_info.value.existing_appointment_id == first.id


def test_patient_id_duplicate_check_blocks_same_linked_patient_same_doctor(hospital_id):
    """Patient identity SEPARATION (Spec.md Section 0): when `patient_id` is
    given (the post-separation WhatsApp path), the duplicate check compares
    `patient_id` directly instead of the name+age heuristic above -- the
    same linked patient booking the same doctor twice is still blocked."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot_a, slot_b = _first_two_slots(hospital_id, doctor_id)
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)

    first = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_a['date']}T{slot_a['time']}"),
        patient_id=patient["id"],
    )
    with pytest.raises(DuplicateBookingError) as exc_info:
        db.create_appointment(
            hospital_id, PHONE, "cardiology", doctor_id,
            datetime.fromisoformat(f"{slot_b['date']}T{slot_b['time']}"),
            patient_id=patient["id"],
        )
    assert exc_info.value.existing_appointment_id == first.id


def test_patient_id_duplicate_check_allows_two_different_linked_patients_same_doctor(hospital_id):
    """The composability the plan flagged as worth confirming, not assuming:
    two DIFFERENT patients linked to the same phone (e.g. a parent and a
    child) booking the SAME doctor must both go through -- the check is
    keyed on patient_id, not phone, so this is naturally correct once
    identity is resolved via active_patient_id rather than re-derived from
    the phone number."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot_a, slot_b = _first_two_slots(hospital_id, doctor_id)
    parent = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    child = db.create_patient_profile(hospital_id, PHONE, "Priya Kumar", 8)

    first = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_a['date']}T{slot_a['time']}"),
        patient_id=parent["id"],
    )
    second = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_b['date']}T{slot_b['time']}"),
        patient_id=child["id"],
    )
    assert second.id != first.id
    assert first.patient_id == parent["id"]
    assert second.patient_id == child["id"]


def test_appointment_stores_its_own_patient_age_denormalized(hospital_id):
    """The other half of this follow-up: appointments.patient_age is now
    populated directly, the same way patient_id/patient_name/patient_phone
    already were (Item 8)."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]

    appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot['date']}T{slot['time']}"),
        patient_name="Ravi Kumar", patient_age=34,
    )
    conn = db.get_connection()
    row = conn.execute("SELECT patient_age FROM appointments WHERE id = ?", (appt.id,)).fetchone()
    assert row["patient_age"] == 34


def test_name_age_saved_even_when_the_first_booking_attempt_fails(hospital_id):
    """Regression fix (Spec.md Section 0): _upsert_patient() used to run
    INSIDE create_appointment()'s explicit transaction, right before the
    INSERT -- so a QuotaExceededError/DuplicateBookingError raised earlier
    in that SAME transaction rolled the upsert back too, leaving a
    first-time patient's name/age never saved if their very first attempt
    happened to fail. Now upserted BEFORE the transaction even opens, as
    its own independent, immediately-durable statement -- this proves it
    survives a failed first attempt, using daily_booking_limit=0 to
    guarantee QuotaExceededError on a genuinely first-ever booking (nothing
    else could have failed it -- there's no prior appointment to duplicate
    against)."""
    department_id = db.get_departments(hospital_id)[0]["id"]
    doctor = db.create_doctor(
        hospital_id, department_id, "Dr. Zero Quota",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=60, daily_booking_limit=0,
    )
    scheduled_at = datetime.now() + timedelta(days=1)

    with pytest.raises(QuotaExceededError):
        db.create_appointment(
            hospital_id, PHONE, department_id, doctor["id"], scheduled_at,
            patient_name="Ravi Kumar", patient_age=34,
        )

    # The booking itself failed and rolled back -- no appointment exists.
    assert db.get_upcoming_appointments_for_phone(hospital_id, PHONE) == []

    # But the patient's name/age were saved anyway -- a later successful
    # attempt (or booking_flow.py's own get_patient_info() lookup) will
    # correctly find them and skip re-asking.
    patient = db.get_patient_by_phone(hospital_id, PHONE)
    assert patient is not None
    assert patient["name"] == "Ravi Kumar"
    assert patient["age"] == 34


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


def test_cancelling_the_exact_same_slot_makes_it_immediately_rebookable(hospital_id):
    """Confirmed working, not a bug (Spec.md Section 0): reported as
    "cancel a slot, it shows as available, but re-selecting it fails with
    'slot was just taken'." Investigation found `get_slots()`, the
    booking_ordinal free-slot query, and the partial UNIQUE index
    (`ux_appointments_doctor_slot_ordinal_booked ... WHERE status='booked'`)
    all consistently gate on the SAME status='booked' condition -- no
    mismatch anywhere. This proves it directly: cancel a slot, then
    re-book the EXACT SAME (doctor, scheduled_at) -- not just the same
    doctor on a different slot, which the test above already covers --
    and confirm it succeeds cleanly, no IntegrityError."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    scheduled_at = datetime.fromisoformat(f"{slot['date']}T{slot['time']}")

    first = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, scheduled_at,
        patient_name="Ravi Kumar", patient_age=34,
    )
    # Freshly cancelled -> immediately re-appears as available.
    db.cancel_appointment(hospital_id, first.id)
    assert slot["id"] in {s["id"] for s in db.get_slots(hospital_id, doctor_id)}

    # Re-booking the EXACT SAME slot (same doctor, same scheduled_at) for a
    # DIFFERENT patient succeeds -- not rejected as "just taken".
    second = db.create_appointment(
        hospital_id, "5490009999", "cardiology", doctor_id, scheduled_at,
        patient_name="Someone Else", patient_age=50,
    )
    assert second.id != first.id
    assert second.doctor_id == doctor_id


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

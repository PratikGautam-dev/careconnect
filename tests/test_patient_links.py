# tests/test_patient_links.py
"""
Patient identity SEPARATION (Spec.md Section 0): db/repository.py's new
patient_links functions -- create/link, the 5-active-link cap, soft-unlink,
and the startup migration that backfills every pre-existing `patients` row
into an implicit "Self" link.
"""
from datetime import datetime, timedelta

import pytest

import db.repository as db
from db.init_db import _backfill_patient_links
from db.repository import MAX_ACTIVE_PATIENT_LINKS, TooManyLinkedPatientsError

PHONE = "5491112345678"


def test_create_patient_profile_creates_a_real_patient_and_an_active_link(hospital_id):
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)

    assert patient["name"] == "Ravi Kumar"
    assert patient["age"] == 34
    assert patient["patient_display_id"]  # a real short code was generated

    linked = db.get_active_patients_for_phone(hospital_id, PHONE)
    assert len(linked) == 1
    assert linked[0]["id"] == patient["id"]
    assert linked[0]["relationship_label"] is None  # never set via WhatsApp chat, per the plan's v1 scope


def test_create_patient_profile_gives_each_profile_its_own_patients_row(hospital_id):
    """The core of the separation: two profiles on one phone are two real
    `patients` rows (two real Patient IDs), not one mutable row."""
    parent = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    child = db.create_patient_profile(hospital_id, PHONE, "Priya Kumar", 8)

    assert parent["id"] != child["id"]
    assert parent["patient_display_id"] != child["patient_display_id"]

    linked = db.get_active_patients_for_phone(hospital_id, PHONE)
    assert {p["id"] for p in linked} == {parent["id"], child["id"]}


def test_count_active_links_for_phone(hospital_id):
    assert db.count_active_links_for_phone(hospital_id, PHONE) == 0
    db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    assert db.count_active_links_for_phone(hospital_id, PHONE) == 1
    db.create_patient_profile(hospital_id, PHONE, "Priya Kumar", 8)
    assert db.count_active_links_for_phone(hospital_id, PHONE) == 2


def test_fifth_patient_link_is_allowed_sixth_is_blocked(hospital_id):
    for i in range(MAX_ACTIVE_PATIENT_LINKS):
        db.create_patient_profile(hospital_id, PHONE, f"Family Member {i}", 20 + i)
    assert db.count_active_links_for_phone(hospital_id, PHONE) == MAX_ACTIVE_PATIENT_LINKS

    with pytest.raises(TooManyLinkedPatientsError):
        db.create_patient_profile(hospital_id, PHONE, "One Too Many", 99)

    # The blocked attempt created neither a patients row nor a link.
    assert db.count_active_links_for_phone(hospital_id, PHONE) == MAX_ACTIVE_PATIENT_LINKS


def test_unlinking_a_patient_frees_a_slot_for_a_new_one(hospital_id):
    patients = [
        db.create_patient_profile(hospital_id, PHONE, f"Family Member {i}", 20 + i)
        for i in range(MAX_ACTIVE_PATIENT_LINKS)
    ]
    with pytest.raises(TooManyLinkedPatientsError):
        db.create_patient_profile(hospital_id, PHONE, "Blocked", 99)

    assert db.unlink_patient(hospital_id, PHONE, patients[0]["id"]) is True
    assert db.count_active_links_for_phone(hospital_id, PHONE) == MAX_ACTIVE_PATIENT_LINKS - 1

    new_patient = db.create_patient_profile(hospital_id, PHONE, "Now Fits", 5)
    assert db.count_active_links_for_phone(hospital_id, PHONE) == MAX_ACTIVE_PATIENT_LINKS
    assert new_patient["id"] in {p["id"] for p in db.get_active_patients_for_phone(hospital_id, PHONE)}


def test_unlinking_an_already_unlinked_patient_returns_false(hospital_id):
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    assert db.unlink_patient(hospital_id, PHONE, patient["id"]) is True
    assert db.unlink_patient(hospital_id, PHONE, patient["id"]) is False


def test_unlinking_a_patient_never_touches_the_patients_row_or_appointment_history(hospital_id):
    """The confirmation the plan explicitly asked for: soft-unlink only
    touches patient_links.unlinked_at -- `patients` and `appointments` are
    completely untouched, so booking history and the Patient ID survive."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot['date']}T{slot['time']}"),
        patient_id=patient["id"],
    )

    db.unlink_patient(hospital_id, PHONE, patient["id"])

    still_there = db.get_patient(hospital_id, patient["id"])
    assert still_there is not None
    assert still_there["name"] == "Ravi Kumar"
    assert still_there["patient_display_id"] == patient["patient_display_id"]

    appointments = db.get_upcoming_appointments_for_phone(hospital_id, PHONE)
    assert any(a.id == appt.id for a in appointments)

    # But the phone no longer sees this patient as an active link.
    assert db.get_active_patients_for_phone(hospital_id, PHONE) == []


def test_unlinking_down_to_zero_active_patients_is_allowed(hospital_id):
    """Confirmed with the user: no special-cased "can't remove the last
    one" rule -- a phone can genuinely have zero active links, and the next
    booking just goes through "Add Patient" again."""
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    assert db.unlink_patient(hospital_id, PHONE, patient["id"]) is True
    assert db.get_active_patients_for_phone(hospital_id, PHONE) == []
    assert db.count_active_links_for_phone(hospital_id, PHONE) == 0


def test_patient_links_are_isolated_per_hospital(hospital_id, second_hospital_id):
    db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    assert db.get_active_patients_for_phone(second_hospital_id, PHONE) == []
    assert db.count_active_links_for_phone(second_hospital_id, PHONE) == 0


def test_backfill_patient_links_creates_one_self_link_per_existing_patient(hospital_id):
    """The migration this round's schema change depends on: every pre-
    existing `patients` row (created before patient_links existed) gets
    exactly one 'Self' link, so no existing patient loses their booking
    history or Patient ID in the transition."""
    conn = db.get_connection()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    # A booking made the OLD way (no patient_id given) -- create_appointment()
    # still upserts a `patients` row via _upsert_patient(), but with no
    # matching patient_links row, exactly like a real pre-migration patient.
    appt = db.create_appointment(
        hospital_id, "5490001111", "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot['date']}T{slot['time']}"),
        patient_name="Legacy Patient", patient_age=50,
    )
    pre_existing_patient_id = appt.patient_id
    assert db.get_active_patients_for_phone(hospital_id, "5490001111") == []  # not linked yet

    _backfill_patient_links(conn)

    linked = db.get_active_patients_for_phone(hospital_id, "5490001111")
    assert len(linked) == 1
    assert linked[0]["id"] == pre_existing_patient_id
    assert linked[0]["name"] == "Legacy Patient"
    assert linked[0]["relationship_label"] == "Self"
    # The Patient ID itself survived the migration untouched.
    assert linked[0]["patient_display_id"] == db.get_patient(hospital_id, pre_existing_patient_id)["patient_display_id"]


def test_backfill_patient_links_covers_every_existing_patient_with_zero_loss(hospital_id, second_hospital_id):
    """1:1 coverage check, per the plan's own verification requirement --
    every `patients` row across every hospital gets exactly one active link,
    none skipped, none duplicated."""
    conn = db.get_connection()
    doctor_a = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    for i in range(3):
        slot = db.get_slots(hospital_id, doctor_a)[i]
        db.create_appointment(
            hospital_id, f"549000111{i}", "cardiology", doctor_a,
            datetime.fromisoformat(f"{slot['date']}T{slot['time']}"),
            patient_name=f"Patient {i}", patient_age=30 + i,
        )

    _backfill_patient_links(conn)

    total_patients = conn.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]
    total_active_links = conn.execute("SELECT COUNT(*) AS c FROM patient_links WHERE unlinked_at IS NULL").fetchone()["c"]
    assert total_patients == total_active_links
    assert total_patients >= 3


def test_backfill_patient_links_is_idempotent(hospital_id):
    """Re-running it (every startup does) never creates a second link for an
    already-linked patient -- gated on NOT EXISTS, same idiom as every other
    backfill in db/init_db.py."""
    conn = db.get_connection()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    db.create_appointment(
        hospital_id, "5490001111", "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot['date']}T{slot['time']}"),
        patient_name="Legacy Patient", patient_age=50,
    )

    _backfill_patient_links(conn)
    _backfill_patient_links(conn)
    _backfill_patient_links(conn)

    linked = db.get_active_patients_for_phone(hospital_id, "5490001111")
    assert len(linked) == 1


def test_backfill_patient_links_does_not_relink_a_deliberately_unlinked_patient(hospital_id):
    """The backfill's NOT EXISTS gate is scoped to "has ANY link row ever",
    not "has an ACTIVE link" -- a patient who was explicitly unlinked after
    the migration already ran must not be silently re-linked by a later
    startup's re-run."""
    conn = db.get_connection()
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    db.unlink_patient(hospital_id, PHONE, patient["id"])

    _backfill_patient_links(conn)

    assert db.get_active_patients_for_phone(hospital_id, PHONE) == []

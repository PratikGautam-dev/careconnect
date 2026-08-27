# tests/test_patient_identity.py
"""
Patient identity system (Spec.md Section 0): two permanent, human-readable
ids generated ONCE per patient, together, sharing the same per-hospital
sequence number -- patient_display_id (DCC-PAT-<sequential number>, e.g.
DCC-PAT-0001, portal-facing) and mrn (MRN-<hospital short code>-<sequential
number>, e.g. MRN-DEF-0001, the clinical/legal record number) -- assigned at
the moment a `patients` row is first created for a (hospital_id, phone)
pair, never regenerated on a later booking.

Covers:
  - sequential + hospital-scoped generation (two hospitals both start at
    0001 independently)
  - never regenerated on a second booking by the same patient
  - the one-time backfill assigns ids to pre-existing patients in creation
    order, no duplicates/gaps, and is idempotent
  - the hospital short code is derived once from the hospital's own name and
    stored permanently (not recomputed on a later lookup) -- visible in mrn,
    not patient_display_id, which is hospital-agnostic-looking on purpose
"""
from datetime import datetime, timedelta

import db.repository as db
from db.connection import get_connection
from db.init_db import _backfill_patient_display_ids

PHONE_A = "5491112223333"
PHONE_B = "5491112224444"


def _book(hospital_id, phone, doctor_id, slot, **kwargs):
    return db.create_appointment(
        hospital_id, phone, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot['date']}T{slot['time']}"), **kwargs,
    )


def test_ids_are_sequential_and_hospital_scoped(hospital_id, second_hospital_id):
    """Two DIFFERENT hospitals each booking their own first-ever patient both
    get 0001 -- the sequence is per-hospital (patient_id_counters), not a
    single global counter."""
    doctor_a = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slots_a = db.get_slots(hospital_id, doctor_a)

    t2_dept = db.get_departments(second_hospital_id)[0]["id"]
    doctor_b = db.get_doctors(second_hospital_id, t2_dept)[0]["id"]
    slots_b = db.get_slots(second_hospital_id, doctor_b)

    db.create_appointment(hospital_id, PHONE_A, "cardiology", doctor_a,
                           datetime.fromisoformat(f"{slots_a[0]['date']}T{slots_a[0]['time']}"), patient_name="Ravi", patient_age=30)
    db.create_appointment(hospital_id, PHONE_B, "cardiology", doctor_a,
                           datetime.fromisoformat(f"{slots_a[1]['date']}T{slots_a[1]['time']}"), patient_name="Priya", patient_age=25)
    db.create_appointment(second_hospital_id, PHONE_A, t2_dept, doctor_b,
                           datetime.fromisoformat(f"{slots_b[0]['date']}T{slots_b[0]['time']}"), patient_name="Amit", patient_age=40)

    patient_a1 = db.get_patient_by_phone(hospital_id, PHONE_A)
    patient_a2 = db.get_patient_by_phone(hospital_id, PHONE_B)
    patient_b1 = db.get_patient_by_phone(second_hospital_id, PHONE_A)

    # Hospital A's own sequence: 0001 then 0002.
    assert patient_a1["patient_display_id"].endswith("-0001")
    assert patient_a2["patient_display_id"].endswith("-0002")
    # Hospital B's sequence starts independently at 0001, even though PHONE_A
    # already has a hospital-A record -- patients are hospital-scoped.
    assert patient_b1["patient_display_id"].endswith("-0001")
    # patient_display_id is hospital-agnostic-looking on purpose (portal-
    # facing internal id) -- both hospitals' first patient get the exact
    # same string.
    assert patient_a1["patient_display_id"] == "DCC-PAT-0001"
    assert patient_b1["patient_display_id"] == "DCC-PAT-0001"
    # mrn is where the derived short code shows up ("Default Hospital" ->
    # DEF, "Test Hospital 2" -> TH2), same sequence number as the paired
    # patient_display_id.
    assert patient_a1["mrn"] == "MRN-DEF-0001"
    assert patient_b1["mrn"] == "MRN-TH2-0001"


def test_id_is_never_regenerated_on_a_second_booking(hospital_id):
    """A second (and third) booking by the same phone must keep the exact
    same Patient ID assigned at their first-ever booking."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slots = db.get_slots(hospital_id, doctor_id)

    _book(hospital_id, PHONE_A, doctor_id, slots[0], patient_name="Ravi Kumar", patient_age=34)
    first_id = db.get_patient_by_phone(hospital_id, PHONE_A)["patient_display_id"]
    assert first_id is not None

    # Second booking, same doctor is blocked by the duplicate-booking guard
    # (same name+age) -- use a different age to simulate a family member on
    # the same phone, still the same underlying `patients` row/id.
    _book(hospital_id, PHONE_A, doctor_id, slots[1], patient_age=8)
    second_id = db.get_patient_by_phone(hospital_id, PHONE_A)["patient_display_id"]

    assert second_id == first_id


def test_id_survives_a_failed_first_booking_attempt(hospital_id):
    """Same regression class as the earlier name/age-upsert fix (Spec.md
    Section 0): _upsert_patient() runs BEFORE create_appointment()'s
    transaction opens, so a patient_display_id assigned there is durable
    even if this exact booking attempt goes on to fail."""
    from db.repository import QuotaExceededError
    import pytest

    department_id = db.get_departments(hospital_id)[0]["id"]
    doctor = db.create_doctor(
        hospital_id, department_id, "Dr. Zero Quota",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["09:00-10:00"], slot_duration_minutes=60, daily_booking_limit=0,
    )
    scheduled_at = datetime.now() + timedelta(days=1)

    with pytest.raises(QuotaExceededError):
        db.create_appointment(
            hospital_id, PHONE_A, department_id, doctor["id"], scheduled_at,
            patient_name="Ravi Kumar", patient_age=34,
        )

    patient = db.get_patient_by_phone(hospital_id, PHONE_A)
    assert patient is not None
    assert patient["patient_display_id"] is not None


def test_backfill_assigns_ids_in_creation_order_with_no_duplicates_or_gaps(hospital_id):
    """Pre-existing patients (created before this column existed, or via a
    path that bypasses _upsert_patient, e.g. a direct row insert) get a real
    id from the one-time backfill, in the order they were originally
    created -- no duplicates, no gaps in the numbering."""
    conn = get_connection()
    # Three "legacy" patients, inserted directly (not through
    # _upsert_patient, so patient_display_id is genuinely NULL) with
    # explicit, out-of-insert-order created_at timestamps.
    conn.execute(
        "INSERT INTO patients (hospital_id, phone, name, created_at) VALUES "
        "(?, 'legacy-3', 'Third', '2024-01-03T00:00:00'), "
        "(?, 'legacy-1', 'First', '2024-01-01T00:00:00'), "
        "(?, 'legacy-2', 'Second', '2024-01-02T00:00:00')",
        (hospital_id, hospital_id, hospital_id),
    )
    conn.commit()

    _backfill_patient_display_ids(conn)

    rows = {
        r["phone"]: (r["patient_display_id"], r["mrn"]) for r in conn.execute(
            "SELECT phone, patient_display_id, mrn FROM patients WHERE hospital_id = ? AND phone LIKE ?",
            (hospital_id, "legacy-%"),
        ).fetchall()
    }
    assert rows["legacy-1"][0] is not None and rows["legacy-2"][0] is not None and rows["legacy-3"][0] is not None
    assert rows["legacy-1"][1] is not None and rows["legacy-2"][1] is not None and rows["legacy-3"][1] is not None
    # Assigned in CREATED_AT order, not insertion/id order.
    seq1 = int(rows["legacy-1"][0].rsplit("-", 1)[1])
    seq2 = int(rows["legacy-2"][0].rsplit("-", 1)[1])
    seq3 = int(rows["legacy-3"][0].rsplit("-", 1)[1])
    assert seq1 < seq2 < seq3
    # No gaps: consecutive.
    assert seq2 == seq1 + 1
    assert seq3 == seq2 + 1
    # mrn shares the exact same sequence number as its paired patient_display_id.
    assert rows["legacy-1"][1].rsplit("-", 1)[1] == rows["legacy-1"][0].rsplit("-", 1)[1]
    # No duplicates across the whole hospital.
    all_ids = [
        r["patient_display_id"] for r in conn.execute(
            "SELECT patient_display_id FROM patients WHERE hospital_id = ? AND patient_display_id IS NOT NULL",
            (hospital_id,),
        ).fetchall()
    ]
    assert len(all_ids) == len(set(all_ids))


def test_backfill_is_idempotent_and_a_later_real_booking_continues_the_sequence(hospital_id):
    """Re-running the backfill (every app startup does) must never touch an
    already-assigned id or create a duplicate; a genuinely NEW patient
    booking after the backfill continues the same counter, no collision."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO patients (hospital_id, phone, name, created_at) VALUES (?, 'legacy-x', 'Legacy', '2024-01-01T00:00:00')",
        (hospital_id,),
    )
    conn.commit()

    _backfill_patient_display_ids(conn)
    first_run_id = conn.execute(
        "SELECT patient_display_id FROM patients WHERE hospital_id = ? AND phone = 'legacy-x'", (hospital_id,),
    ).fetchone()["patient_display_id"]

    _backfill_patient_display_ids(conn)  # re-run, e.g. next startup
    second_run_id = conn.execute(
        "SELECT patient_display_id FROM patients WHERE hospital_id = ? AND phone = 'legacy-x'", (hospital_id,),
    ).fetchone()["patient_display_id"]
    assert second_run_id == first_run_id

    # A real new booking afterward gets the NEXT number, not a collision
    # with the backfilled one.
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    _book(hospital_id, PHONE_A, doctor_id, slot, patient_name="Ravi Kumar", patient_age=34)
    new_id = db.get_patient_by_phone(hospital_id, PHONE_A)["patient_display_id"]
    assert new_id != first_run_id
    old_seq = int(first_run_id.rsplit("-", 1)[1])
    new_seq = int(new_id.rsplit("-", 1)[1])
    assert new_seq == old_seq + 1


def test_hospital_short_code_derivation_and_persistence(hospital_id):
    """Derived once from the hospital's own name and stored on
    hospitals.patient_id_prefix permanently -- confirmed here directly
    rather than just inferred from the generated ids above."""
    conn = get_connection()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    _book(hospital_id, PHONE_A, doctor_id, slot, patient_name="Ravi Kumar", patient_age=34)

    row = conn.execute("SELECT patient_id_prefix, name FROM hospitals WHERE id = ?", (hospital_id,)).fetchone()
    assert row["name"] == "Default Hospital"
    assert row["patient_id_prefix"] == "DEF"

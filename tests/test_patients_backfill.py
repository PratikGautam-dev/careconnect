# tests/test_patients_backfill.py
"""
SPEC Section 12.9: db/init_db.py's _backfill_patients() -- the one-time,
idempotent backfill that seeds a patients row (name NULL) for every distinct
(hospital_id, phone) pair already sitting in appointments, so existing
WhatsApp-only patients are searchable by phone immediately once the patients
table ships.

Covers the two things explicitly worth confirming about this kind of
cross-tenant backfill: the SAME phone number appearing under two different
hospitals must produce two SEPARATE, tenant-scoped patient records (never
one shared record -- patients are hospital_id-scoped like everything else,
SPEC Section 12.2), and that the backfill applies NO validation/filtering to
phone values -- it's a mechanical DISTINCT (hospital_id, phone) copy, so a
malformed (but non-NULL -- appointments.phone is TEXT NOT NULL, so a true
NULL can never reach this backfill at all) phone still gets a patients row,
same as a well-formed one. Nothing is ever skipped or needs a judgment call;
the row count created always equals the number of distinct (hospital_id,
phone) pairs going in.
"""
import db.connection as db_connection
import db.repository as db
from db.connection import IntegrityError
from db.init_db import _backfill_patients


def _insert_second_hospital(conn, name, phone_number_id):
    cur = conn.execute(
        "INSERT INTO hospitals (name, whatsapp_phone_number_id) VALUES (?, ?) RETURNING id",
        (name, phone_number_id),
    )
    conn.commit()
    hosp_id = cur.fetchone()["id"]
    conn.execute("INSERT INTO departments (id, hospital_id, name) VALUES (?, ?, ?)", (f"dept_{hosp_id}", hosp_id, "General"))
    conn.execute(
        "INSERT INTO doctors (id, hospital_id, department_id, name) VALUES (?, ?, ?, ?)",
        (f"doc_{hosp_id}", hosp_id, f"dept_{hosp_id}", "Dr. Second"),
    )
    conn.commit()
    return hosp_id


def _insert_appointment(conn, hospital_id, phone, department_id, doctor_id, scheduled_at):
    conn.execute(
        "INSERT INTO appointments (hospital_id, phone, department_id, doctor_id, scheduled_at) VALUES (?, ?, ?, ?, ?)",
        (hospital_id, phone, department_id, doctor_id, scheduled_at),
    )
    conn.commit()


def test_same_phone_across_two_hospitals_gets_two_separate_patient_records(hospital_id, second_hospital_id):
    """Central requirement: patients are tenant-scoped like everything else
    (SPEC Section 12.2) -- the backfill must never collapse the same phone
    number at two different hospitals into one shared record."""
    conn = db_connection.get_connection()
    shared_phone = "5491112223333"
    dept_a = db.get_departments(hospital_id)[0]["id"]
    doctor_a = db.get_doctors(hospital_id, dept_a)[0]["id"]
    dept_b = db.get_departments(second_hospital_id)[0]["id"]
    doctor_b = db.get_doctors(second_hospital_id, dept_b)[0]["id"]

    _insert_appointment(conn, hospital_id, shared_phone, dept_a, doctor_a, "2027-01-10T09:00:00")
    _insert_appointment(conn, second_hospital_id, shared_phone, dept_b, doctor_b, "2027-01-11T10:00:00")

    _backfill_patients(conn)

    matches_a = db.search_patients(hospital_id, shared_phone)
    matches_b = db.search_patients(second_hospital_id, shared_phone)
    assert len(matches_a) == 1 and matches_a[0]["phone"] == shared_phone
    assert len(matches_b) == 1 and matches_b[0]["phone"] == shared_phone

    rows = conn.execute("SELECT hospital_id FROM patients WHERE phone = ?", (shared_phone,)).fetchall()
    assert {r["hospital_id"] for r in rows} == {hospital_id, second_hospital_id}
    assert len(rows) == 2  # two rows, not one shared row


def test_appointments_phone_cannot_be_null_at_the_schema_level(hospital_id):
    """A true "missing phone" can never reach the backfill at all --
    appointments.phone is TEXT NOT NULL, enforced by Postgres itself, not
    application logic. Confirms that guarantee directly rather than assuming
    it from reading the schema file."""
    conn = db_connection.get_connection()
    dept = db.get_departments(hospital_id)[0]["id"]
    doctor = db.get_doctors(hospital_id, dept)[0]["id"]
    try:
        conn.execute(
            "INSERT INTO appointments (hospital_id, phone, department_id, doctor_id, scheduled_at) "
            "VALUES (?, NULL, ?, ?, ?)",
            (hospital_id, dept, doctor, "2027-01-15T09:00:00"),
        )
        conn.commit()
        assert False, "a NULL phone should have been rejected by the schema"
    except IntegrityError:
        conn.execute("ROLLBACK")


def test_malformed_phones_are_not_filtered_or_skipped_by_the_backfill(hospital_id):
    """The backfill applies no validation -- empty string, whitespace-only,
    and non-phone-looking text all get their own patients row exactly like a
    well-formed phone would. Not a bug: db.search_patients()/the portal UI
    are where any future format cleanup would belong, not a silent-drop in
    a one-time migration."""
    conn = db_connection.get_connection()
    dept = db.get_departments(hospital_id)[0]["id"]
    doctor = db.get_doctors(hospital_id, dept)[0]["id"]
    malformed_phones = ["", "   ", "not-a-phone-number!!"]
    for i, phone in enumerate(malformed_phones):
        _insert_appointment(conn, hospital_id, phone, dept, doctor, f"2027-02-{10 + i:02d}T09:00:00")

    before = conn.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]
    _backfill_patients(conn)
    after = conn.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]

    assert after - before == len(malformed_phones)
    stored_phones = {r["phone"] for r in conn.execute(
        "SELECT phone FROM patients WHERE hospital_id = ?", (hospital_id,)
    ).fetchall()}
    for phone in malformed_phones:
        assert phone in stored_phones


def test_backfill_creates_exactly_one_patient_per_distinct_hospital_phone_pair(hospital_id, second_hospital_id):
    """No row is ever skipped: the count created always equals the number of
    distinct (hospital_id, phone) pairs across every appointment, regardless
    of how many appointments share a pair (repeat patients don't multiply
    patient rows) or how those pairs are distributed across hospitals."""
    conn = db_connection.get_connection()
    dept_a = db.get_departments(hospital_id)[0]["id"]
    doctor_a = db.get_doctors(hospital_id, dept_a)[0]["id"]
    dept_b = db.get_departments(second_hospital_id)[0]["id"]
    doctor_b = db.get_doctors(second_hospital_id, dept_b)[0]["id"]

    # Same phone booked twice at hospital A (repeat patient) -- one pair, two appointments.
    _insert_appointment(conn, hospital_id, "5490001111", dept_a, doctor_a, "2027-03-01T09:00:00")
    _insert_appointment(conn, hospital_id, "5490001111", dept_a, doctor_a, "2027-03-08T09:00:00")
    # A second, distinct patient at hospital A.
    _insert_appointment(conn, hospital_id, "5490002222", dept_a, doctor_a, "2027-03-02T09:00:00")
    # Same two phone numbers again, but at hospital B -- distinct pairs.
    _insert_appointment(conn, second_hospital_id, "5490001111", dept_b, doctor_b, "2027-03-03T09:00:00")
    _insert_appointment(conn, second_hospital_id, "5490002222", dept_b, doctor_b, "2027-03-04T09:00:00")

    distinct_pairs = conn.execute(
        "SELECT COUNT(DISTINCT (hospital_id, phone)) AS c FROM appointments "
        "WHERE hospital_id IN (?, ?) AND phone IN (?, ?)",
        (hospital_id, second_hospital_id, "5490001111", "5490002222"),
    ).fetchone()["c"]
    assert distinct_pairs == 4  # 2 phones x 2 hospitals

    before = conn.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]
    _backfill_patients(conn)
    after = conn.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]
    assert after - before == 4


def test_backfill_is_idempotent(hospital_id):
    """Re-running it (every app startup does) must never create duplicates
    or error, same discipline as every other backfill in this file."""
    conn = db_connection.get_connection()
    dept = db.get_departments(hospital_id)[0]["id"]
    doctor = db.get_doctors(hospital_id, dept)[0]["id"]
    _insert_appointment(conn, hospital_id, "5490009999", dept, doctor, "2027-04-01T09:00:00")

    _backfill_patients(conn)
    count_after_first = conn.execute("SELECT COUNT(*) AS c FROM patients WHERE phone = ?", ("5490009999",)).fetchone()["c"]
    _backfill_patients(conn)
    count_after_second = conn.execute("SELECT COUNT(*) AS c FROM patients WHERE phone = ?", ("5490009999",)).fetchone()["c"]

    assert count_after_first == 1
    assert count_after_second == 1

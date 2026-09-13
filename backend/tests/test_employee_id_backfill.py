# tests/test_employee_id_backfill.py
"""Employee ID auto-numbering feature: db/init_db.py's
_backfill_doctor_employee_ids()/_backfill_staff_employee_ids() -- unlike
every other backfill in this file (gated on IS NULL, only ever filling a
gap), these two REWRITE every pre-existing free-text employee_id into the
new EMP-DC-NNNNN/EMP-ST-NNNNN scheme (explicit user decision). Covers: the
rewrite itself, idempotency (re-running is a safe no-op once caught up), and
the property that matters most for a real hospital -- the code_sequences
counter the backfill leaves behind is exactly where the next REAL doctor/
staff member continues from, no gap or collision."""
import re

import db.connection as db_connection
import db.repository as db
from db.init_db import _backfill_doctor_employee_ids, _backfill_staff_employee_ids

_EMPLOYEE_ID_RE = re.compile(r"^(EMP-DC|EMP-ST)-(\d+)$")


def _seq(employee_id: str) -> int:
    return int(_EMPLOYEE_ID_RE.match(employee_id).group(2))


def test_backfill_doctor_employee_ids_rewrites_legacy_values_and_seeds_the_counter_correctly(hospital_id):
    """The seeded test hospital already has real doctors (db/seed.py's
    DOCTORS_BY_DEPARTMENT), themselves already backfilled by the same
    init_db_on_connection() call every test fixture makes -- so this
    doesn't assert a literal "EMP-DC-00001", just that a legacy value gets
    rewritten into the new format, stays stable across a second run, and
    that whatever number it lands on is exactly where the NEXT real doctor
    continues from (the property that actually matters)."""
    conn = db_connection.get_connection()
    dept = db.get_departments(hospital_id)[0]["id"]
    conn.execute(
        "INSERT INTO doctors (id, hospital_id, department_id, name, employee_id) VALUES (?, ?, ?, ?, ?)",
        ("legacy_doc_1", hospital_id, dept, "Dr. Legacy", "OLD-001"),
    )
    conn.commit()

    _backfill_doctor_employee_ids(conn)
    row = conn.execute("SELECT employee_id FROM doctors WHERE id = ?", ("legacy_doc_1",)).fetchone()
    assert _EMPLOYEE_ID_RE.match(row["employee_id"])
    legacy_seq = _seq(row["employee_id"])

    # Re-running (every app startup does) must not touch an already-rewritten row.
    _backfill_doctor_employee_ids(conn)
    row_again = conn.execute("SELECT employee_id FROM doctors WHERE id = ?", ("legacy_doc_1",)).fetchone()
    assert row_again["employee_id"] == row["employee_id"]

    # A brand-new doctor created AFTER the backfill continues the same
    # counter with no gap or collision -- proves the backfill leaves
    # code_sequences exactly where the next real doctor should pick up.
    new_doctor = db.create_doctor(hospital_id, dept, "Dr. New After Backfill")
    new_full = db.get_doctor_full(hospital_id, new_doctor["id"])
    assert _seq(new_full["employee_id"]) == legacy_seq + 1


def test_backfill_staff_employee_ids_rewrites_legacy_values_and_skips_doctor_role(hospital_id):
    conn = db_connection.get_connection()
    legacy_identity_id = conn.execute(
        "INSERT INTO identities (email, password_hash, name) VALUES (?, ?, ?) RETURNING id",
        ("legacy.staff@example.com", "hash", "Legacy Staff"),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO staff_details (identity_id, hospital_id, role, employee_id) VALUES (?, ?, ?, ?)",
        (legacy_identity_id, hospital_id, "receptionist", "OLD-STAFF-1"),
    )
    conn.commit()

    _backfill_staff_employee_ids(conn)
    row = conn.execute("SELECT employee_id FROM staff_details WHERE identity_id = ?", (legacy_identity_id,)).fetchone()
    assert _EMPLOYEE_ID_RE.match(row["employee_id"])
    legacy_seq = _seq(row["employee_id"])

    # A doctor-role staff_details row is never given its own EMP-ST -- its
    # employee id already lives on the linked doctors row instead.
    dept = db.get_departments(hospital_id)[0]["id"]
    doctor = db.create_doctor(hospital_id, dept, "Dr. Backfill Skip")
    doctor_login_identity_id = conn.execute(
        "INSERT INTO identities (email, password_hash, name) VALUES (?, ?, ?) RETURNING id",
        ("legacy.doctor.login@example.com", "hash", "Legacy Doctor Login"),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO staff_details (identity_id, hospital_id, role, doctor_id, employee_id) VALUES (?, ?, ?, ?, ?)",
        (doctor_login_identity_id, hospital_id, "doctor", doctor["id"], ""),
    )
    conn.commit()

    _backfill_staff_employee_ids(conn)
    doctor_row = conn.execute(
        "SELECT employee_id FROM staff_details WHERE identity_id = ?", (doctor_login_identity_id,)
    ).fetchone()
    assert doctor_row["employee_id"] == ""

    # A brand-new admin/receptionist created AFTER the backfill continues
    # the same counter with no gap or collision.
    receptionist_role_id = next(
        r["id"] for r in db.list_roles(hospital_id) if r["name"].lower() == "receptionist"
    )
    new_staff = db.create_staff_user(
        hospital_id, receptionist_role_id, "new.after.backfill@example.com", "hash", "New Recep",
    )
    assert _seq(new_staff["employee_id"]) == legacy_seq + 1

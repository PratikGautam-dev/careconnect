# db/seed.py
"""
Seed data. Two kinds:

- seed_default_hospital(): the one real hospital this build actually serves,
  carried over verbatim from the old mock_data.py's DEPARTMENTS/DOCTORS_BY_DEPARTMENT.
  Real per-hospital department/doctor rows come from Phase 3's ERP wiring or the
  Section 12.1 onboarding wizard; this is the Tier 1 stand-in for that.

- seed_test_hospital(): a second, entirely fake hospital used ONLY by
  tests/conftest.py to prove multi-tenant isolation (SPEC Section 12.2/Phase 9)
  — never called from init_db_on_connection, so it never exists in a real
  deployment's database.

Every seeded doctor gets the same working pattern (all 7 days, 10:00-11:00 and
15:00-16:00, 60-minute slots -- exactly the old hardcoded _SLOT_TIMES) so
db.repository.get_slots() keeps returning the same "10:00"/"15:00" slots
existing tests already expect, now sourced from real generated doctor_slots
rows (Section 12.1.1) instead of computed on the fly.
"""
from db.repositories.appointment_types import DEFAULT_APPOINTMENT_TYPES
from db.repository import generate_slots_for_doctor

_DEFAULT_WORKING_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_DEFAULT_WORKING_HOURS = ["10:00-11:00", "15:00-16:00"]
_DEFAULT_SLOT_DURATION_MINUTES = 60

DEPARTMENTS = [
    {"id": "cardiology", "name": "Cardiology"},
    {"id": "orthopedics", "name": "Orthopedics"},
    {"id": "general_medicine", "name": "General Medicine"},
    {"id": "pediatrics", "name": "Pediatrics"},
]

DOCTORS_BY_DEPARTMENT = {
    "cardiology": [
        {"id": "doc_card_1", "name": "Dr. Anjali Rao"},
        {"id": "doc_card_2", "name": "Dr. Vikram Sethi"},
    ],
    "orthopedics": [
        {"id": "doc_ortho_1", "name": "Dr. Rajesh Kumar"},
        {"id": "doc_ortho_2", "name": "Dr. Meera Nair"},
        {"id": "doc_ortho_3", "name": "Dr. Sanjay Gupta"},
    ],
    "general_medicine": [
        {"id": "doc_gen_1", "name": "Dr. Priya Sharma"},
        {"id": "doc_gen_2", "name": "Dr. Arjun Mehta"},
    ],
    "pediatrics": [
        {"id": "doc_ped_1", "name": "Dr. Kavita Iyer"},
        {"id": "doc_ped_2", "name": "Dr. Rohan Desai"},
        {"id": "doc_ped_3", "name": "Dr. Neha Kapoor"},
    ],
}

# Deliberately different id slugs from DEPARTMENTS/DOCTORS_BY_DEPARTMENT above
# (not just different names) — department/doctor ids are still globally-unique
# text slugs, not (hospital_id, id)-composite (a known Tier 1 limitation, see
# db/schema.sql), so two hospitals can't both use id="cardiology". Prefixing
# with "t2_" sidesteps that for this fake test hospital rather than fixing it.
TEST_HOSPITAL_2_DEPARTMENTS = [
    {"id": "t2_neurology", "name": "Neurology"},
    {"id": "t2_dermatology", "name": "Dermatology"},
]

TEST_HOSPITAL_2_DOCTORS_BY_DEPARTMENT = {
    "t2_neurology": [
        {"id": "t2_doc_neuro_1", "name": "Dr. Isabel Cruz"},
    ],
    "t2_dermatology": [
        {"id": "t2_doc_derm_1", "name": "Dr. Marcus Webb"},
    ],
}


def seed_default_hospital(
    conn,
    hospital_name: str = "Default Hospital",
    whatsapp_phone_number_id: str | None = None,
    access_token: str | None = None,
    app_secret: str | None = None,
) -> int:
    """Idempotent: if a hospital with this name already exists, returns its id
    without touching departments/doctors again. Returns the hospital's id."""
    row = conn.execute("SELECT id FROM hospitals WHERE name = ?", (hospital_name,)).fetchone()
    if row:
        return row["id"]

    cur = conn.execute(
        "INSERT INTO hospitals (name, whatsapp_phone_number_id, meta_access_token_ref, app_secret_ref) "
        "VALUES (?, ?, ?, ?) RETURNING id",
        (hospital_name, whatsapp_phone_number_id, access_token, app_secret),
    )
    hospital_id = cur.fetchone()["id"]

    for dept in DEPARTMENTS:
        conn.execute(
            "INSERT INTO departments (id, hospital_id, name) VALUES (?, ?, ?)",
            (dept["id"], hospital_id, dept["name"]),
        )
    for department_id, doctors in DOCTORS_BY_DEPARTMENT.items():
        for doc in doctors:
            conn.execute(
                "INSERT INTO doctors (id, hospital_id, department_id, name, working_days, working_hours, "
                "slot_duration_minutes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (doc["id"], hospital_id, department_id, doc["name"],
                 ",".join(_DEFAULT_WORKING_DAYS), ",".join(_DEFAULT_WORKING_HOURS), _DEFAULT_SLOT_DURATION_MINUTES),
            )
            generate_slots_for_doctor(hospital_id, doc["id"], conn=conn)
    conn.commit()
    return hospital_id


def _seed_appointment_types(conn, hospital_id: int) -> None:
    """Called by seed_test_hospital() below -- db/repositories/hospitals.py's
    create_hospital() seeds the same DEFAULT_APPOINTMENT_TYPES catalog for
    the real onboarding path, and seed_default_hospital()'s own hospital
    gets it from db/init_db.py's _backfill_appointment_types() (run right
    after seed_default_hospital() in init_db_on_connection) -- but
    seed_test_hospital() is never followed by that backfill (tests/conftest.py
    calls it standalone, after the backfill already ran for the FIRST
    hospital only), so it needs this step done explicitly."""
    for sort_order, appt_type in enumerate(DEFAULT_APPOINTMENT_TYPES):
        conn.execute(
            "INSERT INTO appointment_types "
            "(id, hospital_id, label, requires_consent, requires_doctor_selection, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                appt_type["id"], hospital_id, appt_type["label"], appt_type["requires_consent"],
                appt_type["requires_doctor_selection"], sort_order,
            ),
        )


def seed_test_hospital(
    conn,
    hospital_name: str = "Test Hospital 2",
    whatsapp_phone_number_id: str = "TEST_HOSPITAL_2_PHONE_ID",
) -> int:
    """A second hospital purely for multi-tenant isolation tests (SPEC Phase 9)
    — a fake phone_number_id, no real Meta credentials, never wired to an
    actual number. Only tests/conftest.py calls this."""
    row = conn.execute("SELECT id FROM hospitals WHERE name = ?", (hospital_name,)).fetchone()
    if row:
        return row["id"]

    cur = conn.execute(
        "INSERT INTO hospitals (name, whatsapp_phone_number_id) VALUES (?, ?) RETURNING id",
        (hospital_name, whatsapp_phone_number_id),
    )
    hospital_id = cur.fetchone()["id"]

    for dept in TEST_HOSPITAL_2_DEPARTMENTS:
        conn.execute(
            "INSERT INTO departments (id, hospital_id, name) VALUES (?, ?, ?)",
            (dept["id"], hospital_id, dept["name"]),
        )
    for department_id, doctors in TEST_HOSPITAL_2_DOCTORS_BY_DEPARTMENT.items():
        for doc in doctors:
            conn.execute(
                "INSERT INTO doctors (id, hospital_id, department_id, name, working_days, working_hours, "
                "slot_duration_minutes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (doc["id"], hospital_id, department_id, doc["name"],
                 ",".join(_DEFAULT_WORKING_DAYS), ",".join(_DEFAULT_WORKING_HOURS), _DEFAULT_SLOT_DURATION_MINUTES),
            )
            generate_slots_for_doctor(hospital_id, doc["id"], conn=conn)
    _seed_appointment_types(conn, hospital_id)
    conn.commit()
    return hospital_id

# db/repositories/appointment_types.py
"""Appointment type step (WhatsApp flow alignment) -- the APPOINTMENT TYPE
node between patient resolution and department selection. Hospital-
configurable set, same "toggle a fixed catalog" shape as
hospitals.enabled_features -- see db/schema.sql's own comment on
appointment_types for why this isn't hardcoded in the flow itself."""
from db.connection import get_connection

# The fixed catalog db/init_db.py seeds per hospital (idempotent, additive --
# a hospital can still deactivate/relabel any of these via is_active/label
# without code changes). Single source of truth for the seed AND for
# validating a hospital-provided id elsewhere, same role
# RELATIONSHIP_OPTIONS plays for patient_links.relationship_label.
DEFAULT_APPOINTMENT_TYPES = (
    {"id": "new", "label": "New Consultation", "requires_consent": False, "requires_doctor_selection": True},
    {"id": "followup", "label": "Follow-up", "requires_consent": False, "requires_doctor_selection": True},
    {"id": "tele", "label": "Tele-consultation", "requires_consent": True, "requires_doctor_selection": True},
    {"id": "second_opinion", "label": "Second Opinion", "requires_consent": True, "requires_doctor_selection": True},
    {"id": "diagnostic", "label": "Diagnostic", "requires_consent": False, "requires_doctor_selection": False},
    {"id": "lab", "label": "Lab Test", "requires_consent": False, "requires_doctor_selection": False},
    {"id": "daycare", "label": "Daycare", "requires_consent": False, "requires_doctor_selection": True},
)


def get_appointment_types(hospital_id: int) -> list[dict]:
    """Active types only, in the hospital's configured display order --
    powers the WhatsApp APPOINTMENT TYPE list, same "only ever read the
    active/enabled subset" discipline as connector.get_departments()."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, label, requires_consent, requires_doctor_selection FROM appointment_types "
        "WHERE hospital_id = ? AND is_active = TRUE ORDER BY sort_order, id",
        (hospital_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_appointment_type(hospital_id: int, appointment_type_id: str) -> dict | None:
    """Looked up once a patient taps a row, to re-validate + read
    requires_consent for the next step -- same "recheck dynamic data at the
    point of use" discipline as _find_by_id() for department/doctor/slot."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, label, requires_consent, requires_doctor_selection FROM appointment_types "
        "WHERE hospital_id = ? AND id = ? AND is_active = TRUE",
        (hospital_id, appointment_type_id),
    ).fetchone()
    return dict(row) if row else None

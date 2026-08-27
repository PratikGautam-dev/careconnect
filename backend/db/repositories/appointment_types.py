# db/repositories/appointment_types.py
"""Appointment type step (WhatsApp flow alignment) -- the APPOINTMENT TYPE
node between patient resolution and department selection. Hospital-
configurable set, same "toggle a fixed catalog" shape as
hospitals.enabled_features -- see db/schema.sql's own comment on
appointment_types for why this isn't hardcoded in the flow itself."""
from sqlalchemy import select

from db.connection import get_session
from db.orm_models import AppointmentType

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
    session = get_session()
    rows = session.execute(
        select(
            AppointmentType.id, AppointmentType.label,
            AppointmentType.requires_consent, AppointmentType.requires_doctor_selection,
        )
        .where(AppointmentType.hospital_id == hospital_id, AppointmentType.is_active.is_(True))
        .order_by(AppointmentType.sort_order, AppointmentType.id)
    ).all()
    return [dict(r._mapping) for r in rows]


def get_appointment_type(hospital_id: int, appointment_type_id: str) -> dict | None:
    """Looked up once a patient taps a row, to re-validate + read
    requires_consent for the next step -- same "recheck dynamic data at the
    point of use" discipline as _find_by_id() for department/doctor/slot."""
    session = get_session()
    row = session.execute(
        select(
            AppointmentType.id, AppointmentType.label,
            AppointmentType.requires_consent, AppointmentType.requires_doctor_selection,
        )
        .where(
            AppointmentType.hospital_id == hospital_id, AppointmentType.id == appointment_type_id,
            AppointmentType.is_active.is_(True),
        )
    ).first()
    return dict(row._mapping) if row else None

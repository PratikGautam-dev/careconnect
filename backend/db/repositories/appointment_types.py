# db/repositories/appointment_types.py
"""Appointment type step (WhatsApp flow alignment) -- the APPOINTMENT TYPE
node between patient resolution and department selection. Hospital-
configurable set, same "toggle a fixed catalog" shape as
hospitals.enabled_features -- see db/schema.sql's own comment on
appointment_types for why this isn't hardcoded in the flow itself."""
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from db.connection import get_session
from db.orm_models import AppointmentType

# The fixed catalog db/init_db.py seeds per hospital (idempotent, additive --
# a hospital can still deactivate/relabel any of these via is_active/label
# without code changes). Single source of truth for the seed AND for
# validating a hospital-provided id elsewhere, same role
# RELATIONSHIP_OPTIONS plays for patient_links.relationship_label.
DEFAULT_APPOINTMENT_TYPES = (
    {"id": "new", "label": "New Consultation", "requires_consent": False, "requires_doctor_selection": True},
    {"id": "followup", "label": "Follow-up Consultation", "requires_consent": False, "requires_doctor_selection": True},
    {"id": "tele", "label": "Video Consultation", "requires_consent": True, "requires_doctor_selection": True},
    {"id": "diagnostic", "label": "Diagnostic Booking", "requires_consent": False, "requires_doctor_selection": False},
    {"id": "lab", "label": "Lab Test Booking", "requires_consent": False, "requires_doctor_selection": False},
    {"id": "daycare", "label": "Daycare Booking", "requires_consent": False, "requires_doctor_selection": True},
    {"id": "second_opinion", "label": "Report Review", "requires_consent": True, "requires_doctor_selection": True},
)

# Which of the fixed catalog's types are ACTIVE by default per tenant_type
# (tenant-capability-gating-plan.md's same "default-by-type, editable later"
# shape as DEFAULT_CAPABILITIES_BY_TYPE in portal/capabilities.py). A row is
# still created for every type on every tenant regardless -- only is_active
# differs -- so a clinic that later upgrades to hospital (or just wants one
# hospital-only type turned on) is a pure is_active flip via the portal, never
# a re-seed/backfill. "daycare" is the one hospital-only type today; unknown
# tenant types fall back to the (fully-active) hospital default, same
# fallback DEFAULT_CAPABILITIES_BY_TYPE uses.
DEFAULT_ACTIVE_TYPES_BY_TENANT_TYPE: dict[str, set[str]] = {
    "hospital": {t["id"] for t in DEFAULT_APPOINTMENT_TYPES},
    "clinic": {t["id"] for t in DEFAULT_APPOINTMENT_TYPES if t["id"] != "daycare"},
}


def default_is_active(tenant_type: str, appointment_type_id: str) -> bool:
    active_ids = DEFAULT_ACTIVE_TYPES_BY_TENANT_TYPE.get(tenant_type, DEFAULT_ACTIVE_TYPES_BY_TENANT_TYPE["hospital"])
    return appointment_type_id in active_ids


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


def get_all_appointment_types_for_hospital(hospital_id: int) -> list[dict]:
    """Active AND inactive types, for the portal's own management screen (a
    staff admin needs to see what's currently off in order to turn it back
    on) -- unlike get_appointment_types() above, which only ever surfaces the
    active subset to the WhatsApp booking flow."""
    session = get_session()
    rows = session.execute(
        select(
            AppointmentType.id, AppointmentType.label, AppointmentType.is_active,
            AppointmentType.requires_consent, AppointmentType.requires_doctor_selection,
        )
        .where(AppointmentType.hospital_id == hospital_id)
        .order_by(AppointmentType.sort_order, AppointmentType.id)
    ).all()
    return [dict(r._mapping) for r in rows]


def set_appointment_type_active(hospital_id: int, appointment_type_id: str, is_active: bool) -> dict | None:
    """Portal toggle (manage_appointment_types capability) -- the one-line
    is_active flip that lets a clinic turn on a hospital-only type (e.g.
    daycare) after upgrading, or a hospital turn one off, without touching
    any other data. Returns None if the type doesn't exist for this hospital
    (an unrecognized/stale id), else the updated row."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(AppointmentType)
        .where(AppointmentType.hospital_id == hospital_id, AppointmentType.id == appointment_type_id)
        .values(is_active=is_active)
    ))
    session.commit()
    if result.rowcount == 0:
        return None
    row = session.execute(
        select(
            AppointmentType.id, AppointmentType.label, AppointmentType.is_active,
            AppointmentType.requires_consent, AppointmentType.requires_doctor_selection,
        )
        .where(AppointmentType.hospital_id == hospital_id, AppointmentType.id == appointment_type_id)
    ).first()
    return dict(row._mapping) if row else None

# flows/booking/types/new_consultation.py
"""New Consultation: unchanged department -> doctor -> date -> slot ->
confirmation flow, plus two booking rules:
1. Same patient, same department, active booking -> blocked right when the
   department is picked (validate_department, shared with tele/second_opinion/
   daycare -- see base.existing_department_appointment), since it doesn't
   need a date.
2. Same patient, different department, same day as an active booking ->
   blocked at confirmation (validate_booking), since it needs scheduled_at.
   New-Consultation-only -- the other FULL_FLOW types don't have this one.
Both scoped by patient_id, not phone (one phone can have several patients)."""
from datetime import datetime

from flows.booking.types.base import FULL_FLOW, TypeFlow, existing_department_appointment


def _validate_new_consultation_booking(
    connector, hospital_id: int, patient_id: int | None, department_id: str | None, scheduled_at: datetime,
) -> str | None:
    """Returns the translations.py key blocking the booking, or None."""
    if patient_id is None:
        return None
    existing = connector.get_active_appointments_for_patient(hospital_id, patient_id)
    if any(a.department_id == department_id for a in existing):
        return "new_consultation_department_conflict"
    if any(a.scheduled_at.date() == scheduled_at.date() for a in existing):
        return "new_consultation_same_day_conflict"
    return None


FLOW = TypeFlow(
    type_id="new", steps=FULL_FLOW,
    validate_booking=_validate_new_consultation_booking,
    validate_department=existing_department_appointment,
)

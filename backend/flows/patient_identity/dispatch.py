# flows/patient_identity/dispatch.py
"""_HANDLERS: state -> handler, for every state this package owns except
consent's two functions (they take extra args flows/router.py's generic
8-arg dispatch shape doesn't carry -- router.py calls them directly instead,
see its own STATE_AWAITING_CONSENT_ACTION branch)."""
from flows.patient_identity.manage_patients import (
    _handle_awaiting_manage_patients_action,
    _handle_awaiting_remove_patient_selection,
    _handle_awaiting_unlink_confirm,
)
from flows.patient_identity.registration import (
    _handle_awaiting_booking_for,
    _handle_awaiting_duplicate_decision,
    _handle_awaiting_patient_age,
    _handle_awaiting_patient_contact_number,
    _handle_awaiting_patient_gender,
    _handle_awaiting_patient_name,
)
from flows.patient_identity.resolution import _handle_awaiting_single_patient_confirm
from flows.patient_identity.state import (
    STATE_AWAITING_BOOKING_FOR,
    STATE_AWAITING_DUPLICATE_DECISION,
    STATE_AWAITING_MANAGE_PATIENTS_ACTION,
    STATE_AWAITING_PATIENT_AGE,
    STATE_AWAITING_PATIENT_CONTACT_PHONE,
    STATE_AWAITING_PATIENT_GENDER,
    STATE_AWAITING_PATIENT_NAME,
    STATE_AWAITING_REMOVE_PATIENT_SELECTION,
    STATE_AWAITING_SINGLE_PATIENT_CONFIRM,
    STATE_AWAITING_UNLINK_CONFIRM,
)

_HANDLERS = {
    STATE_AWAITING_BOOKING_FOR: _handle_awaiting_booking_for,
    STATE_AWAITING_PATIENT_NAME: _handle_awaiting_patient_name,
    STATE_AWAITING_PATIENT_CONTACT_PHONE: _handle_awaiting_patient_contact_number,
    STATE_AWAITING_PATIENT_AGE: _handle_awaiting_patient_age,
    STATE_AWAITING_PATIENT_GENDER: _handle_awaiting_patient_gender,
    STATE_AWAITING_DUPLICATE_DECISION: _handle_awaiting_duplicate_decision,
    STATE_AWAITING_SINGLE_PATIENT_CONFIRM: _handle_awaiting_single_patient_confirm,
    STATE_AWAITING_MANAGE_PATIENTS_ACTION: _handle_awaiting_manage_patients_action,
    STATE_AWAITING_REMOVE_PATIENT_SELECTION: _handle_awaiting_remove_patient_selection,
    STATE_AWAITING_UNLINK_CONFIRM: _handle_awaiting_unlink_confirm,
}

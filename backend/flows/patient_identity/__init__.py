# flows/patient_identity/__init__.py
"""Patient identity resolution: WhatsApp Account != Patient. One phone can be
linked to several patient profiles (family members), so this package figures
out WHICH patient the current conversation is acting on before anything else
runs -- registration for a first-time phone, duplicate-patient detection,
switching between already-linked patients, and the Main Menu itself (with
its "Patient: X / Patient Code: Y" header).

flows/router.py's `_enter_idle()` calls `get_or_prompt_for_active_patient()`
right after language is settled, before the main menu is shown, for every
conversation -- everything after the main menu (flows/booking/, faq.py)
trusts an already-resolved `active_patient_id` instead of re-deriving
identity itself.

Architectural boundary: never import db/repository.py directly, only through
connectors.py -- every hospital-scoped read/write goes through the
`Connector` interface passed into each function here.

Physically split (same motivation/shape as flows/booking/'s own package) into:

  state.py             STATE_* constants, row/button ids, pure parsing
                        helpers (age/name/contact-number)
  menu.py               the unified main menu + patient header
  registration.py       [Myself/Someone Else] -> name -> [contact number] ->
                        age -> gender -> [duplicate decision] -> create/link
  resolution.py          the "which patient is this" entry point --
                        already-resolved fast path, single-patient
                        confirmation, 2+-patient selector
  manage_patients.py    Remove Patient / Add Patient 2-option screen
  consent.py            Consent & Privacy menu item
  dispatch.py            _HANDLERS -- state -> handler, for flows/router.py's
                        generic dispatch

This module re-exports the combined public (and historically
underscore-prefixed private, still relied on by tests/flows/router.py)
surface so every existing `import flows.patient_identity as patient_identity`
/ `from flows.patient_identity import X` call site keeps working exactly as
before this split -- same convention flows/booking/__init__.py already
established.

Known scope note: flows/booking/book.py still has its own older, dead-for-
real-traffic patient-selector/Manage-Patients implementation, kept only
because tests/test_booking_flow.py exercises it directly as a standalone
state machine test.
"""
import logging

logger = logging.getLogger(__name__)

from flows.patient_identity.state import (
    ADD_PATIENT_ENTRY_ID,
    BACK_ID,
    BOOKING_FOR_OTHER_ID,
    BOOKING_FOR_SELF_ID,
    CONFIRM_NO,
    CONFIRM_YES,
    CONSENT_TOGGLE_MARKETING_ID,
    CONSENT_WITHDRAW_SERVICE_ID,
    CONTACT_PHONE_COUNTRY_CODE,
    CONTACT_PHONE_NUMBER_LENGTH,
    DUPLICATE_DIFFERENT_ID,
    DUPLICATE_LINK_ID,
    FREE_TEXT_INPUT_STATES,
    GENDER_FEMALE_ID,
    GENDER_MALE_ID,
    GENDER_OTHER_ID,
    GOTO_MAIN_MENU,
    MAIN_MENU_BACK_ROW,
    MANAGE_ADD_ROW_ID,
    MANAGE_PATIENTS_BACK_ID,
    MANAGE_PATIENTS_ENTRY_ID,
    MANAGE_REMOVE_ROW_ID,
    MAX_PATIENT_AGE,
    MAX_PATIENT_NAME_LENGTH,
    MIN_PATIENT_AGE,
    MIN_PATIENT_NAME_LENGTH,
    STATE_AWAITING_BOOKING_FOR,
    STATE_AWAITING_CONSENT_ACTION,
    STATE_AWAITING_DUPLICATE_DECISION,
    STATE_AWAITING_MANAGE_PATIENTS_ACTION,
    STATE_AWAITING_PATIENT_AGE,
    STATE_AWAITING_PATIENT_CONTACT_PHONE,
    STATE_AWAITING_PATIENT_GENDER,
    STATE_AWAITING_PATIENT_NAME,
    STATE_AWAITING_REMOVE_PATIENT_SELECTION,
    STATE_AWAITING_SINGLE_PATIENT_CONFIRM,
    STATE_AWAITING_UNLINK_CONFIRM,
    _GENDER_ROW_IDS,
    _parse_contact_phone_number,
    _parse_patient_age,
    _parse_patient_name,
    _parse_patient_row_id,
    _parse_unlink_row_id,
    _patient_row_id,
    _patient_row_title,
    _PATIENT_ROW_PREFIX,
    _unlink_row_id,
    _UNLINK_ROW_PREFIX,
)
from flows.patient_identity.menu import (
    _FEATURE_MENU,
    _ROW_ID_TO_FEATURE,
    _patient_header,
    _send_dynamic_menu,
    _send_menu_list,
    ALL_FEATURES,
    REAL_FEATURES,
)
from flows.patient_identity.registration import (
    _create_or_link_patient,
    _handle_awaiting_booking_for,
    _handle_awaiting_duplicate_decision,
    _handle_awaiting_patient_age,
    _handle_awaiting_patient_contact_number,
    _handle_awaiting_patient_gender,
    _handle_awaiting_patient_name,
    _send_back_button,
    _send_booking_for_prompt,
    _send_gender_prompt,
    _start_registration,
)
from flows.patient_identity.resolution import (
    _handle_awaiting_single_patient_confirm,
    _send_patient_selector_for_resolution,
    _send_single_patient_confirm,
    get_or_prompt_for_active_patient,
)
from flows.patient_identity.manage_patients import (
    _handle_awaiting_manage_patients_action,
    _handle_awaiting_remove_patient_selection,
    _handle_awaiting_unlink_confirm,
    _send_remove_patient_list,
    _start_manage_patients,
)
from flows.patient_identity.consent import handle_awaiting_consent_action, start_consent_privacy
from flows.patient_identity.dispatch import _HANDLERS  # noqa: F401

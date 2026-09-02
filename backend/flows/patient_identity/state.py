# flows/patient_identity/state.py
"""Conversation states, row/button ids, and pure parsing helpers for the
patient-identity package -- no WhatsApp sends, no Connector calls, nothing
async. Mirrors flows/booking/state.py's own role in that package."""

from connectors import GENDER_OPTIONS

# --- Row/button ids ---

GOTO_MAIN_MENU = "goto_main_menu"
CONFIRM_YES = "confirm"
CONFIRM_NO = "cancel"
# "Back" for the identity-resolution mini-flow (name -> age -> gender ->
# [duplicate decision]). Separate from flows/booking/state.py's own BACK_ID
# since this module never imports from booking.
BACK_ID = "identity_nav_back"

# Main menu's own "Back" -- opens Manage Patients. Handled in
# flows/router.py's IDLE dispatch, same as CHANGE_LANGUAGE_ROW.
MAIN_MENU_BACK_ROW = "menu_back_manage_patients"

# Always appended to the main menu (unless the hospital disables the language
# picker) -- not a per-hospital feature toggle.
CHANGE_LANGUAGE_ROW = "menu_change_language"

_PATIENT_ROW_PREFIX = "idpat_"
_UNLINK_ROW_PREFIX = "idunlink_"
MANAGE_ADD_ROW_ID = "id_manage_add"
# Manage Patients' own 2-option entry point (confirmed with the user):
# Remove Patient shows the patient list ONLY when removing -- there is no
# "switch active patient" action here anymore, that's the resolution flow's
# job. MANAGE_ADD_ROW_ID (above) doubles as this screen's own "Add Patient"
# button id, same as before.
MANAGE_REMOVE_ROW_ID = "id_manage_remove"
# Remove-patient list's own "Back" row -- returns to the 2-option screen
# above, not the main menu.
MANAGE_PATIENTS_BACK_ID = "id_manage_patients_back"
MANAGE_PATIENTS_ENTRY_ID = "id_manage_patients_entry"
# Single-patient-confirm screen's "add someone else" escape hatch -- goes
# straight into registration, not the full Manage Patients menu.
ADD_PATIENT_ENTRY_ID = "id_add_patient_entry"
DUPLICATE_LINK_ID = "id_dup_link"
DUPLICATE_DIFFERENT_ID = "id_dup_different"
CONSENT_TOGGLE_MARKETING_ID = "id_consent_marketing_toggle"
CONSENT_WITHDRAW_SERVICE_ID = "id_consent_withdraw_service"

GENDER_MALE_ID = "id_gender_male"
GENDER_FEMALE_ID = "id_gender_female"
GENDER_OTHER_ID = "id_gender_other"
_GENDER_ROW_IDS = {GENDER_MALE_ID: "Male", GENDER_FEMALE_ID: "Female", GENDER_OTHER_ID: "Other"}
assert set(_GENDER_ROW_IDS.values()) == set(GENDER_OPTIONS)

# "Myself / Someone Else" registration step -- the new first step of
# registration (see registration.py's _start_registration).
BOOKING_FOR_SELF_ID = "id_booking_for_self"
BOOKING_FOR_OTHER_ID = "id_booking_for_other"


def _patient_row_id(patient_id: int) -> str:
    """Builds a patient list-row id from a patient id."""
    return f"{_PATIENT_ROW_PREFIX}{patient_id}"


def _parse_patient_row_id(row_id: str) -> int | None:
    """Reverses _patient_row_id(); None if row_id isn't one of these rows."""
    if not row_id.startswith(_PATIENT_ROW_PREFIX):
        return None
    try:
        return int(row_id[len(_PATIENT_ROW_PREFIX):])
    except ValueError:
        return None


def _unlink_row_id(patient_id: int) -> str:
    """Builds an unlink-confirm row id from a patient id."""
    return f"{_UNLINK_ROW_PREFIX}{patient_id}"


def _parse_unlink_row_id(row_id: str) -> int | None:
    """Reverses _unlink_row_id(); None if row_id isn't one of these rows."""
    if not row_id.startswith(_UNLINK_ROW_PREFIX):
        return None
    try:
        return int(row_id[len(_UNLINK_ROW_PREFIX):])
    except ValueError:
        return None


def _patient_row_title(patient: dict) -> str:
    """Row title for a patient list -- just the name. relationship_label
    ("Self"/"Other") is an internal bookkeeping value (drives the
    one-Self-per-account rule and the contact-number question), never shown
    to the patient -- confirmed with the user."""
    return patient["name"]


# --- Conversation states ("IDENTITY_" prefixed to stay distinct from
# flows/booking's own similarly-named states -- both sets are dispatched
# from the same table in flows/router.py.) ---

STATE_AWAITING_BOOKING_FOR = "IDENTITY_AWAITING_BOOKING_FOR"
STATE_AWAITING_PATIENT_NAME = "IDENTITY_AWAITING_NAME"
STATE_AWAITING_PATIENT_CONTACT_PHONE = "IDENTITY_AWAITING_CONTACT_PHONE"
STATE_AWAITING_PATIENT_AGE = "IDENTITY_AWAITING_AGE"
STATE_AWAITING_PATIENT_GENDER = "IDENTITY_AWAITING_GENDER"
STATE_AWAITING_DUPLICATE_DECISION = "IDENTITY_AWAITING_DUPLICATE_DECISION"
STATE_AWAITING_SINGLE_PATIENT_CONFIRM = "IDENTITY_AWAITING_SINGLE_CONFIRM"
STATE_AWAITING_MANAGE_PATIENTS_ACTION = "IDENTITY_AWAITING_MANAGE_ACTION"
STATE_AWAITING_REMOVE_PATIENT_SELECTION = "IDENTITY_AWAITING_REMOVE_PATIENT_SELECTION"
STATE_AWAITING_UNLINK_CONFIRM = "IDENTITY_AWAITING_UNLINK_CONFIRM"
STATE_AWAITING_CONSENT_ACTION = "IDENTITY_AWAITING_CONSENT_ACTION"

FREE_TEXT_INPUT_STATES = {STATE_AWAITING_PATIENT_NAME, STATE_AWAITING_PATIENT_CONTACT_PHONE, STATE_AWAITING_PATIENT_AGE}

MIN_PATIENT_AGE = 0
MAX_PATIENT_AGE = 120

MIN_PATIENT_NAME_LENGTH = 3  # ">=3 characters" per spec
MAX_PATIENT_NAME_LENGTH = 50


def _parse_patient_age(text: str) -> int | None:
    """Parses a digits-only age in [MIN_PATIENT_AGE, MAX_PATIENT_AGE]; None
    for anything else (empty, non-numeric, negative, out of range)."""
    text = text.strip()
    if not text.isdigit():
        return None
    age = int(text)
    if age < MIN_PATIENT_AGE or age > MAX_PATIENT_AGE:
        return None
    return age


CONTACT_PHONE_NUMBER_LENGTH = 10
CONTACT_PHONE_COUNTRY_CODE = "91"


def _parse_contact_phone_number(text: str) -> str | None:
    """"Someone Else" registration step: exact 10 digits, digits only, must
    not start with 0 (per the user's own explicit call, not the looser
    is_valid_phone() rule used for the messaging phone elsewhere) -- None for
    anything else. Returned value is prefixed with the country code
    (e.g. "7622569904" -> "917622569904") so it's stored in the same shape
    as the messaging phone (patients.phone / whatsapp_identities.phone_number),
    letting it be matched against an incoming WhatsApp number later."""
    text = text.strip()
    if not text.isdigit() or len(text) != CONTACT_PHONE_NUMBER_LENGTH or text[0] == "0":
        return None
    return CONTACT_PHONE_COUNTRY_CODE + text


def _parse_patient_name(text: str) -> str | None:
    """Letters and spaces only -- no digits/punctuation -- collapsed to
    single spaces, length in [MIN_PATIENT_NAME_LENGTH, MAX_PATIENT_NAME_LENGTH].
    str.isalpha() is Unicode-aware on purpose (accepts Hindi/Devanagari
    names too, not just A-Z) since this app supports Hindi as a full
    language, not just English. None for anything else."""
    name = " ".join(text.split())
    if not name or not all(ch.isalpha() or ch == " " for ch in name):
        return None
    if not (MIN_PATIENT_NAME_LENGTH <= len(name) <= MAX_PATIENT_NAME_LENGTH):
        return None
    return name

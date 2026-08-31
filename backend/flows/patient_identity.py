# core/patient_identity.py
"""Patient identity resolution: WhatsApp Account != Patient. One phone can be
linked to several patient profiles (family members), so this module figures
out WHICH patient the current conversation is acting on before anything else
runs -- registration for a first-time phone, duplicate-patient detection,
switching between already-linked patients, and the Main Menu itself (with
its "Patient: X / Patient Code: Y" header).

flows.py's `_enter_idle()` calls `get_or_prompt_for_active_patient()` right
after language is settled, before the main menu is shown, for every
conversation -- everything after the main menu (core/booking_flow.py,
faq_flow.py) trusts an already-resolved `active_patient_id` instead of
re-deriving identity itself.

Architectural boundary: never import db/repository.py directly, only through
connectors.py -- every hospital-scoped read/write goes through the
`Connector` interface passed into each function here.

Known scope note: core/booking_flow.py still has its own older, dead-for-
real-traffic patient-selector/Manage-Patients implementation, kept only
because tests/test_booking_flow.py exercises it directly as a standalone
state machine test.
"""
import logging

from connectors import (
    Connector, DuplicateSelfLinkError, GENDER_OPTIONS, RELATIONSHIP_OTHER, RELATIONSHIP_SELF, TooManyLinkedPatientsError,
)
from flows.common import cap_rows
from core.translations import t
from core.translations.menu import (
    FEATURE_BOOKING,
    FEATURE_CANCEL,
    FEATURE_CONSENT_PRIVACY,
    FEATURE_FAQ,
    FEATURE_HOSPITAL_INFO,
    FEATURE_MENU_UNAVAILABLE,
    FEATURE_RECEPTION_HANDOFF,
    FEATURE_REPORTS_PRESCRIPTIONS,
    FEATURE_RESCHEDULE,
    FEATURE_VIEW_APPOINTMENTS,
    MAIN_MENU_BUTTON,
    MAIN_MENU_SECTION_TITLE,
    WELCOME_MENU,
)
from core.translations.common import BACK_OPTION
from core.translations.booking import (
    ASK_BOOKING_FOR,
    ASK_PATIENT_AGE,
    ASK_PATIENT_CONTACT_NUMBER,
    ASK_PATIENT_GENDER,
    ASK_PATIENT_NAME,
    BOOKING_FOR_OTHER_BUTTON,
    BOOKING_FOR_SELF_BUTTON,
    CANCEL_BUTTON,
    CONFIRM_BUTTON,
    GENDER_FEMALE,
    GENDER_MALE,
    GENDER_OTHER,
    INVALID_PATIENT_AGE,
    INVALID_PATIENT_CONTACT_NUMBER,
    INVALID_PATIENT_NAME,
)
from core.translations.patient_identity import (
    ADD_PATIENT_OPTION,
    ADD_PATIENT_SHORT,
    BACK_TO_MENU_OPTION,
    DUPLICATE_DIFFERENT_BUTTON,
    DUPLICATE_LINK_BUTTON,
    DUPLICATE_PATIENT_FOUND,
    DUPLICATE_SELF_LINK,
    MANAGE_PATIENTS_SHORT,
    MULTI_PATIENT_SELECTOR_PROMPT,
    PATIENT_ALREADY_LINKED,
    PATIENT_CODE_LABEL,
    PATIENT_HEADER_LABEL,
    PATIENT_SELECTOR_BUTTON,
    PATIENT_SELECTOR_PROMPT,
    PATIENT_SELECTOR_SECTION_TITLE,
    REGISTRATION_BLOCKED_CONTACT_HOSPITAL,
    SINGLE_PATIENT_CONFIRM,
    TOO_MANY_LINKED_PATIENTS,
)
from core.translations.manage_patients import (
    MANAGE_PATIENTS_BUTTON,
    MANAGE_PATIENTS_HEADER,
    MANAGE_PATIENTS_SECTION_TITLE,
    PATIENT_ACTION_PROMPT,
    PATIENT_ADDED,
    PATIENT_UNLINKED,
    UNLINK_OPTION,
    UNLINK_PATIENT_CONFIRM,
    USE_THIS_PATIENT_OPTION,
)
from core.translations.dpdp_consent import (
    CONSENT_MARKETING_DISABLE,
    CONSENT_MARKETING_ENABLE,
    CONSENT_OFF,
    CONSENT_ON,
    CONSENT_PRIVACY_BODY,
    PRIVACY_NOTICE_DEFAULT,
)
from core.whatsapp import WhatsAppClient

logger = logging.getLogger(__name__)

# --- Main menu ---

# feature key -> (menu row id, menu row title translation key). Order here is
# the order rows appear in the main menu.
_FEATURE_MENU = {
    "booking": ("menu_book", FEATURE_BOOKING),
    "reschedule": ("menu_reschedule", FEATURE_RESCHEDULE),
    "cancel": ("menu_cancel", FEATURE_CANCEL),
    "view_appointments": ("menu_view_appointments", FEATURE_VIEW_APPOINTMENTS),
    "reports_prescriptions": ("menu_reports_prescriptions", FEATURE_REPORTS_PRESCRIPTIONS),
    "manage_patients": ("menu_manage_patients", "feature_manage_patients"),
    "consent_privacy": ("menu_consent_privacy", FEATURE_CONSENT_PRIVACY),
    "hospital_info": ("menu_hospital_info", FEATURE_HOSPITAL_INFO),
    "reception_handoff": ("menu_reception", FEATURE_RECEPTION_HANDOFF),
    "faq": ("menu_faq_bot", FEATURE_FAQ),
}
_ROW_ID_TO_FEATURE = {row_id: key for key, (row_id, _title_key) in _FEATURE_MENU.items()}

REAL_FEATURES = set(_FEATURE_MENU.keys())
ALL_FEATURES = REAL_FEATURES

# Always appended to the main menu (unless the hospital disables the language
# picker) -- not a per-hospital feature toggle.
CHANGE_LANGUAGE_ROW = "menu_change_language"

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


def _patient_header(active_patient: dict | None, language: str) -> str:
    """"Patient: {name}\\nPatient Code: {patient_display_id}" header shown
    above the main menu once a patient has been resolved -- the real
    clinical mrn (db/models.py's _generate_patient_identifiers) is never
    shown here, only the patient-facing patient_display_id. Empty string if
    none resolved yet."""
    if active_patient is None:
        return ""
    patient_code = active_patient.get("patient_display_id") or "—"
    return f"*{t(PATIENT_HEADER_LABEL, language)}* {active_patient['name']}\n*{t(PATIENT_CODE_LABEL, language)}* {patient_code}\n\n"


async def _send_dynamic_menu(
    wa: WhatsAppClient, phone: str, hospital_name: str, enabled_features: list[str], language: str = "en",
    feature_labels: dict[str, str] | None = None, language_prompt_enabled: bool = True,
    active_patient: dict | None = None,
) -> None:
    """Sends the hospital's main menu: one row per enabled feature, capped to
    WhatsApp's row limit, with the patient header on top and a separate
    "Back" buttons message underneath (a list can't carry its own back row)."""
    feature_labels = feature_labels or {}
    rows = [
        {"id": row_id, "title": feature_labels.get(key) or t(title_key, language)}
        for key, (row_id, title_key) in _FEATURE_MENU.items()
        if key in enabled_features
    ]
    if not rows:
        await wa.send_text(phone, t(FEATURE_MENU_UNAVAILABLE, language, hospital_name=hospital_name))
        return
    rows = cap_rows(rows, f"main menu for {hospital_name}")
    body_text = _patient_header(active_patient, language) + t(WELCOME_MENU, language, hospital_name=hospital_name)
    await wa.send_list(
        to=phone,
        body_text=body_text,
        button_text=t(MAIN_MENU_BUTTON, language),
        sections=[{"title": t(MAIN_MENU_SECTION_TITLE, language), "rows": rows}],
    )
    # Its own follow-up buttons message right under the list, not a row
    # hidden inside it (WhatsApp collapses a list to just its button_text
    # until tapped).
    await wa.send_buttons(
        to=phone, body_text="​", buttons=[{"id": MAIN_MENU_BACK_ROW, "title": t(BACK_OPTION, language)}],
    )


# --- Row-id helpers ---

_PATIENT_ROW_PREFIX = "idpat_"
_UNLINK_ROW_PREFIX = "idunlink_"
MANAGE_ADD_ROW_ID = "id_manage_add"
MANAGE_PATIENTS_ENTRY_ID = "id_manage_patients_entry"
# Single-patient-confirm screen's "add someone else" escape hatch -- goes
# straight into registration, not the full Manage Patients menu.
ADD_PATIENT_ENTRY_ID = "id_add_patient_entry"
# Manage Patients' own per-patient action choice -- the three buttons shown
# after tapping a linked patient's row in THAT menu specifically.
PATIENT_ACTION_USE_ID = "id_patient_action_use"
PATIENT_ACTION_UNLINK_ID = "id_patient_action_unlink"
PATIENT_ACTION_BACK_ID = "id_patient_action_back"
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
# registration (see _start_registration below).
BOOKING_FOR_SELF_ID = "id_booking_for_self"
BOOKING_FOR_OTHER_ID = "id_booking_for_other"


async def _send_back_button(wa: WhatsAppClient, phone: str, language: str = "en") -> None:
    """Sends a standalone "Back" buttons message (zero-width-space body,
    since Meta rejects a truly empty one) -- duplicated from flows/booking's
    own helper rather than imported, per this module's own boundary."""
    await wa.send_buttons(to=phone, body_text="​", buttons=[{"id": BACK_ID, "title": t(BACK_OPTION, language)}])


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
# core/booking_flow.py's own similarly-named states -- both sets are
# dispatched from the same table in flows.py.) ---

STATE_AWAITING_BOOKING_FOR = "IDENTITY_AWAITING_BOOKING_FOR"
STATE_AWAITING_PATIENT_NAME = "IDENTITY_AWAITING_NAME"
STATE_AWAITING_PATIENT_CONTACT_PHONE = "IDENTITY_AWAITING_CONTACT_PHONE"
STATE_AWAITING_PATIENT_AGE = "IDENTITY_AWAITING_AGE"
STATE_AWAITING_PATIENT_GENDER = "IDENTITY_AWAITING_GENDER"
STATE_AWAITING_DUPLICATE_DECISION = "IDENTITY_AWAITING_DUPLICATE_DECISION"
STATE_AWAITING_SINGLE_PATIENT_CONFIRM = "IDENTITY_AWAITING_SINGLE_CONFIRM"
STATE_AWAITING_MANAGE_PATIENTS_ACTION = "IDENTITY_AWAITING_MANAGE_ACTION"
STATE_AWAITING_PATIENT_ACTION_CHOICE = "IDENTITY_AWAITING_PATIENT_ACTION_CHOICE"
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


def _parse_contact_phone_number(text: str) -> str | None:
    """"Someone Else" registration step: exact 10 digits, digits only (per
    the user's own explicit call, not the looser is_valid_phone() rule used
    for the messaging phone elsewhere) -- None for anything else."""
    text = text.strip()
    if not text.isdigit() or len(text) != CONTACT_PHONE_NUMBER_LENGTH:
        return None
    return text


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


# --- The resolution entry point ---

async def get_or_prompt_for_active_patient(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector,
    language: str = "en", require_patient_confirmation: bool = False,
) -> dict | None:
    """Called once per conversation, before the main menu is ever shown.
    Returns the resolved active patient immediately for the already-resolved
    or exactly-one-linked-patient case; otherwise sends a registration or
    selection prompt and returns None -- the caller must stop, and
    whichever completion path was triggered calls back into this function
    once it's done. A phone linked to more than one patient always re-prompts
    (via _send_patient_selector_for_resolution) rather than silently reusing
    whichever patient happened to be active before -- EXCEPT right after the
    user just confirmed/picked one this same turn
    (context["just_confirmed_patient"], set by _handle_awaiting_single_patient_
    confirm): router.py re-enters this function in the same handle_incoming
    call once state becomes IDLE, and without this flag that re-entry would
    immediately re-show the very confirm screen the user just answered."""
    session = sessions.get(hospital_id, phone)
    active_patient_id = session.get("active_patient_id")
    just_confirmed = session.get("context", {}).get("just_confirmed_patient", False)
    patients = connector.list_active_patients(hospital_id, phone)

    if active_patient_id is not None:
        if connector.validate_active_patient_link(hospital_id, phone, active_patient_id):
            match = next((p for p in patients if p["id"] == active_patient_id), None)
            if match is not None:
                if len(patients) > 1 and not just_confirmed:
                    await _send_patient_selector_for_resolution(wa, sessions, phone, hospital_id, connector, language)
                    return None
                sessions.set(hospital_id, phone, "IDLE", {}, language=language, active_patient_id=match["id"])
                return match
        # Stale (unlinked, or the patient was blocked/inactivated since) --
        # force a fresh resolution rather than trusting it further.
        sessions.clear_active_patient(hospital_id, phone)

    if len(patients) == 0:
        await _start_registration(wa, sessions, phone, hospital_id, connector, language)
        return None
    if len(patients) == 1 and not require_patient_confirmation:
        sessions.set(hospital_id, phone, "IDLE", {}, language=language, active_patient_id=patients[0]["id"])
        return patients[0]
    if len(patients) == 1:
        await _send_single_patient_confirm(wa, sessions, phone, hospital_id, connector, patients[0], language)
    else:
        await _send_patient_selector_for_resolution(wa, sessions, phone, hospital_id, connector, language)
    return None


# --- Registration: [Myself/Someone Else] -> name -> [contact number, Someone
# Else only] -> age -> gender -> [duplicate decision] -> create/link ---

async def _start_registration(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str,
    identity_flow_next: str = "resolve",
) -> None:
    """Kicks off registration -- "Myself / Someone Else" first, UNLESS this
    CareConnect account already has an active "Myself" (relationship_label=
    RELATIONSHIP_SELF) patient linked at this hospital, in which case the
    question is skipped entirely (silently locked to "Someone Else") and
    registration goes straight to the name question. See
    has_self_linked_patient()'s own docstring for the hard, race-safe
    backstop this soft check pairs with."""
    account = connector.identify_contact(phone, phone_number=phone)
    if connector.has_self_linked_patient(hospital_id, account["id"]):
        context = {"identity_flow_next": identity_flow_next, "pending_relationship": RELATIONSHIP_OTHER}
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, context, language=language)
        await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
        if identity_flow_next == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    await _send_booking_for_prompt(wa, sessions, phone, hospital_id, {"identity_flow_next": identity_flow_next}, language)


async def _send_booking_for_prompt(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, language: str,
) -> None:
    sessions.set(hospital_id, phone, STATE_AWAITING_BOOKING_FOR, context, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t(ASK_BOOKING_FOR, language),
        buttons=[
            {"id": BOOKING_FOR_SELF_ID, "title": t(BOOKING_FOR_SELF_BUTTON, language)},
            {"id": BOOKING_FOR_OTHER_ID, "title": t(BOOKING_FOR_OTHER_BUTTON, language)},
        ],
    )
    if context.get("identity_flow_next") == "manage_patients":
        await _send_back_button(wa, phone, language=language)


async def _handle_awaiting_booking_for(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """"Myself" skips the contact-number question later (defaults to the
    messaging phone); "Someone Else" routes the name step into a dedicated
    contact-number question next. BACK returns to Manage Patients -- the
    only screen this step can ever follow, since it's registration's own
    first step."""
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID and context.get("identity_flow_next") == "manage_patients":
        await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        return
    if reply["type"] == "interactive_reply" and reply["id"] == BOOKING_FOR_SELF_ID:
        relationship = RELATIONSHIP_SELF
    elif reply["type"] == "interactive_reply" and reply["id"] == BOOKING_FOR_OTHER_ID:
        relationship = RELATIONSHIP_OTHER
    else:
        await _send_booking_for_prompt(wa, sessions, phone, hospital_id, context, language)
        return
    new_context = {**context, "pending_relationship": relationship, "booking_for_asked": True}
    if relationship == RELATIONSHIP_SELF:
        new_context["pending_contact_phone"] = phone
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, new_context, language=language)
    await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
    if context.get("identity_flow_next") == "manage_patients":
        await _send_back_button(wa, phone, language=language)


async def _handle_awaiting_patient_name(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Accepts a valid name (letters/spaces only, 4-50 characters) and moves
    on -- to the contact-number question for "Someone Else", or straight to
    age for "Myself" (whose contact number is already the messaging phone,
    set back in _handle_awaiting_booking_for). Re-prompts on anything else.
    BACK returns to the Myself/Someone Else question if it was actually
    shown (context["booking_for_asked"]), else to Manage Patients if this
    is mid-"Add Patient" -- the very first registration has no earlier
    screen in either case."""
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID:
        if context.get("booking_for_asked"):
            await _send_booking_for_prompt(
                wa, sessions, phone, hospital_id, {"identity_flow_next": context.get("identity_flow_next", "resolve")}, language,
            )
            return
        if context.get("identity_flow_next") == "manage_patients":
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
    name = _parse_patient_name(reply["text"]) if reply["type"] == "text" else None
    if name is not None:
        new_context = {**context, "pending_name": name}
        if new_context.get("pending_relationship") == RELATIONSHIP_OTHER:
            sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_CONTACT_PHONE, new_context, language=language)
            await wa.send_text(phone, t(ASK_PATIENT_CONTACT_NUMBER, language, patient_name=name))
            if context.get("identity_flow_next") == "manage_patients":
                await _send_back_button(wa, phone, language=language)
            return
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, new_context, language=language)
        await wa.send_text(phone, t(ASK_PATIENT_AGE, language, patient_name=name))
        if context.get("identity_flow_next") == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, context, language=language)
    await wa.send_text(phone, t(INVALID_PATIENT_NAME, language))
    await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
    if context.get("identity_flow_next") == "manage_patients":
        await _send_back_button(wa, phone, language=language)


async def _handle_awaiting_patient_contact_number(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """"Someone Else" only -- never reached for "Myself", which uses the
    messaging phone directly (set in _handle_awaiting_booking_for). Accepts
    an exact 10-digit number and moves to the age question; re-prompts on
    anything invalid/missing. BACK returns to the name question."""
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID:
        identity_flow_next = context.get("identity_flow_next", "resolve")
        new_context = {k: v for k, v in context.items() if k != "pending_contact_phone"}
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, new_context, language=language)
        await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
        if identity_flow_next == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    contact_phone = _parse_contact_phone_number(reply["text"]) if reply["type"] == "text" else None
    if contact_phone is None:
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_CONTACT_PHONE, context, language=language)
        await wa.send_text(phone, t(INVALID_PATIENT_CONTACT_NUMBER, language))
        await wa.send_text(phone, t(ASK_PATIENT_CONTACT_NUMBER, language, patient_name=context.get("pending_name", "")))
        if context.get("identity_flow_next") == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    new_context = {**context, "pending_contact_phone": contact_phone}
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, new_context, language=language)
    await wa.send_text(phone, t(ASK_PATIENT_AGE, language, patient_name=new_context.get("pending_name", "")))
    if context.get("identity_flow_next") == "manage_patients":
        await _send_back_button(wa, phone, language=language)


async def _handle_awaiting_patient_age(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Accepts a valid age and moves to the gender question; re-prompts on
    anything invalid/missing. BACK returns to the contact-number question
    for "Someone Else" (who has one), or the name question for "Myself"."""
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID:
        identity_flow_next = context.get("identity_flow_next", "resolve")
        if context.get("pending_relationship") == RELATIONSHIP_OTHER:
            new_context = {k: v for k, v in context.items() if k != "pending_age"}
            sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_CONTACT_PHONE, new_context, language=language)
            await wa.send_text(phone, t(ASK_PATIENT_CONTACT_NUMBER, language, patient_name=context.get("pending_name", "")))
            if identity_flow_next == "manage_patients":
                await _send_back_button(wa, phone, language=language)
            return
        new_context = {k: v for k, v in context.items() if k not in ("pending_name", "pending_age")}
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, new_context, language=language)
        await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
        if identity_flow_next == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    age = _parse_patient_age(reply["text"]) if reply["type"] == "text" else None
    if age is None:
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, context, language=language)
        await wa.send_text(phone, t(INVALID_PATIENT_AGE, language))
        await wa.send_text(phone, t(ASK_PATIENT_AGE, language, patient_name=context.get("pending_name", "")))
        if context.get("identity_flow_next") == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    new_context = {**context, "pending_age": age}
    await _send_gender_prompt(wa, sessions, phone, hospital_id, new_context, language)


async def _send_gender_prompt(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, language: str,
) -> None:
    """Sends the required Male/Female/Other gender prompt -- the third and
    final step of registration before duplicate-checking/creation."""
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_GENDER, context, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t(ASK_PATIENT_GENDER, language),
        buttons=[
            {"id": GENDER_MALE_ID, "title": t(GENDER_MALE, language)},
            {"id": GENDER_FEMALE_ID, "title": t(GENDER_FEMALE, language)},
            {"id": GENDER_OTHER_ID, "title": t(GENDER_OTHER, language)},
        ],
    )
    if context.get("identity_flow_next") == "manage_patients":
        await _send_back_button(wa, phone, language=language)


async def _handle_awaiting_patient_gender(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Accepts a gender choice, then either surfaces a duplicate-patient
    match (exact name + contact phone, among this hospital's active
    patients) for the user to resolve, creates the profile directly if
    there's no match, or -- if the match is already actively linked to THIS
    phone -- tells the user plainly and creates nothing (re-adding the same
    name+contact you already have would otherwise silently create a genuine
    duplicate `patients` row every time; see
    find_potential_duplicate_patient()'s own docstring). Re-prompts on an
    unrecognized tap; BACK returns to the age question."""
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID:
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, context, language=language)
        await wa.send_text(phone, t(ASK_PATIENT_AGE, language, patient_name=context.get("pending_name", "")))
        if context.get("identity_flow_next") == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    gender = _GENDER_ROW_IDS.get(reply["id"]) if reply["type"] == "interactive_reply" else None
    if gender is None:
        await _send_gender_prompt(wa, sessions, phone, hospital_id, context, language)
        return

    new_context = {**context, "pending_gender": gender}
    match = connector.find_potential_duplicate_patient(
        hospital_id, new_context["pending_name"], new_context["pending_contact_phone"],
    )
    if match is not None and connector.validate_active_patient_link(hospital_id, phone, match["id"]):
        identity_flow_next = context.get("identity_flow_next", "resolve")
        await wa.send_text(phone, t(PATIENT_ALREADY_LINKED, language, name=match["name"]))
        if identity_flow_next == "manage_patients":
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        else:
            sessions.reset(hospital_id, phone)
        return
    if match is not None:
        new_context["duplicate_patient_id"] = match["id"]
        new_context["duplicate_patient_name"] = match["name"]
        new_context["duplicate_patient_display_id"] = match["patient_display_id"]
        sessions.set(hospital_id, phone, STATE_AWAITING_DUPLICATE_DECISION, new_context, language=language)
        await wa.send_buttons(
            to=phone,
            body_text=t(DUPLICATE_PATIENT_FOUND, language, name=match["name"], patient_code=match["patient_display_id"] or "—"),
            buttons=[
                {"id": DUPLICATE_LINK_ID, "title": t(DUPLICATE_LINK_BUTTON, language)},
                {"id": DUPLICATE_DIFFERENT_ID, "title": t(DUPLICATE_DIFFERENT_BUTTON, language)},
                {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
            ],
        )
        return
    await _create_or_link_patient(wa, sessions, phone, hospital_id, new_context, connector, language)


async def _handle_awaiting_duplicate_decision(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Resolves a duplicate-patient match: link the existing profile (no new
    MRN), create a genuinely new one anyway, or cancel back to the start.
    Re-shows the same choice on an unrecognized/stale tap."""
    identity_flow_next = context.get("identity_flow_next", "resolve")
    if reply["type"] == "interactive_reply":
        if reply["id"] == DUPLICATE_LINK_ID:
            # Link the EXISTING patient -- no new MRN.
            link_context = {**context, "link_target_patient_id": context["duplicate_patient_id"]}
            await _create_or_link_patient(wa, sessions, phone, hospital_id, link_context, connector, language)
            return
        if reply["id"] == DUPLICATE_DIFFERENT_ID:
            await _create_or_link_patient(wa, sessions, phone, hospital_id, context, connector, language)
            return
        if reply["id"] == CONFIRM_NO:
            if identity_flow_next == "manage_patients":
                await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            else:
                await _start_registration(wa, sessions, phone, hospital_id, connector, language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_DUPLICATE_DECISION, context, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t(DUPLICATE_PATIENT_FOUND, language,
            name=context.get("duplicate_patient_name", ""), patient_code=context.get("duplicate_patient_display_id") or "—",
        ),
        buttons=[
            {"id": DUPLICATE_LINK_ID, "title": t(DUPLICATE_LINK_BUTTON, language)},
            {"id": DUPLICATE_DIFFERENT_ID, "title": t(DUPLICATE_DIFFERENT_BUTTON, language)},
            {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
        ],
    )


async def _create_or_link_patient(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, connector: Connector, language: str,
) -> None:
    """Shared tail end of registration: links an existing patient
    (context["link_target_patient_id"] set) or creates a brand-new one from
    the collected name/age/gender, then lands on the main menu (or back on
    Manage Patients, if that's where this registration was launched from)."""
    identity_flow_next = context.get("identity_flow_next", "resolve")
    try:
        if context.get("link_target_patient_id") is not None:
            patient = connector.link_existing_patient(
                hospital_id, phone, context["link_target_patient_id"],
                relationship_label=context.get("pending_relationship"),
            )
        else:
            patient = connector.create_patient_profile(
                hospital_id, phone, context["pending_name"], context.get("pending_age"),
                relationship_label=context.get("pending_relationship"), gender=context.get("pending_gender"),
                contact_phone=context.get("pending_contact_phone"),
            )
    except TooManyLinkedPatientsError:
        await wa.send_text(phone, t(TOO_MANY_LINKED_PATIENTS, language))
        if identity_flow_next == "manage_patients":
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        else:
            sessions.reset(hospital_id, phone)
            await wa.send_text(phone, t(REGISTRATION_BLOCKED_CONTACT_HOSPITAL, language))
        return
    except DuplicateSelfLinkError:
        # The soft pre-check (has_self_linked_patient, in _start_registration)
        # should make this essentially unreachable outside a genuine race
        # between two concurrent "Myself" registrations from the same
        # account -- restart registration rather than dead-end; by the time
        # they retry, has_self_linked_patient() will correctly lock them to
        # "Someone Else".
        await wa.send_text(phone, t(DUPLICATE_SELF_LINK, language))
        if identity_flow_next == "manage_patients":
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        else:
            await _start_registration(wa, sessions, phone, hospital_id, connector, language)
        return

    if identity_flow_next == "manage_patients":
        await wa.send_text(phone, t(PATIENT_ADDED, language, patient_name=patient["name"]))
        await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        return
    sessions.set(
        hospital_id, phone, "IDLE", {"just_confirmed_patient": True}, language=language,
        active_patient_id=patient["id"],
    )


# --- Single-linked-patient confirmation (hospital-configurable) ---
#
# Sends two messages together, in one turn: a 2-button "Continue as X?"
# (Confirm / Add Patient), immediately followed by the plain patient-list
# picker -- so the list is always visible, with no extra "Patient List"
# button tap needed to reveal it first. Both messages reply into the same
# state; tapping a patient row there sets them active immediately, with no
# further "what do you want to do with X" step (that step is Manage-
# Patients-only, below).

async def _send_single_patient_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, patient: dict, language: str,
) -> None:
    """Sends the "Continue as X?" buttons, then the patient-list message
    right after, both under STATE_AWAITING_SINGLE_PATIENT_CONFIRM. Only
    reached today with exactly one linked patient and
    hospitals.require_patient_confirmation on -- the 2+ patient case goes
    through _send_patient_selector_for_resolution below instead, which has
    no single candidate to name in a "Continue as X?" card."""
    sessions.set(
        hospital_id, phone, STATE_AWAITING_SINGLE_PATIENT_CONFIRM, {"candidate_patient_id": patient["id"]},
        language=language,
    )
    await wa.send_buttons(
        to=phone,
        body_text=t(SINGLE_PATIENT_CONFIRM, language, patient_name=patient["name"], patient_code=patient["patient_display_id"] or "—",
        ),
        buttons=[
            {"id": CONFIRM_YES, "title": t(CONFIRM_BUTTON, language)},
            {"id": ADD_PATIENT_ENTRY_ID, "title": t(ADD_PATIENT_SHORT, language)},
        ],
    )
    patients = connector.list_active_patients(hospital_id, phone)
    rows = [{"id": _patient_row_id(p["id"]), "title": _patient_row_title(p)} for p in patients]
    rows.append({"id": MANAGE_PATIENTS_ENTRY_ID, "title": t(MANAGE_PATIENTS_SHORT, language)})
    rows = cap_rows(rows, "patient selector")
    await wa.send_list(
        to=phone,
        body_text=t(PATIENT_SELECTOR_PROMPT, language),
        button_text=t(PATIENT_SELECTOR_BUTTON, language),
        sections=[{"title": t(PATIENT_SELECTOR_SECTION_TITLE, language), "rows": rows}],
    )


async def _send_patient_selector_for_resolution(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str,
) -> None:
    """2+ linked patients: no default/candidate patient is auto-picked, so
    there's no single name for a "Continue as X?" card -- the list itself
    (welcome text folded straight into its body, MULTI_PATIENT_SELECTOR_
    PROMPT) is the only prompt, and tapping a row activates that patient
    directly via the same STATE_AWAITING_SINGLE_PATIENT_CONFIRM row-tap
    handling _handle_awaiting_single_patient_confirm already has (no
    candidate_patient_id in context here, so its CONFIRM_YES branch is simply
    never reached -- there's no Confirm button offered). A separate
    "Add Patient" follow-up button matches _send_single_patient_confirm's own,
    minus the "Confirm" option it has no candidate to confirm."""
    sessions.set(hospital_id, phone, STATE_AWAITING_SINGLE_PATIENT_CONFIRM, {}, language=language)
    patients = connector.list_active_patients(hospital_id, phone)
    rows = [{"id": _patient_row_id(p["id"]), "title": _patient_row_title(p)} for p in patients]
    rows.append({"id": MANAGE_PATIENTS_ENTRY_ID, "title": t(MANAGE_PATIENTS_SHORT, language)})
    rows = cap_rows(rows, "patient selector")
    await wa.send_list(
        to=phone,
        body_text=t(MULTI_PATIENT_SELECTOR_PROMPT, language),
        button_text=t(PATIENT_SELECTOR_BUTTON, language),
        sections=[{"title": t(PATIENT_SELECTOR_SECTION_TITLE, language), "rows": rows}],
    )
    await wa.send_buttons(
        to=phone,
        body_text="​",
        buttons=[{"id": ADD_PATIENT_ENTRY_ID, "title": t(ADD_PATIENT_SHORT, language)}],
    )


async def _handle_awaiting_single_patient_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Handles taps from either message sent by _send_single_patient_confirm:
    the 2 buttons (Confirm/Add Patient) or a row from the patient list
    (a linked patient, or Manage Patients). Re-fetches and re-shows fresh on
    an unrecognized/stale tap (the patient list may have changed since)."""
    if reply["type"] == "interactive_reply":
        if reply["id"] == CONFIRM_YES:
            sessions.set(
                hospital_id, phone, "IDLE", {"just_confirmed_patient": True}, language=language,
                active_patient_id=context["candidate_patient_id"],
            )
            return
        if reply["id"] == ADD_PATIENT_ENTRY_ID:
            await _start_registration(wa, sessions, phone, hospital_id, connector, language)
            return
        if reply["id"] == MANAGE_PATIENTS_ENTRY_ID:
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
        patient_id = _parse_patient_row_id(reply["id"])
        if patient_id is not None:
            patients = connector.list_active_patients(hospital_id, phone)
            if any(p["id"] == patient_id for p in patients):
                sessions.set(
                    hospital_id, phone, "IDLE", {"just_confirmed_patient": True}, language=language,
                    active_patient_id=patient_id,
                )
                return
    patients = connector.list_active_patients(hospital_id, phone)
    if len(patients) == 1:
        await _send_single_patient_confirm(wa, sessions, phone, hospital_id, connector, patients[0], language)
    elif len(patients) > 1:
        await _send_patient_selector_for_resolution(wa, sessions, phone, hospital_id, connector, language)
    else:
        sessions.clear_active_patient(hospital_id, phone)
        sessions.reset(hospital_id, phone)


# --- Manage Patients: view / add / unlink, plus the per-patient action
# choice (Use This Patient / Unlink / Back) -- distinct from the plain
# Patient List above, which never shows that extra choice screen. ---

async def _start_manage_patients(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    """Sends the Manage Patients list: every linked patient, an "Add
    Patient" row if under the cap, and "Back to Menu"."""
    patients = connector.list_active_patients(hospital_id, phone)
    rows = [{"id": _patient_row_id(p["id"]), "title": _patient_row_title(p)} for p in patients]
    if len(patients) < connector.get_max_active_patient_links():
        rows.append({"id": MANAGE_ADD_ROW_ID, "title": t(ADD_PATIENT_OPTION, language)})
    rows.append({"id": GOTO_MAIN_MENU, "title": t(BACK_TO_MENU_OPTION, language)})
    rows = cap_rows(rows, "manage patients list")
    sessions.set(hospital_id, phone, STATE_AWAITING_MANAGE_PATIENTS_ACTION, {}, language=language)
    await wa.send_list(
        to=phone,
        body_text=t(MANAGE_PATIENTS_HEADER, language),
        button_text=t(MANAGE_PATIENTS_BUTTON, language),
        sections=[{"title": t(MANAGE_PATIENTS_SECTION_TITLE, language), "rows": rows}],
    )


async def _handle_awaiting_manage_patients_action(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Starts "Add Patient" registration (blocked with a message if already
    at the cap), or opens the per-patient action choice for a tapped row."""
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == MANAGE_ADD_ROW_ID:
            patients = connector.list_active_patients(hospital_id, phone)
            if len(patients) >= connector.get_max_active_patient_links():
                await wa.send_text(phone, t(TOO_MANY_LINKED_PATIENTS, language))
                await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
                return
            await _start_registration(wa, sessions, phone, hospital_id, connector, language, identity_flow_next="manage_patients")
            return
        patient_id = _parse_patient_row_id(rid)
        if patient_id is not None:
            patients = connector.list_active_patients(hospital_id, phone)
            match = next((p for p in patients if p["id"] == patient_id), None)
            if match:
                await _send_patient_action_choice(wa, sessions, phone, hospital_id, patient_id, match["name"], language)
                return
    await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)


async def _send_patient_action_choice(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, patient_id: int, patient_name: str, language: str,
) -> None:
    """Sends the Use This Patient / Unlink / Back choice for one patient
    tapped from the Manage Patients list."""
    sessions.set(
        hospital_id, phone, STATE_AWAITING_PATIENT_ACTION_CHOICE,
        {"chosen_patient_id": patient_id, "chosen_patient_name": patient_name}, language=language,
    )
    await wa.send_buttons(
        to=phone,
        body_text=t(PATIENT_ACTION_PROMPT, language, patient_name=patient_name),
        buttons=[
            {"id": PATIENT_ACTION_USE_ID, "title": t(USE_THIS_PATIENT_OPTION, language)},
            {"id": PATIENT_ACTION_UNLINK_ID, "title": t(UNLINK_OPTION, language)},
            {"id": PATIENT_ACTION_BACK_ID, "title": t(BACK_OPTION, language)},
        ],
    )


async def _handle_awaiting_patient_action_choice(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Switches to the chosen patient, asks to confirm unlinking them, or
    goes back to the Manage Patients list."""
    patient_id = context.get("chosen_patient_id")
    patient_name = context.get("chosen_patient_name", "")
    if reply["type"] == "interactive_reply" and patient_id is not None:
        if reply["id"] == PATIENT_ACTION_USE_ID:
            # Switching to an already-linked patient needs no confirmation
            # (unlike unlinking, it's trivially reversible). just_confirmed_
            # patient prevents router.py's same-turn IDLE re-entry from
            # immediately re-showing a single-patient-confirm screen (see
            # get_or_prompt_for_active_patient's own docstring).
            sessions.set(
                hospital_id, phone, "IDLE", {"just_confirmed_patient": True}, language=language,
                active_patient_id=patient_id,
            )
            return
        if reply["id"] == PATIENT_ACTION_UNLINK_ID:
            sessions.set(
                hospital_id, phone, STATE_AWAITING_UNLINK_CONFIRM,
                {"unlink_patient_id": patient_id, "unlink_patient_name": patient_name}, language=language,
            )
            await wa.send_buttons(
                to=phone,
                body_text=t(UNLINK_PATIENT_CONFIRM, language, patient_name=patient_name),
                buttons=[
                    {"id": CONFIRM_YES, "title": t(CONFIRM_BUTTON, language)},
                    {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
                ],
            )
            return
        if reply["id"] == PATIENT_ACTION_BACK_ID:
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
    if patient_id is not None:
        await _send_patient_action_choice(wa, sessions, phone, hospital_id, patient_id, patient_name, language)
        return
    await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)


async def _handle_awaiting_unlink_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Soft-unlinks the patient on confirmation (never touches `patients` or
    appointment history), or cancels back to the Manage Patients list."""
    patient_id = context.get("unlink_patient_id")
    patient_name = context.get("unlink_patient_name", "")
    if reply["type"] == "interactive_reply" and patient_id is not None:
        if reply["id"] == CONFIRM_YES:
            connector.unlink_patient(hospital_id, phone, patient_id)
            session = sessions.get(hospital_id, phone)
            if session.get("active_patient_id") == patient_id:
                # Unlinked the currently-active patient -- force
                # re-resolution rather than keep using a stale reference.
                sessions.clear_active_patient(hospital_id, phone)
            await wa.send_text(phone, t(PATIENT_UNLINKED, language, patient_name=patient_name))
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
        if reply["id"] == CONFIRM_NO:
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_UNLINK_CONFIRM, context, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t(UNLINK_PATIENT_CONFIRM, language, patient_name=patient_name),
        buttons=[
            {"id": CONFIRM_YES, "title": t(CONFIRM_BUTTON, language)},
            {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
        ],
    )


# --- Consent & Privacy menu item ---

async def start_consent_privacy(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector,
    active_patient_id: int, privacy_notice_text: str | None = None, language: str = "en",
) -> None:
    """Shows the active patient's consent status and a marketing-consent
    toggle. Service consent has no separate toggle here -- withdrawing it
    maps to Manage Patients' unlink instead."""
    consent = connector.get_patient_link_consent(hospital_id, phone, active_patient_id)
    if consent is None:
        # Stale active_patient_id (shouldn't normally happen -- resolution
        # already validates it) -- fall back to a safe re-resolution.
        sessions.clear_active_patient(hospital_id, phone)
        sessions.reset(hospital_id, phone)
        return
    notice = privacy_notice_text or t(PRIVACY_NOTICE_DEFAULT, language)
    marketing_status = t(CONSENT_ON, language) if consent["marketing_consent"] else t(CONSENT_OFF, language)
    body = t(CONSENT_PRIVACY_BODY, language, notice=notice,
        marketing_status=marketing_status,
    )
    sessions.set(hospital_id, phone, STATE_AWAITING_CONSENT_ACTION, {}, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=body,
        buttons=[
            {
                "id": CONSENT_TOGGLE_MARKETING_ID,
                "title": t(CONSENT_MARKETING_DISABLE, language) if consent["marketing_consent"] else t(CONSENT_MARKETING_ENABLE, language),
            },
            {"id": GOTO_MAIN_MENU, "title": t(BACK_TO_MENU_OPTION, language)},
        ],
    )


async def handle_awaiting_consent_action(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict,
    connector: Connector, active_patient_id: int, privacy_notice_text: str | None = None, language: str = "en",
) -> None:
    """Toggles marketing consent if that button was tapped, then re-shows
    the consent screen either way."""
    if reply["type"] == "interactive_reply" and reply["id"] == CONSENT_TOGGLE_MARKETING_ID:
        consent = connector.get_patient_link_consent(hospital_id, phone, active_patient_id)
        if consent is not None:
            connector.set_marketing_consent(hospital_id, phone, active_patient_id, not consent["marketing_consent"])
    await start_consent_privacy(
        wa, sessions, phone, hospital_id, connector, active_patient_id,
        privacy_notice_text=privacy_notice_text, language=language,
    )


# Handlers taking the "standard" 8-arg shape flows.py's generic dispatch
# uses -- consent's two functions above need extra args, so flows.py calls
# them directly instead (see its own STATE_AWAITING_CONSENT_ACTION branch).
_HANDLERS = {
    STATE_AWAITING_BOOKING_FOR: _handle_awaiting_booking_for,
    STATE_AWAITING_PATIENT_NAME: _handle_awaiting_patient_name,
    STATE_AWAITING_PATIENT_CONTACT_PHONE: _handle_awaiting_patient_contact_number,
    STATE_AWAITING_PATIENT_AGE: _handle_awaiting_patient_age,
    STATE_AWAITING_PATIENT_GENDER: _handle_awaiting_patient_gender,
    STATE_AWAITING_DUPLICATE_DECISION: _handle_awaiting_duplicate_decision,
    STATE_AWAITING_SINGLE_PATIENT_CONFIRM: _handle_awaiting_single_patient_confirm,
    STATE_AWAITING_MANAGE_PATIENTS_ACTION: _handle_awaiting_manage_patients_action,
    STATE_AWAITING_PATIENT_ACTION_CHOICE: _handle_awaiting_patient_action_choice,
    STATE_AWAITING_UNLINK_CONFIRM: _handle_awaiting_unlink_confirm,
}

# core/translations/patient_identity.py
"""Patient identity SEPARATION (Spec.md Section 0): the shared "who is this
for" selector, duplicate-patient detection, the structured relationship
field, and the single-linked-patient confirmation. Split out from
manage_patients.py (adjacent file) since that one is specifically the
view/add/unlink screen -- this one is identity RESOLUTION, used ahead of
booking/cancel/reschedule/view_appointments."""
from core.translations._common import Language


PATIENT_SELECTOR_PROMPT_BOOKING = "patient_selector_prompt_booking"
PATIENT_SELECTOR_PROMPT_CANCEL = "patient_selector_prompt_cancel"
PATIENT_SELECTOR_PROMPT_RESCHEDULE = "patient_selector_prompt_reschedule"
PATIENT_SELECTOR_PROMPT_VIEW_APPOINTMENTS = "patient_selector_prompt_view_appointments"
PATIENT_SELECTOR_BUTTON = "patient_selector_button"
PATIENT_SELECTOR_SECTION_TITLE = "patient_selector_section_title"
ADD_PATIENT_OPTION = "add_patient_option"
ALL_PATIENTS_OPTION = "all_patients_option"
TOO_MANY_LINKED_PATIENTS = "too_many_linked_patients"
PATIENT_HEADER_LABEL = "patient_header_label"
PATIENT_SELECTOR_PROMPT = "patient_selector_prompt"
MANAGE_PATIENTS_SHORT = "manage_patients_short"
ADD_PATIENT_SHORT = "add_patient_short"
BACK_TO_MENU_OPTION = "back_to_menu_option"
REGISTRATION_BLOCKED_CONTACT_HOSPITAL = "registration_blocked_contact_hospital"
PATIENT_CONTEXT_INVALID = "patient_context_invalid"
DUPLICATE_PATIENT_FOUND = "duplicate_patient_found"
DUPLICATE_LINK_BUTTON = "duplicate_link_button"
DUPLICATE_DIFFERENT_BUTTON = "duplicate_different_button"
ASK_RELATIONSHIP = "ask_relationship"
ASK_RELATIONSHIP_BUTTON = "ask_relationship_button"
ASK_RELATIONSHIP_SECTION_TITLE = "ask_relationship_section_title"
RELATIONSHIP_SELF = "relationship_self"
RELATIONSHIP_MOTHER = "relationship_mother"
RELATIONSHIP_FATHER = "relationship_father"
RELATIONSHIP_SON = "relationship_son"
RELATIONSHIP_DAUGHTER = "relationship_daughter"
RELATIONSHIP_SPOUSE = "relationship_spouse"
RELATIONSHIP_GUARDIAN = "relationship_guardian"
RELATIONSHIP_OTHER = "relationship_other"
SINGLE_PATIENT_CONFIRM = "single_patient_confirm"

STRINGS: dict[str, dict[Language, str]] = {
    # The shared "who is this for" selector, shown whenever a phone has >1
    # active linked patient, ahead of booking/cancel/reschedule/
    # view_appointments. One prompt per next_action -- the body text differs
    # slightly by what's about to happen, but the list itself (rows + button
    # + section title) is otherwise identical across all four.
    PATIENT_SELECTOR_PROMPT_BOOKING: {
        "en": "Who is this appointment for?",
        "hi": "यह अपॉइंटमेंट किसके लिए है?",
    },
    PATIENT_SELECTOR_PROMPT_CANCEL: {
        "en": "Whose appointment would you like to cancel?",
        "hi": "आप किसकी अपॉइंटमेंट रद्द करना चाहते हैं?",
    },
    PATIENT_SELECTOR_PROMPT_RESCHEDULE: {
        "en": "Whose appointment would you like to reschedule?",
        "hi": "आप किसकी अपॉइंटमेंट का समय बदलना चाहते हैं?",
    },
    PATIENT_SELECTOR_PROMPT_VIEW_APPOINTMENTS: {
        "en": "Whose appointments would you like to see?",
        "hi": "आप किसकी अपॉइंटमेंट देखना चाहते हैं?",
    },
    PATIENT_SELECTOR_BUTTON: {"en": "Select Patient", "hi": "मरीज़ चुनें"},
    PATIENT_SELECTOR_SECTION_TITLE: {"en": "Patients", "hi": "मरीज़"},
    ADD_PATIENT_OPTION: {"en": "+ Add Patient", "hi": "+ मरीज़ जोड़ें"},
    ALL_PATIENTS_OPTION: {"en": "All Patients", "hi": "सभी मरीज़"},
    TOO_MANY_LINKED_PATIENTS: {
        "en": "This phone number already has 5 linked patients — the maximum allowed. "
              "Unlink someone first if you'd like to add another.",
        "hi": "इस फोन नंबर पर पहले से ही 5 मरीज़ जुड़े हुए हैं — यह अधिकतम सीमा है। "
              "किसी और को जोड़ने के लिए पहले किसी एक को अनलिंक करें।",
    },

    # CareConnect architecture doc alignment (Spec.md Section 0): resolution
    # now happens ONCE per conversation, before the main menu --
    # patient_selector_prompt below replaces the 4 action-specific
    # patient_selector_prompt_* keys above (still left in place, unreachable
    # but harmless, same "orphaned key" precedent CHANGE_LANGUAGE_ROW's own
    # comment already established).
    PATIENT_HEADER_LABEL: {"en": "Patient:", "hi": "मरीज़:"},
    PATIENT_SELECTOR_PROMPT: {
        "en": "Who are you accessing CareConnect for?",
        "hi": "आप CareConnect किसके लिए इस्तेमाल कर रहे हैं?",
    },
    MANAGE_PATIENTS_SHORT: {"en": "Manage Patients", "hi": "मरीज़ प्रबंधित करें"},
    ADD_PATIENT_SHORT: {"en": "Add Patient", "hi": "मरीज़ जोड़ें"},
    BACK_TO_MENU_OPTION: {"en": "Back to Menu", "hi": "मेनू पर वापस"},
    REGISTRATION_BLOCKED_CONTACT_HOSPITAL: {
        "en": "This phone number already has the maximum number of linked patients. Please contact the hospital directly.",
        "hi": "इस फोन नंबर पर पहले से ही अधिकतम मरीज़ जुड़े हुए हैं। कृपया सीधे अस्पताल से संपर्क करें।",
    },
    PATIENT_CONTEXT_INVALID: {
        "en": "This patient is no longer linked to this number. Please send any message to start over.",
        "hi": "यह मरीज़ अब इस नंबर से जुड़ा नहीं है। कृपया फिर से शुरू करने के लिए कोई भी संदेश भेजें।",
    },

    # --- Sections 8-10: duplicate-patient detection before creating a new profile ---
    DUPLICATE_PATIENT_FOUND: {
        "en": "We found an existing hospital profile that may match:\n\n*{name}*\nMRN: {mrn}\n\n"
              "Would you like to link this profile, or is this a different patient?",
        "hi": "हमें एक मौजूदा अस्पताल प्रोफ़ाइल मिली जो मेल खा सकती है:\n\n*{name}*\nMRN: {mrn}\n\n"
              "क्या आप इस प्रोफ़ाइल को लिंक करना चाहेंगे, या यह एक अलग मरीज़ है?",
    },
    DUPLICATE_LINK_BUTTON: {"en": "Link Existing", "hi": "लिंक करें"},
    DUPLICATE_DIFFERENT_BUTTON: {"en": "Different Patient", "hi": "अलग मरीज़"},

    # --- Section 17: structured relationship field (RELATIONSHIP_OPTIONS in
    # db/repository.py is the single source of truth these keys mirror) ---
    ASK_RELATIONSHIP: {
        "en": "What is this patient's relationship to you?",
        "hi": "यह मरीज़ आपसे किस रिश्ते में है?",
    },
    ASK_RELATIONSHIP_BUTTON: {"en": "Select", "hi": "चुनें"},
    ASK_RELATIONSHIP_SECTION_TITLE: {"en": "Relationship", "hi": "रिश्ता"},
    RELATIONSHIP_SELF: {"en": "Self", "hi": "स्वयं"},
    RELATIONSHIP_MOTHER: {"en": "Mother", "hi": "माँ"},
    RELATIONSHIP_FATHER: {"en": "Father", "hi": "पिता"},
    RELATIONSHIP_SON: {"en": "Son", "hi": "बेटा"},
    RELATIONSHIP_DAUGHTER: {"en": "Daughter", "hi": "बेटी"},
    RELATIONSHIP_SPOUSE: {"en": "Spouse", "hi": "जीवनसाथी"},
    RELATIONSHIP_GUARDIAN: {"en": "Guardian", "hi": "अभिभावक"},
    RELATIONSHIP_OTHER: {"en": "Other", "hi": "अन्य"},

    # --- Section 11: optional single-linked-patient confirmation
    # (hospitals.require_patient_confirmation, default off) ---
    SINGLE_PATIENT_CONFIRM: {
        "en": "Welcome to CareConnect.\n\nYou are accessing services for:\n\n*{patient_name}*\nMRN: {mrn}\n\nContinue?",
        "hi": "CareConnect में आपका स्वागत है।\n\nआप इनके लिए सेवाएं प्राप्त कर रहे हैं:\n\n*{patient_name}*\nMRN: {mrn}\n\nजारी रखें?",
    },
}

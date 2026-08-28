# core/translations/patient_identity.py
"""Patient identity SEPARATION (Spec.md Section 0): the shared "who is this
for" selector, duplicate-patient detection, the structured relationship
field, and the single-linked-patient confirmation. Split out from
manage_patients.py (adjacent file) since that one is specifically the
view/add/unlink screen -- this one is identity RESOLUTION, used ahead of
booking/cancel/reschedule/view_appointments."""
from core.translations._common import Language

STRINGS: dict[str, dict[Language, str]] = {
    # The shared "who is this for" selector, shown whenever a phone has >1
    # active linked patient, ahead of booking/cancel/reschedule/
    # view_appointments. One prompt per next_action -- the body text differs
    # slightly by what's about to happen, but the list itself (rows + button
    # + section title) is otherwise identical across all four.
    "patient_selector_prompt_booking": {
        "en": "Who is this appointment for?",
        "hi": "यह अपॉइंटमेंट किसके लिए है?",
    },
    "patient_selector_prompt_cancel": {
        "en": "Whose appointment would you like to cancel?",
        "hi": "आप किसकी अपॉइंटमेंट रद्द करना चाहते हैं?",
    },
    "patient_selector_prompt_reschedule": {
        "en": "Whose appointment would you like to reschedule?",
        "hi": "आप किसकी अपॉइंटमेंट का समय बदलना चाहते हैं?",
    },
    "patient_selector_prompt_view_appointments": {
        "en": "Whose appointments would you like to see?",
        "hi": "आप किसकी अपॉइंटमेंट देखना चाहते हैं?",
    },
    "patient_selector_button": {"en": "Select Patient", "hi": "मरीज़ चुनें"},
    "patient_selector_section_title": {"en": "Patients", "hi": "मरीज़"},
    "add_patient_option": {"en": "+ Add Patient", "hi": "+ मरीज़ जोड़ें"},
    "all_patients_option": {"en": "All Patients", "hi": "सभी मरीज़"},
    "too_many_linked_patients": {
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
    "patient_header_label": {"en": "Patient:", "hi": "मरीज़:"},
    "patient_selector_prompt": {
        "en": "Who are you accessing CareConnect for?",
        "hi": "आप CareConnect किसके लिए इस्तेमाल कर रहे हैं?",
    },
    "manage_patients_short": {"en": "Manage Patients", "hi": "मरीज़ प्रबंधित करें"},
    "add_patient_short": {"en": "Add Patient", "hi": "मरीज़ जोड़ें"},
    "back_to_menu_option": {"en": "Back to Menu", "hi": "मेनू पर वापस"},
    "registration_blocked_contact_hospital": {
        "en": "This phone number already has the maximum number of linked patients. Please contact the hospital directly.",
        "hi": "इस फोन नंबर पर पहले से ही अधिकतम मरीज़ जुड़े हुए हैं। कृपया सीधे अस्पताल से संपर्क करें।",
    },
    "patient_context_invalid": {
        "en": "This patient is no longer linked to this number. Please send any message to start over.",
        "hi": "यह मरीज़ अब इस नंबर से जुड़ा नहीं है। कृपया फिर से शुरू करने के लिए कोई भी संदेश भेजें।",
    },

    # --- Sections 8-10: duplicate-patient detection before creating a new profile ---
    "duplicate_patient_found": {
        "en": "We found an existing hospital profile that may match:\n\n*{name}*\nMRN: {mrn}\n\n"
              "Would you like to link this profile, or is this a different patient?",
        "hi": "हमें एक मौजूदा अस्पताल प्रोफ़ाइल मिली जो मेल खा सकती है:\n\n*{name}*\nMRN: {mrn}\n\n"
              "क्या आप इस प्रोफ़ाइल को लिंक करना चाहेंगे, या यह एक अलग मरीज़ है?",
    },
    "duplicate_link_button": {"en": "Link Existing", "hi": "लिंक करें"},
    "duplicate_different_button": {"en": "Different Patient", "hi": "अलग मरीज़"},

    # --- Section 17: structured relationship field (RELATIONSHIP_OPTIONS in
    # db/repository.py is the single source of truth these keys mirror) ---
    "ask_relationship": {
        "en": "What is this patient's relationship to you?",
        "hi": "यह मरीज़ आपसे किस रिश्ते में है?",
    },
    "ask_relationship_button": {"en": "Select", "hi": "चुनें"},
    "ask_relationship_section_title": {"en": "Relationship", "hi": "रिश्ता"},
    "relationship_self": {"en": "Self", "hi": "स्वयं"},
    "relationship_mother": {"en": "Mother", "hi": "माँ"},
    "relationship_father": {"en": "Father", "hi": "पिता"},
    "relationship_son": {"en": "Son", "hi": "बेटा"},
    "relationship_daughter": {"en": "Daughter", "hi": "बेटी"},
    "relationship_spouse": {"en": "Spouse", "hi": "जीवनसाथी"},
    "relationship_guardian": {"en": "Guardian", "hi": "अभिभावक"},
    "relationship_other": {"en": "Other", "hi": "अन्य"},

    # --- Section 11: optional single-linked-patient confirmation
    # (hospitals.require_patient_confirmation, default off) ---
    "single_patient_confirm": {
        "en": "Welcome to CareConnect.\n\nYou are accessing services for:\n\n*{patient_name}*\nMRN: {mrn}\n\nContinue?",
        "hi": "CareConnect में आपका स्वागत है।\n\nआप इनके लिए सेवाएं प्राप्त कर रहे हैं:\n\n*{patient_name}*\nMRN: {mrn}\n\nजारी रखें?",
    },
}

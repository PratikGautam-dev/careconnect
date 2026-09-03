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
# messages.py's _send_patient_selector builds its lookup key dynamically as
# f"patient_selector_prompt_{next_action}" -- view_appointments.py passes
# "view_appointments_previous"/"view_appointments_upcoming" as next_action
# (not the bare "view_appointments" above) so the Previous/Upcoming range
# choice survives through the multi-patient selector. Two keys, not a
# constant, since nothing else needs to import these by name.
PATIENT_SELECTOR_PROMPT_VIEW_APPOINTMENTS_PREVIOUS = "patient_selector_prompt_view_appointments_previous"
PATIENT_SELECTOR_PROMPT_VIEW_APPOINTMENTS_UPCOMING = "patient_selector_prompt_view_appointments_upcoming"
PATIENT_SELECTOR_BUTTON = "patient_selector_button"
PATIENT_SELECTOR_SECTION_TITLE = "patient_selector_section_title"
ADD_PATIENT_OPTION = "add_patient_option"
ALL_PATIENTS_OPTION = "all_patients_option"
TOO_MANY_LINKED_PATIENTS = "too_many_linked_patients"
DUPLICATE_SELF_LINK = "duplicate_self_link"
PATIENT_ALREADY_LINKED = "patient_already_linked"
PATIENT_HEADER_LABEL = "patient_header_label"
PATIENT_CODE_LABEL = "patient_code_label"
PATIENT_SELECTOR_PROMPT = "patient_selector_prompt"
MANAGE_PATIENTS_SHORT = "manage_patients_short"
ADD_PATIENT_SHORT = "add_patient_short"
BACK_TO_MENU_OPTION = "back_to_menu_option"
REGISTRATION_BLOCKED_CONTACT_HOSPITAL = "registration_blocked_contact_hospital"
PATIENT_CONTEXT_INVALID = "patient_context_invalid"
DUPLICATE_PATIENT_FOUND = "duplicate_patient_found"
DUPLICATE_LINK_BUTTON = "duplicate_link_button"
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
PLEASE_ADD_NEW_PATIENT = "please_add_new_patient"
MULTI_PATIENT_SELECTOR_PROMPT = "multi_patient_selector_prompt"
PATIENT_SELECTED_BANNER = "patient_selected_banner"

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
    PATIENT_SELECTOR_PROMPT_VIEW_APPOINTMENTS_PREVIOUS: {
        "en": "Whose previous appointments would you like to see?",
        "hi": "आप किसकी पिछली अपॉइंटमेंट देखना चाहते हैं?",
    },
    PATIENT_SELECTOR_PROMPT_VIEW_APPOINTMENTS_UPCOMING: {
        "en": "Whose upcoming appointments would you like to see?",
        "hi": "आप किसकी आगामी अपॉइंटमेंट देखना चाहते हैं?",
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
    # "Myself / Someone Else" registration step: the hard, race-safe
    # backstop (db.DuplicateSelfLinkError) firing in practice -- the chat
    # flow's own soft pre-check (has_self_linked_patient) means a user
    # should essentially never see this outside a genuine two-taps-at-once
    # race.
    DUPLICATE_SELF_LINK: {
        "en": "You already have a \"Myself\" profile linked at this hospital. Please try again to add someone else.",
        "hi": "इस अस्पताल में आपकी \"मैं खुद\" प्रोफ़ाइल पहले से ही जुड़ी हुई है। कृपया किसी और को जोड़ने के लिए फिर से प्रयास करें।",
    },
    # find_potential_duplicate_patient() matched an existing patient that's
    # ALREADY actively linked to this same phone -- re-adding them (same
    # name+contact) would either violate patient_links' own uniqueness
    # constraint (Link Existing) or silently create a genuine duplicate
    # `patients` row (Different Patient), so neither choice is offered here.
    PATIENT_ALREADY_LINKED: {
        "en": "{name} is already in your patient list at this hospital -- no need to add them again.",
        "hi": "{name} इस अस्पताल में आपकी मरीज़ सूची में पहले से मौजूद हैं -- उन्हें दोबारा जोड़ने की ज़रूरत नहीं है।",
    },

    # CareConnect architecture doc alignment (Spec.md Section 0): resolution
    # now happens ONCE per conversation, before the main menu --
    # patient_selector_prompt below replaces the 4 action-specific
    # patient_selector_prompt_* keys above (still left in place, unreachable
    # but harmless, same "orphaned key" precedent CHANGE_LANGUAGE_ROW's own
    # comment already established).
    PATIENT_HEADER_LABEL: {"en": "Patient:", "hi": "मरीज़:"},
    # patient_display_id (e.g. DCCP-2026-00003) shown to the patient -- NEVER
    # the real clinical mrn (db/models.py's _generate_patient_identifiers,
    # MRN-<hospital short code>-<seq>), which is an internal hospital record
    # never surfaced over WhatsApp. "mrn" was previously used as both the
    # label text AND the kwarg name at every call site below even though the
    # value passed was always patient_display_id -- renamed throughout to
    # avoid that confusion.
    PATIENT_CODE_LABEL: {"en": "Patient ID:", "hi": "पेशेंट आईडी:"},
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
    # Matching is a strict 4-field match (name+contact+age+gender, confirmed
    # with the user) -- essentially certain to be the same real person, so
    # the body no longer offers a "different patient" framing.
    DUPLICATE_PATIENT_FOUND: {
        "en": "We found an existing hospital profile that may match:\n\n*{name}*\nPatient ID: {patient_code}\n\n"
              "Would you like to link this profile?",
        "hi": "हमें एक मौजूदा अस्पताल प्रोफ़ाइल मिली जो मेल खा सकती है:\n\n*{name}*\nपेशेंट आईडी: {patient_code}\n\n"
              "क्या आप इस प्रोफ़ाइल को लिंक करना चाहेंगे?",
    },
    DUPLICATE_LINK_BUTTON: {"en": "Link Existing", "hi": "लिंक करें"},

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
    # Used as the main menu LIST's own body text for this specific case
    # (overriding _send_menu_list's generic patient-header + "How can we
    # assist you today?" body) -- the patient is already active by the time
    # this is shown, so the list itself both names them and offers the menu.
    SINGLE_PATIENT_CONFIRM: {
        "en": "🏥 Welcome to CareConnect\n\nCurrent Patient: {patient_name}\nPatient ID: {patient_code}\n\nHow can we assist you today?",
        "hi": "🏥 CareConnect में आपका स्वागत है\n\nवर्तमान मरीज़: {patient_name}\nपेशेंट आईडी: {patient_code}\n\nहम आज आपकी कैसे सहायता कर सकते हैं?",
    },
    # Sent as a separate follow-up buttons message right under that list --
    # an offer to switch patient, not a gate blocking the menu.
    PLEASE_ADD_NEW_PATIENT: {
        "en": "Please add new patient",
        "hi": "कृपया नया मरीज़ जोड़ें",
    },

    # 2+ linked patients: no default candidate is picked (unlike
    # single_patient_confirm above), so the welcome text is folded directly
    # into the list prompt itself instead of a separate "Continue as X?" card.
    MULTI_PATIENT_SELECTOR_PROMPT: {
        "en": "Welcome to CareConnect.\n\nPlease select the patient.",
        "hi": "CareConnect में आपका स्वागत है।\n\nकृपया मरीज़ का चयन करें।",
    },

    # Prepended onto the main menu list's own body (flows/router.py's
    # _enter_idle, via _send_dynamic_menu's body_text_prefix) right after a
    # row is tapped in the 2+ linked-patient list -- confirms which patient
    # this conversation is now acting on, in the SAME message as the menu
    # itself (not a separate "Patient Selected" text before it). Not shown
    # for the exactly-one-patient case, which already has its own "Current
    # Patient" card (SINGLE_PATIENT_CONFIRM).
    PATIENT_SELECTED_BANNER: {
        "en": "✅ Patient Selected\n\n",
        "hi": "✅ मरीज़ चुना गया\n\n",
    },
}

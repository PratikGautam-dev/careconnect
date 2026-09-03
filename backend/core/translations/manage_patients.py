# core/translations/manage_patients.py
"""Manage Patients (Spec.md Section 0): add/remove the patients linked to
this phone. Redesigned (confirmed with the user) from a single "tap a
patient to act on them" list into a 2-button Remove Patient/Add Patient
entry point -- Remove Patient shows the patient list ONLY when removing;
there is no separate "switch active patient" action here anymore (that's
handled entirely by the patient-selector/resolution flow shown before the
main menu). Add reuses booking.py's ask_patient_name/ask_patient_age
(patient_flow_next="manage_patients"); remove reuses booking.py's
confirm_button/cancel_button as its Yes/No labels, same convention the
cancel/reschedule confirmation cards already use."""
from core.translations._common import Language


FEATURE_MANAGE_PATIENTS = "feature_manage_patients"
MANAGE_PATIENTS_PROMPT = "manage_patients_prompt"
REMOVE_PATIENT_OPTION = "remove_patient_option"
MANAGE_PATIENTS_HEADER = "manage_patients_header"
MANAGE_PATIENTS_BUTTON = "manage_patients_button"
MANAGE_PATIENTS_SECTION_TITLE = "manage_patients_section_title"
NO_PATIENTS_TO_REMOVE = "no_patients_to_remove"
PATIENT_ADDED = "patient_added"
UNLINK_PATIENT_CONFIRM = "unlink_patient_confirm"
PATIENT_UNLINKED = "patient_unlinked"
PATIENT_REMOVAL_CANCELLED = "patient_removal_cancelled"
UNLINK_SELF_BLOCKED = "unlink_self_blocked"
UNLINK_SELF_CONTACT_RECEPTION = "unlink_self_contact_reception"

STRINGS: dict[str, dict[Language, str]] = {
    FEATURE_MANAGE_PATIENTS: {"en": "Manage Patients", "hi": "मरीज़ प्रबंधित करें"},
    MANAGE_PATIENTS_PROMPT: {
        "en": "What would you like to do?",
        "hi": "आप क्या करना चाहेंगे?",
    },
    REMOVE_PATIENT_OPTION: {"en": "Remove Patient", "hi": "मरीज़ हटाएं"},
    MANAGE_PATIENTS_HEADER: {
        "en": "Select the patient you would like to remove:",
        "hi": "जिस मरीज़ को आप हटाना चाहते हैं उसे चुनें:",
    },
    MANAGE_PATIENTS_BUTTON: {"en": "Patients", "hi": "मरीज़"},
    MANAGE_PATIENTS_SECTION_TITLE: {"en": "Linked Patients", "hi": "जुड़े हुए मरीज़"},
    NO_PATIENTS_TO_REMOVE: {
        "en": "You have no patients to remove.",
        "hi": "आपके पास हटाने के लिए कोई मरीज़ नहीं है।",
    },
    PATIENT_ADDED: {
        "en": "{patient_name} has been added.",
        "hi": "{patient_name} को जोड़ दिया गया है।",
    },
    UNLINK_PATIENT_CONFIRM: {
        "en": "Are you sure you want to remove {patient_name}? Their appointment history and Patient ID are not "
              "affected — you can add them again anytime.",
        "hi": "क्या आप वाकई {patient_name} को हटाना चाहते हैं? उनका अपॉइंटमेंट इतिहास और पेशेंट आईडी प्रभावित नहीं "
              "होंगे — आप उन्हें कभी भी दोबारा जोड़ सकते हैं।",
    },
    PATIENT_UNLINKED: {
        # Previous body (kept for reference, not deleted):
        # "en": "{patient_name} has been removed from this number.",
        # "hi": "{patient_name} को इस नंबर से हटा दिया गया है।",
        "en": (
            "✅ {patient_name} has been removed from this WhatsApp number.\n\n"
            "Their Patient ID, medical records, and appointment history remain unchanged."
        ),
        "hi": (
            "✅ {patient_name} को इस व्हाट्सएप नंबर से हटा दिया गया है।\n\n"
            "उनकी पेशेंट आईडी, मेडिकल रिकॉर्ड और अपॉइंटमेंट इतिहास अपरिवर्तित रहेंगे।"
        ),
    },
    PATIENT_REMOVAL_CANCELLED: {
        "en": "No changes made — {patient_name} is still linked.",
        "hi": "कोई बदलाव नहीं किया गया — {patient_name} अभी भी जुड़ा हुआ है।",
    },
    # Confirmed with the user: the "Myself"/master patient can never be
    # self-unlinked -- two separate messages, not merged into one.
    UNLINK_SELF_BLOCKED: {
        "en": "{patient_name} is the main patient linked to this number and can't be removed here.",
        "hi": "{patient_name} इस नंबर से जुड़ा मुख्य मरीज़ है और इसे यहां से हटाया नहीं जा सकता।",
    },
    UNLINK_SELF_CONTACT_RECEPTION: {
        "en": "If you need help with this, please use \"Talk to Reception\" from the main menu — our team can assist you further.",
        "hi": "इसमें मदद के लिए, कृपया मुख्य मेनू से \"रिसेप्शन से बात करें\" का उपयोग करें — हमारी टीम आपकी आगे सहायता करेगी।",
    },
}

# core/translations/manage_patients.py
"""Manage Patients (Spec.md Section 0): view/add/unlink the patients linked
to this phone. Add reuses booking.py's ask_patient_name/ask_patient_age
(patient_flow_next="manage_patients"); unlink reuses booking.py's
confirm_button/cancel_button as its Yes/No labels, same convention the
cancel/reschedule confirmation cards already use."""
from core.translations._common import Language

STRINGS: dict[str, dict[Language, str]] = {
    "feature_manage_patients": {"en": "Manage Patients", "hi": "मरीज़ प्रबंधित करें"},
    "manage_patients_header": {
        "en": "Patients linked to this number. Tap one to unlink, or add another:",
        "hi": "इस नंबर से जुड़े मरीज़। अनलिंक करने के लिए एक पर टैप करें, या दूसरा जोड़ें:",
    },
    "manage_patients_button": {"en": "Patients", "hi": "मरीज़"},
    "manage_patients_section_title": {"en": "Linked Patients", "hi": "जुड़े हुए मरीज़"},
    "patient_added": {
        "en": "{patient_name} has been added.",
        "hi": "{patient_name} को जोड़ दिया गया है।",
    },
    # Tapping a patient row in Manage Patients (confirmed with the user):
    # asks which action, rather than jumping straight to unlink -- "Use This
    # Patient" switches the conversation to act as them.
    "patient_action_prompt": {
        "en": "What would you like to do with {patient_name}?",
        "hi": "{patient_name} के साथ आप क्या करना चाहेंगे?",
    },
    "use_this_patient_option": {"en": "Use This Patient", "hi": "इस मरीज़ का उपयोग करें"},
    "unlink_option": {"en": "Unlink", "hi": "अनलिंक करें"},
    "unlink_patient_confirm": {
        "en": "Unlink {patient_name} from this number? Their appointment history and Patient ID are not affected "
              "— you can add them again anytime.",
        "hi": "इस नंबर से {patient_name} को अनलिंक करें? उनका अपॉइंटमेंट इतिहास और पेशेंट आईडी प्रभावित नहीं होंगे "
              "— आप उन्हें कभी भी दोबारा जोड़ सकते हैं।",
    },
    "patient_unlinked": {
        "en": "{patient_name} has been unlinked from this number.",
        "hi": "{patient_name} को इस नंबर से अनलिंक कर दिया गया है।",
    },
}

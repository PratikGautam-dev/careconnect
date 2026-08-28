# core/translations/menu.py
"""Language picker, main/feature menu, and simple fixed-reply features
reachable directly from that menu (hospital info, reception handoff)."""
from core.translations._common import Language

STRINGS: dict[str, dict[Language, str]] = {
    # --- Language picker (shown before anything else, first contact / new session) ---
    "language_picker_body": {
        "en": "Please choose your language.\nकृपया अपनी भाषा चुनें।",
        "hi": "Please choose your language.\nकृपया अपनी भाषा चुनें।",
    },
    "language_picker_button_en": {"en": "English", "hi": "English"},
    "language_picker_button_hi": {"en": "हिन्दी", "hi": "हिन्दी"},

    # --- Main / feature menu ---
    # Section 12.12: two-line body (greeting + call-to-action) matching the
    # reference screenshot -- \n renders as a real line break in a WhatsApp
    # list/text message body.
    "welcome_menu": {
        "en": "Welcome to {hospital_name}! 🏥\nHow can we assist you today? Please select an option:",
        "hi": "{hospital_name} में आपका स्वागत है! 🏥\nआज हम आपकी कैसे सहायता कर सकते हैं? कृपया एक विकल्प चुनें:",
    },
    "main_menu_button": {"en": "Main Menu", "hi": "मुख्य मेनू"},
    "main_menu_section_title": {"en": "Main Menu", "hi": "मुख्य मेनू"},
    "feature_menu_unavailable": {
        "en": "Sorry, {hospital_name} hasn't finished setting up WhatsApp yet. Please check back later.",
        "hi": "क्षमा करें, {hospital_name} ने अभी तक व्हाट्सएप सेटअप पूरा नहीं किया है। कृपया बाद में फिर से देखें।",
    },

    # feature_menu labels (flows.py's _FEATURE_MENU row titles -- 24-char WhatsApp limit)
    "feature_booking": {"en": "Book Appointment", "hi": "अपॉइंटमेंट बुक करें"},
    "feature_reschedule": {"en": "Reschedule Appointment", "hi": "समय बदलें"},
    "feature_cancel": {"en": "Cancel Appointment", "hi": "अपॉइंटमेंट रद्द करें"},
    "feature_view_appointments": {"en": "My Appointments", "hi": "मेरी अपॉइंटमेंट"},
    "feature_hospital_info": {"en": "Hospital Information", "hi": "अस्पताल की जानकारी"},
    "feature_reception_handoff": {"en": "Talk to Reception", "hi": "रिसेप्शन से बात करें"},
    "feature_faq": {"en": "FAQ / Information", "hi": "सामान्य प्रश्न"},
    # CareConnect architecture doc alignment (Spec.md Section 0), Section 20's
    # exact menu list -- "reports_prescriptions" replaces "my_details" (same
    # underlying feature, renamed+rescoped -- see db/init_db.py's own
    # migration); "consent_privacy" is new.
    "feature_reports_prescriptions": {"en": "Reports & Prescriptions", "hi": "रिपोर्ट और पर्चे"},
    "feature_consent_privacy": {"en": "Consent & Privacy", "hi": "सहमति और गोपनीयता"},
    # Item 4 (Spec.md Section 0): not a hospital-toggleable enabled_features
    # entry like the rows above -- always appended to the main menu itself
    # (when the hospital hasn't disabled the language picker entirely), since
    # it's core session behavior, not a business capability a hospital opts
    # in/out of.
    "feature_change_language": {"en": "Change Language", "hi": "भाषा बदलें"},

    # booking_flow.py's OWN static 4-item menu (superseded for real traffic by
    # flows.py's dynamic one, but tests/test_booking_flow.py exercises it
    # directly as a standalone state-machine unit -- kept translated too so
    # that coverage stays meaningful, not just passing on hardcoded English).
    "book_appointment_short": {"en": "Book Appointment", "hi": "अपॉइंटमेंट बुक करें"},
    "reschedule_short": {"en": "Reschedule", "hi": "समय बदलें"},
    "cancel_short": {"en": "Cancel", "hi": "रद्द करें"},
    "faq_short": {"en": "FAQ", "hi": "सामान्य प्रश्न"},

    "view_appointments_list": {
        "en": "You don't have any upcoming appointments.",
        "hi": "आपकी कोई आगामी अपॉइंटमेंट नहीं है।",
    },
    "view_appointments_header": {
        "en": "Your upcoming appointments:\n\n",
        "hi": "आपकी आगामी अपॉइंटमेंट:\n\n",
    },
    "reception_handoff_text": {
        "en": "We've let our reception team know — they'll reach out to you here shortly. "
              "If you need anything else in the meantime, just type \"menu\".",
        "hi": "हमने अपनी रिसेप्शन टीम को सूचित कर दिया है — वे जल्द ही आपसे यहां संपर्क करेंगे। "
              "इस बीच अगर आपको कुछ और चाहिए, तो बस \"menu\" लिखें।",
    },

    # --- Hospital info (booking_flow.py's _FAQ_TEXT, reused by flows.py as
    # the fixed "hospital_info" feature reply) ---
    "hospital_info_text": {
        "en": "Frequently Asked Questions:\n\n"
              "- Hours: Mon-Sat, 9:00 AM - 6:00 PM\n"
              "- To book, reschedule or cancel an appointment, just send us any message.\n"
              "- For emergencies, please call the hospital directly instead of messaging here.\n\n"
              "Send any message to return to the main menu.",
        "hi": "अक्सर पूछे जाने वाले प्रश्न:\n\n"
              "- समय: सोम-शनि, सुबह 9:00 - शाम 6:00\n"
              "- अपॉइंटमेंट बुक करने, समय बदलने या रद्द करने के लिए, बस हमें कोई भी संदेश भेजें।\n"
              "- आपातकाल के लिए, कृपया यहां संदेश भेजने के बजाय सीधे अस्पताल को कॉल करें।\n\n"
              "मुख्य मेनू पर वापस जाने के लिए कोई भी संदेश भेजें।",
    },
}

# core/translations/menu.py
"""Language picker, main/feature menu, and simple fixed-reply features
reachable directly from that menu (hospital info, reception handoff).

Every key has a module-level constant below (e.g. WELCOME_MENU) -- call
sites should import and pass the constant to t()/translate(), not the raw
string. A renamed/typo'd string key fails silently as far as static tools
are concerned (STRINGS[key][lang] only raises KeyError once that code path
actually runs); a renamed/typo'd constant fails immediately as an
ImportError/NameError, and an IDE "rename symbol" updates every call site
for you."""
from core.translations._common import Language

# --- Language picker (shown before anything else, first contact / new session) ---
LANGUAGE_PICKER_BODY = "language_picker_body"
LANGUAGE_PICKER_BUTTON_EN = "language_picker_button_en"
LANGUAGE_PICKER_BUTTON_HI = "language_picker_button_hi"

# --- Main / feature menu ---
WELCOME_MENU = "welcome_menu"
MAIN_MENU_BUTTON = "main_menu_button"
MAIN_MENU_SECTION_TITLE = "main_menu_section_title"
FEATURE_MENU_UNAVAILABLE = "feature_menu_unavailable"

# feature_menu labels (flows.py's _FEATURE_MENU row titles -- 24-char WhatsApp limit)
FEATURE_BOOKING = "feature_booking"
FEATURE_RESCHEDULE = "feature_reschedule"
FEATURE_CANCEL = "feature_cancel"
FEATURE_VIEW_APPOINTMENTS = "feature_view_appointments"
FEATURE_HOSPITAL_INFO = "feature_hospital_info"
FEATURE_RECEPTION_HANDOFF = "feature_reception_handoff"
FEATURE_FAQ = "feature_faq"
FEATURE_REPORTS_PRESCRIPTIONS = "feature_reports_prescriptions"
FEATURE_CONSENT_PRIVACY = "feature_consent_privacy"
FEATURE_CHANGE_LANGUAGE = "feature_change_language"

# booking_flow.py's OWN static 4-item menu (superseded for real traffic by
# flows.py's dynamic one, but tests/test_booking_flow.py exercises it
# directly as a standalone state-machine unit -- kept translated too so
# that coverage stays meaningful, not just passing on hardcoded English).
BOOK_APPOINTMENT_SHORT = "book_appointment_short"
RESCHEDULE_SHORT = "reschedule_short"
CANCEL_SHORT = "cancel_short"
FAQ_SHORT = "faq_short"

VIEW_APPOINTMENTS_LIST = "view_appointments_list"
VIEW_APPOINTMENTS_HEADER = "view_appointments_header"

# "My Appointments" -> Previous/Upcoming 1 Month range choice, shown before
# the list itself. VIEW_APPOINTMENTS_HEADER/VIEW_APPOINTMENTS_LIST above stay
# the upcoming-range header/empty-state text (unchanged copy); these are the
# previous-range equivalents plus the range-choice prompt/buttons.
VIEW_APPOINTMENTS_RANGE_PROMPT = "view_appointments_range_prompt"
VIEW_APPOINTMENTS_RANGE_PREVIOUS_BUTTON = "view_appointments_range_previous_button"
VIEW_APPOINTMENTS_RANGE_UPCOMING_BUTTON = "view_appointments_range_upcoming_button"
VIEW_APPOINTMENTS_HEADER_PREVIOUS = "view_appointments_header_previous"
VIEW_APPOINTMENTS_LIST_PREVIOUS = "view_appointments_list_previous"

RECEPTION_HANDOFF_TEXT = "reception_handoff_text"

# --- Hospital info (booking_flow.py's _FAQ_TEXT, reused by flows.py as
# the fixed "hospital_info" feature reply) ---
HOSPITAL_INFO_TEXT = "hospital_info_text"

STRINGS: dict[str, dict[Language, str]] = {
    LANGUAGE_PICKER_BODY: {
        "en": "Please choose your language.\nकृपया अपनी भाषा चुनें।",
        "hi": "Please choose your language.\nकृपया अपनी भाषा चुनें।",
    },
    LANGUAGE_PICKER_BUTTON_EN: {"en": "English", "hi": "English"},
    LANGUAGE_PICKER_BUTTON_HI: {"en": "हिन्दी", "hi": "हिन्दी"},

    # Section 12.12: two-line body (greeting + call-to-action) matching the
    # reference screenshot -- \n renders as a real line break in a WhatsApp
    # list/text message body.
    WELCOME_MENU: {
        "en": "How can we assist you today?\nPlease select an option:",
        "hi": "आज हम आपकी कैसे सहायता कर सकते हैं?\nकृपया एक विकल्प चुनें:",
    },
    MAIN_MENU_BUTTON: {"en": "Main Menu", "hi": "मुख्य मेनू"},
    MAIN_MENU_SECTION_TITLE: {"en": "Main Menu", "hi": "मुख्य मेनू"},
    FEATURE_MENU_UNAVAILABLE: {
        "en": "Sorry, {hospital_name} hasn't finished setting up WhatsApp yet. Please check back later.",
        "hi": "क्षमा करें, {hospital_name} ने अभी तक व्हाट्सएप सेटअप पूरा नहीं किया है। कृपया बाद में फिर से देखें।",
    },

    FEATURE_BOOKING: {"en": "Book Appointment", "hi": "अपॉइंटमेंट बुक करें"},
    FEATURE_RESCHEDULE: {"en": "Reschedule Appointment", "hi": "समय बदलें"},
    FEATURE_CANCEL: {"en": "Cancel Appointment", "hi": "अपॉइंटमेंट रद्द करें"},
    FEATURE_VIEW_APPOINTMENTS: {"en": "My Appointments", "hi": "मेरी अपॉइंटमेंट"},
    FEATURE_HOSPITAL_INFO: {"en": "Hospital Information", "hi": "अस्पताल की जानकारी"},
    FEATURE_RECEPTION_HANDOFF: {"en": "Talk to Reception", "hi": "रिसेप्शन से बात करें"},
    FEATURE_FAQ: {"en": "FAQ / Information", "hi": "सामान्य प्रश्न"},
    # CareConnect architecture doc alignment (Spec.md Section 0), Section 20's
    # exact menu list -- "reports_prescriptions" replaces "my_details" (same
    # underlying feature, renamed+rescoped -- see db/init_db.py's own
    # migration); "consent_privacy" is new.
    FEATURE_REPORTS_PRESCRIPTIONS: {"en": "Reports & Prescriptions", "hi": "रिपोर्ट और पर्चे"},
    FEATURE_CONSENT_PRIVACY: {"en": "Consent & Privacy", "hi": "सहमति और गोपनीयता"},
    # Item 4 (Spec.md Section 0): not a hospital-toggleable enabled_features
    # entry like the rows above -- always appended to the main menu itself
    # (when the hospital hasn't disabled the language picker entirely), since
    # it's core session behavior, not a business capability a hospital opts
    # in/out of.
    FEATURE_CHANGE_LANGUAGE: {"en": "Change Language", "hi": "भाषा बदलें"},

    BOOK_APPOINTMENT_SHORT: {"en": "Book Appointment", "hi": "अपॉइंटमेंट बुक करें"},
    RESCHEDULE_SHORT: {"en": "Reschedule", "hi": "समय बदलें"},
    CANCEL_SHORT: {"en": "Cancel", "hi": "रद्द करें"},
    FAQ_SHORT: {"en": "FAQ", "hi": "सामान्य प्रश्न"},

    VIEW_APPOINTMENTS_LIST: {
        "en": "You don't have any upcoming appointments.",
        "hi": "आपकी कोई आगामी अपॉइंटमेंट नहीं है।",
    },
    VIEW_APPOINTMENTS_HEADER: {
        "en": "Your upcoming appointments:\n\n",
        "hi": "आपकी आगामी अपॉइंटमेंट:\n\n",
    },
    VIEW_APPOINTMENTS_RANGE_PROMPT: {
        "en": "Which appointments would you like to see?",
        "hi": "आप कौन सी अपॉइंटमेंट देखना चाहते हैं?",
    },
    VIEW_APPOINTMENTS_RANGE_PREVIOUS_BUTTON: {"en": "Previous 1 Month", "hi": "पिछला 1 महीना"},
    VIEW_APPOINTMENTS_RANGE_UPCOMING_BUTTON: {"en": "Upcoming 1 Month", "hi": "आगामी 1 महीना"},
    VIEW_APPOINTMENTS_HEADER_PREVIOUS: {
        "en": "Your appointments from the last month:\n\n",
        "hi": "पिछले एक महीने की आपकी अपॉइंटमेंट:\n\n",
    },
    VIEW_APPOINTMENTS_LIST_PREVIOUS: {
        "en": "You don't have any appointments from the last month.",
        "hi": "पिछले एक महीने में आपकी कोई अपॉइंटमेंट नहीं है।",
    },
    RECEPTION_HANDOFF_TEXT: {
        "en": "We've let our reception team know — they'll reach out to you here shortly. "
              "If you need anything else in the meantime, just type \"menu\".",
        "hi": "हमने अपनी रिसेप्शन टीम को सूचित कर दिया है — वे जल्द ही आपसे यहां संपर्क करेंगे। "
              "इस बीच अगर आपको कुछ और चाहिए, तो बस \"menu\" लिखें।",
    },

    HOSPITAL_INFO_TEXT: {
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

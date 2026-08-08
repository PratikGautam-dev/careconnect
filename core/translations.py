# core/translations.py
"""
Patient-facing string lookup, English + Hindi (language-selection follow-up
to Section 14.5's feature-toggle model). Every fixed UI string the bot sends
lives here, keyed by a short semantic name, with one template per supported
language -- flows.py/core/booking_flow.py/faq_flow.py/core/main.py look
strings up here via t(key, language, **kwargs) instead of hardcoding text
inline, so adding a language later means adding one dict, not hunting down
every send_text/send_list/send_buttons call site again.

Deliberately NOT translated here: hospital-configured content (welcome
message text, FAQ topic/answer pairs, doctor/department names) -- that's the
hospital's own entered data, not this app's fixed UI chrome, and auto-
translating it would be actively wrong (a hospital's FAQ answer says what it
says). Only the bot's own fixed prompts/menus/confirmations are in scope.

Translation quality note: these Hindi strings are a first pass, not
reviewed by a native speaker -- standard/formal Hindi appropriate for a
hospital context, good enough to ship and iterate on, not verified
production copy. Worth a native-speaker pass before relying on it heavily.

WhatsApp constraint worth knowing if these get edited: interactive BUTTON
titles are capped at 20 characters and LIST ROW titles at 24 (Meta's limit,
same one core/flow_common.py's cap_rows() docstring already flags for row
COUNT) -- nothing in this module enforces title LENGTH, so a translated
button/row label that's too long would make Meta reject the whole send the
same silent way an 11th list row already could before cap_rows() existed.
Kept short here on purpose; if you lengthen one, check it against a real
send.
"""
from typing import Literal

Language = Literal["en", "hi"]
DEFAULT_LANGUAGE: Language = "en"
SUPPORTED_LANGUAGES: set[str] = {"en", "hi"}

STRINGS: dict[str, dict[Language, str]] = {
    # --- Language picker (shown before anything else, first contact / new session) ---
    "language_picker_body": {
        "en": "Please choose your language.\nकृपया अपनी भाषा चुनें।",
        "hi": "Please choose your language.\nकृपया अपनी भाषा चुनें।",
    },
    "language_picker_button_en": {"en": "English", "hi": "English"},
    "language_picker_button_hi": {"en": "हिन्दी", "hi": "हिन्दी"},

    # --- Main / feature menu ---
    "welcome_menu": {
        "en": "Welcome to {hospital_name}! How can we help you today?",
        "hi": "{hospital_name} में आपका स्वागत है! हम आपकी कैसे मदद कर सकते हैं?",
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

    # --- Booking: department/doctor/slot menus ---
    "select_department": {"en": "Please select a department:", "hi": "कृपया एक विभाग चुनें:"},
    "view_departments_button": {"en": "View Departments", "hi": "विभाग देखें"},
    "departments_section_title": {"en": "Departments", "hi": "विभाग"},

    "select_doctor": {
        "en": "Please select a doctor in {department_name}:",
        "hi": "कृपया {department_name} में एक डॉक्टर चुनें:",
    },
    "view_doctors_button": {"en": "View Doctors", "hi": "डॉक्टर देखें"},

    "select_slot": {
        "en": "Please select a time slot with {doctor_name}:",
        "hi": "कृपया {doctor_name} के साथ एक समय स्लॉट चुनें:",
    },
    "view_slots_button": {"en": "View Slots", "hi": "स्लॉट देखें"},
    "available_slots_section_title": {"en": "Available Slots", "hi": "उपलब्ध स्लॉट"},

    "no_doctors_available": {
        "en": "Sorry, there are no doctors available in {department_name} right now. Please check back later.",
        "hi": "क्षमा करें, {department_name} में अभी कोई डॉक्टर उपलब्ध नहीं है। कृपया बाद में फिर से देखें।",
    },
    "no_slots_available": {
        "en": "Sorry, there are no available slots for {doctor_name} right now. Please check back later.",
        "hi": "क्षमा करें, {doctor_name} के लिए अभी कोई स्लॉट उपलब्ध नहीं है। कृपया बाद में फिर से देखें।",
    },
    "slot_taken_no_alternatives": {
        "en": "Sorry, that slot was just taken and there are no other slots available for {doctor_name} right now. "
              "Please check back later.",
        "hi": "क्षमा करें, वह स्लॉट अभी-अभी बुक हो गया और {doctor_name} के लिए अभी कोई अन्य स्लॉट उपलब्ध नहीं है। "
              "कृपया बाद में फिर से देखें।",
    },
    "slot_taken_choose_another": {
        "en": "Sorry, that slot was just taken. Please choose another time.",
        "hi": "क्षमा करें, वह स्लॉट अभी-अभी बुक हो गया। कृपया कोई और समय चुनें।",
    },

    # --- Booking: patient name/age collection (new) ---
    "ask_patient_name": {
        "en": "Before we confirm — could you share the patient's name?",
        "hi": "पुष्टि करने से पहले — क्या आप मरीज़ का नाम बता सकते हैं?",
    },
    "invalid_patient_name": {
        "en": "Please enter a valid name.",
        "hi": "कृपया एक मान्य नाम दर्ज करें।",
    },
    "ask_patient_age": {
        "en": "Thanks, {patient_name}! And could you share the patient's age?",
        "hi": "धन्यवाद, {patient_name}! और क्या आप मरीज़ की उम्र बता सकते हैं?",
    },
    "invalid_patient_age": {
        "en": "Please enter a valid age (a number between 0 and 120).",
        "hi": "कृपया एक मान्य उम्र दर्ज करें (0 से 120 के बीच की संख्या)।",
    },

    # --- Booking: confirmation ---
    "confirm_booking_summary": {
        "en": "Please confirm your appointment:\n\nDepartment: {department_name}\nDoctor: {doctor_name}\nSlot: {slot_label}",
        "hi": "कृपया अपनी अपॉइंटमेंट की पुष्टि करें:\n\nविभाग: {department_name}\nडॉक्टर: {doctor_name}\nस्लॉट: {slot_label}",
    },
    "confirm_button": {"en": "Confirm", "hi": "पुष्टि करें"},
    "cancel_button": {"en": "Cancel", "hi": "रद्द करें"},
    "booking_confirmed": {
        "en": "Your appointment is confirmed!\n\nDepartment: {department_name}\nDoctor: {doctor_name}\n"
              "Slot: {slot_label}\n\nWe look forward to seeing you.",
        "hi": "आपकी अपॉइंटमेंट पुष्टि हो गई है!\n\nविभाग: {department_name}\nडॉक्टर: {doctor_name}\n"
              "स्लॉट: {slot_label}\n\nहम आपसे मिलने के लिए उत्सुक हैं।",
    },
    "booking_not_confirmed": {
        "en": "Okay, I've cancelled this booking. Send any message to start over.",
        "hi": "ठीक है, मैंने यह बुकिंग रद्द कर दी है। फिर से शुरू करने के लिए कोई भी संदेश भेजें।",
    },

    # --- Cancel flow ---
    "no_upcoming_to_cancel": {
        "en": "You don't have any upcoming appointments to cancel.",
        "hi": "आपकी रद्द करने के लिए कोई आगामी अपॉइंटमेंट नहीं है।",
    },
    "which_appointment_cancel": {
        "en": "Which appointment would you like to cancel?",
        "hi": "आप कौन सी अपॉइंटमेंट रद्द करना चाहते हैं?",
    },
    "appointment_lookup_error": {
        "en": "Something went wrong finding that appointment. Please start over.",
        "hi": "उस अपॉइंटमेंट को खोजने में कुछ गलत हो गया। कृपया फिर से शुरू करें।",
    },
    "cancel_confirm_question": {
        "en": "Are you sure you want to cancel your appointment with {doctor_name} on {when}?",
        "hi": "क्या आप वाकई {doctor_name} के साथ {when} की अपनी अपॉइंटमेंट रद्द करना चाहते हैं?",
    },
    "appointment_cancelled": {
        "en": "Your appointment with {doctor_name} on {when} has been cancelled.",
        "hi": "{doctor_name} के साथ {when} की आपकी अपॉइंटमेंट रद्द कर दी गई है।",
    },
    "cancellation_aborted": {
        "en": "Okay, your appointment was not cancelled.",
        "hi": "ठीक है, आपकी अपॉइंटमेंट रद्द नहीं की गई।",
    },

    # --- Reschedule flow ---
    "no_upcoming_to_reschedule": {
        "en": "You don't have any upcoming appointments to reschedule.",
        "hi": "आपके पास रीशेड्यूल करने के लिए कोई आगामी अपॉइंटमेंट नहीं है।",
    },
    "which_appointment_reschedule": {
        "en": "Which appointment would you like to reschedule?",
        "hi": "आप किस अपॉइंटमेंट का समय बदलना चाहते हैं?",
    },
    "reschedule_confirm_summary": {
        "en": "Please confirm your new appointment time:\n\nDoctor: {doctor_name}\nNew Slot: {slot_label}",
        "hi": "कृपया अपनी नई अपॉइंटमेंट का समय की पुष्टि करें:\n\nडॉक्टर: {doctor_name}\nनया स्लॉट: {slot_label}",
    },
    "appointment_rescheduled": {
        "en": "Your appointment has been rescheduled!\n\nDoctor: {doctor_name}\nNew Slot: {slot_label}\n\n"
              "We look forward to seeing you.",
        "hi": "आपकी अपॉइंटमेंट का समय बदल दिया गया है!\n\nडॉक्टर: {doctor_name}\nनया स्लॉट: {slot_label}\n\n"
              "हम आपसे मिलने के लिए उत्सुक हैं।",
    },
    "reschedule_aborted": {
        "en": "Okay, your appointment was not rescheduled.",
        "hi": "ठीक है, आपकी अपॉइंटमेंट का समय नहीं बदला गया।",
    },

    # --- Shared: appointment-selection menu (cancel + reschedule) ---
    "view_appointments_button": {"en": "View Appointments", "hi": "अपॉइंटमेंट देखें"},
    "your_appointments_section_title": {"en": "Your Appointments", "hi": "आपकी अपॉइंटमेंट"},

    # --- Shared fallback ---
    "please_choose": {
        "en": "Please choose an option from the list above",
        "hi": "कृपया ऊपर दी गई सूची में से एक विकल्प चुनें",
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

    # --- FAQ sub-flow (faq_flow.py) ---
    "faq_no_topics": {
        "en": "Sorry, {hospital_name} hasn't set up any FAQ topics yet. Please check back later.",
        "hi": "क्षमा करें, {hospital_name} ने अभी तक कोई सामान्य प्रश्न सेट नहीं किए हैं। कृपया बाद में फिर से देखें।",
    },
    "faq_topic_prompt": {
        "en": "{hospital_name} — choose a topic to learn more:",
        "hi": "{hospital_name} — अधिक जानने के लिए एक विषय चुनें:",
    },
    "view_topics_button": {"en": "View Topics", "hi": "विषय देखें"},
    "topics_section_title": {"en": "Topics", "hi": "विषय"},

    # --- core/main.py: paths outside the normal flow dispatch ---
    "audio_not_supported": {
        "en": "I couldn't process your audio. Could you send it as text instead?",
        "hi": "मैं आपका ऑडियो प्रोसेस नहीं कर सका। क्या आप इसे टेक्स्ट के रूप में भेज सकते हैं?",
    },
    "system_error_notify": {
        "en": "Sorry, something went wrong on our end. We've notified our team and someone will follow up with "
              "you here shortly.",
        "hi": "क्षमा करें, हमारी तरफ से कुछ गलत हो गया। हमने अपनी टीम को सूचित कर दिया है और जल्द ही कोई आपसे यहां संपर्क करेगा।",
    },
}


def t(key: str, language: str | None, **kwargs) -> str:
    """The one lookup function every flow module calls instead of hardcoding
    a string. Falls back to English for an unset/unrecognized language
    (never raises over a bad/missing language value -- a session that
    somehow has language=None or an unsupported code still gets a real
    reply, not a crash)."""
    lang: Language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE  # type: ignore[assignment]
    template = STRINGS[key][lang]
    return template.format(**kwargs) if kwargs else template

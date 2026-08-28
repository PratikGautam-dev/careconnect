# core/translations/cancel_reschedule.py
"""Cancel and reschedule flows, plus the appointment-selection menu they
both share."""
from core.translations._common import Language

STRINGS: dict[str, dict[Language, str]] = {
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
}

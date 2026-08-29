# core/translations/cancel_reschedule.py
"""Cancel and reschedule flows, plus the appointment-selection menu they
both share."""
from core.translations._common import Language


NO_UPCOMING_TO_CANCEL = "no_upcoming_to_cancel"
WHICH_APPOINTMENT_CANCEL = "which_appointment_cancel"
APPOINTMENT_LOOKUP_ERROR = "appointment_lookup_error"
CANCEL_CONFIRM_QUESTION = "cancel_confirm_question"
APPOINTMENT_CANCELLED = "appointment_cancelled"
CANCELLATION_ABORTED = "cancellation_aborted"
NO_UPCOMING_TO_RESCHEDULE = "no_upcoming_to_reschedule"
WHICH_APPOINTMENT_RESCHEDULE = "which_appointment_reschedule"
RESCHEDULE_CONFIRM_SUMMARY = "reschedule_confirm_summary"
APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
RESCHEDULE_ABORTED = "reschedule_aborted"
VIEW_APPOINTMENTS_BUTTON = "view_appointments_button"
YOUR_APPOINTMENTS_SECTION_TITLE = "your_appointments_section_title"

STRINGS: dict[str, dict[Language, str]] = {
    # --- Cancel flow ---
    NO_UPCOMING_TO_CANCEL: {
        "en": "You don't have any upcoming appointments to cancel.",
        "hi": "आपकी रद्द करने के लिए कोई आगामी अपॉइंटमेंट नहीं है।",
    },
    WHICH_APPOINTMENT_CANCEL: {
        "en": "Which appointment would you like to cancel?",
        "hi": "आप कौन सी अपॉइंटमेंट रद्द करना चाहते हैं?",
    },
    APPOINTMENT_LOOKUP_ERROR: {
        "en": "Something went wrong finding that appointment. Please start over.",
        "hi": "उस अपॉइंटमेंट को खोजने में कुछ गलत हो गया। कृपया फिर से शुरू करें।",
    },
    CANCEL_CONFIRM_QUESTION: {
        "en": "Are you sure you want to cancel your appointment with {doctor_name} on {when}?",
        "hi": "क्या आप वाकई {doctor_name} के साथ {when} की अपनी अपॉइंटमेंट रद्द करना चाहते हैं?",
    },
    APPOINTMENT_CANCELLED: {
        "en": "✅ *Appointment Cancelled*\n\n"
              "Doctor: {doctor_name}\nDate: {when}\n\n"
              "Your appointment has been cancelled successfully.",
        "hi": "✅ *अपॉइंटमेंट रद्द*\n\n"
              "डॉक्टर: {doctor_name}\nतारीख: {when}\n\n"
              "आपकी अपॉइंटमेंट सफलतापूर्वक रद्द कर दी गई है।",
    },
    CANCELLATION_ABORTED: {
        "en": "Okay, your appointment was not cancelled.",
        "hi": "ठीक है, आपकी अपॉइंटमेंट रद्द नहीं की गई।",
    },

    # --- Reschedule flow ---
    NO_UPCOMING_TO_RESCHEDULE: {
        "en": "You don't have any upcoming appointments to reschedule.",
        "hi": "आपके पास रीशेड्यूल करने के लिए कोई आगामी अपॉइंटमेंट नहीं है।",
    },
    WHICH_APPOINTMENT_RESCHEDULE: {
        "en": "Which appointment would you like to reschedule?",
        "hi": "आप किस अपॉइंटमेंट का समय बदलना चाहते हैं?",
    },
    RESCHEDULE_CONFIRM_SUMMARY: {
        "en": "Please confirm your new appointment time:\n\nDoctor: {doctor_name}\nNew Slot: {slot_label}",
        "hi": "कृपया अपनी नई अपॉइंटमेंट का समय की पुष्टि करें:\n\nडॉक्टर: {doctor_name}\nनया स्लॉट: {slot_label}",
    },
    APPOINTMENT_RESCHEDULED: {
        "en": "✅ *Appointment Rescheduled!*\n\n"
              "Doctor: {doctor_name}\nNew Slot: {slot_label}\n\n"
              "We look forward to seeing you.",
        "hi": "✅ *अपॉइंटमेंट का समय बदला गया!*\n\n"
              "डॉक्टर: {doctor_name}\nनया स्लॉट: {slot_label}\n\n"
              "हम आपसे मिलने के लिए उत्सुक हैं।",
    },
    RESCHEDULE_ABORTED: {
        "en": "Okay, your appointment was not rescheduled.",
        "hi": "ठीक है, आपकी अपॉइंटमेंट का समय नहीं बदला गया।",
    },

    # --- Shared: appointment-selection menu (cancel + reschedule) ---
    VIEW_APPOINTMENTS_BUTTON: {"en": "View Appointments", "hi": "अपॉइंटमेंट देखें"},
    YOUR_APPOINTMENTS_SECTION_TITLE: {"en": "Your Appointments", "hi": "आपकी अपॉइंटमेंट"},
}

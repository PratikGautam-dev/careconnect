# core/translations/booking.py
"""The booking flow itself: appointment type, per-type consent,
department/doctor/date/time selection, patient name/age collection, the
confirmation card, and the booking-conflict/follow-up variants."""
from core.translations._common import Language


SELECT_APPOINTMENT_TYPE = "select_appointment_type"
VIEW_APPOINTMENT_TYPES_BUTTON = "view_appointment_types_button"
APPOINTMENT_TYPES_SECTION_TITLE = "appointment_types_section_title"
CHANGE_APPOINTMENT_TYPE_OPTION = "change_appointment_type_option"
CONSENT_PROMPT = "consent_prompt"
CONSENT_AGREE_BUTTON = "consent_agree_button"
CONSENT_DECLINED = "consent_declined"
SELECT_DEPARTMENT = "select_department"
VIEW_DEPARTMENTS_BUTTON = "view_departments_button"
DEPARTMENTS_SECTION_TITLE = "departments_section_title"
SELECT_DOCTOR = "select_doctor"
VIEW_DOCTORS_BUTTON = "view_doctors_button"
DOCTOR_SELECTED_ASK_DATE = "doctor_selected_ask_date"
VIEW_DATES_BUTTON = "view_dates_button"
AVAILABLE_DATES_SECTION_TITLE = "available_dates_section_title"
SELECT_TIME_SLOT = "select_time_slot"
VIEW_TIMES_BUTTON = "view_times_button"
AVAILABLE_TIMES_SECTION_TITLE = "available_times_section_title"
SELECT_DAYCARE_DURATION = "select_daycare_duration"
VIEW_DURATIONS_BUTTON = "view_durations_button"
DAYCARE_DURATIONS_SECTION_TITLE = "daycare_durations_section_title"
CONFIRM_DAYCARE_DURATION_LINE = "confirm_daycare_duration_line"
SELECT_SLOT = "select_slot"
VIEW_SLOTS_BUTTON = "view_slots_button"
AVAILABLE_SLOTS_SECTION_TITLE = "available_slots_section_title"
NO_DOCTORS_AVAILABLE = "no_doctors_available"
NO_SLOTS_AVAILABLE = "no_slots_available"
SLOT_TAKEN_NO_ALTERNATIVES = "slot_taken_no_alternatives"
SLOT_TAKEN_CHOOSE_ANOTHER = "slot_taken_choose_another"
ASK_BOOKING_FOR = "ask_booking_for"
BOOKING_FOR_SELF_BUTTON = "booking_for_self_button"
BOOKING_FOR_OTHER_BUTTON = "booking_for_other_button"
ASK_PATIENT_NAME = "ask_patient_name"
INVALID_PATIENT_NAME = "invalid_patient_name"
ASK_PATIENT_CONTACT_NUMBER = "ask_patient_contact_number"
INVALID_PATIENT_CONTACT_NUMBER = "invalid_patient_contact_number"
ASK_PATIENT_AGE = "ask_patient_age"
INVALID_PATIENT_AGE = "invalid_patient_age"
ASK_PATIENT_GENDER = "ask_patient_gender"
INVALID_PATIENT_GENDER = "invalid_patient_gender"
GENDER_MALE = "gender_male"
GENDER_FEMALE = "gender_female"
GENDER_OTHER = "gender_other"
CONFIRM_BOOKING_SUMMARY = "confirm_booking_summary"
CONFIRM_BUTTON = "confirm_button"
CANCEL_BUTTON = "cancel_button"
WHAT_WOULD_YOU_LIKE_TO_CHANGE = "what_would_you_like_to_change"
VIEW_CHANGE_OPTIONS_BUTTON = "view_change_options_button"
CHANGE_OPTIONS_SECTION_TITLE = "change_options_section_title"
CHANGE_DEPARTMENT_OPTION = "change_department_option"
CHANGE_DOCTOR_OPTION = "change_doctor_option"
CHANGE_DATE_OPTION = "change_date_option"
CHANGE_TIME_OPTION = "change_time_option"
CHANGE_DURATION_OPTION = "change_duration_option"
BOOKING_CONFIRMED = "booking_confirmed"
BOOKING_NOT_CONFIRMED = "booking_not_confirmed"
DUPLICATE_BOOKING_TEXT = "duplicate_booking_text"
DEPARTMENT_APPOINTMENT_CONFLICT = "department_appointment_conflict"
NEW_CONSULTATION_DEPARTMENT_CONFLICT = "new_consultation_department_conflict"
NEW_CONSULTATION_SAME_DAY_CONFLICT = "new_consultation_same_day_conflict"
NO_PREVIOUS_APPOINTMENT_FOR_FOLLOWUP = "no_previous_appointment_for_followup"
FOLLOWUP_CONFIRM_PROMPT = "followup_confirm_prompt"
MANAGE_APPOINTMENT_PROMPT = "manage_appointment_prompt"

STRINGS: dict[str, dict[Language, str]] = {
    # --- Booking: appointment type (shown right after patient resolution,
    # before department selection) ---
    SELECT_APPOINTMENT_TYPE: {
        "en": "Please choose the type of consultation you would like to book.",
        "hi": "कृपया वह परामर्श प्रकार चुनें जिसे आप बुक करना चाहते हैं।",
    },
    VIEW_APPOINTMENT_TYPES_BUTTON: {"en": "View Types", "hi": "प्रकार देखें"},
    APPOINTMENT_TYPES_SECTION_TITLE: {"en": "Appointment Type", "hi": "अपॉइंटमेंट प्रकार"},
    CHANGE_APPOINTMENT_TYPE_OPTION: {"en": "Appointment Type", "hi": "अपॉइंटमेंट प्रकार"},

    # --- Booking: consent (shown after confirmation, only for an
    # appointment type with requires_consent=TRUE, e.g. tele-consultation) ---
    CONSENT_PROMPT: {
        "en": "This is a {appointment_type_label} appointment. Do you consent to proceed with this type of consultation?",
        "hi": "यह एक {appointment_type_label} अपॉइंटमेंट है। क्या आप इस प्रकार के परामर्श के साथ आगे बढ़ने के लिए सहमत हैं?",
    },
    CONSENT_AGREE_BUTTON: {"en": "I Agree", "hi": "मैं सहमत हूँ"},
    CONSENT_DECLINED: {
        "en": "No problem -- this appointment type needs your consent to proceed, so it hasn't been booked.",
        "hi": "कोई बात नहीं -- इस प्रकार की अपॉइंटमेंट के लिए आपकी सहमति आवश्यक है, इसलिए इसे बुक नहीं किया गया है।",
    },

    # --- Booking: department/doctor/date/time menus ---
    SELECT_DEPARTMENT: {"en": "Please choose the medical specialty you would like to consult.", "hi": "कृपया वह चिकित्सा विशेषज्ञता चुनें जिसके लिए आप परामर्श लेना चाहते हैं।"},
    VIEW_DEPARTMENTS_BUTTON: {"en": "View Departments", "hi": "विभाग देखें"},
    DEPARTMENTS_SECTION_TITLE: {"en": "Departments", "hi": "विभाग"},

    SELECT_DOCTOR: {
        "en": "Please select a specialist doctor for {department_name}:",
        "hi": "कृपया {department_name} के लिए एक विशेषज्ञ डॉक्टर चुनें:",
    },
    VIEW_DOCTORS_BUTTON: {"en": "View Doctors", "hi": "डॉक्टर देखें"},

    # Section 12.12: booking's date/time step is now two separate prompts
    # (was one combined slot list) -- "select_slot"/"view_slots_button"/
    # "available_slots_section_title" below are kept as-is for the
    # RESCHEDULE flow only (_send_slot_menu), which the reference screenshot
    # this section is based on doesn't cover and so was deliberately left
    # as a single combined list, unchanged from before this section.
    # NOTE: doctor_name already includes a "Dr." prefix everywhere in this
    # codebase (db/seed.py's own seeded names, e.g. "Dr. Anjali Rao") -- do
    # NOT hardcode a second "Dr."/"डॉ." here, or every real send doubles it
    # ("You have selected Dr. Dr. Anjali Rao."), caught live via a full
    # conversation trace before this shipped.
    DOCTOR_SELECTED_ASK_DATE: {
        # Previous body (kept for reference, not deleted):
        # "en": "You have selected {doctor_name}. Now please select a consulting date:",
        # "hi": "आपने {doctor_name} को चुना है। अब कृपया परामर्श की तारीख चुनें:",
        "en": "{doctor_name} selected ✅\nPlease choose your preferred appointment date.",
        "hi": "{doctor_name} चुने गए ✅\nकृपया अपनी पसंदीदा अपॉइंटमेंट की तारीख चुनें।",
    },
    VIEW_DATES_BUTTON: {"en": "View Dates", "hi": "तारीखें देखें"},
    AVAILABLE_DATES_SECTION_TITLE: {"en": "Available Dates", "hi": "उपलब्ध तारीखें"},

    SELECT_TIME_SLOT: {
        "en": "Please select a preferred consulting time slot:",
        "hi": "कृपया अपनी पसंदीदा परामर्श समय स्लॉट चुनें:",
    },
    VIEW_TIMES_BUTTON: {"en": "View Times", "hi": "समय देखें"},
    AVAILABLE_TIMES_SECTION_TITLE: {"en": "Available Times", "hi": "उपलब्ध समय"},

    # --- Booking: daycare duration (Phase 2, docs/per-appointment-type-
    # flow-plan.md) -- shown right after time-slot selection, daycare only ---
    SELECT_DAYCARE_DURATION: {
        "en": "Please select how long the daycare stay will be:",
        "hi": "कृपया बताएं कि डेकेयर में ठहराव कितने समय का होगा:",
    },
    VIEW_DURATIONS_BUTTON: {"en": "View Durations", "hi": "अवधि देखें"},
    DAYCARE_DURATIONS_SECTION_TITLE: {"en": "Duration", "hi": "अवधि"},
    CONFIRM_DAYCARE_DURATION_LINE: {"en": "⏱ *Duration:* {duration_label}", "hi": "⏱ *अवधि:* {duration_label}"},

    SELECT_SLOT: {
        "en": "Please select a time slot with {doctor_name}:",
        "hi": "कृपया {doctor_name} के साथ एक समय स्लॉट चुनें:",
    },
    VIEW_SLOTS_BUTTON: {"en": "View Slots", "hi": "स्लॉट देखें"},
    AVAILABLE_SLOTS_SECTION_TITLE: {"en": "Available Slots", "hi": "उपलब्ध स्लॉट"},

    NO_DOCTORS_AVAILABLE: {
        "en": "Sorry, there are no doctors available in {department_name} right now. Please check back later.",
        "hi": "क्षमा करें, {department_name} में अभी कोई डॉक्टर उपलब्ध नहीं है। कृपया बाद में फिर से देखें।",
    },
    NO_SLOTS_AVAILABLE: {
        "en": "Sorry, there are no available slots for {doctor_name} right now. Please check back later.",
        "hi": "क्षमा करें, {doctor_name} के लिए अभी कोई स्लॉट उपलब्ध नहीं है। कृपया बाद में फिर से देखें।",
    },
    SLOT_TAKEN_NO_ALTERNATIVES: {
        "en": "Sorry, that slot was just taken and there are no other slots available for {doctor_name} right now. "
              "Please check back later.",
        "hi": "क्षमा करें, वह स्लॉट अभी-अभी बुक हो गया और {doctor_name} के लिए अभी कोई अन्य स्लॉट उपलब्ध नहीं है। "
              "कृपया बाद में फिर से देखें।",
    },
    SLOT_TAKEN_CHOOSE_ANOTHER: {
        "en": "Sorry, that slot was just taken. Please choose another time.",
        "hi": "क्षमा करें, वह स्लॉट अभी-अभी बुक हो गया। कृपया कोई और समय चुनें।",
    },

    # --- Booking: patient name + age collection ---
    # Section 12.13 follow-up: age is BACK in the WhatsApp flow (Section 12.12
    # had dropped it to match a reference screenshot's exact wording, flagged
    # in Spec.md as a decision worth confirming -- confirmed the user did
    # want it, so it's restored here, now also shown on the confirmation card
    # per that follow-up's own explicit choice).
    # Patient identity/UX follow-up (Spec.md Section 0): "Almost done!" was
    # accurate when this was the LAST step before confirmation -- now that
    # name/age is asked FIRST (before department selection), that framing
    # was actively misleading, caught live and dropped.
    ASK_BOOKING_FOR: {
        "en": "Who would you like to book this appointment for?",
        "hi": "आप यह अपॉइंटमेंट किसके लिए बुक करना चाहेंगे?",
    },
    BOOKING_FOR_SELF_BUTTON: {"en": "Myself", "hi": "मैं खुद"},
    BOOKING_FOR_OTHER_BUTTON: {"en": "Someone Else", "hi": "कोई और"},
    ASK_PATIENT_NAME: {
        "en": "Please enter the patient's full name.",
        "hi": "कृपया मरीज का पूरा नाम दर्ज करें।",
    },
    INVALID_PATIENT_NAME: {
        "en": "Please enter a valid name using letters only (4–50 characters).",
        "hi": "कृपया केवल अक्षरों का उपयोग करके एक मान्य नाम दर्ज करें (4–50 अक्षर)।",
    },
    ASK_PATIENT_CONTACT_NUMBER: {
        "en": "Please enter the patient's age.",
        "hi": "कृपया मरीज की आयु दर्ज करें।",
    },
    INVALID_PATIENT_CONTACT_NUMBER: {
        "en": "Please enter a valid 10-digit contact number, digits only, not starting with 0.",
        "hi": "कृपया केवल अंकों में एक मान्य 10 अंकों का संपर्क नंबर दर्ज करें, जो 0 से शुरू न हो।",
    },
    ASK_PATIENT_AGE: {
        "en": "Please select the patient's gender.",
        "hi": "कृपया मरीज का लिंग चुनें।",
    },
    INVALID_PATIENT_AGE: {
        "en": "Please enter a valid age (a number between 0 and 100).",
        "hi": "कृपया एक मान्य उम्र दर्ज करें (0 से 100 के बीच की संख्या)।",
    },
    ASK_PATIENT_GENDER: {
        "en": "Please share the patient's gender:",
        "hi": "कृपया मरीज़ का लिंग बताएं:",
    },
    INVALID_PATIENT_GENDER: {
        "en": "Please select an option below.",
        "hi": "कृपया नीचे दिए गए विकल्पों में से एक चुनें।",
    },
    GENDER_MALE: {"en": "Male", "hi": "पुरुष"},
    GENDER_FEMALE: {"en": "Female", "hi": "महिला"},
    GENDER_OTHER: {"en": "Other", "hi": "अन्य"},

    # --- Booking: confirmation ---
    # Section 12.12: structured "card" style with WhatsApp *bold* markdown and
    # fixed emoji per field, matching the reference screenshot exactly, with
    # an added age line (Section 12.13 follow-up, not in the original
    # reference screenshot but explicitly requested).
    # Item 10 (Spec.md Section 0): patient name/age moved first, ahead of
    # department/doctor/date/time -- was department/doctor/date/time then
    # patient info last.
    # Appointment type step (WhatsApp flow alignment): {appointment_type_label}
    # line added above Patient. Always populated for real traffic --
    # _select_patient_and_continue's booking branch sets STATE_AWAITING_
    # APPOINTMENT_TYPE as the very first booking step now, before this
    # confirmation can ever be reached.
    CONFIRM_BOOKING_SUMMARY: {
        # Previous body (kept for reference, not deleted -- same
        # already-established convention as dpdp_consent.py/this hospital's
        # other recently-restyled templates):
        # "en": "*Confirm Booking Details:*\n"
        #       "📋 *Type:* {appointment_type_label}\n"
        #       "👤 *Patient:* {patient_name}\n"
        #       "🎂 *Age:* {patient_age}\n"
        #       "🏥 *Dept:* {department_name}\n"
        #       "👨‍⚕️ *Doctor:* {doctor_name}\n"
        #       "📅 *Date:* {date_label}\n"
        #       "🕐 *Slot:* {time_label}\n\n"
        #       "Please confirm this appointment:",
        # "hi": "*बुकिंग विवरण की पुष्टि करें:*\n"
        #       "📋 *प्रकार:* {appointment_type_label}\n"
        #       "👤 *मरीज़:* {patient_name}\n"
        #       "🎂 *उम्र:* {patient_age}\n"
        #       "🏥 *विभाग:* {department_name}\n"
        #       "👨‍⚕️ *डॉक्टर:* {doctor_name}\n"
        #       "📅 *तारीख:* {date_label}\n"
        #       "🕐 *स्लॉट:* {time_label}\n\n"
        #       "कृपया इस अपॉइंटमेंट की पुष्टि करें:",
        # Consultation Fee is a static placeholder line (confirmed with the
        # user) -- there's no fee/pricing field anywhere on appointment_types
        # or hospitals to source a real amount from yet.
        "en": (
            "*Confirm Booking Details:*\n"
            "👤 Patient: {patient_name}\n"
            "🆔 Patient Code: {patient_code}\n"
            "🎂 Age: {patient_age}\n"
            "📋 Appointment Type: {appointment_type_label}\n"
            "🏥 Department: {department_name}\n"
            "👨‍⚕️ Doctor: {doctor_name}\n"
            "📅 Date: {date_label}\n"
            "🕐 Time: {time_label}\n\n"
            "💰 Consultation Fee: ₹800\n"
            "(if applicable)\n\n"
            "Please review the details before confirming your appointment."
        ),
        "hi": (
            "*बुकिंग विवरण की पुष्टि करें:*\n"
            "👤 मरीज़: {patient_name}\n"
            "🆔 पेशेंट कोड: {patient_code}\n"
            "🎂 उम्र: {patient_age}\n"
            "📋 अपॉइंटमेंट प्रकार: {appointment_type_label}\n"
            "🏥 विभाग: {department_name}\n"
            "👨‍⚕️ डॉक्टर: {doctor_name}\n"
            "📅 तारीख: {date_label}\n"
            "🕐 समय: {time_label}\n\n"
            "💰 परामर्श शुल्क: ₹800\n"
            "(यदि लागू हो)\n\n"
            "कृपया अपॉइंटमेंट की पुष्टि करने से पहले विवरण की समीक्षा करें।"
        ),
    },
    CONFIRM_BUTTON: {"en": "Confirm", "hi": "पुष्टि करें"},
    CANCEL_BUTTON: {"en": "Cancel", "hi": "रद्द करें"},

    # Confirmation's own Back routes here instead of popping one field --
    # "which one field" isn't knowable, so this asks instead of guessing.
    WHAT_WOULD_YOU_LIKE_TO_CHANGE: {
        "en": "No problem — what would you like to change?",
        "hi": "कोई बात नहीं — आप क्या बदलना चाहेंगे?",
    },
    VIEW_CHANGE_OPTIONS_BUTTON: {"en": "Choose", "hi": "चुनें"},
    CHANGE_OPTIONS_SECTION_TITLE: {"en": "Change", "hi": "बदलें"},
    CHANGE_DEPARTMENT_OPTION: {"en": "Department", "hi": "विभाग"},
    CHANGE_DOCTOR_OPTION: {"en": "Doctor", "hi": "डॉक्टर"},
    CHANGE_DATE_OPTION: {"en": "Date", "hi": "तारीख"},
    CHANGE_TIME_OPTION: {"en": "Time", "hi": "समय"},
    CHANGE_DURATION_OPTION: {"en": "Duration", "hi": "अवधि"},
    BOOKING_CONFIRMED: {
        "en": (
            "✅ Appointment Confirmed\n\n"
            "Your appointment has been successfully booked.\n\n"
            "Appointment ID: {reference_id}\n"
            "Patient: {patient_name}\n"
            "Department: {department_name}\n"
            "Doctor: {doctor_name}\n"
            "Date: {date_label}\n"
            "Time: {time_label}\n\n"
            "Please arrive 15 minutes before your appointment.\n"
            "We look forward to seeing you."
        ),
        "hi": (
            "✅ अपॉइंटमेंट की पुष्टि हो गई\n\n"
            "आपकी अपॉइंटमेंट सफलतापूर्वक बुक हो गई है।\n\n"
            "अपॉइंटमेंट आईडी: {reference_id}\n"
            "मरीज़: {patient_name}\n"
            "विभाग: {department_name}\n"
            "डॉक्टर: {doctor_name}\n"
            "तारीख: {date_label}\n"
            "समय: {time_label}\n\n"
            "कृपया अपनी अपॉइंटमेंट से 15 मिनट पहले पहुंचें।\n"
            "हम आपसे मिलने के लिए उत्सुक हैं।"
        ),
    },
    BOOKING_NOT_CONFIRMED: {
        "en": "Okay, I've cancelled this booking. Send any message to start over.",
        "hi": "ठीक है, मैंने यह बुकिंग रद्द कर दी है। फिर से शुरू करने के लिए कोई भी संदेश भेजें।",
    },
    # Item 5 (Spec.md Section 0): shown when create_appointment() raises
    # DuplicateBookingError -- an active booking with this same doctor (and
    # age on file) already exists, so this attempt is blocked rather than
    # creating a second one.
    DUPLICATE_BOOKING_TEXT: {
        "en": "You already have an appointment booked with {doctor_name} — reply below to manage it.",
        "hi": "आपकी {doctor_name} के साथ पहले से ही एक अपॉइंटमेंट बुक है — इसे प्रबंधित करने के लिए नीचे उत्तर दें।",
    },
    # Shared department-selection conflict (base.existing_department_appointment):
    # new/tele/second_opinion/daycare all block picking a department the
    # patient already has an active appointment (or follow-up) in, showing
    # that existing appointment's own details plus Main Menu/Cancel/Reschedule
    # quick actions -- same shape as DUPLICATE_BOOKING_TEXT above.
    DEPARTMENT_APPOINTMENT_CONFLICT: {
        "en": "You already have an appointment in {department_name} with {doctor_name} on {when} — reply below to manage it.",
        "hi": "आपकी {department_name} में {doctor_name} के साथ {when} को पहले से ही एक अपॉइंटमेंट है — इसे प्रबंधित करने के लिए नीचे उत्तर दें।",
    },
    # docs/per-appointment-type-flow-plan.md Phase 2: New Consultation-only
    # booking rules -- flows/booking/types/new_consultation.py. (The
    # department half is now a same-day-of-booking safety net only --
    # DEPARTMENT_APPOINTMENT_CONFLICT above already blocks this earlier, at
    # department selection.)
    NEW_CONSULTATION_DEPARTMENT_CONFLICT: {
        "en": "You already have an active appointment in this department. Please cancel it first if you'd like to book again.",
        "hi": "इस विभाग में आपकी पहले से ही एक सक्रिय अपॉइंटमेंट है। दोबारा बुक करने के लिए कृपया पहले उसे रद्द करें।",
    },
    NEW_CONSULTATION_SAME_DAY_CONFLICT: {
        "en": "You already have an appointment booked on this day. Please choose a different date, or manage your existing appointment first.",
        "hi": "इस दिन आपकी पहले से ही एक अपॉइंटमेंट बुक है। कृपया कोई और तारीख चुनें, या पहले अपनी मौजूदा अपॉइंटमेंट प्रबंधित करें।",
    },
    # docs/per-appointment-type-flow-plan.md Phase 2 Step 2:
    # flows/booking/types/followup.py.
    NO_PREVIOUS_APPOINTMENT_FOR_FOLLOWUP: {
        # Previous body (kept for reference, not deleted):
        # "en": "We couldn't find any previous completed appointment for you, so Follow-up isn't available yet. Please choose New Consultation instead.",
        # "hi": "हमें आपकी कोई पिछली पूर्ण अपॉइंटमेंट नहीं मिली, इसलिए फॉलो-अप अभी उपलब्ध नहीं है। कृपया इसके बजाय नई परामर्श चुनें।",
        "en": (
            "No Previous Consultation Found\n"
            "We couldn't find any completed consultation for {name}.\n\n"
            "A follow-up appointment can only be booked after a previous consultation. Please book a New Consultation instead."
        ),
        "hi": (
            "कोई पिछला परामर्श नहीं मिला\n"
            "हमें {name} के लिए कोई पूर्ण परामर्श नहीं मिला।\n\n"
            "फॉलो-अप अपॉइंटमेंट केवल पिछले परामर्श के बाद ही बुक की जा सकती है। कृपया इसके बजाय नई परामर्श बुक करें।"
        ),
    },
    FOLLOWUP_CONFIRM_PROMPT: {
        "en": "Book a follow-up with {doctor_name} ({department_name})?\nYour last visit was on {last_visit_label}.",
        "hi": "क्या {doctor_name} ({department_name}) के साथ फॉलो-अप बुक करें?\nआपकी पिछली मुलाकात {last_visit_label} को हुई थी।",
    },
    # Item 6 (Spec.md Section 0): shown after tapping one appointment in "My
    # Appointments" -- the same quick-action buttons item 3/5 use.
    MANAGE_APPOINTMENT_PROMPT: {
        "en": "Your appointment with {doctor_name} — what would you like to do?",
        "hi": "{doctor_name} के साथ आपकी अपॉइंटमेंट — आप क्या करना चाहेंगे?",
    },
}

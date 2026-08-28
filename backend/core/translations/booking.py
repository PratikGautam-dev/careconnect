# core/translations/booking.py
"""The booking flow itself: appointment type, per-type consent,
department/doctor/date/time selection, patient name/age collection, the
confirmation card, and the booking-conflict/follow-up variants."""
from core.translations._common import Language

STRINGS: dict[str, dict[Language, str]] = {
    # --- Booking: appointment type (shown right after patient resolution,
    # before department selection) ---
    "select_appointment_type": {
        "en": "What type of appointment would you like to book?",
        "hi": "आप किस प्रकार की अपॉइंटमेंट बुक करना चाहेंगे?",
    },
    "view_appointment_types_button": {"en": "View Types", "hi": "प्रकार देखें"},
    "appointment_types_section_title": {"en": "Appointment Type", "hi": "अपॉइंटमेंट प्रकार"},
    "change_appointment_type_option": {"en": "Appointment Type", "hi": "अपॉइंटमेंट प्रकार"},

    # --- Booking: consent (shown after confirmation, only for an
    # appointment type with requires_consent=TRUE, e.g. tele-consultation) ---
    "consent_prompt": {
        "en": "This is a {appointment_type_label} appointment. Do you consent to proceed with this type of consultation?",
        "hi": "यह एक {appointment_type_label} अपॉइंटमेंट है। क्या आप इस प्रकार के परामर्श के साथ आगे बढ़ने के लिए सहमत हैं?",
    },
    "consent_agree_button": {"en": "I Agree", "hi": "मैं सहमत हूँ"},
    "consent_declined": {
        "en": "No problem -- this appointment type needs your consent to proceed, so it hasn't been booked.",
        "hi": "कोई बात नहीं -- इस प्रकार की अपॉइंटमेंट के लिए आपकी सहमति आवश्यक है, इसलिए इसे बुक नहीं किया गया है।",
    },

    # --- Booking: department/doctor/date/time menus ---
    "select_department": {"en": "Please select a medical department:", "hi": "कृपया एक चिकित्सा विभाग चुनें:"},
    "view_departments_button": {"en": "View Departments", "hi": "विभाग देखें"},
    "departments_section_title": {"en": "Departments", "hi": "विभाग"},

    "select_doctor": {
        "en": "Please select a specialist doctor for {department_name}:",
        "hi": "कृपया {department_name} के लिए एक विशेषज्ञ डॉक्टर चुनें:",
    },
    "view_doctors_button": {"en": "View Doctors", "hi": "डॉक्टर देखें"},

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
    "doctor_selected_ask_date": {
        "en": "You have selected {doctor_name}. Now please select a consulting date:",
        "hi": "आपने {doctor_name} को चुना है। अब कृपया परामर्श की तारीख चुनें:",
    },
    "view_dates_button": {"en": "View Dates", "hi": "तारीखें देखें"},
    "available_dates_section_title": {"en": "Available Dates", "hi": "उपलब्ध तारीखें"},

    "select_time_slot": {
        "en": "Please select a preferred consulting time slot:",
        "hi": "कृपया अपनी पसंदीदा परामर्श समय स्लॉट चुनें:",
    },
    "view_times_button": {"en": "View Times", "hi": "समय देखें"},
    "available_times_section_title": {"en": "Available Times", "hi": "उपलब्ध समय"},

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
    "ask_patient_name": {
        "en": "Please type the patient's full name in the chat box below and send it:",
        "hi": "कृपया चैट बॉक्स में मरीज़ का पूरा नाम टाइप करें और भेजें:",
    },
    "invalid_patient_name": {
        "en": "Please enter a valid name using letters only (4–50 characters).",
        "hi": "कृपया केवल अक्षरों का उपयोग करके एक मान्य नाम दर्ज करें (4–50 अक्षर)।",
    },
    "ask_patient_age": {
        "en": "Thanks, {patient_name}! And could you share the patient's age?",
        "hi": "धन्यवाद, {patient_name}! और क्या आप मरीज़ की उम्र बता सकते हैं?",
    },
    "invalid_patient_age": {
        "en": "Please enter a valid age (a number between 0 and 100).",
        "hi": "कृपया एक मान्य उम्र दर्ज करें (0 से 100 के बीच की संख्या)।",
    },
    "ask_patient_gender": {
        "en": "And what is the patient's gender?",
        "hi": "और मरीज़ का लिंग क्या है?",
    },
    "invalid_patient_gender": {
        "en": "Please select an option below.",
        "hi": "कृपया नीचे दिए गए विकल्पों में से एक चुनें।",
    },
    "gender_male": {"en": "Male", "hi": "पुरुष"},
    "gender_female": {"en": "Female", "hi": "महिला"},
    "gender_other": {"en": "Other", "hi": "अन्य"},

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
    "confirm_booking_summary": {
        "en": "*Confirm Booking Details:*\n"
              "📋 *Type:* {appointment_type_label}\n"
              "👤 *Patient:* {patient_name}\n"
              "🎂 *Age:* {patient_age}\n"
              "🏥 *Dept:* {department_name}\n"
              "👨‍⚕️ *Doctor:* {doctor_name}\n"
              "📅 *Date:* {date_label}\n"
              "🕐 *Slot:* {time_label}\n\n"
              "Please confirm this appointment:",
        "hi": "*बुकिंग विवरण की पुष्टि करें:*\n"
              "📋 *प्रकार:* {appointment_type_label}\n"
              "👤 *मरीज़:* {patient_name}\n"
              "🎂 *उम्र:* {patient_age}\n"
              "🏥 *विभाग:* {department_name}\n"
              "👨‍⚕️ *डॉक्टर:* {doctor_name}\n"
              "📅 *तारीख:* {date_label}\n"
              "🕐 *स्लॉट:* {time_label}\n\n"
              "कृपया इस अपॉइंटमेंट की पुष्टि करें:",
    },
    "confirm_button": {"en": "Confirm", "hi": "पुष्टि करें"},
    "cancel_button": {"en": "Cancel", "hi": "रद्द करें"},

    # Confirmation's own Back routes here instead of popping one field --
    # "which one field" isn't knowable, so this asks instead of guessing.
    "what_would_you_like_to_change": {
        "en": "No problem — what would you like to change?",
        "hi": "कोई बात नहीं — आप क्या बदलना चाहेंगे?",
    },
    "view_change_options_button": {"en": "Choose", "hi": "चुनें"},
    "change_options_section_title": {"en": "Change", "hi": "बदलें"},
    "change_department_option": {"en": "Department", "hi": "विभाग"},
    "change_doctor_option": {"en": "Doctor", "hi": "डॉक्टर"},
    "change_date_option": {"en": "Date", "hi": "तारीख"},
    "change_time_option": {"en": "Time", "hi": "समय"},
    "booking_confirmed": {
        "en": "✅ *Consulting Booked successfully!*\n\n"
              "Reference ID: *{reference_id}*\n"
              "Your appointment is registered. We look forward to seeing you.",
        "hi": "✅ *परामर्श सफलतापूर्वक बुक हो गया!*\n\n"
              "संदर्भ आईडी: *{reference_id}*\n"
              "आपकी अपॉइंटमेंट पंजीकृत हो गई है। हम आपसे मिलने के लिए उत्सुक हैं।",
    },
    "booking_not_confirmed": {
        "en": "Okay, I've cancelled this booking. Send any message to start over.",
        "hi": "ठीक है, मैंने यह बुकिंग रद्द कर दी है। फिर से शुरू करने के लिए कोई भी संदेश भेजें।",
    },
    # Item 5 (Spec.md Section 0): shown when create_appointment() raises
    # DuplicateBookingError -- an active booking with this same doctor (and
    # age on file) already exists, so this attempt is blocked rather than
    # creating a second one.
    "duplicate_booking_text": {
        "en": "You already have an appointment booked with {doctor_name} — reply below to manage it.",
        "hi": "आपकी {doctor_name} के साथ पहले से ही एक अपॉइंटमेंट बुक है — इसे प्रबंधित करने के लिए नीचे उत्तर दें।",
    },
    # docs/per-appointment-type-flow-plan.md Phase 2: New Consultation-only
    # booking rules -- flows/booking/types/new_consultation.py.
    "new_consultation_department_conflict": {
        "en": "You already have an active appointment in this department. Please cancel it first if you'd like to book again.",
        "hi": "इस विभाग में आपकी पहले से ही एक सक्रिय अपॉइंटमेंट है। दोबारा बुक करने के लिए कृपया पहले उसे रद्द करें।",
    },
    "new_consultation_same_day_conflict": {
        "en": "You already have an appointment booked on this day. Please choose a different date, or manage your existing appointment first.",
        "hi": "इस दिन आपकी पहले से ही एक अपॉइंटमेंट बुक है। कृपया कोई और तारीख चुनें, या पहले अपनी मौजूदा अपॉइंटमेंट प्रबंधित करें।",
    },
    # docs/per-appointment-type-flow-plan.md Phase 2 Step 2:
    # flows/booking/types/followup.py.
    "no_previous_appointment_for_followup": {
        "en": "We couldn't find any previous completed appointment for you, so Follow-up isn't available yet. Please choose New Consultation instead.",
        "hi": "हमें आपकी कोई पिछली पूर्ण अपॉइंटमेंट नहीं मिली, इसलिए फॉलो-अप अभी उपलब्ध नहीं है। कृपया इसके बजाय नई परामर्श चुनें।",
    },
    "followup_confirm_prompt": {
        "en": "Book a follow-up with {doctor_name} ({department_name})?\nYour last visit was on {last_visit_label}.",
        "hi": "क्या {doctor_name} ({department_name}) के साथ फॉलो-अप बुक करें?\nआपकी पिछली मुलाकात {last_visit_label} को हुई थी।",
    },
    # Item 6 (Spec.md Section 0): shown after tapping one appointment in "My
    # Appointments" -- the same quick-action buttons item 3/5 use.
    "manage_appointment_prompt": {
        "en": "Your appointment with {doctor_name} — what would you like to do?",
        "hi": "{doctor_name} के साथ आपकी अपॉइंटमेंट — आप क्या करना चाहेंगे?",
    },
}

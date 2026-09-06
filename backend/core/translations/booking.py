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
CONSULTATION_FEE_LINE = "consultation_fee_line"
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
BOOKING_CONFIRMED = "booking_confirmed"
BOOKING_NOT_CONFIRMED = "booking_not_confirmed"
DUPLICATE_BOOKING_TEXT = "duplicate_booking_text"
DEPARTMENT_APPOINTMENT_CONFLICT = "department_appointment_conflict"
NEW_CONSULTATION_DEPARTMENT_CONFLICT = "new_consultation_department_conflict"
NEW_CONSULTATION_SAME_DAY_CONFLICT = "new_consultation_same_day_conflict"
NO_PREVIOUS_APPOINTMENT_FOR_FOLLOWUP = "no_previous_appointment_for_followup"
FOLLOWUP_ELIGIBLE_LIST_PROMPT = "followup_eligible_list_prompt"
VIEW_FOLLOWUP_OPTIONS_BUTTON = "view_followup_options_button"
FOLLOWUP_ELIGIBLE_SECTION_TITLE = "followup_eligible_section_title"
FOLLOWUP_CONFIRMATION_SUMMARY = "followup_confirmation_summary"
FOLLOWUP_APPOINTMENT_CONFIRMED = "followup_appointment_confirmed"
MANAGE_APPOINTMENT_PROMPT = "manage_appointment_prompt"

# --- Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5) ---
SELECT_DIAGNOSTIC_TEST = "select_diagnostic_test"
VIEW_TESTS_BUTTON = "view_tests_button"
DIAGNOSTIC_TESTS_SECTION_TITLE = "diagnostic_tests_section_title"
SELECT_DIAGNOSTIC_VARIANT = "select_diagnostic_variant"
VIEW_VARIANTS_BUTTON = "view_variants_button"
DIAGNOSTIC_VARIANTS_SECTION_TITLE = "diagnostic_variants_section_title"
NO_DIAGNOSTIC_TESTS_CONFIGURED = "no_diagnostic_tests_configured"
CHANGE_DIAGNOSTIC_TEST_OPTION = "change_diagnostic_test_option"
CHANGE_DIAGNOSTIC_VARIANT_OPTION = "change_diagnostic_variant_option"
DIAGNOSTIC_CONFIRMATION_SUMMARY = "diagnostic_confirmation_summary"
DIAGNOSTIC_BOOKING_CONFIRMED = "diagnostic_booking_confirmed"
DIAGNOSTIC_AMOUNT_LINE = "diagnostic_amount_line"
DIAGNOSTIC_PREPARATION_LINE = "diagnostic_preparation_line"

# --- Lab Test Phase 2 follow-up (business spec Sections 4.1-4.4): unlike
# Diagnostic Test above, a Lab Test booking is a multi-test BASKET with its
# own collection-method (visit vs. home sample)/serviceability/address steps
# before date/time. See flows/booking/types/lab.py. ---
SELECT_LAB_TEST = "select_lab_test"
LAB_TEST_ADDED_PROMPT = "lab_test_added_prompt"
LAB_DONE_BUTTON = "lab_done_button"
SELECT_COLLECTION_METHOD = "select_collection_method"
COLLECTION_VISIT_BUTTON = "collection_visit_button"
COLLECTION_HOME_BUTTON = "collection_home_button"
ASK_COLLECTION_PINCODE = "ask_collection_pincode"
NOT_SERVICEABLE_PINCODE = "not_serviceable_pincode"
TRY_ANOTHER_PINCODE_BUTTON = "try_another_pincode_button"
ASK_COLLECTION_ADDRESS = "ask_collection_address"
ASK_COLLECTION_ADDRESS_WITH_SUGGESTION = "ask_collection_address_with_suggestion"
CHANGE_COLLECTION_METHOD_OPTION = "change_collection_method_option"
LAB_CONFIRMATION_SUMMARY = "lab_confirmation_summary"
LAB_TEST_CHARGES_LINE = "lab_test_charges_line"
LAB_HOME_COLLECTION_LINE = "lab_home_collection_line"
LAB_TOTAL_LINE = "lab_total_line"
LAB_FASTING_LINE = "lab_fasting_line"
LAB_BOOKING_CONFIRMED = "lab_booking_confirmed"

# --- Daycare/Procedure rebuild (Step 1's catalog through the approval
# workflow and "Request Reschedule") ---
SELECT_PROCEDURE = "select_procedure"
VIEW_PROCEDURES_BUTTON = "view_procedures_button"
PROCEDURES_SECTION_TITLE = "procedures_section_title"
NO_PROCEDURES_CONFIGURED = "no_procedures_configured"
PROCEDURE_REQUEST_CONFIRM_SUMMARY = "procedure_request_confirm_summary"
PROCEDURE_REQUEST_SUBMITTED = "procedure_request_submitted"
PROCEDURE_APPROVED = "procedure_approved"
PROCEDURE_REJECTED = "procedure_rejected"
PROCEDURE_CONFIRMATION_SUMMARY = "procedure_confirmation_summary"
PROCEDURE_ESTIMATE_LINE = "procedure_estimate_line"
PROCEDURE_ORDER_REFERENCE_LINE = "procedure_order_reference_line"
PROCEDURE_INSTRUCTIONS_LINE = "procedure_instructions_line"
PROCEDURE_BOOKING_CONFIRMED = "procedure_booking_confirmed"
PROCEDURE_RESCHEDULE_REQUEST_PROMPT = "procedure_reschedule_request_prompt"
PROCEDURE_RESCHEDULE_REQUESTED = "procedure_reschedule_requested"
PROCEDURE_RESCHEDULE_APPROVED = "procedure_reschedule_approved"
PROCEDURE_RESCHEDULE_REJECTED = "procedure_reschedule_rejected"

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
        "en": "✅ {doctor_name} selected\nPlease choose your preferred appointment date.",
        "hi": "✅ {doctor_name} चुने गए\nकृपया अपनी पसंदीदा अपॉइंटमेंट की तारीख चुनें।",
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
    CONSULTATION_FEE_LINE: {"en": "💰 Consultation Fee: ₹{amount}\n\n", "hi": "💰 परामर्श शुल्क: ₹{amount}\n\n"},

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
        "en": "Please enter a valid name using letters only (3–50 characters).",
        "hi": "कृपया केवल अक्षरों का उपयोग करके एक मान्य नाम दर्ज करें (3–50 अक्षर)।",
    },
    ASK_PATIENT_CONTACT_NUMBER: {
        "en": "Please enter the patient's contact number",
        "hi": "कृपया मरीज का संपर्क नंबर दर्ज करें।",
    },
    INVALID_PATIENT_CONTACT_NUMBER: {
        "en": "Please enter a valid 10-digit contact number, digits only, not starting with 0.",
        "hi": "कृपया केवल अंकों में एक मान्य 10 अंकों का संपर्क नंबर दर्ज करें, जो 0 से शुरू न हो।",
    },
    ASK_PATIENT_AGE: {
        "en": "Please select the patient's age.",
        "hi": "कृपया मरीज की आयु दर्ज करें।",
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
        # fee_line: "💰 Consultation Fee: ₹{amount}\n\n" when hospital_settings.
        # new_consultation_fee is configured for a "new" (New Consultation)
        # booking, "" otherwise (flows/booking/messages.py's _send_confirmation
        # builds it) -- was a static "₹800 (if applicable)" placeholder before
        # a real per-hospital fee field existed; now sourced for real, and
        # omitted entirely (not shown as ₹0) when unset or not a New
        # Consultation booking.
        "en": (
            "*Confirm Booking Details:*\n"
            "👤 Patient: {patient_name}\n"
            "🆔 Patient Id: {patient_code}\n"
            "🎂 Age: {patient_age}\n"
            "📋 Appointment Type: {appointment_type_label}\n"
            "🏥 Department: {department_name}\n"
            "👨‍⚕️ Doctor: {doctor_name}\n"
            "📅 Date: {date_label}\n"
            "🕐 Time: {time_label}\n\n"
            "{fee_line}"
            "Please review the details before confirming your appointment."
        ),
        "hi": (
            "*बुकिंग विवरण की पुष्टि करें:*\n"
            "👤 मरीज़: {patient_name}\n"
            "🆔 पेशेंट आईडी: {patient_code}\n"
            "🎂 उम्र: {patient_age}\n"
            "📋 अपॉइंटमेंट प्रकार: {appointment_type_label}\n"
            "🏥 विभाग: {department_name}\n"
            "👨‍⚕️ डॉक्टर: {doctor_name}\n"
            "📅 तारीख: {date_label}\n"
            "🕐 समय: {time_label}\n\n"
            "{fee_line}"
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
    BOOKING_CONFIRMED: {
        "en": (
            "✅ *Appointment Confirmed*\n\n"
            "Your appointment has been successfully booked.\n\n"
            "🆔 Appointment ID: {reference_id}\n"
            "👤 Patient: {patient_name}\n"
            "🏥 Department: {department_name}\n"
            "👨‍⚕️ Doctor: {doctor_name}\n"
            "📅 Date: {date_label}\n"
            "🕐 Time: {time_label}\n\n"
            "Please arrive 15 minutes before your appointment.\n"
            "We look forward to seeing you."
        ),
        "hi": (
            "✅ *अपॉइंटमेंट की पुष्टि हो गई*\n\n"
            "आपकी अपॉइंटमेंट सफलतापूर्वक बुक हो गई है।\n\n"
            "🆔 अपॉइंटमेंट आईडी: {reference_id}\n"
            "👤 मरीज़: {patient_name}\n"
            "🏥 विभाग: {department_name}\n"
            "👨‍⚕️ डॉक्टर: {doctor_name}\n"
            "📅 तारीख: {date_label}\n"
            "🕐 समय: {time_label}\n\n"
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
    # docs/per-appointment-type-flow-plan.md Phase 2 Step 2 follow-up: the
    # eligible-consultations list -- one row per department's most recent
    # ATTENDED appointment still within the hospital's eligibility window.
    FOLLOWUP_ELIGIBLE_LIST_PROMPT: {
        "en": (
            "✅ *Follow-up Consultation Available*\n\n"
            "Below are {patient_name}'s latest eligible consultations for follow-up.\n"
            "For each department, only the most recent consultation is shown.\n\n"
            "Please select the consultation you would like to continue with."
        ),
        "hi": (
            "✅ *फॉलो-अप परामर्श उपलब्ध है*\n\n"
            "नीचे {patient_name} के फॉलो-अप के लिए नवीनतम योग्य परामर्श दिए गए हैं।\n"
            "प्रत्येक विभाग के लिए, केवल सबसे हालिया परामर्श दिखाया गया है।\n\n"
            "कृपया वह परामर्श चुनें जिसके साथ आप आगे बढ़ना चाहेंगे।"
        ),
    },
    VIEW_FOLLOWUP_OPTIONS_BUTTON: {"en": "View Options", "hi": "विकल्प देखें"},
    FOLLOWUP_ELIGIBLE_SECTION_TITLE: {"en": "Eligible Consultations", "hi": "योग्य परामर्श"},
    # fee_line: CONSULTATION_FEE_LINE-shaped ("💰 ...Fee: ₹{amount}\n\n") when
    # hospital_settings.followup_fee is configured, "" otherwise -- same
    # omit-rather-than-fake-₹0 discipline CONFIRM_BOOKING_SUMMARY's own
    # fee_line uses.
    FOLLOWUP_CONFIRMATION_SUMMARY: {
        "en": (
            "📋 *Confirm Follow-up Appointment*\n\n"
            "👤 Patient: {patient_name}\n"
            "🆔 Patient ID: {patient_code}\n"
            "📋 Appointment Type: {appointment_type_label}\n"
            "🏥 Department: {department_name}\n"
            "👨‍⚕️ Doctor: {doctor_name}\n"
            "🔁 Previous Visit: {previous_visit_label}\n"
            "📅 Appointment Date: {date_label}\n"
            "🕐 Time: {time_label}\n"
            "{fee_line}\n"
            "Please review the details before confirming."
        ),
        "hi": (
            "📋 *फॉलो-अप अपॉइंटमेंट की पुष्टि करें*\n\n"
            "👤 मरीज़: {patient_name}\n"
            "🆔 मरीज़ आईडी: {patient_code}\n"
            "📋 अपॉइंटमेंट प्रकार: {appointment_type_label}\n"
            "🏥 विभाग: {department_name}\n"
            "👨‍⚕️ डॉक्टर: {doctor_name}\n"
            "🔁 पिछली मुलाकात: {previous_visit_label}\n"
            "📅 अपॉइंटमेंट तारीख: {date_label}\n"
            "🕐 समय: {time_label}\n"
            "{fee_line}\n"
            "कृपया पुष्टि करने से पहले विवरण की समीक्षा करें।"
        ),
    },
    FOLLOWUP_APPOINTMENT_CONFIRMED: {
        "en": (
            "✅ *Follow-up Appointment Confirmed*\n\n"
            "Your follow-up consultation has been successfully booked.\n\n"
            "🆔 Appointment ID: {reference_id}\n"
            "👤 Patient: {patient_name}\n"
            "👨‍⚕️ Doctor: {doctor_name}\n"
            "🏥 Department: {department_name}\n"
            "📅 Date: {date_label}\n"
            "🕐 Time: {time_label}\n\n"
            "Please arrive 15 minutes before your appointment.\n\n"
            "We look forward to seeing you."
        ),
        "hi": (
            "✅ *फॉलो-अप अपॉइंटमेंट की पुष्टि हो गई*\n\n"
            "आपका फॉलो-अप परामर्श सफलतापूर्वक बुक हो गया है।\n\n"
            "🆔 अपॉइंटमेंट आईडी: {reference_id}\n"
            "👤 मरीज़: {patient_name}\n"
            "👨‍⚕️ डॉक्टर: {doctor_name}\n"
            "🏥 विभाग: {department_name}\n"
            "📅 तारीख: {date_label}\n"
            "🕐 समय: {time_label}\n\n"
            "कृपया अपनी अपॉइंटमेंट से 15 मिनट पहले पहुंचें।\n\n"
            "हम आपसे मिलने के लिए उत्सुक हैं।"
        ),
    },
    # Item 6 (Spec.md Section 0): shown after tapping one appointment in "My
    # Appointments" -- the same quick-action buttons item 3/5 use.
    MANAGE_APPOINTMENT_PROMPT: {
        "en": "Your appointment with {doctor_name} — what would you like to do?",
        "hi": "{doctor_name} के साथ आपकी अपॉइंटमेंट — आप क्या करना चाहेंगे?",
    },

    # --- Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md
    # Step 5): test selection -> variant selection -> date/time (resource-
    # linked when the test has one) -> confirm, with prep instructions
    # folded into the confirmation card. ---
    SELECT_DIAGNOSTIC_TEST: {
        "en": "Please select the test you would like to book.",
        "hi": "कृपया वह जांच चुनें जिसे आप बुक करना चाहते हैं।",
    },
    VIEW_TESTS_BUTTON: {"en": "View Tests", "hi": "जांच देखें"},
    DIAGNOSTIC_TESTS_SECTION_TITLE: {"en": "Tests", "hi": "जांच"},
    SELECT_DIAGNOSTIC_VARIANT: {
        "en": "Please select the specific type of {test_name}.",
        "hi": "कृपया {test_name} का विशिष्ट प्रकार चुनें।",
    },
    VIEW_VARIANTS_BUTTON: {"en": "View Options", "hi": "विकल्प देखें"},
    DIAGNOSTIC_VARIANTS_SECTION_TITLE: {"en": "Options", "hi": "विकल्प"},
    NO_DIAGNOSTIC_TESTS_CONFIGURED: {
        "en": "Sorry, no tests are available to book right now. Please check back later.",
        "hi": "क्षमा करें, अभी बुक करने के लिए कोई जांच उपलब्ध नहीं है। कृपया बाद में फिर से देखें।",
    },
    CHANGE_DIAGNOSTIC_TEST_OPTION: {"en": "Test", "hi": "जांच"},
    CHANGE_DIAGNOSTIC_VARIANT_OPTION: {"en": "Test Option", "hi": "जांच विकल्प"},
    DIAGNOSTIC_AMOUNT_LINE: {"en": "💰 Amount: ₹{amount}\n", "hi": "💰 राशि: ₹{amount}\n"},
    DIAGNOSTIC_PREPARATION_LINE: {
        "en": "📝 *Preparation:* {instructions}\n\n",
        "hi": "📝 *तैयारी:* {instructions}\n\n",
    },
    # amount_line/prep_line: built by _diagnostic_shared.py, "" when unset --
    # same omit-rather-than-fake-value discipline as fee_line elsewhere.
    DIAGNOSTIC_CONFIRMATION_SUMMARY: {
        "en": (
            "🔬 *Review {appointment_type_label} Booking*\n\n"
            "👤 Patient: {patient_name}\n"
            "🆔 Patient ID: {patient_code}\n"
            "🧪 Test: {test_name}\n"
            "🧾 Option: {variant_label}\n"
            "🏥 Location: {hospital_name}\n"
            "📅 Date: {date_label}\n"
            "🕐 Time: {time_label}\n"
            "{amount_line}"
            "{prep_line}"
            "Please review the details and preparation instructions before confirming."
        ),
        "hi": (
            "🔬 *{appointment_type_label} बुकिंग की समीक्षा करें*\n\n"
            "👤 मरीज़: {patient_name}\n"
            "🆔 मरीज़ आईडी: {patient_code}\n"
            "🧪 जांच: {test_name}\n"
            "🧾 विकल्प: {variant_label}\n"
            "🏥 स्थान: {hospital_name}\n"
            "📅 तारीख: {date_label}\n"
            "🕐 समय: {time_label}\n"
            "{amount_line}"
            "{prep_line}"
            "कृपया पुष्टि करने से पहले विवरण और तैयारी निर्देशों की समीक्षा करें।"
        ),
    },
    DIAGNOSTIC_BOOKING_CONFIRMED: {
        "en": (
            "✅ *{appointment_type_label} Booked*\n\n"
            "🆔 Booking ID: {reference_id}\n"
            "👤 Patient: {patient_name}\n"
            "🧪 Test: {test_name}\n"
            "🧾 Option: {variant_label}\n"
            "📅 Date: {date_label}\n"
            "🕐 Time: {time_label}\n\n"
            "Please arrive at the instructed time and follow the preparation guidance provided."
        ),
        "hi": (
            "✅ *{appointment_type_label} बुक हो गई*\n\n"
            "🆔 बुकिंग आईडी: {reference_id}\n"
            "👤 मरीज़: {patient_name}\n"
            "🧪 जांच: {test_name}\n"
            "🧾 विकल्प: {variant_label}\n"
            "📅 तारीख: {date_label}\n"
            "🕐 समय: {time_label}\n\n"
            "कृपया निर्देशित समय पर पहुंचें और दी गई तैयारी संबंधी जानकारी का पालन करें।"
        ),
    },

    # --- Lab Test Phase 2 follow-up: multi-test basket -> collection method
    # (visit vs. home sample, serviceability-gated) -> date/time -> confirm,
    # with an itemized price review and a conditional fasting/prep paragraph. ---
    SELECT_LAB_TEST: {
        "en": "Please select a test to add to your booking.",
        "hi": "कृपया अपनी बुकिंग में जोड़ने के लिए एक जांच चुनें।",
    },
    # WhatsApp menu restructuring follow-up (confirmed with the user): shown
    # as the remaining-tests LIST's own body text, not a separate "would you
    # like to add another test?" buttons detour -- picking another test
    # happens straight from that list, with "Done, Continue" offered
    # alongside "Back" underneath once the basket has at least one item.
    LAB_TEST_ADDED_PROMPT: {
        "en": "Added *{item_label}* to your booking.\n\nSelect another test below, or tap \"Done, Continue\" when you're finished.",
        "hi": "*{item_label}* आपकी बुकिंग में जोड़ दी गई है।\n\nनीचे से एक और जांच चुनें, या पूरा होने पर \"हो गया, आगे बढ़ें\" पर टैप करें।",
    },
    LAB_DONE_BUTTON: {"en": "Done, Continue", "hi": "हो गया, आगे बढ़ें"},
    SELECT_COLLECTION_METHOD: {
        "en": "How would you like to provide your sample?",
        "hi": "आप अपना सैंपल कैसे देना चाहेंगे?",
    },
    COLLECTION_VISIT_BUTTON: {"en": "Visit Hospital/Lab", "hi": "अस्पताल/लैब जाएं"},
    COLLECTION_HOME_BUTTON: {"en": "Home Collection", "hi": "होम कलेक्शन"},
    ASK_COLLECTION_PINCODE: {
        "en": "Please enter your area PIN code so we can check home-collection availability.",
        "hi": "कृपया अपना क्षेत्र पिन कोड दर्ज करें ताकि हम होम कलेक्शन की उपलब्धता जांच सकें।",
    },
    NOT_SERVICEABLE_PINCODE: {
        "en": "Sorry, home sample collection isn't available in your area yet. "
              "You can visit the hospital/lab instead, or try a different PIN code.",
        "hi": "क्षमा करें, आपके क्षेत्र में अभी होम सैंपल कलेक्शन उपलब्ध नहीं है। "
              "आप इसके बजाय अस्पताल/लैब जा सकते हैं, या कोई अन्य पिन कोड आज़मा सकते हैं।",
    },
    TRY_ANOTHER_PINCODE_BUTTON: {"en": "Try Another PIN", "hi": "अन्य पिन आज़माएं"},
    ASK_COLLECTION_ADDRESS: {
        "en": "Please enter the full address where the sample should be collected.",
        "hi": "कृपया वह पूरा पता दर्ज करें जहां सैंपल एकत्र किया जाना चाहिए।",
    },
    ASK_COLLECTION_ADDRESS_WITH_SUGGESTION: {
        "en": "Please enter the full address where the sample should be collected, "
              "or reply \"same\" to use your address on file:\n{address}",
        "hi": "कृपया वह पूरा पता दर्ज करें जहां सैंपल एकत्र किया जाना चाहिए, "
              "या अपने दर्ज पते का उपयोग करने के लिए \"same\" लिखें:\n{address}",
    },
    CHANGE_COLLECTION_METHOD_OPTION: {"en": "Collection Method", "hi": "कलेक्शन तरीका"},
    # tests_block/collection_line/amount_block/fasting_block: built by
    # flows/booking/types/lab.py, "" when not applicable -- same
    # omit-rather-than-fake-value discipline every other card in this file uses.
    LAB_CONFIRMATION_SUMMARY: {
        "en": (
            "🔬 *Review {appointment_type_label} Booking*\n\n"
            "👤 Patient: {patient_name}\n"
            "🆔 Patient ID: {patient_code}\n"
            "{tests_block}"
            "{collection_line}"
            "📅 Date: {date_label}\n"
            "🕐 Time: {time_label}\n"
            "{amount_block}"
            "{fasting_block}"
            "Please review the details before confirming your booking."
        ),
        "hi": (
            "🔬 *{appointment_type_label} बुकिंग की समीक्षा करें*\n\n"
            "👤 मरीज़: {patient_name}\n"
            "🆔 मरीज़ आईडी: {patient_code}\n"
            "{tests_block}"
            "{collection_line}"
            "📅 तारीख: {date_label}\n"
            "🕐 समय: {time_label}\n"
            "{amount_block}"
            "{fasting_block}"
            "कृपया पुष्टि करने से पहले विवरण की समीक्षा करें।"
        ),
    },
    LAB_TEST_CHARGES_LINE: {"en": "💰 Test Charges: ₹{amount}\n", "hi": "💰 जांच शुल्क: ₹{amount}\n"},
    LAB_HOME_COLLECTION_LINE: {"en": "🏠 Home Collection: ₹{amount}\n", "hi": "🏠 होम कलेक्शन: ₹{amount}\n"},
    LAB_TOTAL_LINE: {"en": "🧾 Total: ₹{amount}\n\n", "hi": "🧾 कुल: ₹{amount}\n\n"},
    LAB_FASTING_LINE: {
        "en": "📝 *Preparation:* {instructions}\n\n",
        "hi": "📝 *तैयारी:* {instructions}\n\n",
    },
    LAB_BOOKING_CONFIRMED: {
        "en": (
            "✅ *{appointment_type_label} Booked*\n\n"
            "🆔 Booking ID: {reference_id}\n"
            "👤 Patient: {patient_name}\n"
            "🧪 Tests: {test_count}\n"
            "{collection_line}"
            "📅 Date: {date_label}\n"
            "🕐 Time: {time_label}\n\n"
            "We'll notify you here on WhatsApp the moment your report is ready."
        ),
        "hi": (
            "✅ *{appointment_type_label} बुक हो गई*\n\n"
            "🆔 बुकिंग आईडी: {reference_id}\n"
            "👤 मरीज़: {patient_name}\n"
            "🧪 जांच: {test_count}\n"
            "{collection_line}"
            "📅 तारीख: {date_label}\n"
            "🕐 समय: {time_label}\n\n"
            "आपकी रिपोर्ट तैयार होते ही हम आपको यहीं WhatsApp पर सूचित करेंगे।"
        ),
    },
    SELECT_PROCEDURE: {
        "en": "Please select the treatment or procedure recommended by your doctor.",
        "hi": "कृपया अपने डॉक्टर द्वारा सुझाई गई उपचार या प्रक्रिया चुनें।",
    },
    VIEW_PROCEDURES_BUTTON: {"en": "View Procedures", "hi": "प्रक्रियाएं देखें"},
    PROCEDURES_SECTION_TITLE: {"en": "Procedures", "hi": "प्रक्रियाएं"},
    NO_PROCEDURES_CONFIGURED: {
        "en": "Sorry, no procedures are available to book right now. Please check back later.",
        "hi": "क्षमा करें, अभी बुक करने के लिए कोई प्रक्रिया उपलब्ध नहीं है। कृपया बाद में फिर से देखें।",
    },
    # amount_line/order_line/instructions_line: built by procedure.py, "" when
    # unset -- same omit-rather-than-fake-value discipline as fee_line/
    # amount_line elsewhere.
    PROCEDURE_REQUEST_CONFIRM_SUMMARY: {
        "en": (
            "📋 *Review Your Request*\n\n"
            "👤 Patient: {patient_name}\n"
            "🩺 Procedure: {procedure_name}\n"
            "{estimate_line}"
            "{instructions_line}"
            "This procedure requires hospital verification before a slot is confirmed. "
            "Please review the details above before sending your request."
        ),
        "hi": (
            "📋 *अपना अनुरोध जांचें*\n\n"
            "👤 मरीज़: {patient_name}\n"
            "🩺 प्रक्रिया: {procedure_name}\n"
            "{estimate_line}"
            "{instructions_line}"
            "इस प्रक्रिया के लिए स्लॉट कन्फर्म होने से पहले अस्पताल की मंजूरी आवश्यक है। "
            "कृपया अनुरोध भेजने से पहले ऊपर दिए गए विवरण जांच लें।"
        ),
    },
    PROCEDURE_REQUEST_SUBMITTED: {
        "en": (
            "Your request for the selected procedure has been sent to the hospital for verification.\n\n"
            "We will notify you once the request is approved and eligible slots are available."
        ),
        "hi": (
            "चुनी गई प्रक्रिया के लिए आपका अनुरोध सत्यापन हेतु अस्पताल को भेज दिया गया है।\n\n"
            "अनुरोध स्वीकृत होने और स्लॉट उपलब्ध होने पर हम आपको सूचित करेंगे।"
        ),
    },
    PROCEDURE_APPROVED: {
        "en": (
            "Your procedure request has been approved.\n\n"
            "Please select an available date and time to continue with the booking."
        ),
        "hi": (
            "आपकी प्रक्रिया का अनुरोध स्वीकृत कर दिया गया है।\n\n"
            "बुकिंग जारी रखने के लिए कृपया एक उपलब्ध तारीख और समय चुनें।"
        ),
    },
    PROCEDURE_REJECTED: {
        "en": "Your request for {procedure_name} could not be approved at this time.{reason_line}",
        "hi": "इस समय {procedure_name} के लिए आपका अनुरोध स्वीकृत नहीं किया जा सका।{reason_line}",
    },
    PROCEDURE_CONFIRMATION_SUMMARY: {
        "en": (
            "🩺 *Review {appointment_type_label} Booking*\n\n"
            "👤 Patient: {patient_name}\n"
            "🆔 Patient ID: {patient_code}\n"
            "Procedure: {procedure_name}\n"
            "{order_reference_line}"
            "🏥 Location: {department_name}\n"
            "📅 Date: {date_label}\n"
            "🕐 Time: {time_label}\n"
            "{estimate_line}"
            "{instructions_line}"
            "Please review the details before confirming your booking."
        ),
        "hi": (
            "🩺 *{appointment_type_label} बुकिंग जांचें*\n\n"
            "👤 मरीज़: {patient_name}\n"
            "🆔 मरीज़ आईडी: {patient_code}\n"
            "प्रक्रिया: {procedure_name}\n"
            "{order_reference_line}"
            "🏥 स्थान: {department_name}\n"
            "📅 तारीख: {date_label}\n"
            "🕐 समय: {time_label}\n"
            "{estimate_line}"
            "{instructions_line}"
            "कृपया बुकिंग कन्फर्म करने से पहले विवरण जांच लें।"
        ),
    },
    PROCEDURE_ESTIMATE_LINE: {
        "en": "💰 Estimated Charges: ₹{amount}\nNote: Medicines, consumables, investigations, or additional services may affect the final charge.\n\n",
        "hi": "💰 अनुमानित शुल्क: ₹{amount}\nनोट: दवाइयां, उपभोग्य सामग्री, जांच, या अतिरिक्त सेवाएं अंतिम शुल्क को प्रभावित कर सकती हैं।\n\n",
    },
    PROCEDURE_ORDER_REFERENCE_LINE: {"en": "🔗 Linked Order: {order_reference}\n", "hi": "🔗 संबंधित आदेश: {order_reference}\n"},
    PROCEDURE_INSTRUCTIONS_LINE: {
        "en": "📝 *Please note:* {instructions}\n\n",
        "hi": "📝 *कृपया ध्यान दें:* {instructions}\n\n",
    },
    PROCEDURE_BOOKING_CONFIRMED: {
        "en": (
            "✅ *Daycare / Procedure Booking Confirmed*\n"
            "Booking ID: {reference_id}\n"
            "Patient: {patient_name}\n"
            "Procedure: {procedure_name}\n"
            "Department: {department_name}\n"
            "Date: {date_label}\n"
            "Time: {time_label}\n\n"
            "Please arrive as instructed and carry the required documents/orders."
        ),
        "hi": (
            "✅ *डेकेयर / प्रक्रिया बुकिंग कन्फर्म*\n"
            "बुकिंग आईडी: {reference_id}\n"
            "मरीज़: {patient_name}\n"
            "प्रक्रिया: {procedure_name}\n"
            "विभाग: {department_name}\n"
            "तारीख: {date_label}\n"
            "समय: {time_label}\n\n"
            "कृपया निर्देशानुसार समय पर पहुंचें और आवश्यक दस्तावेज़/आदेश साथ लाएं।"
        ),
    },
    PROCEDURE_RESCHEDULE_REQUEST_PROMPT: {
        "en": "Please select your preferred new date and time. This procedure requires hospital approval before the change is confirmed.",
        "hi": "कृपया अपनी पसंदीदा नई तारीख और समय चुनें। इस प्रक्रिया में बदलाव कन्फर्म होने से पहले अस्पताल की मंजूरी आवश्यक है।",
    },
    PROCEDURE_RESCHEDULE_REQUESTED: {
        "en": "Your reschedule request has been sent to the hospital for approval. We will notify you once it's confirmed.",
        "hi": "आपका रीशेड्यूल अनुरोध अस्पताल को मंजूरी हेतु भेज दिया गया है। कन्फर्म होते ही हम आपको सूचित करेंगे।",
    },
    PROCEDURE_RESCHEDULE_APPROVED: {
        "en": (
            "✅ Your reschedule request has been approved.\n"
            "New Date: {date_label}\nNew Time: {time_label}"
        ),
        "hi": (
            "✅ आपका रीशेड्यूल अनुरोध स्वीकृत कर दिया गया है।\n"
            "नई तारीख: {date_label}\nनया समय: {time_label}"
        ),
    },
    PROCEDURE_RESCHEDULE_REJECTED: {
        "en": "Your reschedule request could not be approved. Your original appointment remains unchanged.",
        "hi": "आपका रीशेड्यूल अनुरोध स्वीकृत नहीं किया जा सका। आपकी मूल अपॉइंटमेंट अपरिवर्तित है।",
    },
}

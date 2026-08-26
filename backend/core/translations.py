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

    # --- My Details (patient identity system, Spec.md Section 0): a
    # self-service "look up my own record" feature, alongside view_appointments
    # above rather than replacing it -- that one shows upcoming bookings with
    # cancel/reschedule actions; this one shows identity/summary info and any
    # documents on file. ---
    "feature_my_details": {"en": "My Details", "hi": "मेरी जानकारी"},
    "my_details_not_found": {
        "en": "We don't have a record on file for this number yet at this hospital. "
              "Book an appointment first and we'll create one for you.",
        "hi": "इस अस्पताल में इस नंबर के लिए अभी तक कोई रिकॉर्ड नहीं है। "
              "पहले एक अपॉइंटमेंट बुक करें, हम आपके लिए एक रिकॉर्ड बना देंगे।",
    },
    # {summary_lines} is a pre-built block of "*Label:* value" lines (Patient
    # ID, Name, Age, Total appointments, Most recent) -- not templated field
    # by field here, since "most recent" needs a formatted date/status pair
    # assembled in code (core/translations.py deliberately has no date-
    # formatting logic of its own, same reasoning as every other computed-
    # value split in this file, e.g. slot_label).
    "my_details_summary": {
        "en": "Here are your details on file:\n\n{summary_lines}",
        "hi": "यहां आपकी दर्ज जानकारी है:\n\n{summary_lines}",
    },
    "my_details_field_patient_id": {"en": "Patient ID", "hi": "पेशेंट आईडी"},
    "my_details_field_name": {"en": "Name", "hi": "नाम"},
    "my_details_field_age": {"en": "Age", "hi": "आयु"},
    "my_details_field_total_appointments": {"en": "Total appointments", "hi": "कुल अपॉइंटमेंट"},
    "my_details_field_most_recent": {"en": "Most recent", "hi": "सबसे हाल की"},
    "my_details_not_provided": {"en": "Not provided", "hi": "दर्ज नहीं"},
    "my_details_no_appointments_yet": {"en": "None yet", "hi": "अभी कोई नहीं"},
    "status_booked": {"en": "Confirmed", "hi": "पुष्ट"},
    "status_cancelled": {"en": "Cancelled", "hi": "रद्द"},
    "status_rescheduled": {"en": "Rescheduled", "hi": "समय बदला गया"},
    "status_attended": {"en": "Attended", "hi": "उपस्थित"},
    "status_no_show": {"en": "No-show", "hi": "अनुपस्थित"},
    "my_details_documents_header": {
        "en": "You also have documents on file. Tap one to receive it here:",
        "hi": "आपकी फाइल में दस्तावेज़ भी हैं। यहां प्राप्त करने के लिए एक पर टैप करें:",
    },
    "view_documents_button": {"en": "View Documents", "hi": "दस्तावेज़ देखें"},
    "documents_section_title": {"en": "Your Documents", "hi": "आपके दस्तावेज़"},
    "my_details_document_sent": {
        "en": "Sent! Check your chat for the document.",
        "hi": "भेज दिया गया! दस्तावेज़ के लिए अपनी चैट देखें।",
    },
    "my_details_document_send_failed": {
        "en": "Sorry, we couldn't send that document right now. Please try again later or contact the hospital.",
        "hi": "क्षमा करें, हम अभी वह दस्तावेज़ नहीं भेज सके। कृपया बाद में पुनः प्रयास करें या अस्पताल से संपर्क करें।",
    },

    # "Go back" navigation (Spec.md Section 0 follow-up): one shared button
    # label -- the 3rd button on the confirmation card (Meta's 3-button max),
    # and (a later UX follow-up, Spec.md Section 0) the department/doctor/
    # date/time menus' own follow-up Back-button message (_send_back_button),
    # sent as its own message right after the list rather than a row inside
    # it. Reused as that message's body text too -- no separate prompt line,
    # no "◀" arrow, both dropped per the user's own request.
    # Reused as both this message's body text AND its one button's label.
    "back_option": {"en": "Back", "hi": "पीछे"},

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

    # --- Patient identity SEPARATION (Spec.md Section 0): the shared "who is
    # this for" selector, shown whenever a phone has >1 active linked
    # patient, ahead of booking/cancel/reschedule/view_appointments. One
    # prompt per next_action -- the body text differs slightly by what's
    # about to happen, but the list itself (rows + button + section title)
    # is otherwise identical across all four. ---
    "patient_selector_prompt_booking": {
        "en": "Who is this appointment for?",
        "hi": "यह अपॉइंटमेंट किसके लिए है?",
    },
    "patient_selector_prompt_cancel": {
        "en": "Whose appointment would you like to cancel?",
        "hi": "आप किसकी अपॉइंटमेंट रद्द करना चाहते हैं?",
    },
    "patient_selector_prompt_reschedule": {
        "en": "Whose appointment would you like to reschedule?",
        "hi": "आप किसकी अपॉइंटमेंट का समय बदलना चाहते हैं?",
    },
    "patient_selector_prompt_view_appointments": {
        "en": "Whose appointments would you like to see?",
        "hi": "आप किसकी अपॉइंटमेंट देखना चाहते हैं?",
    },
    "patient_selector_button": {"en": "Select Patient", "hi": "मरीज़ चुनें"},
    "patient_selector_section_title": {"en": "Patients", "hi": "मरीज़"},
    "add_patient_option": {"en": "+ Add Patient", "hi": "+ मरीज़ जोड़ें"},
    "all_patients_option": {"en": "All Patients", "hi": "सभी मरीज़"},
    "too_many_linked_patients": {
        "en": "This phone number already has 5 linked patients — the maximum allowed. "
              "Unlink someone first if you'd like to add another.",
        "hi": "इस फोन नंबर पर पहले से ही 5 मरीज़ जुड़े हुए हैं — यह अधिकतम सीमा है। "
              "किसी और को जोड़ने के लिए पहले किसी एक को अनलिंक करें।",
    },

    # --- Manage Patients (Spec.md Section 0): view/add/unlink the patients
    # linked to this phone. Add reuses ask_patient_name/ask_patient_age
    # above (patient_flow_next="manage_patients"); unlink reuses
    # confirm_button/cancel_button as its Yes/No labels, same convention the
    # cancel/reschedule confirmation cards already use. ---
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

    # --- CareConnect architecture doc alignment (Spec.md Section 0):
    # resolution now happens ONCE per conversation, before the main menu --
    # patient_selector_prompt below replaces the 4 action-specific
    # patient_selector_prompt_* keys above (still left in place, unreachable
    # but harmless, same "orphaned key" precedent CHANGE_LANGUAGE_ROW's own
    # comment already established). ---
    "patient_header_label": {"en": "Patient:", "hi": "मरीज़:"},
    "patient_selector_prompt": {
        "en": "Who are you accessing CareConnect for?",
        "hi": "आप CareConnect किसके लिए इस्तेमाल कर रहे हैं?",
    },
    "manage_patients_short": {"en": "Manage Patients", "hi": "मरीज़ प्रबंधित करें"},
    "add_patient_short": {"en": "Add Patient", "hi": "मरीज़ जोड़ें"},
    "back_to_menu_option": {"en": "Back to Menu", "hi": "मेनू पर वापस"},
    "registration_blocked_contact_hospital": {
        "en": "This phone number already has the maximum number of linked patients. Please contact the hospital directly.",
        "hi": "इस फोन नंबर पर पहले से ही अधिकतम मरीज़ जुड़े हुए हैं। कृपया सीधे अस्पताल से संपर्क करें।",
    },
    "patient_context_invalid": {
        "en": "This patient is no longer linked to this number. Please send any message to start over.",
        "hi": "यह मरीज़ अब इस नंबर से जुड़ा नहीं है। कृपया फिर से शुरू करने के लिए कोई भी संदेश भेजें।",
    },

    # --- Sections 8-10: duplicate-patient detection before creating a new profile ---
    "duplicate_patient_found": {
        "en": "We found an existing hospital profile that may match:\n\n*{name}*\nMRN: {mrn}\n\n"
              "Would you like to link this profile, or is this a different patient?",
        "hi": "हमें एक मौजूदा अस्पताल प्रोफ़ाइल मिली जो मेल खा सकती है:\n\n*{name}*\nMRN: {mrn}\n\n"
              "क्या आप इस प्रोफ़ाइल को लिंक करना चाहेंगे, या यह एक अलग मरीज़ है?",
    },
    "duplicate_link_button": {"en": "Link Existing", "hi": "लिंक करें"},
    "duplicate_different_button": {"en": "Different Patient", "hi": "अलग मरीज़"},

    # --- Section 17: structured relationship field (RELATIONSHIP_OPTIONS in
    # db/repository.py is the single source of truth these keys mirror) ---
    "ask_relationship": {
        "en": "What is this patient's relationship to you?",
        "hi": "यह मरीज़ आपसे किस रिश्ते में है?",
    },
    "ask_relationship_button": {"en": "Select", "hi": "चुनें"},
    "ask_relationship_section_title": {"en": "Relationship", "hi": "रिश्ता"},
    "relationship_self": {"en": "Self", "hi": "स्वयं"},
    "relationship_mother": {"en": "Mother", "hi": "माँ"},
    "relationship_father": {"en": "Father", "hi": "पिता"},
    "relationship_son": {"en": "Son", "hi": "बेटा"},
    "relationship_daughter": {"en": "Daughter", "hi": "बेटी"},
    "relationship_spouse": {"en": "Spouse", "hi": "जीवनसाथी"},
    "relationship_guardian": {"en": "Guardian", "hi": "अभिभावक"},
    "relationship_other": {"en": "Other", "hi": "अन्य"},

    # --- Section 11: optional single-linked-patient confirmation
    # (hospitals.require_patient_confirmation, default off) ---
    "single_patient_confirm": {
        "en": "Welcome to CareConnect.\n\nYou are accessing services for:\n\n*{patient_name}*\nMRN: {mrn}\n\nContinue?",
        "hi": "CareConnect में आपका स्वागत है।\n\nआप इनके लिए सेवाएं प्राप्त कर रहे हैं:\n\n*{patient_name}*\nMRN: {mrn}\n\nजारी रखें?",
    },

    # --- DPDP Act consent gate (hospitals.dpdp_consent_required, default
    # off) -- shown right after language selection, before any patient
    # identity is resolved, for a hospital that has turned this on. Only
    # "I Agree" is ever persisted (db/schema.sql's own comment on
    # dpdp_consents explains why); the exact copy here was given verbatim,
    # not drafted -- do not reword without checking with the user first,
    # since this is compliance-facing text. ---
    "dpdp_consent_body": {
        "en": (
            "Welcome to the {hospital_name} Booking Bot!\n\n"
            "Your privacy is important to us. In compliance with the Digital Personal Data Protection (DPDP) Act, "
            "we need your explicit consent before we begin:\n\n"
            "* We will securely store your name, phone number, age, and doctor preferences to manage your "
            "appointments and send medical reminders.\n"
            "* Your data remains strictly confidential and will never be shared with third parties.\n"
            "* You can request the removal of your data at any time by texting \"DELETE\".\n\n"
            "Please select an option below to proceed:"
        ),
        "hi": (
            "नमस्ते! {hospital_name} बुकिंग बोट में आपका स्वागत है।\n\n"
            "आपकी गोपनीयता हमारे लिए महत्वपूर्ण है। डिजिटल व्यक्तिगत डेटा संरक्षण (DPDP) अधिनियम के तहत, "
            "आगे बढ़ने से पहले हमें आपकी सहमति की आवश्यकता है:\n\n"
            "* हम आपका नाम, फ़ोन नंबर, उम्र और डॉक्टर की पसंद जैसी जानकारी आपके अपॉइंटमेंट बुक करने और आपको "
            "मेडिकल रिमाइंडर भेजने के लिए सुरक्षित रूप से जमा (store) करेंगे।\n"
            "* आपका डेटा पूरी तरह से सुरक्षित रहेगा और इसे किसी बाहरी संस्था के साथ साझा (share) नहीं किया जाएगा।\n"
            "* आप जब चाहें \"DELETE\" लिखकर अपना डेटा हटाने का अनुरोध कर सकते हैं।\n\n"
            "आगे बढ़ने के लिए कृपया नीचे दिए गए विकल्पों में से एक चुनें:"
        ),
    },
    "dpdp_agree_button": {"en": "I Agree", "hi": "मैं सहमत हूँ"},
    "dpdp_decline_button": {"en": "I Do Not Agree", "hi": "मैं सहमत नहीं हूँ"},
    "dpdp_declined_message": {
        "en": "No problem — we can't proceed without your consent to store this information, so we're unable to "
              "continue right now. Message us again anytime if you change your mind.",
        "hi": "कोई बात नहीं — इस जानकारी को सुरक्षित रखने की आपकी सहमति के बिना हम आगे नहीं बढ़ सकते, इसलिए अभी जारी "
              "रखना संभव नहीं है। यदि आप अपना मन बदलें, तो कभी भी दोबारा संदेश भेजें।",
    },

    # --- Section 20's "Consent & Privacy" menu item -- kept intentionally
    # minimal (a real status display + one genuine toggle, not a full
    # legal consent-management platform). Service consent and marketing
    # consent are shown/controlled separately, never bundled, per the doc's
    # own explicit instruction. ---
    "privacy_notice_default": {
        "en": "We use WhatsApp to help manage your appointments and hospital communication. "
              "Your information is used only for the services you request and is not shared with third parties "
              "without your consent.",
        "hi": "हम आपकी अपॉइंटमेंट और अस्पताल संचार प्रबंधित करने के लिए व्हाट्सएप का उपयोग करते हैं। "
              "आपकी जानकारी केवल आपके अनुरोध की गई सेवाओं के लिए उपयोग की जाती है और आपकी सहमति के बिना "
              "किसी तीसरे पक्ष के साथ साझा नहीं की जाती।",
    },
    "consent_privacy_body": {
        "en": "*Privacy Notice*\n{notice}\n\n*Consent Status*\nMarketing messages: {marketing_status}",
        "hi": "*गोपनीयता सूचना*\n{notice}\n\n*सहमति की स्थिति*\nमार्केटिंग संदेश: {marketing_status}",
    },
    "consent_on": {"en": "Enabled", "hi": "सक्षम"},
    "consent_off": {"en": "Disabled", "hi": "अक्षम"},
    "consent_marketing_enable": {"en": "Enable Marketing", "hi": "मार्केटिंग चालू करें"},
    "consent_marketing_disable": {"en": "Disable Marketing", "hi": "मार्केटिंग बंद करें"},

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

# core/translations/my_details.py
"""My Details (patient identity system, Spec.md Section 0): a self-service
"look up my own record" feature, alongside "view appointments" (menu.py)
rather than replacing it -- that one shows upcoming bookings with cancel/
reschedule actions; this one shows identity/summary info and any documents
on file. status_* labels are also reused by the appointments list itself."""
from core.translations._common import Language


FEATURE_MY_DETAILS = "feature_my_details"
MY_DETAILS_NOT_FOUND = "my_details_not_found"
MY_DETAILS_SUMMARY = "my_details_summary"
MY_DETAILS_FIELD_PATIENT_ID = "my_details_field_patient_id"
MY_DETAILS_FIELD_NAME = "my_details_field_name"
MY_DETAILS_FIELD_AGE = "my_details_field_age"
MY_DETAILS_FIELD_TOTAL_APPOINTMENTS = "my_details_field_total_appointments"
MY_DETAILS_FIELD_MOST_RECENT = "my_details_field_most_recent"
MY_DETAILS_NOT_PROVIDED = "my_details_not_provided"
MY_DETAILS_NO_APPOINTMENTS_YET = "my_details_no_appointments_yet"
STATUS_BOOKED = "status_booked"
STATUS_CANCELLED = "status_cancelled"
STATUS_RESCHEDULED = "status_rescheduled"
STATUS_ATTENDED = "status_attended"
STATUS_NO_SHOW = "status_no_show"
MY_DETAILS_DOCUMENTS_HEADER = "my_details_documents_header"
VIEW_DOCUMENTS_BUTTON = "view_documents_button"
DOCUMENTS_SECTION_TITLE = "documents_section_title"
MY_DETAILS_DOCUMENT_SENT = "my_details_document_sent"
MY_DETAILS_DOCUMENT_SEND_FAILED = "my_details_document_send_failed"

STRINGS: dict[str, dict[Language, str]] = {
    FEATURE_MY_DETAILS: {"en": "My Details", "hi": "मेरी जानकारी"},
    MY_DETAILS_NOT_FOUND: {
        "en": "We don't have a record on file for this number yet at this hospital. "
              "Book an appointment first and we'll create one for you.",
        "hi": "इस अस्पताल में इस नंबर के लिए अभी तक कोई रिकॉर्ड नहीं है। "
              "पहले एक अपॉइंटमेंट बुक करें, हम आपके लिए एक रिकॉर्ड बना देंगे।",
    },
    # {summary_lines} is a pre-built block of "*Label:* value" lines (Patient
    # ID, Name, Age, Total appointments, Most recent) -- not templated field
    # by field here, since "most recent" needs a formatted date/status pair
    # assembled in code (this package deliberately has no date-formatting
    # logic of its own, same reasoning as every other computed-value split
    # in these files, e.g. slot_label).
    MY_DETAILS_SUMMARY: {
        "en": "Here are your details on file:\n\n{summary_lines}",
        "hi": "यहां आपकी दर्ज जानकारी है:\n\n{summary_lines}",
    },
    MY_DETAILS_FIELD_PATIENT_ID: {"en": "Patient ID", "hi": "पेशेंट आईडी"},
    MY_DETAILS_FIELD_NAME: {"en": "Name", "hi": "नाम"},
    MY_DETAILS_FIELD_AGE: {"en": "Age", "hi": "आयु"},
    MY_DETAILS_FIELD_TOTAL_APPOINTMENTS: {"en": "Total appointments", "hi": "कुल अपॉइंटमेंट"},
    MY_DETAILS_FIELD_MOST_RECENT: {"en": "Most recent", "hi": "सबसे हाल की"},
    MY_DETAILS_NOT_PROVIDED: {"en": "Not provided", "hi": "दर्ज नहीं"},
    MY_DETAILS_NO_APPOINTMENTS_YET: {"en": "None yet", "hi": "अभी कोई नहीं"},
    STATUS_BOOKED: {"en": "Confirmed", "hi": "पुष्ट"},
    STATUS_CANCELLED: {"en": "Cancelled", "hi": "रद्द"},
    STATUS_RESCHEDULED: {"en": "Rescheduled", "hi": "समय बदला गया"},
    STATUS_ATTENDED: {"en": "Attended", "hi": "उपस्थित"},
    STATUS_NO_SHOW: {"en": "No-show", "hi": "अनुपस्थित"},
    MY_DETAILS_DOCUMENTS_HEADER: {
        "en": "You also have documents on file. Tap one to receive it here:",
        "hi": "आपकी फाइल में दस्तावेज़ भी हैं। यहां प्राप्त करने के लिए एक पर टैप करें:",
    },
    VIEW_DOCUMENTS_BUTTON: {"en": "View Documents", "hi": "दस्तावेज़ देखें"},
    DOCUMENTS_SECTION_TITLE: {"en": "Your Documents", "hi": "आपके दस्तावेज़"},
    MY_DETAILS_DOCUMENT_SENT: {
        "en": "Sent! Check your chat for the document.",
        "hi": "भेज दिया गया! दस्तावेज़ के लिए अपनी चैट देखें।",
    },
    MY_DETAILS_DOCUMENT_SEND_FAILED: {
        "en": "Sorry, we couldn't send that document right now. Please try again later or contact the hospital.",
        "hi": "क्षमा करें, हम अभी वह दस्तावेज़ नहीं भेज सके। कृपया बाद में पुनः प्रयास करें या अस्पताल से संपर्क करें।",
    },
}

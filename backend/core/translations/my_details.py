# core/translations/my_details.py
"""My Details (patient identity system, Spec.md Section 0): a self-service
"look up my own record" feature, alongside "view appointments" (menu.py)
rather than replacing it -- that one shows upcoming bookings with cancel/
reschedule actions; this one shows identity/summary info and any documents
on file. status_* labels are also reused by the appointments list itself."""
from core.translations._common import Language

STRINGS: dict[str, dict[Language, str]] = {
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
    # assembled in code (this package deliberately has no date-formatting
    # logic of its own, same reasoning as every other computed-value split
    # in these files, e.g. slot_label).
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
}

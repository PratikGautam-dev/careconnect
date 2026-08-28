# core/translations/faq.py
"""FAQ sub-flow (faq_flow.py) -- per-hospital custom topic/answer pairs are
NOT translated here (that's the hospital's own entered data, see the package
docstring in __init__.py); only this sub-flow's own fixed chrome is."""
from core.translations._common import Language

STRINGS: dict[str, dict[Language, str]] = {
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
}

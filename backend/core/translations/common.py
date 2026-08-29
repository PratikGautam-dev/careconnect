# core/translations/common.py
"""Strings shared across multiple flows, or reached from outside the normal
flow dispatch entirely (core/main.py's audio/system-error paths), rather
than belonging to any one domain file in this package."""
from core.translations._common import Language


BACK_OPTION = "back_option"
PLEASE_CHOOSE = "please_choose"
AUDIO_NOT_SUPPORTED = "audio_not_supported"
SYSTEM_ERROR_NOTIFY = "system_error_notify"

STRINGS: dict[str, dict[Language, str]] = {
    # "Go back" navigation (Spec.md Section 0 follow-up): one shared button
    # label -- the 3rd button on the confirmation card (Meta's 3-button max),
    # and (a later UX follow-up, Spec.md Section 0) the department/doctor/
    # date/time menus' own follow-up Back-button message (_send_back_button),
    # sent as its own message right after the list rather than a row inside
    # it. Reused as that message's body text too -- no separate prompt line,
    # no "◀" arrow, both dropped per the user's own request.
    # Reused as both this message's body text AND its one button's label.
    BACK_OPTION: {"en": "Back", "hi": "पीछे"},

    # --- Shared fallback ---
    PLEASE_CHOOSE: {
        "en": "Please choose an option from the list above",
        "hi": "कृपया ऊपर दी गई सूची में से एक विकल्प चुनें",
    },

    # --- core/main.py: paths outside the normal flow dispatch ---
    AUDIO_NOT_SUPPORTED: {
        "en": "I couldn't process your audio. Could you send it as text instead?",
        "hi": "मैं आपका ऑडियो प्रोसेस नहीं कर सका। क्या आप इसे टेक्स्ट के रूप में भेज सकते हैं?",
    },
    SYSTEM_ERROR_NOTIFY: {
        "en": "Sorry, something went wrong on our end. We've notified our team and someone will follow up with "
              "you here shortly.",
        "hi": "क्षमा करें, हमारी तरफ से कुछ गलत हो गया। हमने अपनी टीम को सूचित कर दिया है और जल्द ही कोई आपसे यहां संपर्क करेगा।",
    },
}

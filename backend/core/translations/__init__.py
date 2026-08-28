# core/translations/__init__.py
"""
Patient-facing string lookup, English + Hindi (language-selection follow-up
to Section 14.5's feature-toggle model). Every fixed UI string the bot sends
lives here, keyed by a short semantic name, with one template per supported
language -- flows.py/core/booking_flow.py/faq_flow.py/core/main.py look
strings up here via t(key, language, **kwargs) instead of hardcoding text
inline, so adding a language later means adding one dict, not hunting down
every send_text/send_list/send_buttons call site again.

Split into one file per flow domain (menu.py, booking.py, cancel_reschedule.py,
patient_identity.py, manage_patients.py, dpdp_consent.py, faq.py, my_details.py,
common.py) -- this file just merges their STRINGS dicts into one and exposes
the same t()/Language/DEFAULT_LANGUAGE/SUPPORTED_LANGUAGES every caller
already imports, so `from core.translations import t` (or SUPPORTED_LANGUAGES,
or STRINGS) works identically to before this was a package. Add a new key to
whichever domain file it belongs to, not here.

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
from core.translations import (
    booking, cancel_reschedule, common, dpdp_consent, faq, manage_patients, menu, my_details, patient_identity,
)
from core.translations._common import DEFAULT_LANGUAGE, Language, SUPPORTED_LANGUAGES

STRINGS: dict[str, dict[Language, str]] = {
    **menu.STRINGS,
    **my_details.STRINGS,
    **booking.STRINGS,
    **cancel_reschedule.STRINGS,
    **patient_identity.STRINGS,
    **manage_patients.STRINGS,
    **dpdp_consent.STRINGS,
    **faq.STRINGS,
    **common.STRINGS,
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

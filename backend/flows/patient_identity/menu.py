# flows/patient_identity/menu.py
"""The unified main menu -- one row per hospital-enabled feature, plus the
"Patient: X / Patient Code: Y" header once a patient has been resolved."""
from flows.common import cap_rows
from core.translations import t
from core.translations.menu import (
    FEATURE_BOOKING,
    FEATURE_CANCEL,
    FEATURE_CONSENT_PRIVACY,
    FEATURE_FAQ,
    FEATURE_HOSPITAL_INFO,
    FEATURE_MENU_UNAVAILABLE,
    FEATURE_RECEPTION_HANDOFF,
    FEATURE_REPORTS_PRESCRIPTIONS,
    FEATURE_RESCHEDULE,
    FEATURE_VIEW_APPOINTMENTS,
    MAIN_MENU_BUTTON,
    MAIN_MENU_SECTION_TITLE,
    WELCOME_MENU,
)
from core.translations.common import BACK_OPTION
from core.translations.patient_identity import PATIENT_CODE_LABEL, PATIENT_HEADER_LABEL
from core.whatsapp import WhatsAppClient

from flows.patient_identity.state import MAIN_MENU_BACK_ROW

# feature key -> (menu row id, menu row title translation key). Order here is
# the order rows appear in the main menu.
_FEATURE_MENU = {
    "booking": ("menu_book", FEATURE_BOOKING),
    "reschedule": ("menu_reschedule", FEATURE_RESCHEDULE),
    "cancel": ("menu_cancel", FEATURE_CANCEL),
    "view_appointments": ("menu_view_appointments", FEATURE_VIEW_APPOINTMENTS),
    "reports_prescriptions": ("menu_reports_prescriptions", FEATURE_REPORTS_PRESCRIPTIONS),
    "manage_patients": ("menu_manage_patients", "feature_manage_patients"),
    "consent_privacy": ("menu_consent_privacy", FEATURE_CONSENT_PRIVACY),
    "hospital_info": ("menu_hospital_info", FEATURE_HOSPITAL_INFO),
    "reception_handoff": ("menu_reception", FEATURE_RECEPTION_HANDOFF),
    "faq": ("menu_faq_bot", FEATURE_FAQ),
}
_ROW_ID_TO_FEATURE = {row_id: key for key, (row_id, _title_key) in _FEATURE_MENU.items()}

REAL_FEATURES = set(_FEATURE_MENU.keys())
ALL_FEATURES = REAL_FEATURES


def _patient_header(active_patient: dict | None, language: str) -> str:
    """"Patient: {name}\\nPatient Code: {patient_display_id}" header shown
    above the main menu once a patient has been resolved -- the real
    clinical mrn (db/models.py's _generate_patient_identifiers) is never
    shown here, only the patient-facing patient_display_id. Empty string if
    none resolved yet."""
    if active_patient is None:
        return ""
    patient_code = active_patient.get("patient_display_id") or "—"
    return f"*{t(PATIENT_HEADER_LABEL, language)}* {active_patient['name']}\n*{t(PATIENT_CODE_LABEL, language)}* {patient_code}\n\n"


async def _send_dynamic_menu(
    wa: WhatsAppClient, phone: str, hospital_name: str, enabled_features: list[str], language: str = "en",
    feature_labels: dict[str, str] | None = None, language_prompt_enabled: bool = True,
    active_patient: dict | None = None,
) -> None:
    """Sends the hospital's main menu: one row per enabled feature, capped to
    WhatsApp's row limit, with the patient header on top and a separate
    "Back" buttons message underneath (a list can't carry its own back row)."""
    feature_labels = feature_labels or {}
    rows = [
        {"id": row_id, "title": feature_labels.get(key) or t(title_key, language)}
        for key, (row_id, title_key) in _FEATURE_MENU.items()
        if key in enabled_features
    ]
    if not rows:
        await wa.send_text(phone, t(FEATURE_MENU_UNAVAILABLE, language, hospital_name=hospital_name))
        return
    rows = cap_rows(rows, f"main menu for {hospital_name}")
    body_text = _patient_header(active_patient, language) + t(WELCOME_MENU, language, hospital_name=hospital_name)
    await wa.send_list(
        to=phone,
        body_text=body_text,
        button_text=t(MAIN_MENU_BUTTON, language),
        sections=[{"title": t(MAIN_MENU_SECTION_TITLE, language), "rows": rows}],
    )
    # Its own follow-up buttons message right under the list, not a row
    # hidden inside it (WhatsApp collapses a list to just its button_text
    # until tapped).
    await wa.send_buttons(
        to=phone, body_text="​", buttons=[{"id": MAIN_MENU_BACK_ROW, "title": t(BACK_OPTION, language)}],
    )

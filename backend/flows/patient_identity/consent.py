# flows/patient_identity/consent.py
"""Consent & Privacy menu item: shows the active patient's consent status
and a marketing-consent toggle. Service consent has no separate toggle here
-- withdrawing it maps to Manage Patients' unlink instead."""
from connectors import Connector
from core.translations import t
from core.translations.patient_identity import BACK_TO_MENU_OPTION
from core.translations.dpdp_consent import (
    CONSENT_MARKETING_DISABLE,
    CONSENT_MARKETING_ENABLE,
    CONSENT_OFF,
    CONSENT_ON,
    CONSENT_PRIVACY_BODY,
    PRIVACY_NOTICE_DEFAULT,
)
from core.whatsapp import WhatsAppClient

from flows.patient_identity.state import CONSENT_TOGGLE_MARKETING_ID, GOTO_MAIN_MENU, STATE_AWAITING_CONSENT_ACTION


async def start_consent_privacy(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector,
    active_patient_id: int, privacy_notice_text: str | None = None, language: str = "en",
) -> None:
    """Shows the active patient's consent status and a marketing-consent
    toggle. Service consent has no separate toggle here -- withdrawing it
    maps to Manage Patients' unlink instead."""
    consent = connector.get_patient_link_consent(hospital_id, phone, active_patient_id)
    if consent is None:
        # Stale active_patient_id (shouldn't normally happen -- resolution
        # already validates it) -- fall back to a safe re-resolution.
        sessions.clear_active_patient(hospital_id, phone)
        sessions.reset(hospital_id, phone)
        return
    notice = privacy_notice_text or t(PRIVACY_NOTICE_DEFAULT, language)
    marketing_status = t(CONSENT_ON, language) if consent["marketing_consent"] else t(CONSENT_OFF, language)
    body = t(CONSENT_PRIVACY_BODY, language, notice=notice,
        marketing_status=marketing_status,
    )
    sessions.set(hospital_id, phone, STATE_AWAITING_CONSENT_ACTION, {}, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=body,
        buttons=[
            {
                "id": CONSENT_TOGGLE_MARKETING_ID,
                "title": t(CONSENT_MARKETING_DISABLE, language) if consent["marketing_consent"] else t(CONSENT_MARKETING_ENABLE, language),
            },
            {"id": GOTO_MAIN_MENU, "title": t(BACK_TO_MENU_OPTION, language)},
        ],
    )


async def handle_awaiting_consent_action(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict,
    connector: Connector, active_patient_id: int, privacy_notice_text: str | None = None, language: str = "en",
) -> None:
    """Toggles marketing consent if that button was tapped, then re-shows
    the consent screen either way."""
    if reply["type"] == "interactive_reply" and reply["id"] == CONSENT_TOGGLE_MARKETING_ID:
        consent = connector.get_patient_link_consent(hospital_id, phone, active_patient_id)
        if consent is not None:
            connector.set_marketing_consent(hospital_id, phone, active_patient_id, not consent["marketing_consent"])
    await start_consent_privacy(
        wa, sessions, phone, hospital_id, connector, active_patient_id,
        privacy_notice_text=privacy_notice_text, language=language,
    )

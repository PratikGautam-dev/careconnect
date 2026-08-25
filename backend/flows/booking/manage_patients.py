# flows/booking/manage_patients.py
"""ARCHITECTURE_PLAN.md Phase 3b: view/add/unlink the patients linked to a
phone (Spec.md Section 0) -- split out of the former single
core/booking_flow.py module. Add reuses STATE_AWAITING_PATIENT_NAME/AGE
(patient_flow_next="manage_patients"), handled by flows.booking.book, same
as booking's implicit-first-profile and selector "+ Add Patient" paths."""
from connectors import Connector, MAX_ACTIVE_PATIENT_LINKS
from core.translations import t
from core.whatsapp import WhatsAppClient

from flows.booking.state import (
    CONFIRM_NO, CONFIRM_YES, MANAGE_PATIENTS_ADD_ROW_ID, STATE_AWAITING_MANAGE_PATIENTS_ACTION,
    STATE_AWAITING_PATIENT_NAME, STATE_AWAITING_UNLINK_CONFIRM, _cap_rows, _parse_patient_row_id, _patient_row_id,
    _patient_row_title,
)

async def _start_manage_patients_flow(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    patients = connector.list_active_patients(hospital_id, phone)
    rows = [{"id": _patient_row_id(p["id"]), "title": _patient_row_title(p)} for p in patients]
    if len(patients) < MAX_ACTIVE_PATIENT_LINKS:
        rows.append({"id": MANAGE_PATIENTS_ADD_ROW_ID, "title": t("add_patient_option", language)})
    rows = _cap_rows(rows, "manage patients list")
    sessions.set(hospital_id, phone, STATE_AWAITING_MANAGE_PATIENTS_ACTION, {})
    await wa.send_list(
        to=phone,
        body_text=t("manage_patients_header", language),
        button_text=t("manage_patients_button", language),
        sections=[{"title": t("manage_patients_section_title", language), "rows": rows}],
    )


async def _handle_awaiting_manage_patients_action(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == MANAGE_PATIENTS_ADD_ROW_ID:
            patients = connector.list_active_patients(hospital_id, phone)
            if len(patients) >= MAX_ACTIVE_PATIENT_LINKS:
                await wa.send_text(phone, t("too_many_linked_patients", language))
                await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)
                return
            sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, {"patient_flow_next": "manage_patients"})
            await wa.send_text(phone, t("ask_patient_name", language))
            return
        patient_id = _parse_patient_row_id(rid)
        if patient_id is not None:
            patients = connector.list_active_patients(hospital_id, phone)
            match = next((p for p in patients if p["id"] == patient_id), None)
            if match:
                sessions.set(
                    hospital_id, phone, STATE_AWAITING_UNLINK_CONFIRM,
                    {"unlink_patient_id": patient_id, "unlink_patient_name": match["name"]},
                )
                await wa.send_buttons(
                    to=phone,
                    body_text=t("unlink_patient_confirm", language, patient_name=match["name"]),
                    buttons=[
                        {"id": CONFIRM_YES, "title": t("confirm_button", language)},
                        {"id": CONFIRM_NO, "title": t("cancel_button", language)},
                    ],
                )
                return
    # Stale/unrecognized tap, or the list went stale between send and reply
    # -- re-fetch and re-show fresh rather than acting on a stale id.
    await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)


async def _handle_awaiting_unlink_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    patient_id = context.get("unlink_patient_id")
    patient_name = context.get("unlink_patient_name", "")
    if reply["type"] == "interactive_reply" and patient_id is not None:
        if reply["id"] == CONFIRM_YES:
            # Soft-unlink only -- unlink_patient() sets patient_links.unlinked_at
            # and never touches `patients`/`appointments`, so this patient's
            # booking history and Patient ID are completely unaffected.
            connector.unlink_patient(hospital_id, phone, patient_id)
            await wa.send_text(phone, t("patient_unlinked", language, patient_name=patient_name))
            await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)
            return
        if reply["id"] == CONFIRM_NO:
            await _start_manage_patients_flow(wa, sessions, phone, hospital_id, connector, language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_UNLINK_CONFIRM, context)
    await wa.send_buttons(
        to=phone,
        body_text=t("unlink_patient_confirm", language, patient_name=patient_name),
        buttons=[
            {"id": CONFIRM_YES, "title": t("confirm_button", language)},
            {"id": CONFIRM_NO, "title": t("cancel_button", language)},
        ],
    )

# flows/patient_identity/manage_patients.py
"""Manage Patients (confirmed with the user): a 2-option entry point --
Remove Patient (shows the patient list ONLY to pick who to remove, then
confirms) / Add Patient (the existing registration flow, registration.py) --
no "switch active patient" action here anymore, that's resolution.py's job."""
from connectors import Connector, RELATIONSHIP_SELF
from core.translations import t
from core.translations.common import BACK_OPTION
from core.translations.booking import CANCEL_BUTTON, CONFIRM_BUTTON
from core.translations.patient_identity import ADD_PATIENT_SHORT, TOO_MANY_LINKED_PATIENTS
from core.translations.manage_patients import (
    MANAGE_PATIENTS_BUTTON,
    MANAGE_PATIENTS_HEADER,
    MANAGE_PATIENTS_PROMPT,
    MANAGE_PATIENTS_SECTION_TITLE,
    NO_PATIENTS_TO_REMOVE,
    PATIENT_REMOVAL_CANCELLED,
    PATIENT_UNLINKED,
    REMOVE_PATIENT_OPTION,
    UNLINK_PATIENT_CONFIRM,
    UNLINK_SELF_BLOCKED,
)
from core.whatsapp import WhatsAppClient

from flows.common import cap_rows
from flows.patient_identity.registration import _start_registration
from flows.patient_identity.state import (
    CONFIRM_NO,
    CONFIRM_YES,
    MANAGE_ADD_ROW_ID,
    MANAGE_PATIENTS_BACK_ID,
    MANAGE_REMOVE_ROW_ID,
    STATE_AWAITING_MANAGE_PATIENTS_ACTION,
    STATE_AWAITING_REMOVE_PATIENT_SELECTION,
    STATE_AWAITING_UNLINK_CONFIRM,
    _parse_unlink_row_id,
    _patient_row_title,
    _unlink_row_id,
)


async def _start_manage_patients(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    """Sends the Remove Patient / Add Patient choice."""
    sessions.set(hospital_id, phone, STATE_AWAITING_MANAGE_PATIENTS_ACTION, {}, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t(MANAGE_PATIENTS_PROMPT, language),
        buttons=[
            {"id": MANAGE_REMOVE_ROW_ID, "title": t(REMOVE_PATIENT_OPTION, language)},
            {"id": MANAGE_ADD_ROW_ID, "title": t(ADD_PATIENT_SHORT, language)},
        ],
    )


async def _handle_awaiting_manage_patients_action(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Starts "Add Patient" registration (blocked with a message if already
    at the cap), or shows the patient list to remove one. Re-prompts the
    2-option choice on anything else."""
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == MANAGE_ADD_ROW_ID:
            patients = connector.list_active_patients(hospital_id, phone)
            if len(patients) >= connector.get_max_active_patient_links():
                await wa.send_text(phone, t(TOO_MANY_LINKED_PATIENTS, language))
                await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
                return
            await _start_registration(wa, sessions, phone, hospital_id, connector, language, identity_flow_next="manage_patients")
            return
        if rid == MANAGE_REMOVE_ROW_ID:
            await _send_remove_patient_list(wa, sessions, phone, hospital_id, connector, language)
            return
    await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)


async def _send_remove_patient_list(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str,
) -> None:
    """"Remove Patient" tapped: the patient list, shown ONLY to pick who to
    remove (confirmed with the user -- exactly matches the instruction to
    show "you have no patients to remove" and re-prompt the 2-option choice
    when there's nothing to show)."""
    patients = connector.list_active_patients(hospital_id, phone)
    if not patients:
        await wa.send_text(phone, t(NO_PATIENTS_TO_REMOVE, language))
        await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        return
    rows = [{"id": _unlink_row_id(p["id"]), "title": _patient_row_title(p)} for p in patients]
    rows.append({"id": MANAGE_PATIENTS_BACK_ID, "title": t(BACK_OPTION, language)})
    rows = cap_rows(rows, "remove patient list")
    sessions.set(hospital_id, phone, STATE_AWAITING_REMOVE_PATIENT_SELECTION, {}, language=language)
    await wa.send_list(
        to=phone,
        body_text=t(MANAGE_PATIENTS_HEADER, language),
        button_text=t(MANAGE_PATIENTS_BUTTON, language),
        sections=[{"title": t(MANAGE_PATIENTS_SECTION_TITLE, language), "rows": rows}],
    )


async def _handle_awaiting_remove_patient_selection(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """A patient tapped from the remove-list -> asks to confirm; "Back", or
    an unrecognized/stale tap, re-shows the current (fresh) list."""
    if reply["type"] == "interactive_reply":
        if reply["id"] == MANAGE_PATIENTS_BACK_ID:
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
        patient_id = _parse_unlink_row_id(reply["id"])
        if patient_id is not None:
            patients = connector.list_active_patients(hospital_id, phone)
            match = next((p for p in patients if p["id"] == patient_id), None)
            if match:
                sessions.set(
                    hospital_id, phone, STATE_AWAITING_UNLINK_CONFIRM,
                    {
                        "unlink_patient_id": patient_id, "unlink_patient_name": match["name"],
                        "unlink_relationship_label": match.get("relationship_label"),
                    },
                    language=language,
                )
                await wa.send_buttons(
                    to=phone,
                    body_text=t(UNLINK_PATIENT_CONFIRM, language, patient_name=match["name"]),
                    buttons=[
                        {"id": CONFIRM_YES, "title": t(CONFIRM_BUTTON, language)},
                        {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
                    ],
                )
                return
    await _send_remove_patient_list(wa, sessions, phone, hospital_id, connector, language)


async def _handle_awaiting_unlink_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Confirmed with the user: BOTH outcomes (removed, or cancelled) send
    a message and then land on the main menu (state IDLE) -- router.py's own
    post-dispatch check shows the main menu immediately once it sees IDLE,
    same hook registration.py's _create_or_link_patient "Add Patient"
    success path now uses. Neither branch re-shows Manage Patients anymore.

    just_confirmed_patient is set on both outcomes UNLESS the removed
    patient was the active one -- otherwise, with 2+ patients still linked,
    get_or_prompt_for_active_patient would treat this same IDLE re-entry as
    "2+ patients, no confirmation yet" and show the "who is this for"
    selector instead of going straight to the real main menu (see that
    function's own docstring, and _create_or_link_patient's identical fix
    for the Add Patient path)."""
    patient_id = context.get("unlink_patient_id")
    patient_name = context.get("unlink_patient_name", "")
    if reply["type"] == "interactive_reply" and patient_id is not None:
        if reply["id"] == CONFIRM_YES:
            if context.get("unlink_relationship_label") == RELATIONSHIP_SELF:
                # Confirmed with the user: the "Myself"/master patient can
                # never be self-unlinked -- one combined message, then land
                # exactly like CONFIRM_NO (cancelled) already does below:
                # nothing changed, so main menu (IDLE) with
                # just_confirmed_patient set.
                await wa.send_text(phone, t(UNLINK_SELF_BLOCKED, language, patient_name=patient_name))
                sessions.set(hospital_id, phone, "IDLE", {"just_confirmed_patient": True}, language=language)
                return
            connector.unlink_patient(hospital_id, phone, patient_id)
            session = sessions.get(hospital_id, phone)
            removed_was_active = session.get("active_patient_id") == patient_id
            if removed_was_active:
                # Unlinked the currently-active patient -- force
                # re-resolution rather than keep using a stale reference.
                sessions.clear_active_patient(hospital_id, phone)
            await wa.send_text(phone, t(PATIENT_UNLINKED, language, patient_name=patient_name))
            new_context = {} if removed_was_active else {"just_confirmed_patient": True}
            sessions.set(hospital_id, phone, "IDLE", new_context, language=language)
            return
        if reply["id"] == CONFIRM_NO:
            await wa.send_text(phone, t(PATIENT_REMOVAL_CANCELLED, language, patient_name=patient_name))
            sessions.set(hospital_id, phone, "IDLE", {"just_confirmed_patient": True}, language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_UNLINK_CONFIRM, context, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t(UNLINK_PATIENT_CONFIRM, language, patient_name=patient_name),
        buttons=[
            {"id": CONFIRM_YES, "title": t(CONFIRM_BUTTON, language)},
            {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
        ],
    )

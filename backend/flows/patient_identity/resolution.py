# flows/patient_identity/resolution.py
"""The resolution entry point: figures out WHICH patient the current
conversation is acting on, before the main menu is ever shown -- the
already-resolved/exactly-one-linked-patient fast path, the optional
single-patient confirmation card, and the 2+-linked-patients selector."""
from connectors import Connector
from core.translations import t
from core.translations.common import BACK_OPTION
from core.translations.menu import MAIN_MENU_BUTTON
from core.translations.patient_identity import (
    ADD_PATIENT_SHORT,
    MULTI_PATIENT_SELECTOR_PROMPT,
    PATIENT_SELECTED_CONFIRMATION,
    PATIENT_SELECTOR_BUTTON,
    PATIENT_SELECTOR_PROMPT,
    PATIENT_SELECTOR_SECTION_TITLE,
    SINGLE_PATIENT_CONFIRM,
)
from core.whatsapp import WhatsAppClient

from flows.common import cap_rows
from flows.patient_identity.manage_patients import _start_manage_patients
from flows.patient_identity.registration import _start_registration
from flows.patient_identity.state import (
    ADD_PATIENT_ENTRY_ID,
    BACK_ID,
    CONFIRM_YES,
    MANAGE_PATIENTS_ENTRY_ID,
    STATE_AWAITING_SINGLE_PATIENT_CONFIRM,
    _parse_patient_row_id,
    _patient_row_id,
    _patient_row_title,
)


async def get_or_prompt_for_active_patient(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector,
    language: str = "en", require_patient_confirmation: bool = False,
) -> dict | None:
    """Called once per conversation, before the main menu is ever shown.
    Returns the resolved active patient immediately for the already-resolved
    or exactly-one-linked-patient case; otherwise sends a registration or
    selection prompt and returns None -- the caller must stop, and
    whichever completion path was triggered calls back into this function
    once it's done. A phone linked to more than one patient always re-prompts
    (via _send_patient_selector_for_resolution) rather than silently reusing
    whichever patient happened to be active before -- EXCEPT right after the
    user just confirmed/picked one this same turn
    (context["just_confirmed_patient"], set by _handle_awaiting_single_patient_
    confirm): router.py re-enters this function in the same handle_incoming
    call once state becomes IDLE, and without this flag that re-entry would
    immediately re-show the very confirm screen the user just answered."""
    session = sessions.get(hospital_id, phone)
    active_patient_id = session.get("active_patient_id")
    just_confirmed = session.get("context", {}).get("just_confirmed_patient", False)
    patients = connector.list_active_patients(hospital_id, phone)

    if active_patient_id is not None:
        if connector.validate_active_patient_link(hospital_id, phone, active_patient_id):
            match = next((p for p in patients if p["id"] == active_patient_id), None)
            if match is not None:
                if len(patients) > 1 and not just_confirmed:
                    await _send_patient_selector_for_resolution(wa, sessions, phone, hospital_id, connector, language)
                    return None
                sessions.set(hospital_id, phone, "IDLE", {}, language=language, active_patient_id=match["id"])
                return match
        # Stale (unlinked, or the patient was blocked/inactivated since) --
        # force a fresh resolution rather than trusting it further.
        sessions.clear_active_patient(hospital_id, phone)

    if len(patients) == 0:
        await _start_registration(wa, sessions, phone, hospital_id, connector, language)
        return None
    if len(patients) == 1 and not require_patient_confirmation:
        sessions.set(hospital_id, phone, "IDLE", {}, language=language, active_patient_id=patients[0]["id"])
        return patients[0]
    if len(patients) == 1:
        await _send_single_patient_confirm(wa, sessions, phone, hospital_id, connector, patients[0], language)
    else:
        await _send_patient_selector_for_resolution(wa, sessions, phone, hospital_id, connector, language)
    return None


# --- Single-linked-patient confirmation (hospital-configurable) ---
#
# Sends two messages together, in one turn: a 2-button "Continue as X?"
# (Confirm / Add Patient), immediately followed by the plain patient-list
# picker -- so the list is always visible, with no extra "Patient List"
# button tap needed to reveal it first. Both messages reply into the same
# state; tapping a patient row there sets them active immediately, with no
# further "what do you want to do with X" step (that step is Manage-
# Patients-only, in manage_patients.py).

async def _send_single_patient_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, patient: dict, language: str,
) -> None:
    """Sends the "Current Patient: X" card, then the patient-list message
    right after, both under STATE_AWAITING_SINGLE_PATIENT_CONFIRM. Only
    reached today with exactly one linked patient and
    hospitals.require_patient_confirmation on -- the 2+ patient case goes
    through _send_patient_selector_for_resolution below instead, which has
    no single candidate to name in this card.

    No separate "Confirm" button (confirmed with the user): with exactly one
    linked patient there's nothing to choose between, so they're already the
    active candidate -- CONFIRM_YES below (now labelled "Main Menu", not
    "Confirm") just proceeds, same handling _handle_awaiting_single_patient_
    confirm always had for it. "Back" re-opens the language picker -- the
    only earlier screen this one can follow, since it's shown right after
    language selection, before any main menu exists yet."""
    sessions.set(
        hospital_id, phone, STATE_AWAITING_SINGLE_PATIENT_CONFIRM, {"candidate_patient_id": patient["id"]},
        language=language,
    )
    await wa.send_buttons(
        to=phone,
        body_text=t(SINGLE_PATIENT_CONFIRM, language, patient_name=patient["name"], patient_code=patient["patient_display_id"] or "—",
        ),
        buttons=[
            {"id": CONFIRM_YES, "title": t(MAIN_MENU_BUTTON, language)},
            {"id": ADD_PATIENT_ENTRY_ID, "title": t(ADD_PATIENT_SHORT, language)},
            {"id": BACK_ID, "title": t(BACK_OPTION, language)},
        ],
    )
    # patients = connector.list_active_patients(hospital_id, phone)
    # rows = [{"id": _patient_row_id(p["id"]), "title": _patient_row_title(p)} for p in patients]
    # rows.append({"id": MANAGE_PATIENTS_ENTRY_ID, "title": t(MANAGE_PATIENTS_SHORT, language)})
    # rows = cap_rows(rows, "patient selector")
    # await wa.send_list(
    #     to=phone,
    #     body_text=t(PATIENT_SELECTOR_PROMPT, language),
    #     button_text=t(PATIENT_SELECTOR_BUTTON, language),
    #     sections=[{"title": t(PATIENT_SELECTOR_SECTION_TITLE, language), "rows": rows}],
    # )


async def _send_patient_selector_for_resolution(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str,
) -> None:
    """2+ linked patients: no default/candidate patient is auto-picked, so
    there's no single name for a "Continue as X?" card -- the list itself
    (welcome text folded straight into its body, MULTI_PATIENT_SELECTOR_
    PROMPT) is the only prompt, and tapping a row activates that patient
    directly via the same STATE_AWAITING_SINGLE_PATIENT_CONFIRM row-tap
    handling _handle_awaiting_single_patient_confirm already has (no
    candidate_patient_id in context here, so its CONFIRM_YES branch is simply
    never reached -- there's no Confirm button offered). A separate
    "Add Patient" follow-up button matches _send_single_patient_confirm's own,
    minus the "Confirm" option it has no candidate to confirm.

    Deliberately no "Manage Patients" row in this sheet (confirmed with the
    user) -- this list is purely "which patient is this conversation for,"
    Manage Patients is its own separate main-menu feature, reached only from
    there; _handle_awaiting_single_patient_confirm's MANAGE_PATIENTS_ENTRY_ID
    branch is kept only as a harmless stale-tap fallback for an
    already-sent, older message that still has that row."""
    sessions.set(hospital_id, phone, STATE_AWAITING_SINGLE_PATIENT_CONFIRM, {}, language=language)
    patients = connector.list_active_patients(hospital_id, phone)
    rows = [{"id": _patient_row_id(p["id"]), "title": _patient_row_title(p)} for p in patients]
    rows = cap_rows(rows, "patient selector")
    await wa.send_list(
        to=phone,
        body_text=t(MULTI_PATIENT_SELECTOR_PROMPT, language),
        button_text=t(PATIENT_SELECTOR_BUTTON, language),
        sections=[{"title": t(PATIENT_SELECTOR_SECTION_TITLE, language), "rows": rows}],
    )
    await wa.send_buttons(
        to=phone,
        body_text="​",
        buttons=[{"id": ADD_PATIENT_ENTRY_ID, "title": t(ADD_PATIENT_SHORT, language)}],
    )


async def _handle_awaiting_single_patient_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Handles taps from either message sent by _send_single_patient_confirm:
    the 3 buttons (Main Menu/Add Patient/Back) or a row from the patient list
    (a linked patient, or Manage Patients). Re-fetches and re-shows fresh on
    an unrecognized/stale tap (the patient list may have changed since)."""
    if reply["type"] == "interactive_reply":
        if reply["id"] == CONFIRM_YES:
            sessions.set(
                hospital_id, phone, "IDLE", {"just_confirmed_patient": True}, language=language,
                active_patient_id=context["candidate_patient_id"],
            )
            return
        if reply["id"] == ADD_PATIENT_ENTRY_ID:
            await _start_registration(wa, sessions, phone, hospital_id, connector, language)
            return
        if reply["id"] == BACK_ID:
            # Lazy import: flows.router imports this package at the top
            # level, so importing it back here at module scope would cycle
            # (same reason followup.py/daycare.py lazy-import messages.py).
            from flows.router import STATE_AWAITING_LANGUAGE, _send_language_picker

            sessions.set(hospital_id, phone, STATE_AWAITING_LANGUAGE, {})
            await _send_language_picker(wa, phone)
            return
        if reply["id"] == MANAGE_PATIENTS_ENTRY_ID:
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
        patient_id = _parse_patient_row_id(reply["id"])
        if patient_id is not None:
            patients = connector.list_active_patients(hospital_id, phone)
            selected = next((p for p in patients if p["id"] == patient_id), None)
            if selected is not None:
                await wa.send_text(
                    phone,
                    t(
                        PATIENT_SELECTED_CONFIRMATION, language,
                        patient_name=selected["name"], patient_code=selected["patient_display_id"] or "—",
                    ),
                )
                sessions.set(
                    hospital_id, phone, "IDLE", {"just_confirmed_patient": True}, language=language,
                    active_patient_id=patient_id,
                )
                return
    patients = connector.list_active_patients(hospital_id, phone)
    if len(patients) == 1:
        await _send_single_patient_confirm(wa, sessions, phone, hospital_id, connector, patients[0], language)
    elif len(patients) > 1:
        await _send_patient_selector_for_resolution(wa, sessions, phone, hospital_id, connector, language)
    else:
        sessions.clear_active_patient(hospital_id, phone)
        sessions.reset(hospital_id, phone)

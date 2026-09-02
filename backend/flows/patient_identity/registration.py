# flows/patient_identity/registration.py
"""Registration: [Myself/Someone Else] -> name -> [contact number, Someone
Else only] -> age -> gender -> [duplicate decision] -> create/link. The
first-time-phone path out of resolution.py's get_or_prompt_for_active_patient,
and also reachable mid-conversation via Manage Patients' "Add Patient"
(identity_flow_next="manage_patients")."""
from connectors import Connector, DuplicateSelfLinkError, RELATIONSHIP_OTHER, RELATIONSHIP_SELF, TooManyLinkedPatientsError
from core.translations import t
from core.translations.common import BACK_OPTION
from core.translations.booking import (
    ASK_BOOKING_FOR,
    ASK_PATIENT_AGE,
    ASK_PATIENT_CONTACT_NUMBER,
    ASK_PATIENT_GENDER,
    ASK_PATIENT_NAME,
    BOOKING_FOR_OTHER_BUTTON,
    BOOKING_FOR_SELF_BUTTON,
    CANCEL_BUTTON,
    GENDER_FEMALE,
    GENDER_MALE,
    GENDER_OTHER,
    INVALID_PATIENT_AGE,
    INVALID_PATIENT_CONTACT_NUMBER,
    INVALID_PATIENT_NAME,
)
from core.translations.patient_identity import (
    DUPLICATE_DIFFERENT_BUTTON,
    DUPLICATE_LINK_BUTTON,
    DUPLICATE_PATIENT_FOUND,
    DUPLICATE_SELF_LINK,
    PATIENT_ALREADY_LINKED,
    REGISTRATION_BLOCKED_CONTACT_HOSPITAL,
    TOO_MANY_LINKED_PATIENTS,
)
from core.translations.manage_patients import PATIENT_ADDED
from core.whatsapp import WhatsAppClient

from flows.patient_identity.state import (
    BACK_ID,
    BOOKING_FOR_OTHER_ID,
    BOOKING_FOR_SELF_ID,
    CONFIRM_NO,
    DUPLICATE_DIFFERENT_ID,
    DUPLICATE_LINK_ID,
    GENDER_FEMALE_ID,
    GENDER_MALE_ID,
    GENDER_OTHER_ID,
    STATE_AWAITING_BOOKING_FOR,
    STATE_AWAITING_DUPLICATE_DECISION,
    STATE_AWAITING_PATIENT_AGE,
    STATE_AWAITING_PATIENT_CONTACT_PHONE,
    STATE_AWAITING_PATIENT_GENDER,
    STATE_AWAITING_PATIENT_NAME,
    _GENDER_ROW_IDS,
    _parse_contact_phone_number,
    _parse_patient_age,
    _parse_patient_name,
)


async def _send_back_button(wa: WhatsAppClient, phone: str, language: str = "en") -> None:
    """Sends a standalone "Back" buttons message (zero-width-space body,
    since Meta rejects a truly empty one) -- duplicated from flows/booking's
    own helper rather than imported, per this package's own boundary."""
    await wa.send_buttons(to=phone, body_text="​", buttons=[{"id": BACK_ID, "title": t(BACK_OPTION, language)}])


async def _start_registration(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str,
    identity_flow_next: str = "resolve",
) -> None:
    """Kicks off registration -- "Myself / Someone Else" first, UNLESS this
    CareConnect account already has an active "Myself" (relationship_label=
    RELATIONSHIP_SELF) patient linked at this hospital, in which case the
    question is skipped entirely (silently locked to "Someone Else") and
    registration goes straight to the name question. See
    has_self_linked_patient()'s own docstring for the hard, race-safe
    backstop this soft check pairs with."""
    account = connector.identify_contact(phone, phone_number=phone)
    if connector.has_self_linked_patient(hospital_id, account["id"]):
        context = {"identity_flow_next": identity_flow_next, "pending_relationship": RELATIONSHIP_OTHER}
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, context, language=language)
        await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
        if identity_flow_next == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    await _send_booking_for_prompt(wa, sessions, phone, hospital_id, {"identity_flow_next": identity_flow_next}, language)


async def _send_booking_for_prompt(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, language: str,
) -> None:
    sessions.set(hospital_id, phone, STATE_AWAITING_BOOKING_FOR, context, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t(ASK_BOOKING_FOR, language),
        buttons=[
            {"id": BOOKING_FOR_SELF_ID, "title": t(BOOKING_FOR_SELF_BUTTON, language)},
            {"id": BOOKING_FOR_OTHER_ID, "title": t(BOOKING_FOR_OTHER_BUTTON, language)},
        ],
    )
    if context.get("identity_flow_next") == "manage_patients":
        await _send_back_button(wa, phone, language=language)


async def _handle_awaiting_booking_for(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """"Myself" skips the contact-number question later (defaults to the
    messaging phone); "Someone Else" routes the name step into a dedicated
    contact-number question next. BACK returns to Manage Patients -- the
    only screen this step can ever follow, since it's registration's own
    first step."""
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID and context.get("identity_flow_next") == "manage_patients":
        from flows.patient_identity.manage_patients import _start_manage_patients

        await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        return
    if reply["type"] == "interactive_reply" and reply["id"] == BOOKING_FOR_SELF_ID:
        relationship = RELATIONSHIP_SELF
    elif reply["type"] == "interactive_reply" and reply["id"] == BOOKING_FOR_OTHER_ID:
        relationship = RELATIONSHIP_OTHER
    else:
        await _send_booking_for_prompt(wa, sessions, phone, hospital_id, context, language)
        return
    new_context = {**context, "pending_relationship": relationship, "booking_for_asked": True}
    if relationship == RELATIONSHIP_SELF:
        new_context["pending_contact_phone"] = phone
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, new_context, language=language)
    await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
    if context.get("identity_flow_next") == "manage_patients":
        await _send_back_button(wa, phone, language=language)


async def _handle_awaiting_patient_name(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Accepts a valid name (letters/spaces only, 4-50 characters) and moves
    on -- to the contact-number question for "Someone Else", or straight to
    age for "Myself" (whose contact number is already the messaging phone,
    set back in _handle_awaiting_booking_for). Re-prompts on anything else.
    BACK returns to the Myself/Someone Else question if it was actually
    shown (context["booking_for_asked"]), else to Manage Patients if this
    is mid-"Add Patient" -- the very first registration has no earlier
    screen in either case."""
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID:
        if context.get("booking_for_asked"):
            await _send_booking_for_prompt(
                wa, sessions, phone, hospital_id, {"identity_flow_next": context.get("identity_flow_next", "resolve")}, language,
            )
            return
        if context.get("identity_flow_next") == "manage_patients":
            from flows.patient_identity.manage_patients import _start_manage_patients

            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
    name = _parse_patient_name(reply["text"]) if reply["type"] == "text" else None
    if name is not None:
        new_context = {**context, "pending_name": name}
        if new_context.get("pending_relationship") == RELATIONSHIP_OTHER:
            sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_CONTACT_PHONE, new_context, language=language)
            await wa.send_text(phone, t(ASK_PATIENT_CONTACT_NUMBER, language, patient_name=name))
            if context.get("identity_flow_next") == "manage_patients":
                await _send_back_button(wa, phone, language=language)
            return
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, new_context, language=language)
        await wa.send_text(phone, t(ASK_PATIENT_AGE, language, patient_name=name))
        if context.get("identity_flow_next") == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, context, language=language)
    await wa.send_text(phone, t(INVALID_PATIENT_NAME, language))
    await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
    if context.get("identity_flow_next") == "manage_patients":
        await _send_back_button(wa, phone, language=language)


async def _handle_awaiting_patient_contact_number(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """"Someone Else" only -- never reached for "Myself", which uses the
    messaging phone directly (set in _handle_awaiting_booking_for). Accepts
    an exact 10-digit number and moves to the age question; re-prompts on
    anything invalid/missing. BACK returns to the name question."""
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID:
        identity_flow_next = context.get("identity_flow_next", "resolve")
        new_context = {k: v for k, v in context.items() if k != "pending_contact_phone"}
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, new_context, language=language)
        await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
        if identity_flow_next == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    contact_phone = _parse_contact_phone_number(reply["text"]) if reply["type"] == "text" else None
    if contact_phone is None:
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_CONTACT_PHONE, context, language=language)
        await wa.send_text(phone, t(INVALID_PATIENT_CONTACT_NUMBER, language))
        await wa.send_text(phone, t(ASK_PATIENT_CONTACT_NUMBER, language, patient_name=context.get("pending_name", "")))
        if context.get("identity_flow_next") == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    new_context = {**context, "pending_contact_phone": contact_phone}
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, new_context, language=language)
    await wa.send_text(phone, t(ASK_PATIENT_AGE, language, patient_name=new_context.get("pending_name", "")))
    if context.get("identity_flow_next") == "manage_patients":
        await _send_back_button(wa, phone, language=language)


async def _handle_awaiting_patient_age(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Accepts a valid age and moves to the gender question; re-prompts on
    anything invalid/missing. BACK returns to the contact-number question
    for "Someone Else" (who has one), or the name question for "Myself"."""
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID:
        identity_flow_next = context.get("identity_flow_next", "resolve")
        if context.get("pending_relationship") == RELATIONSHIP_OTHER:
            new_context = {k: v for k, v in context.items() if k != "pending_age"}
            sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_CONTACT_PHONE, new_context, language=language)
            await wa.send_text(phone, t(ASK_PATIENT_CONTACT_NUMBER, language, patient_name=context.get("pending_name", "")))
            if identity_flow_next == "manage_patients":
                await _send_back_button(wa, phone, language=language)
            return
        new_context = {k: v for k, v in context.items() if k not in ("pending_name", "pending_age")}
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, new_context, language=language)
        await wa.send_text(phone, t(ASK_PATIENT_NAME, language))
        if identity_flow_next == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    age = _parse_patient_age(reply["text"]) if reply["type"] == "text" else None
    if age is None:
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, context, language=language)
        await wa.send_text(phone, t(INVALID_PATIENT_AGE, language))
        await wa.send_text(phone, t(ASK_PATIENT_AGE, language, patient_name=context.get("pending_name", "")))
        if context.get("identity_flow_next") == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    new_context = {**context, "pending_age": age}
    await _send_gender_prompt(wa, sessions, phone, hospital_id, new_context, language)


async def _send_gender_prompt(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, language: str,
) -> None:
    """Sends the required Male/Female/Other gender prompt -- the third and
    final step of registration before duplicate-checking/creation."""
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_GENDER, context, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t(ASK_PATIENT_GENDER, language),
        buttons=[
            {"id": GENDER_MALE_ID, "title": t(GENDER_MALE, language)},
            {"id": GENDER_FEMALE_ID, "title": t(GENDER_FEMALE, language)},
            {"id": GENDER_OTHER_ID, "title": t(GENDER_OTHER, language)},
        ],
    )
    if context.get("identity_flow_next") == "manage_patients":
        await _send_back_button(wa, phone, language=language)


async def _handle_awaiting_patient_gender(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Accepts a gender choice, then either surfaces a duplicate-patient
    match (exact name + contact phone, among this hospital's active
    patients) for the user to resolve, creates the profile directly if
    there's no match, or -- if the match is already actively linked to THIS
    phone -- tells the user plainly and creates nothing (re-adding the same
    name+contact you already have would otherwise silently create a genuine
    duplicate `patients` row every time; see
    find_potential_duplicate_patient()'s own docstring). Re-prompts on an
    unrecognized tap; BACK returns to the age question."""
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID:
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, context, language=language)
        await wa.send_text(phone, t(ASK_PATIENT_AGE, language, patient_name=context.get("pending_name", "")))
        if context.get("identity_flow_next") == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    gender = _GENDER_ROW_IDS.get(reply["id"]) if reply["type"] == "interactive_reply" else None
    if gender is None:
        await _send_gender_prompt(wa, sessions, phone, hospital_id, context, language)
        return

    new_context = {**context, "pending_gender": gender}
    match = connector.find_potential_duplicate_patient(
        hospital_id, new_context["pending_name"], new_context["pending_contact_phone"],
    )
    if match is not None and connector.validate_active_patient_link(hospital_id, phone, match["id"]):
        identity_flow_next = context.get("identity_flow_next", "resolve")
        await wa.send_text(phone, t(PATIENT_ALREADY_LINKED, language, name=match["name"]))
        if identity_flow_next == "manage_patients":
            from flows.patient_identity.manage_patients import _start_manage_patients

            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        else:
            sessions.reset(hospital_id, phone)
        return
    if match is not None:
        new_context["duplicate_patient_id"] = match["id"]
        new_context["duplicate_patient_name"] = match["name"]
        new_context["duplicate_patient_display_id"] = match["patient_display_id"]
        sessions.set(hospital_id, phone, STATE_AWAITING_DUPLICATE_DECISION, new_context, language=language)
        await wa.send_buttons(
            to=phone,
            body_text=t(DUPLICATE_PATIENT_FOUND, language, name=match["name"], patient_code=match["patient_display_id"] or "—"),
            buttons=[
                {"id": DUPLICATE_LINK_ID, "title": t(DUPLICATE_LINK_BUTTON, language)},
                {"id": DUPLICATE_DIFFERENT_ID, "title": t(DUPLICATE_DIFFERENT_BUTTON, language)},
                {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
            ],
        )
        return
    await _create_or_link_patient(wa, sessions, phone, hospital_id, new_context, connector, language)


async def _handle_awaiting_duplicate_decision(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Resolves a duplicate-patient match: link the existing profile (no new
    MRN), create a genuinely new one anyway, or cancel back to the start.
    Re-shows the same choice on an unrecognized/stale tap."""
    identity_flow_next = context.get("identity_flow_next", "resolve")
    if reply["type"] == "interactive_reply":
        if reply["id"] == DUPLICATE_LINK_ID:
            # Link the EXISTING patient -- no new MRN.
            link_context = {**context, "link_target_patient_id": context["duplicate_patient_id"]}
            await _create_or_link_patient(wa, sessions, phone, hospital_id, link_context, connector, language)
            return
        if reply["id"] == DUPLICATE_DIFFERENT_ID:
            await _create_or_link_patient(wa, sessions, phone, hospital_id, context, connector, language)
            return
        if reply["id"] == CONFIRM_NO:
            if identity_flow_next == "manage_patients":
                from flows.patient_identity.manage_patients import _start_manage_patients

                await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            else:
                await _start_registration(wa, sessions, phone, hospital_id, connector, language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_DUPLICATE_DECISION, context, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t(DUPLICATE_PATIENT_FOUND, language,
            name=context.get("duplicate_patient_name", ""), patient_code=context.get("duplicate_patient_display_id") or "—",
        ),
        buttons=[
            {"id": DUPLICATE_LINK_ID, "title": t(DUPLICATE_LINK_BUTTON, language)},
            {"id": DUPLICATE_DIFFERENT_ID, "title": t(DUPLICATE_DIFFERENT_BUTTON, language)},
            {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
        ],
    )


async def _create_or_link_patient(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, connector: Connector, language: str,
) -> None:
    """Shared tail end of registration: links an existing patient
    (context["link_target_patient_id"] set) or creates a brand-new one from
    the collected name/age/gender, then lands on the main menu (or back on
    Manage Patients, if that's where this registration was launched from)."""
    identity_flow_next = context.get("identity_flow_next", "resolve")
    try:
        if context.get("link_target_patient_id") is not None:
            patient = connector.link_existing_patient(
                hospital_id, phone, context["link_target_patient_id"],
                relationship_label=context.get("pending_relationship"),
            )
        else:
            patient = connector.create_patient_profile(
                hospital_id, phone, context["pending_name"], context.get("pending_age"),
                relationship_label=context.get("pending_relationship"), gender=context.get("pending_gender"),
                contact_phone=context.get("pending_contact_phone"),
            )
    except TooManyLinkedPatientsError:
        await wa.send_text(phone, t(TOO_MANY_LINKED_PATIENTS, language))
        if identity_flow_next == "manage_patients":
            from flows.patient_identity.manage_patients import _start_manage_patients

            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        else:
            sessions.reset(hospital_id, phone)
            await wa.send_text(phone, t(REGISTRATION_BLOCKED_CONTACT_HOSPITAL, language))
        return
    except DuplicateSelfLinkError:
        # The soft pre-check (has_self_linked_patient, in _start_registration)
        # should make this essentially unreachable outside a genuine race
        # between two concurrent "Myself" registrations from the same
        # account -- restart registration rather than dead-end; by the time
        # they retry, has_self_linked_patient() will correctly lock them to
        # "Someone Else".
        await wa.send_text(phone, t(DUPLICATE_SELF_LINK, language))
        if identity_flow_next == "manage_patients":
            from flows.patient_identity.manage_patients import _start_manage_patients

            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        else:
            await _start_registration(wa, sessions, phone, hospital_id, connector, language)
        return

    if identity_flow_next == "manage_patients":
        # Confirmed with the user: lands on the main menu now, not back on
        # the Manage Patients screen -- same "message, then IDLE" ending as
        # the Remove Patient flow (manage_patients.py). Doesn't override
        # active_patient_id, so whichever patient was already active (Manage
        # Patients is only ever reached with one already resolved) stays
        # active -- just_confirmed_patient is still required, though: adding
        # a 2nd+ patient here means get_or_prompt_for_active_patient would
        # otherwise treat this same IDLE re-entry as "2+ patients, no
        # confirmation yet" and show the "who is this for" selector instead
        # of the real main menu (see that function's own docstring).
        await wa.send_text(phone, t(PATIENT_ADDED, language, patient_name=patient["name"]))
        sessions.set(hospital_id, phone, "IDLE", {"just_confirmed_patient": True}, language=language)
        return
    sessions.set(
        hospital_id, phone, "IDLE", {"just_confirmed_patient": True}, language=language,
        active_patient_id=patient["id"],
    )

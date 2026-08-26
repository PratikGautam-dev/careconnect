# core/patient_identity.py
"""
CareConnect architecture doc alignment (Spec.md Section 0) -- implements the
doc's Sections 1-20 almost verbatim: WhatsApp Account != Patient. This module
owns everything the doc's "Final Architecture Boundary" (Section 23) covers --
account identification, patient registration/duplicate-matching, patient
selection, and the transition into the Main Menu -- so that everything AFTER
the Main Menu (core/booking_flow.py, faq_flow.py) can simply trust an already-
resolved `active_patient_id` rather than re-deriving identity itself (Section
23's own explicit instruction).

This is now the ONE place a fresh/returning conversation's patient identity
gets resolved -- flows.py's `_enter_idle()` calls `get_or_prompt_for_active_
patient()` right after language is settled and BEFORE the main menu is ever
shown, for every hospital, matching the doc's Section 5/19 flow exactly
(confirmed with the user: applies universally, not gated on which features a
hospital has enabled).

Also owns `_send_dynamic_menu()` (moved from flows.py) and the feature-menu
constants (`_FEATURE_MENU`/`REAL_FEATURES`/`ALL_FEATURES`) -- moved here
rather than left in flows.py so this module can show the Main Menu itself
(with the "Patient: X / MRN: Y" header, Section 20) the instant resolution
completes, without flows.py needing to import back into this module (which
WOULD be circular, since flows.py already imports the resolution entry point
from here). flows.py re-exports these same names for every existing importer
(admin/tenants_api.py, portal/routes/settings.py) that already does `from flows import
REAL_FEATURES` etc. -- unchanged from their point of view.

Architectural boundary (same rule core/booking_flow.py's own docstring
states): this module never imports db/repository.py directly, only through
connectors.py -- every hospital-scoped read/write goes through the
`Connector` interface passed into every function here.

Known, deliberate scope decision (flagged, not hidden): core/booking_flow.py
ALSO still contains its own older, now-effectively-dead-for-real-traffic
patient-selector/Manage-Patients implementation from the previous round
(`_send_patient_selector`, `_handle_awaiting_patient_selection`, its own
Manage Patients mini-flow) -- real traffic (flows.py) no longer reaches any
of it, since patient identity is now resolved HERE, before the main menu, not
lazily per-feature inside booking_flow.py. It's kept in place only because
tests/test_booking_flow.py exercises core/booking_flow.py's OWN standalone
handle_incoming() directly (a documented, pre-existing pattern -- see that
module's docstring) as a unit test of the state machine independent of
whichever router sits in front of it; deleting it would mean rewriting that
entire test file blind, which was judged too risky to do in the same pass as
this restructuring. Worth a dedicated cleanup pass later.
"""
import logging

from connectors import Connector, MAX_ACTIVE_PATIENT_LINKS, RELATIONSHIP_OPTIONS, TooManyLinkedPatientsError
from flows.common import cap_rows
from core.translations import t
from core.whatsapp import WhatsAppClient

logger = logging.getLogger(__name__)

# --- Main menu (moved from flows.py -- see module docstring for why) ---

# feature key -> (menu row id, menu row title key into core/translations.py).
# Order here is the order rows appear in the main menu, matching the
# onboarding wizard's Patient Experience step (Section 14.6) and the
# reference design's own toggle-grid ordering.
#
# CareConnect architecture doc alignment (Spec.md Section 0): "my_details"
# renamed to "reports_prescriptions" (Section 20's exact menu item), with an
# idempotent migration (db/init_db.py's _backfill_reports_prescriptions_feature())
# converting any hospital's existing "my_details" entry in enabled_features/
# feature_labels to the new key -- the underlying implementation
# (flows.py's _send_my_details/_handle_awaiting_my_details_document) is
# unchanged, just repositioned/rescoped (now to the ACTIVE patient, not the
# phone generally -- see _send_my_details' own docstring). "manage_patients"
# and "consent_privacy" are new (Section 20's own menu list).
_FEATURE_MENU = {
    "booking": ("menu_book", "feature_booking"),
    "reschedule": ("menu_reschedule", "feature_reschedule"),
    "cancel": ("menu_cancel", "feature_cancel"),
    "view_appointments": ("menu_view_appointments", "feature_view_appointments"),
    "reports_prescriptions": ("menu_reports_prescriptions", "feature_reports_prescriptions"),
    "manage_patients": ("menu_manage_patients", "feature_manage_patients"),
    "consent_privacy": ("menu_consent_privacy", "feature_consent_privacy"),
    "hospital_info": ("menu_hospital_info", "feature_hospital_info"),
    "reception_handoff": ("menu_reception", "feature_reception_handoff"),
    "faq": ("menu_faq_bot", "feature_faq"),
}
_ROW_ID_TO_FEATURE = {row_id: key for key, (row_id, _title_key) in _FEATURE_MENU.items()}

REAL_FEATURES = set(_FEATURE_MENU.keys())
ALL_FEATURES = REAL_FEATURES

# Item 4 (Spec.md Section 0, pre-existing): deliberately NOT a member of
# _FEATURE_MENU/enabled_features -- always appended to the main menu (unless
# the hospital has disabled the language picker outright), not a per-hospital
# toggle.
CHANGE_LANGUAGE_ROW = "menu_change_language"

# Lets the same phone switch which linked patient the conversation acts as --
# always offered (not gated on >1 linked patient), since the patient
# selector it opens also has the "Manage Patients"/add-a-patient entry point,
# so it's the way to go from exactly one linked patient to a second one too.
# A separate row/mechanism from the "manage_patients" FEATURE (that one's a
# full view/add/unlink screen, opt-in per hospital, reached from its own
# main-menu row when enabled) -- this is always available, on every tenant,
# confirmed with the user directly: "give back button also after main menu
# to go to select patients."
SWITCH_PATIENT_ROW = "menu_switch_patient"

GOTO_MAIN_MENU = "goto_main_menu"
CONFIRM_YES = "confirm"
CONFIRM_NO = "cancel"
# "Back" for the identity-resolution mini-flow (name -> age -> [duplicate
# decision] -> relationship). A separate id from flows/booking/state.py's
# BACK_ID -- this module's own docstring forbids importing from booking, and
# since each state's handler only ever checks its own id, there's no
# functional need to share one. GOTO_MAIN_MENU/CONFIRM_NO already serve as
# "back" for the states reachable only from an existing menu (manage
# patients, unlink-confirm, consent) or that are themselves the first screen
# shown (single-patient-confirm, patient selector) -- this id only covers the
# genuinely-linear steps that had no way back before.
BACK_ID = "identity_nav_back"


def _patient_header(active_patient: dict | None, language: str) -> str:
    """Section 20's exact header shape -- "Patient: {name}\\nMRN: {id}" --
    shown above the main menu whenever a patient has been resolved for this
    conversation. patient_display_id (Section 12's own permanent, human-
    readable id) IS the MRN here -- confirmed with the user rather than
    building a second parallel identifier system."""
    if active_patient is None:
        return ""
    mrn = active_patient.get("patient_display_id") or "—"
    return f"*{t('patient_header_label', language)}* {active_patient['name']}\n*MRN:* {mrn}\n\n"


async def _send_dynamic_menu(
    wa: WhatsAppClient, phone: str, hospital_name: str, enabled_features: list[str], language: str = "en",
    feature_labels: dict[str, str] | None = None, language_prompt_enabled: bool = True,
    active_patient: dict | None = None,
) -> None:
    feature_labels = feature_labels or {}
    rows = [
        {"id": row_id, "title": feature_labels.get(key) or t(title_key, language)}
        for key, (row_id, title_key) in _FEATURE_MENU.items()
        if key in enabled_features
    ]
    if not rows:
        await wa.send_text(phone, t("feature_menu_unavailable", language, hospital_name=hospital_name))
        return
    rows = cap_rows(rows, f"main menu for {hospital_name}")
    body_text = _patient_header(active_patient, language) + t("welcome_menu", language, hospital_name=hospital_name)
    await wa.send_list(
        to=phone,
        body_text=body_text,
        button_text=t("main_menu_button", language),
        sections=[{"title": t("main_menu_section_title", language), "rows": rows}],
    )
    # Confirmed with the user directly: shown as its OWN follow-up buttons
    # message right under the main menu list, not as a row hidden inside it
    # (WhatsApp collapses a list to just its button_text until tapped, so a
    # row-based version was invisible until the patient opened the list) --
    # same "list, then a separate Back message" convention flows/booking/
    # messages.py's own _send_back_button already established.
    await wa.send_buttons(
        to=phone, body_text="​", buttons=[{"id": SWITCH_PATIENT_ROW, "title": t("back_option", language)}],
    )


# --- Row-id helpers ---

_PATIENT_ROW_PREFIX = "idpat_"
_UNLINK_ROW_PREFIX = "idunlink_"
_REL_ROW_PREFIX = "idrel_"
MANAGE_ADD_ROW_ID = "id_manage_add"
MANAGE_PATIENTS_ENTRY_ID = "id_manage_patients_entry"
# Single-patient-confirm screen's escape hatch (confirmed with the user):
# goes straight into registration (_start_registration(), same entry point
# the 0-linked-patients case uses) rather than the full Manage Patients
# menu -- the natural action from "continue as X?" is adding someone else
# on this phone, not managing existing links.
ADD_PATIENT_ENTRY_ID = "id_add_patient_entry"
DUPLICATE_LINK_ID = "id_dup_link"
DUPLICATE_DIFFERENT_ID = "id_dup_different"
CONSENT_TOGGLE_MARKETING_ID = "id_consent_marketing_toggle"
CONSENT_WITHDRAW_SERVICE_ID = "id_consent_withdraw_service"

_RELATIONSHIP_ROW_IDS = {f"{_REL_ROW_PREFIX}{opt.lower()}": opt for opt in RELATIONSHIP_OPTIONS}


async def _send_back_button(wa: WhatsAppClient, phone: str, language: str = "en") -> None:
    """Same follow-up-buttons-message pattern as flows/booking/messages.py's
    own _send_back_button (zero-width-space body, since Meta's button
    message type rejects a truly empty one) -- duplicated rather than
    imported per this module's own architectural boundary (no dependency on
    flows/booking)."""
    await wa.send_buttons(to=phone, body_text="​", buttons=[{"id": BACK_ID, "title": t("back_option", language)}])


def _patient_row_id(patient_id: int) -> str:
    return f"{_PATIENT_ROW_PREFIX}{patient_id}"


def _parse_patient_row_id(row_id: str) -> int | None:
    if not row_id.startswith(_PATIENT_ROW_PREFIX):
        return None
    try:
        return int(row_id[len(_PATIENT_ROW_PREFIX):])
    except ValueError:
        return None


def _unlink_row_id(patient_id: int) -> str:
    return f"{_UNLINK_ROW_PREFIX}{patient_id}"


def _parse_unlink_row_id(row_id: str) -> int | None:
    if not row_id.startswith(_UNLINK_ROW_PREFIX):
        return None
    try:
        return int(row_id[len(_UNLINK_ROW_PREFIX):])
    except ValueError:
        return None


def _patient_row_title(patient: dict) -> str:
    label = patient.get("relationship_label")
    return f"{patient['name']} — {label}" if label else patient["name"]


# --- Conversation states ("IDENTITY_" prefixed -- deliberately distinct
# string values from core/booking_flow.py's own similarly-named leftover
# states, see module docstring's "known scope decision" -- these two sets
# are dispatched from the same combined table in flows.py, so a collision
# would silently shadow one implementation with the other.) ---

STATE_AWAITING_PATIENT_NAME = "IDENTITY_AWAITING_NAME"
STATE_AWAITING_PATIENT_AGE = "IDENTITY_AWAITING_AGE"
STATE_AWAITING_DUPLICATE_DECISION = "IDENTITY_AWAITING_DUPLICATE_DECISION"
STATE_AWAITING_RELATIONSHIP = "IDENTITY_AWAITING_RELATIONSHIP"
STATE_AWAITING_SINGLE_PATIENT_CONFIRM = "IDENTITY_AWAITING_SINGLE_CONFIRM"
STATE_AWAITING_PATIENT_SELECTION = "IDENTITY_AWAITING_SELECTION"
STATE_AWAITING_MANAGE_PATIENTS_ACTION = "IDENTITY_AWAITING_MANAGE_ACTION"
STATE_AWAITING_UNLINK_CONFIRM = "IDENTITY_AWAITING_UNLINK_CONFIRM"
STATE_AWAITING_CONSENT_ACTION = "IDENTITY_AWAITING_CONSENT_ACTION"

FREE_TEXT_INPUT_STATES = {STATE_AWAITING_PATIENT_NAME, STATE_AWAITING_PATIENT_AGE}

MIN_PATIENT_AGE = 0
MAX_PATIENT_AGE = 120


def _parse_patient_age(text: str) -> int | None:
    text = text.strip()
    if not text.isdigit():
        return None
    age = int(text)
    if age < MIN_PATIENT_AGE or age > MAX_PATIENT_AGE:
        return None
    return age


# --- Section 5/19: the resolution entry point ---

async def get_or_prompt_for_active_patient(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector,
    language: str = "en", require_patient_confirmation: bool = False,
) -> dict | None:
    """Called by flows.py's `_enter_idle()` right after language is settled,
    BEFORE the main menu is ever shown (Section 5's "Initial WhatsApp Flow" /
    Section 19's "Main Menu Entry Conditions"). Returns the resolved active
    patient's info dict (id/name/age/patient_display_id/relationship_label)
    the instant one is available -- zero-friction for the already-resolved
    case (this session already has a valid active_patient_id) and the
    exactly-one-linked-patient case (unless the hospital's
    require_patient_confirmation is on, Section 11) -- or None if it just
    sent an interstitial message (registration / confirmation / selection)
    and the caller must stop; the conversation continues from whatever state
    was just set, and will re-enter here once resolution actually completes
    (every completion path below ends by calling this again)."""
    session = sessions.get(hospital_id, phone)
    active_patient_id = session.get("active_patient_id")
    if active_patient_id is not None:
        if connector.validate_active_patient_link(hospital_id, phone, active_patient_id):
            patients = connector.list_active_patients(hospital_id, phone)
            match = next((p for p in patients if p["id"] == active_patient_id), None)
            if match is not None:
                return match
        # Stale (unlinked, or the patient was blocked/inactivated since) --
        # force a fresh resolution rather than trusting it further.
        sessions.clear_active_patient(hospital_id, phone)

    patients = connector.list_active_patients(hospital_id, phone)
    if len(patients) == 0:
        await _start_registration(wa, sessions, phone, hospital_id, language)
        return None
    if len(patients) == 1:
        if require_patient_confirmation:
            await _send_single_patient_confirm(wa, sessions, phone, hospital_id, patients[0], language)
            return None
        sessions.set(hospital_id, phone, "IDLE", {}, language=language, active_patient_id=patients[0]["id"])
        return patients[0]
    await _send_patient_selector(wa, sessions, phone, hospital_id, connector, language)
    return None


# --- Section 6/7: registration ---

async def _start_registration(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, language: str) -> None:
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, {"identity_flow_next": "resolve"}, language=language)
    await wa.send_text(phone, t("ask_patient_name", language))


async def _handle_awaiting_patient_name(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    # Only reachable when this name-ask has a real earlier screen to return
    # to -- the very first, pre-resolution registration (identity_flow_next
    # == "resolve") has nothing before it, same reasoning as booking's own
    # BACK_ID at its first step.
    if (
        reply["type"] == "interactive_reply" and reply["id"] == BACK_ID
        and context.get("identity_flow_next") == "manage_patients"
    ):
        await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        return
    if reply["type"] == "text" and reply["text"].strip():
        name = reply["text"].strip()
        new_context = {**context, "pending_name": name}
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, new_context, language=language)
        await wa.send_text(phone, t("ask_patient_age", language, patient_name=name))
        if context.get("identity_flow_next") == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, context, language=language)
    await wa.send_text(phone, t("invalid_patient_name", language))
    await wa.send_text(phone, t("ask_patient_name", language))
    if context.get("identity_flow_next") == "manage_patients":
        await _send_back_button(wa, phone, language=language)


async def _handle_awaiting_patient_age(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID:
        identity_flow_next = context.get("identity_flow_next", "resolve")
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, {"identity_flow_next": identity_flow_next}, language=language)
        await wa.send_text(phone, t("ask_patient_name", language))
        if identity_flow_next == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    age = _parse_patient_age(reply["text"]) if reply["type"] == "text" else None
    if age is None:
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, context, language=language)
        await wa.send_text(phone, t("invalid_patient_age", language))
        await wa.send_text(phone, t("ask_patient_age", language, patient_name=context.get("pending_name", "")))
        if context.get("identity_flow_next") == "manage_patients":
            await _send_back_button(wa, phone, language=language)
        return
    new_context = {**context, "pending_age": age}
    # Sections 8-10: search for a plausible existing match BEFORE creating
    # anything -- confirmed with the user, simple/conservative criteria only
    # (exact normalized name + exact age, no fuzzy matching).
    match = connector.find_potential_duplicate_patient(hospital_id, phone, context["pending_name"], age)
    if match is not None:
        new_context["duplicate_patient_id"] = match["id"]
        new_context["duplicate_patient_name"] = match["name"]
        new_context["duplicate_patient_display_id"] = match["patient_display_id"]
        sessions.set(hospital_id, phone, STATE_AWAITING_DUPLICATE_DECISION, new_context, language=language)
        await wa.send_buttons(
            to=phone,
            body_text=t("duplicate_patient_found", language, name=match["name"], mrn=match["patient_display_id"] or "—"),
            buttons=[
                {"id": DUPLICATE_LINK_ID, "title": t("duplicate_link_button", language)},
                {"id": DUPLICATE_DIFFERENT_ID, "title": t("duplicate_different_button", language)},
                {"id": CONFIRM_NO, "title": t("cancel_button", language)},
            ],
        )
        return
    await _send_relationship_picker(wa, sessions, phone, hospital_id, new_context, language)


async def _handle_awaiting_duplicate_decision(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    identity_flow_next = context.get("identity_flow_next", "resolve")
    if reply["type"] == "interactive_reply":
        if reply["id"] == DUPLICATE_LINK_ID:
            # Section 9: link the EXISTING patient -- no new MRN.
            link_context = {
                "identity_flow_next": identity_flow_next,
                "link_target_patient_id": context["duplicate_patient_id"],
                # Kept only so "Back" from the relationship picker can
                # reconstruct this exact screen -- not otherwise consulted
                # here since link_target_patient_id above is what matters.
                "duplicate_patient_id": context["duplicate_patient_id"],
                "duplicate_patient_name": context.get("duplicate_patient_name"),
                "duplicate_patient_display_id": context.get("duplicate_patient_display_id"),
            }
            await _send_relationship_picker(wa, sessions, phone, hospital_id, link_context, language)
            return
        if reply["id"] == DUPLICATE_DIFFERENT_ID:
            new_context = {
                "identity_flow_next": identity_flow_next,
                "pending_name": context.get("pending_name"),
                "pending_age": context.get("pending_age"),
                "duplicate_patient_id": context.get("duplicate_patient_id"),
                "duplicate_patient_name": context.get("duplicate_patient_name"),
                "duplicate_patient_display_id": context.get("duplicate_patient_display_id"),
            }
            await _send_relationship_picker(wa, sessions, phone, hospital_id, new_context, language)
            return
        if reply["id"] == CONFIRM_NO:
            if identity_flow_next == "manage_patients":
                await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            else:
                await _start_registration(wa, sessions, phone, hospital_id, language)
            return
    # Unrecognized/stale tap -- re-show the same decision.
    sessions.set(hospital_id, phone, STATE_AWAITING_DUPLICATE_DECISION, context, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t(
            "duplicate_patient_found", language,
            name=context.get("duplicate_patient_name", ""), mrn=context.get("duplicate_patient_display_id") or "—",
        ),
        buttons=[
            {"id": DUPLICATE_LINK_ID, "title": t("duplicate_link_button", language)},
            {"id": DUPLICATE_DIFFERENT_ID, "title": t("duplicate_different_button", language)},
            {"id": CONFIRM_NO, "title": t("cancel_button", language)},
        ],
    )


# --- Section 17: structured relationship field ---

async def _send_relationship_picker(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, language: str,
) -> None:
    rows = [{"id": row_id, "title": t(f"relationship_{opt.lower()}", language)} for row_id, opt in _RELATIONSHIP_ROW_IDS.items()]
    rows.append({"id": BACK_ID, "title": t("back_option", language)})
    sessions.set(hospital_id, phone, STATE_AWAITING_RELATIONSHIP, context, language=language)
    await wa.send_list(
        to=phone,
        body_text=t("ask_relationship", language),
        button_text=t("ask_relationship_button", language),
        sections=[{"title": t("ask_relationship_section_title", language), "rows": rows}],
    )


async def _handle_awaiting_relationship(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    if reply["type"] == "interactive_reply" and reply["id"] == BACK_ID:
        # Came either via the duplicate-decision screen (duplicate_patient_id
        # set, whichever of DUPLICATE_LINK_ID/DUPLICATE_DIFFERENT_ID was
        # tapped) or straight from age when no duplicate was found.
        if context.get("duplicate_patient_id") is not None:
            sessions.set(hospital_id, phone, STATE_AWAITING_DUPLICATE_DECISION, context, language=language)
            await wa.send_buttons(
                to=phone,
                body_text=t(
                    "duplicate_patient_found", language,
                    name=context.get("duplicate_patient_name", ""), mrn=context.get("duplicate_patient_display_id") or "—",
                ),
                buttons=[
                    {"id": DUPLICATE_LINK_ID, "title": t("duplicate_link_button", language)},
                    {"id": DUPLICATE_DIFFERENT_ID, "title": t("duplicate_different_button", language)},
                    {"id": CONFIRM_NO, "title": t("cancel_button", language)},
                ],
            )
            return
        sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_AGE, context, language=language)
        await wa.send_text(phone, t("ask_patient_age", language, patient_name=context.get("pending_name", "")))
        await _send_back_button(wa, phone, language=language)
        return
    relationship_label = _RELATIONSHIP_ROW_IDS.get(reply["id"]) if reply["type"] == "interactive_reply" else None
    if relationship_label is None:
        await _send_relationship_picker(wa, sessions, phone, hospital_id, context, language)
        return

    identity_flow_next = context.get("identity_flow_next", "resolve")
    try:
        if context.get("link_target_patient_id") is not None:
            patient = connector.link_existing_patient(
                hospital_id, phone, context["link_target_patient_id"], relationship_label=relationship_label,
            )
        else:
            patient = connector.create_patient_profile(
                hospital_id, phone, context["pending_name"], context.get("pending_age"),
                relationship_label=relationship_label,
            )
    except TooManyLinkedPatientsError:
        await wa.send_text(phone, t("too_many_linked_patients", language))
        if identity_flow_next == "manage_patients":
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        else:
            sessions.reset(hospital_id, phone)
            await wa.send_text(phone, t("registration_blocked_contact_hospital", language))
        return

    if identity_flow_next == "manage_patients":
        await wa.send_text(phone, t("patient_added", language, patient_name=patient["name"]))
        await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
        return
    sessions.set(hospital_id, phone, "IDLE", {}, language=language, active_patient_id=patient["id"])


# --- Section 11: single-linked-patient confirmation (hospital-configurable) ---

async def _send_single_patient_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, patient: dict, language: str,
) -> None:
    sessions.set(
        hospital_id, phone, STATE_AWAITING_SINGLE_PATIENT_CONFIRM, {"candidate_patient_id": patient["id"]},
        language=language,
    )
    await wa.send_buttons(
        to=phone,
        body_text=t(
            "single_patient_confirm", language, patient_name=patient["name"], mrn=patient["patient_display_id"] or "—",
        ),
        buttons=[
            {"id": CONFIRM_YES, "title": t("confirm_button", language)},
            # Confirmed with the user: the natural action from "continue as
            # X?" is adding someone ELSE on this phone (a family member not
            # yet linked), not the full Manage Patients menu -- goes
            # straight into registration via _start_registration(), which
            # auto-selects the newly added patient as active once done
            # (identity_flow_next defaults to "resolve").
            {"id": ADD_PATIENT_ENTRY_ID, "title": t("add_patient_short", language)},
        ],
    )


async def _handle_awaiting_single_patient_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    if reply["type"] == "interactive_reply":
        if reply["id"] == CONFIRM_YES:
            sessions.set(
                hospital_id, phone, "IDLE", {}, language=language, active_patient_id=context["candidate_patient_id"],
            )
            return
        if reply["id"] == ADD_PATIENT_ENTRY_ID:
            await _start_registration(wa, sessions, phone, hospital_id, language)
            return
    # Unrecognized/stale -- re-fetch (the single patient may have changed
    # since this was sent) and re-show fresh.
    patients = connector.list_active_patients(hospital_id, phone)
    if len(patients) == 1:
        await _send_single_patient_confirm(wa, sessions, phone, hospital_id, patients[0], language)
    else:
        sessions.clear_active_patient(hospital_id, phone)
        sessions.reset(hospital_id, phone)


# --- Section 12: multi-patient selection ---

async def _send_patient_selector(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str,
) -> None:
    patients = connector.list_active_patients(hospital_id, phone)
    rows = [{"id": _patient_row_id(p["id"]), "title": _patient_row_title(p)} for p in patients]
    rows.append({"id": MANAGE_PATIENTS_ENTRY_ID, "title": t("manage_patients_short", language)})
    rows = cap_rows(rows, "patient selector")
    sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_SELECTION, {}, language=language)
    await wa.send_list(
        to=phone,
        body_text=t("patient_selector_prompt", language),
        button_text=t("patient_selector_button", language),
        sections=[{"title": t("patient_selector_section_title", language), "rows": rows}],
    )


async def _handle_awaiting_patient_selection(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    if reply["type"] == "interactive_reply":
        if reply["id"] == MANAGE_PATIENTS_ENTRY_ID:
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
        patient_id = _parse_patient_row_id(reply["id"])
        if patient_id is not None:
            patients = connector.list_active_patients(hospital_id, phone)
            if any(p["id"] == patient_id for p in patients):
                sessions.set(hospital_id, phone, "IDLE", {}, language=language, active_patient_id=patient_id)
                return
    await _send_patient_selector(wa, sessions, phone, hospital_id, connector, language)


# --- Section 15/16: Manage Patients (view / add / unlink) ---

async def _start_manage_patients(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    patients = connector.list_active_patients(hospital_id, phone)
    rows = [{"id": _patient_row_id(p["id"]), "title": _patient_row_title(p)} for p in patients]
    if len(patients) < MAX_ACTIVE_PATIENT_LINKS:
        rows.append({"id": MANAGE_ADD_ROW_ID, "title": t("add_patient_option", language)})
    rows.append({"id": GOTO_MAIN_MENU, "title": t("back_to_menu_option", language)})
    rows = cap_rows(rows, "manage patients list")
    sessions.set(hospital_id, phone, STATE_AWAITING_MANAGE_PATIENTS_ACTION, {}, language=language)
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
        if rid == MANAGE_ADD_ROW_ID:
            patients = connector.list_active_patients(hospital_id, phone)
            if len(patients) >= MAX_ACTIVE_PATIENT_LINKS:
                await wa.send_text(phone, t("too_many_linked_patients", language))
                await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
                return
            sessions.set(hospital_id, phone, STATE_AWAITING_PATIENT_NAME, {"identity_flow_next": "manage_patients"}, language=language)
            await wa.send_text(phone, t("ask_patient_name", language))
            await _send_back_button(wa, phone, language=language)
            return
        patient_id = _parse_patient_row_id(rid)
        if patient_id is not None:
            patients = connector.list_active_patients(hospital_id, phone)
            match = next((p for p in patients if p["id"] == patient_id), None)
            if match:
                sessions.set(
                    hospital_id, phone, STATE_AWAITING_UNLINK_CONFIRM,
                    {"unlink_patient_id": patient_id, "unlink_patient_name": match["name"]}, language=language,
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
    await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)


async def _handle_awaiting_unlink_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    patient_id = context.get("unlink_patient_id")
    patient_name = context.get("unlink_patient_name", "")
    if reply["type"] == "interactive_reply" and patient_id is not None:
        if reply["id"] == CONFIRM_YES:
            # Section 16: soft-unlink only -- never touches `patients` or
            # appointment history.
            connector.unlink_patient(hospital_id, phone, patient_id)
            session = sessions.get(hospital_id, phone)
            if session.get("active_patient_id") == patient_id:
                # Unlinked the currently-active patient -- force
                # re-resolution rather than keep using a stale reference.
                sessions.clear_active_patient(hospital_id, phone)
            await wa.send_text(phone, t("patient_unlinked", language, patient_name=patient_name))
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
        if reply["id"] == CONFIRM_NO:
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_UNLINK_CONFIRM, context, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t("unlink_patient_confirm", language, patient_name=patient_name),
        buttons=[
            {"id": CONFIRM_YES, "title": t("confirm_button", language)},
            {"id": CONFIRM_NO, "title": t("cancel_button", language)},
        ],
    )


# --- Section 20's "Consent & Privacy" menu item ---

async def start_consent_privacy(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector: Connector,
    active_patient_id: int, privacy_notice_text: str | None = None, language: str = "en",
) -> None:
    """Kept appropriately minimal, per the user's own instruction -- a real,
    working consent-status display + marketing-consent toggle, not a full
    legal consent-management platform. Service consent and marketing consent
    are shown and controlled separately (never bundled), per the doc's own
    explicit instruction: service consent is implicit in having an active
    link at all (withdrawing it maps to Manage Patients' unlink, not a
    second toggle here -- see db/schema.sql's own comment on why);
    marketing_consent is a genuine, independently-togglable opt-in."""
    consent = connector.get_patient_link_consent(hospital_id, phone, active_patient_id)
    if consent is None:
        # Stale active_patient_id (shouldn't normally happen -- resolution
        # already validates it) -- fall back to a safe re-resolution.
        sessions.clear_active_patient(hospital_id, phone)
        sessions.reset(hospital_id, phone)
        return
    notice = privacy_notice_text or t("privacy_notice_default", language)
    marketing_status = t("consent_on", language) if consent["marketing_consent"] else t("consent_off", language)
    body = t(
        "consent_privacy_body", language, notice=notice,
        marketing_status=marketing_status,
    )
    sessions.set(hospital_id, phone, STATE_AWAITING_CONSENT_ACTION, {}, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=body,
        buttons=[
            {
                "id": CONSENT_TOGGLE_MARKETING_ID,
                "title": t("consent_marketing_disable", language) if consent["marketing_consent"] else t("consent_marketing_enable", language),
            },
            {"id": GOTO_MAIN_MENU, "title": t("back_to_menu_option", language)},
        ],
    )


async def handle_awaiting_consent_action(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict,
    connector: Connector, active_patient_id: int, privacy_notice_text: str | None = None, language: str = "en",
) -> None:
    if reply["type"] == "interactive_reply" and reply["id"] == CONSENT_TOGGLE_MARKETING_ID:
        consent = connector.get_patient_link_consent(hospital_id, phone, active_patient_id)
        if consent is not None:
            connector.set_marketing_consent(hospital_id, phone, active_patient_id, not consent["marketing_consent"])
    await start_consent_privacy(
        wa, sessions, phone, hospital_id, connector, active_patient_id,
        privacy_notice_text=privacy_notice_text, language=language,
    )


# Handlers taking the "standard" 8-arg shape flows.py's generic dispatch
# already uses for core/booking_flow.py's own _HANDLERS -- consent's two
# functions above need extra args (hospital/active_patient_id) so they're
# NOT in this table; flows.py calls them directly instead (see its own
# STATE_AWAITING_CONSENT_ACTION branch).
_HANDLERS = {
    STATE_AWAITING_PATIENT_NAME: _handle_awaiting_patient_name,
    STATE_AWAITING_PATIENT_AGE: _handle_awaiting_patient_age,
    STATE_AWAITING_DUPLICATE_DECISION: _handle_awaiting_duplicate_decision,
    STATE_AWAITING_RELATIONSHIP: _handle_awaiting_relationship,
    STATE_AWAITING_SINGLE_PATIENT_CONFIRM: _handle_awaiting_single_patient_confirm,
    STATE_AWAITING_PATIENT_SELECTION: _handle_awaiting_patient_selection,
    STATE_AWAITING_MANAGE_PATIENTS_ACTION: _handle_awaiting_manage_patients_action,
    STATE_AWAITING_UNLINK_CONFIRM: _handle_awaiting_unlink_confirm,
}

# flows.py
"""
SPEC Section 14.5: the feature-toggle router -- supersedes Section 14.1's
single flow_type dispatch. A hospital enables a SET of patient-facing
capabilities (hospitals.enabled_features, Section 14.5) rather than picking
one exclusive conversation shape; this module is now the actual conversation
entry point core/main.py calls (not just a lookup table), because building
the IDLE main menu is inherently a cross-cutting concern once more than one
feature can be enabled at once -- no single flow module can own it anymore.

How it works:
- IDLE (or an unrecognized/stale state): resolves the active patient first
  (core/patient_identity.py, CareConnect architecture doc alignment -- see
  _enter_idle()'s own docstring), then shows a WhatsApp list built from
  whichever of the hospital's enabled_features are real, tapping a row hands
  the conversation to that feature's own entry point.
- A state that belongs to core/booking_flow.py's own state machine
  (STATE_AWAITING_DEPARTMENT, STATE_AWAITING_DATE/TIME_SLOT, the cancel/
  reschedule states, ...): delegated STRAIGHT to booking_flow.py's existing per-state
  handlers (_HANDLERS), unchanged -- booking_flow.py's own internal
  validation/booking logic was not touched for this. booking_flow.py's OWN
  handle_incoming()/_handle_idle() (a fixed 4-item menu) are now effectively
  superseded for real traffic -- core/main.py never calls them directly
  anymore -- but they're left as-is (not deleted) since tests/test_booking_flow.py
  still exercises them directly as a standalone unit test of the state
  machine's internals, independent of which menu structure sits in front of it.
- A state that belongs to core/patient_identity.py's own state machine
  (registration, duplicate-match decision, relationship picking, patient
  selection, Manage Patients, unlink confirm): delegated to that module's
  own _HANDLERS, same generic dispatch shape as booking_flow.py's. If that
  handler's own action fully resolved the active patient (session state is
  now IDLE), the main menu is shown immediately afterward -- see
  handle_incoming()'s own dispatch block for why this check lives here and
  not in core/patient_identity.py itself (avoiding a circular import).
- faq_flow.STATE_FAQ_ACTIVE: delegated to faq_flow.handle_incoming(), which
  (as of this section) stays in that state across messages instead of
  resetting to true IDLE, so the topic-tap loop keeps working across multiple
  incoming messages without falling back to the unified menu after every tap.
- A reset keyword (any state): always returns to the TOP-level unified menu,
  not just whichever sub-flow's own idea of "start over" is -- this is new
  behavior, and deliberately so: a patient two levels deep (e.g. mid-FAQ
  after tapping in from the unified menu) typing "hi" should land back at
  the full menu of everything this hospital offers, not just FAQ's own topic
  list.

REAL_FEATURES/ALL_FEATURES/_FEATURE_MENU/_send_dynamic_menu now live in
core/patient_identity.py (re-exported here for every existing importer that
already does `from flows import REAL_FEATURES` etc.) -- see that module's own
docstring for why.

Section 12.11 (language selection): this module owns the ONE language-
selection decision point -- STATE_AWAITING_LANGUAGE, entered whenever a
session reaches true IDLE with no language chosen yet (first contact, or a
genuinely expired/new session; core/session_store.py's session store preserves an
already-chosen language across an in-conversation reset(), so this does NOT
re-ask after every completed action, only once per fresh conversation). Once
chosen, `language` is threaded down into every sub-flow (booking_flow.py,
patient_identity.py, faq_flow.py) this router delegates to, so the whole
conversation -- not just this module's own menu -- responds in the chosen
language.
"""
import logging

import db.repository as db
import flows.patient_identity as patient_identity
from flows.booking import (
    HANDLERS as _BOOKING_STATE_HANDLERS,
    manage_cancel_id,
    manage_reschedule_id,
    parse_manage_id,
    start_booking_flow,
    start_cancel_flow,
    start_cancel_flow_for_appointment,
    start_reschedule_flow,
    start_reschedule_flow_for_appointment,
    start_view_appointments_flow,
    FREE_TEXT_INPUT_STATES as _BOOKING_FREE_TEXT_INPUT_STATES,
    GOTO_MAIN_MENU,
    MANAGE_CANCEL_PREFIX,
    MANAGE_RESCHEDULE_PREFIX,
    STATE_IDLE,
)
from flows.patient_identity import (
    _FEATURE_MENU,
    _ROW_ID_TO_FEATURE,
    _send_dynamic_menu,
    _start_manage_patients,
    ALL_FEATURES,
    MAIN_MENU_BACK_ROW,
    REAL_FEATURES,
)
from flows.common import cap_rows, is_reset_keyword
from core.storage import get_storage
from core.translations import SUPPORTED_LANGUAGES, t
from core.translations.menu import (
    HOSPITAL_INFO_TEXT,
    LANGUAGE_PICKER_BODY,
    LANGUAGE_PICKER_BUTTON_EN,
    LANGUAGE_PICKER_BUTTON_HI,
    RECEPTION_HANDOFF_TEXT,
)
from core.translations.dpdp_consent import (
    DPDP_AGREE_BUTTON,
    DPDP_CONSENT_BODY,
    DPDP_DECLINED_MESSAGE,
    DPDP_DECLINE_BUTTON,
)
from core.translations.my_details import (
    DOCUMENTS_SECTION_TITLE,
    MY_DETAILS_DOCUMENTS_HEADER,
    MY_DETAILS_DOCUMENT_SEND_FAILED,
    MY_DETAILS_DOCUMENT_SENT,
    MY_DETAILS_NOT_FOUND,
    REPORTS_MENU_BOOK_REPORT_REVIEW,
    REPORTS_MENU_BUTTON,
    REPORTS_MENU_PROMPT,
    REPORTS_MENU_SECTION_TITLE,
    REPORTS_MENU_VIEW_DIAGNOSTIC_REPORTS,
    REPORTS_MENU_VIEW_LAB_REPORTS,
    REPORTS_MENU_VIEW_PRESCRIPTIONS,
    REPORTS_NO_DOCUMENTS_IN_CATEGORY,
    VIEW_DOCUMENTS_BUTTON,
)
from core.translations.patient_identity import BACK_TO_MENU_OPTION
from core.whatsapp import WhatsAppClient
from connectors import Connector, Tier1Connector
import flows.faq as faq_flow

logger = logging.getLogger(__name__)

_DEFAULT_CONNECTOR = Tier1Connector()

FREE_TEXT_INPUT_STATES = _BOOKING_FREE_TEXT_INPUT_STATES | patient_identity.FREE_TEXT_INPUT_STATES

STATE_AWAITING_LANGUAGE = "AWAITING_LANGUAGE"
LANGUAGE_ROW_EN = "lang_en"
LANGUAGE_ROW_HI = "lang_hi"
_LANGUAGE_ROW_TO_CODE = {LANGUAGE_ROW_EN: "en", LANGUAGE_ROW_HI: "hi"}


async def _send_language_picker(wa: WhatsAppClient, phone: str, default_language: str = "en") -> None:
    """Shown before anything else on a genuinely fresh conversation (see
    module docstring). Body text is bilingual on purpose -- we don't know
    the patient's language yet, so the prompt itself can't be in only one.

    Section 12.13: default_language (set via /portal/settings) decides which
    button is listed FIRST -- WhatsApp buttons have no concept of a
    "pre-selected" option, so leading with the hospital's preferred language
    is the only real way to "default to" it."""
    buttons = [
        {"id": LANGUAGE_ROW_EN, "title": t(LANGUAGE_PICKER_BUTTON_EN, None)},
        {"id": LANGUAGE_ROW_HI, "title": t(LANGUAGE_PICKER_BUTTON_HI, None)},
    ]
    if default_language == "hi":
        buttons.reverse()
    await wa.send_buttons(to=phone, body_text=t(LANGUAGE_PICKER_BODY, None), buttons=buttons)


STATE_AWAITING_DPDP_CONSENT = "AWAITING_DPDP_CONSENT"
DPDP_AGREE_ID = "dpdp_agree"
DPDP_DECLINE_ID = "dpdp_decline"


async def _send_dpdp_consent_prompt(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, hospital_name: str, language: str,
) -> None:
    """DPDP Act consent gate (hospitals.dpdp_consent_required, default off):
    shown right after language selection, before any patient identity is
    resolved -- see _enter_idle()'s own call site. The exact copy is fixed
    (core/translations.py's dpdp_consent_body), not a per-hospital custom
    text field like closing_message_text -- this is compliance-facing text
    given verbatim, not something to make freely editable per tenant yet."""
    sessions.set(hospital_id, phone, STATE_AWAITING_DPDP_CONSENT, {}, language=language)
    await wa.send_buttons(
        to=phone,
        body_text=t(DPDP_CONSENT_BODY, language, hospital_name=hospital_name),
        buttons=[
            {"id": DPDP_AGREE_ID, "title": t(DPDP_AGREE_BUTTON, language)},
            {"id": DPDP_DECLINE_ID, "title": t(DPDP_DECLINE_BUTTON, language)},
        ],
    )


async def _enter_idle(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, hospital_name: str,
    enabled_features: list[str], language: str | None, connector: Connector,
    feature_labels: dict[str, str] | None = None,
    default_language: str = "en", language_prompt_enabled: bool = True,
    require_patient_confirmation: bool = False,
    dpdp_consent_required: bool = False,
) -> None:
    """The one place that decides "does this session need the language
    picker, or does it already know what to show." Called everywhere the
    router used to jump straight to _send_dynamic_menu -- first contact, a
    reset keyword, a stale/unrecognized tap, GOTO_MAIN_MENU.

    Section 12.13: language_prompt_enabled=False (a hospital that only ever
    wants one language, set via /portal/settings) skips the picker entirely
    -- every fresh conversation goes straight to patient resolution/the menu
    in default_language, the same as if the patient had tapped that language
    on the picker.

    CareConnect architecture doc alignment (Spec.md Section 0), Sections 5/19:
    once language is settled, patient identity is resolved (or an
    interstitial registration/confirmation/selection message is sent)
    BEFORE the main menu is ever shown -- for every hospital, not gated on
    which features are enabled (confirmed with the user). Only once
    core/patient_identity.py returns an actual resolved patient (not None --
    None means it already sent its own message and this call must stop) does
    the menu itself get shown, now with that patient's "Patient: X / Patient
    Code: Y" header (Section 20).

    Language-persistence follow-up (confirmed with the user): `language`
    being None here no longer means "show the picker" outright -- it means
    "not known for THIS session" (a fresh session, or one that just timed
    out). The CareConnect account itself may already have a language saved
    from a previous conversation (_handle_awaiting_language persists it
    there, not just on the session) -- checked here, once, before falling
    back to the picker, so a returning patient is never re-asked just
    because their session expired. identify_contact() is idempotent/cheap
    (already called once per message by handle_incoming above) -- this is
    the same "re-resolve rather than thread five more params through"
    precedent flows/patient_identity.py's own _start_registration() uses."""
    if not language_prompt_enabled:
        resolved_language = default_language
    elif language is None:
        account_language = connector.identify_contact(phone, phone_number=phone).get("language")
        if account_language in SUPPORTED_LANGUAGES:
            resolved_language = account_language
        else:
            sessions.set(hospital_id, phone, STATE_AWAITING_LANGUAGE, {})
            await _send_language_picker(wa, phone, default_language=default_language)
            return
    else:
        resolved_language = language

    if dpdp_consent_required and not db.has_agreed_to_dpdp_consent(hospital_id, phone):
        await _send_dpdp_consent_prompt(wa, sessions, phone, hospital_id, hospital_name, resolved_language)
        return

    active_patient = await patient_identity.get_or_prompt_for_active_patient(
        wa, sessions, phone, hospital_id, connector, language=resolved_language,
        require_patient_confirmation=require_patient_confirmation,
        hospital_name=hospital_name, enabled_features=enabled_features, feature_labels=feature_labels,
    )
    if active_patient is None:
        return
    await _send_dynamic_menu(
        wa, phone, hospital_name, enabled_features, language=resolved_language, feature_labels=feature_labels,
        language_prompt_enabled=language_prompt_enabled, active_patient=active_patient,
    )


async def _handle_awaiting_language(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, hospital_name: str,
    enabled_features: list[str], connector: Connector, feature_labels: dict[str, str] | None = None,
    default_language: str = "en", require_patient_confirmation: bool = False,
    dpdp_consent_required: bool = False,
) -> None:
    chosen = _LANGUAGE_ROW_TO_CODE.get(reply["id"]) if reply["type"] == "interactive_reply" else None
    if chosen is None:
        # Didn't tap a valid option -- re-show the picker (still bilingual,
        # we still don't know their language).
        sessions.set(hospital_id, phone, STATE_AWAITING_LANGUAGE, {})
        await _send_language_picker(wa, phone, default_language=default_language)
        return
    # Language-persistence follow-up (confirmed with the user): saved once,
    # globally, on the CareConnect account -- reached from BOTH the
    # first-time picker (a brand-new session) and the "Change Language" main
    # menu item, so either path updates the same durable value, never just
    # this session.
    account = connector.identify_contact(phone, phone_number=phone)
    connector.set_account_language(account["id"], chosen)
    sessions.set(hospital_id, phone, STATE_IDLE, {}, language=chosen)
    # Reachable only via STATE_AWAITING_LANGUAGE, which _enter_idle only ever
    # sets when language_prompt_enabled is True (see its own branch above) --
    # safe and explicit to hardcode True here rather than thread the flag
    # through a 3rd function signature for a value that can't actually vary.
    await _enter_idle(
        wa, sessions, phone, hospital_id, hospital_name, enabled_features, chosen, connector,
        feature_labels=feature_labels, default_language=default_language, language_prompt_enabled=True,
        require_patient_confirmation=require_patient_confirmation,
        dpdp_consent_required=dpdp_consent_required,
    )


async def _handle_awaiting_dpdp_consent(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, hospital_name: str,
    enabled_features: list[str], connector: Connector, language: str, feature_labels: dict[str, str] | None = None,
    default_language: str = "en", language_prompt_enabled: bool = True,
    require_patient_confirmation: bool = False, dpdp_consent_required: bool = False,
) -> None:
    if reply["type"] == "interactive_reply" and reply["id"] == DPDP_DECLINE_ID:
        await wa.send_text(phone, t(DPDP_DECLINED_MESSAGE, language, hospital_name=hospital_name))
        # Declining isn't a soft "ask again later" -- the whole conversation
        # restarts from language selection (keep_language=False, unlike
        # every other reset() call site) so agreeing to DPDP terms is a real
        # gate the patient must clear before using any part of the bot, not
        # something they can silently skip past.
        sessions.reset(hospital_id, phone, keep_language=False)
        await _enter_idle(
            wa, sessions, phone, hospital_id, hospital_name, enabled_features, None, connector,
            feature_labels=feature_labels, default_language=default_language,
            language_prompt_enabled=language_prompt_enabled,
            require_patient_confirmation=require_patient_confirmation,
            dpdp_consent_required=dpdp_consent_required,
        )
        return
    if reply["type"] == "interactive_reply" and reply["id"] == DPDP_AGREE_ID:
        db.record_dpdp_consent(hospital_id, phone)
    # Agreed, or an unrecognized/stale tap -- either way re-enter the same
    # gate _enter_idle() itself checks: a genuine agreement just recorded
    # above now passes has_agreed_to_dpdp_consent() and proceeds straight to
    # patient resolution; an unrecognized tap still fails that check and
    # re-shows this same prompt fresh (same "recheck rather than trust the
    # tap" discipline this codebase uses everywhere else).
    await _enter_idle(
        wa, sessions, phone, hospital_id, hospital_name, enabled_features, language, connector,
        feature_labels=feature_labels, default_language=default_language,
        language_prompt_enabled=language_prompt_enabled,
        require_patient_confirmation=require_patient_confirmation,
        dpdp_consent_required=dpdp_consent_required,
    )


STATE_AWAITING_REPORTS_MENU = "AWAITING_REPORTS_MENU"
STATE_AWAITING_REPORTS_DOCUMENT = "AWAITING_REPORTS_DOCUMENT"

_REPORTS_DOC_PREFIX = "reportdoc_"

REPORTS_MENU_PRESCRIPTIONS_ROW = "reportsmenu_prescriptions"
REPORTS_MENU_LAB_ROW = "reportsmenu_lab_reports"
REPORTS_MENU_DIAGNOSTIC_ROW = "reportsmenu_diagnostic_reports"
REPORTS_MENU_BOOK_REVIEW_ROW = "reportsmenu_book_review"


def _reports_document_row_id(document_id: int) -> str:
    return f"{_REPORTS_DOC_PREFIX}{document_id}"


def _parse_reports_document_row_id(row_id: str) -> int | None:
    if not row_id.startswith(_REPORTS_DOC_PREFIX):
        return None
    try:
        return int(row_id[len(_REPORTS_DOC_PREFIX):])
    except ValueError:
        return None


async def _send_reports_menu(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, active_patient_id: int, language: str = "en",
) -> None:
    """WhatsApp menu restructuring: Reports & Prescriptions' own 4-row
    submenu -- replaces the old one-shot combined patient-summary +
    uncategorized document list entirely (see this module's docstring
    history for the prior _send_reports_prescriptions behavior)."""
    rows = [
        {"id": REPORTS_MENU_PRESCRIPTIONS_ROW, "title": t(REPORTS_MENU_VIEW_PRESCRIPTIONS, language)},
        {"id": REPORTS_MENU_LAB_ROW, "title": t(REPORTS_MENU_VIEW_LAB_REPORTS, language)},
        {"id": REPORTS_MENU_DIAGNOSTIC_ROW, "title": t(REPORTS_MENU_VIEW_DIAGNOSTIC_REPORTS, language)},
        {"id": REPORTS_MENU_BOOK_REVIEW_ROW, "title": t(REPORTS_MENU_BOOK_REPORT_REVIEW, language)},
        {"id": GOTO_MAIN_MENU, "title": t(BACK_TO_MENU_OPTION, language)},
    ]
    sessions.set(hospital_id, phone, STATE_AWAITING_REPORTS_MENU, {"patient_id": active_patient_id})
    await wa.send_list(
        to=phone,
        body_text=t(REPORTS_MENU_PROMPT, language),
        button_text=t(REPORTS_MENU_BUTTON, language),
        sections=[{"title": t(REPORTS_MENU_SECTION_TITLE, language), "rows": rows}],
    )


async def _send_filtered_documents(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, patient_id: int, document_type: str,
    language: str = "en",
) -> None:
    """One of Reports & Prescriptions' 3 "View X" rows -- a real filtered
    query against patient_documents.document_type (added for this
    restructuring), scoped to the ACTIVE patient (`db.get_patient()`, by id)
    rather than `get_patient_by_phone()` -- now that multiple patients can
    share a phone, the old phone-scoped lookup could show the WRONG family
    member's record. Deliberately calls db.repository directly rather than
    through connectors.py -- patient records/documents are a Tier-1-only
    concept never abstracted through the Connector interface, same
    precedent portal/routes/documents.py's own send-to-WhatsApp endpoint
    already established for this exact data."""
    patient = db.get_patient(hospital_id, patient_id)
    if patient is None:
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t(MY_DETAILS_NOT_FOUND, language))
        return

    documents = db.get_patient_documents(hospital_id, patient["id"], document_type=document_type)
    if not documents:
        await wa.send_text(phone, t(REPORTS_NO_DOCUMENTS_IN_CATEGORY, language))
        await _send_reports_menu(wa, sessions, phone, hospital_id, patient["id"], language=language)
        return

    rows = [{"id": _reports_document_row_id(d["id"]), "title": d["file_name"]} for d in documents]
    rows.append({"id": GOTO_MAIN_MENU, "title": t(BACK_TO_MENU_OPTION, language)})
    rows = cap_rows(rows, f"reports & prescriptions documents for patient {patient['id']}")
    sessions.set(
        hospital_id, phone, STATE_AWAITING_REPORTS_DOCUMENT,
        {"patient_id": patient["id"], "document_type": document_type},
    )
    await wa.send_list(
        to=phone,
        body_text=t(MY_DETAILS_DOCUMENTS_HEADER, language),
        button_text=t(VIEW_DOCUMENTS_BUTTON, language),
        sections=[{"title": t(DOCUMENTS_SECTION_TITLE, language), "rows": rows}],
    )


async def _handle_awaiting_reports_menu(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector: Connector,
    language: str = "en",
) -> None:
    patient_id = context.get("patient_id")
    if patient_id is None:
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t(MY_DETAILS_NOT_FOUND, language))
        return
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == REPORTS_MENU_PRESCRIPTIONS_ROW:
            await _send_filtered_documents(wa, sessions, phone, hospital_id, patient_id, "prescription", language=language)
            return
        if rid == REPORTS_MENU_LAB_ROW:
            await _send_filtered_documents(wa, sessions, phone, hospital_id, patient_id, "lab_report", language=language)
            return
        if rid == REPORTS_MENU_DIAGNOSTIC_ROW:
            await _send_filtered_documents(wa, sessions, phone, hospital_id, patient_id, "diagnostic_report", language=language)
            return
        if rid == REPORTS_MENU_BOOK_REVIEW_ROW:
            await start_booking_flow(
                wa, sessions, phone, hospital_id, connector, language=language, active_patient_id=patient_id,
                next_action="book_report_review",
            )
            return
    # Stale/unrecognized tap -- re-show fresh rather than acting on it.
    await _send_reports_menu(wa, sessions, phone, hospital_id, patient_id, language=language)


async def _handle_awaiting_reports_document(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, language: str = "en",
) -> None:
    patient_id = context.get("patient_id")
    if patient_id is None:
        # No patient context to re-fetch against -- stale session, back to idle.
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, t(MY_DETAILS_NOT_FOUND, language))
        return
    document_id = _parse_reports_document_row_id(reply["id"]) if reply["type"] == "interactive_reply" else None
    document = db.get_patient_document(hospital_id, document_id) if document_id is not None else None
    if document is None or document["patient_id"] != patient_id:
        # Stale/unrecognized tap, or the list went stale between send and
        # reply -- re-fetch and re-show fresh rather than acting on a stale
        # id (Phase 8's established "recheck dynamic data" discipline). Same
        # filtered category as the list that was actually shown, not the
        # unfiltered combined list.
        document_type = context.get("document_type")
        if document_type is not None:
            await _send_filtered_documents(wa, sessions, phone, hospital_id, patient_id, document_type, language=language)
        else:
            await _send_reports_menu(wa, sessions, phone, hospital_id, patient_id, language=language)
        return

    storage = get_storage()
    document_url = storage.get_signed_url(document["file_url"], expires_in=3600)
    sent = await wa.send_document(phone, document_url, document["file_name"])
    sessions.reset(hospital_id, phone)
    if not sent:
        await wa.send_text(phone, t(MY_DETAILS_DOCUMENT_SEND_FAILED, language))
        return
    db.mark_document_sent_to_whatsapp(hospital_id, document["id"])
    await wa.send_text(phone, t(MY_DETAILS_DOCUMENT_SENT, language))


async def _start_feature(
    key: str,
    wa: WhatsAppClient,
    sessions,
    phone: str,
    hospital_id: int,
    hospital_name: str,
    connector: Connector,
    active_patient_id: int | None,
    language: str = "en",
    business_hours_text: str | None = None,
    privacy_notice_text: str | None = None,
) -> None:
    """Hands the conversation off to whichever feature was tapped from the
    unified menu. Real features either transition into an existing sub-flow's
    own state machine (booking/reschedule/cancel -> core/booking_flow.py,
    faq -> faq_flow.py's FAQ_ACTIVE loop) or are simple one-shot replies that
    immediately return to IDLE (view_appointments, hospital_info).

    CareConnect architecture doc alignment (Spec.md Section 0): every
    patient-scoped branch now threads `active_patient_id` (resolved once,
    up front, by _enter_idle() -- Section 13's "Active Patient Context")
    into the sub-flow instead of letting it re-derive identity itself."""
    if key == "book_doctor_appointment":
        await start_booking_flow(
            wa, sessions, phone, hospital_id, connector, language=language, active_patient_id=active_patient_id,
            category=db.BOOK_DOCTOR_APPOINTMENT_CATEGORY,
        )
        return
    if key == "tests_diagnostics":
        await start_booking_flow(
            wa, sessions, phone, hospital_id, connector, language=language, active_patient_id=active_patient_id,
            category=db.TESTS_DIAGNOSTICS_CATEGORY,
        )
        return
    if key == "reschedule":
        await start_reschedule_flow(wa, sessions, phone, hospital_id, connector, language=language, active_patient_id=active_patient_id)
        return
    if key == "cancel":
        await start_cancel_flow(wa, sessions, phone, hospital_id, connector, language=language, active_patient_id=active_patient_id)
        return
    if key == "faq":
        sessions.set(hospital_id, phone, faq_flow.STATE_FAQ_ACTIVE, {})
        await faq_flow.send_topic_menu(wa, phone, hospital_id, hospital_name, language=language)
        return
    if key == "view_appointments":
        await start_view_appointments_flow(wa, sessions, phone, hospital_id, connector, language=language, active_patient_id=active_patient_id)
        return
    if key == "reports_prescriptions":
        if active_patient_id is None:
            # No active patient resolved -- shouldn't normally happen (menu
            # taps only reach here after _enter_idle() has already resolved
            # one), but re-prompt rather than query with no patient.
            sessions.reset(hospital_id, phone)
            await _enter_idle(
                wa, sessions, phone, hospital_id, hospital_name, [key], language, connector,
            )
            return
        await _send_reports_menu(wa, sessions, phone, hospital_id, active_patient_id, language=language)
        return
    if key == "manage_patients":
        await patient_identity._start_manage_patients(wa, sessions, phone, hospital_id, connector, language=language)
        return
    if key == "manage_language":
        sessions.set(hospital_id, phone, STATE_AWAITING_LANGUAGE, {})
        await _send_language_picker(wa, phone, default_language=language)
        return
    if key == "consent_privacy":
        if active_patient_id is None:
            # No active patient resolved -- shouldn't normally happen (menu
            # taps only reach here after _enter_idle() has already resolved
            # one), but re-prompt rather than proceed with no patient.
            sessions.reset(hospital_id, phone)
            await _enter_idle(
                wa, sessions, phone, hospital_id, hospital_name, [key], language, connector,
            )
            return
        await patient_identity.start_consent_privacy(
            wa, sessions, phone, hospital_id, connector, active_patient_id,
            privacy_notice_text=privacy_notice_text, language=language,
        )
        return
    if key == "hospital_info":
        sessions.reset(hospital_id, phone)
        # Section 12.13: a hospital's own business_hours_text (set via
        # /portal/settings), appended as an extra informational line -- purely
        # display, never enforced against real doctor slot availability.
        info_text = t(HOSPITAL_INFO_TEXT, language)
        if business_hours_text:
            info_text = f"{info_text}\n\n{business_hours_text}"
        await wa.send_text(phone, info_text)
        return
    if key == "reception_handoff":
        sessions.reset(hospital_id, phone)
        db.create_handoff_request(
            hospital_id, phone, reason="patient_requested",
            message_text="Patient tapped \"Talk to Reception\" from the main menu.",
        )
        await wa.send_text(phone, t(RECEPTION_HANDOFF_TEXT, language))
        return
    # Defensive only -- every key in REAL_FEATURES has a branch above, so this
    # is only reachable if a new feature key is added to REAL_FEATURES without
    # a matching branch here (a coding bug), never from real user input (the
    # _ROW_ID_TO_FEATURE/enabled_features gates in handle_incoming() already
    # filter those out).
    logger.warning("No _start_feature branch for feature key %r -- falling back to menu", key)
    sessions.reset(hospital_id, phone)
    await _send_dynamic_menu(wa, phone, hospital_name, list(REAL_FEATURES), language=language)


async def handle_incoming(
    wa: WhatsAppClient,
    sessions,
    phone: str,
    hospital_id: int,
    reply: dict,
    hospital_name: str = "the hospital",
    connector: Connector | None = None,
    enabled_features: list[str] | None = None,
    feature_labels: dict[str, str] | None = None,
    closing_message_text: str | None = None,
    business_hours_text: str | None = None,
    default_language: str = "en",
    language_prompt_enabled: bool = True,
    session_timeout_minutes: int | None = None,
    require_patient_confirmation: bool = False,
    privacy_notice_text: str | None = None,
    provider_user_id: str | None = None,
    username: str | None = None,
    dpdp_consent_required: bool = False,
) -> None:
    """The real conversation entry point (SPEC Section 14.5) -- core/main.py
    calls this directly now, passing the resolved hospital's enabled_features
    alongside everything core/booking_flow.py's handle_incoming() already
    needed. Defaults enabled_features to [] (not "booking") so a caller that
    forgets to pass it gets an honest "nothing enabled" menu rather than a
    guessed one -- matching db.create_hospital()'s own default.

    Section 12.13: feature_labels/closing_message_text/business_hours_text/
    default_language/language_prompt_enabled are all self-serve bot
    customization (hospitals.<field>, set via /portal/settings) -- every one
    defaults to "no customization" (None/{}/en/True) so a caller that doesn't
    pass them (including the whole pre-Section-12.13 test suite) gets
    byte-for-byte the same fixed behavior as before this section.

    require_patient_confirmation/privacy_notice_text (CareConnect
    architecture doc alignment, Spec.md Section 0): same "self-serve bot
    customization, defaults to off/unset" treatment.

    provider_user_id/username (CareConnect account/identity layer,
    db/schema.sql's own comment on care_connect_accounts): CONTACT
    IDENTIFICATION, resolved on every message before anything else --
    provider_user_id defaults to `phone` when not given (today's WhatsApp
    Cloud API webhook has no identifier distinct from the phone number; see
    webhook/dispatch.py), so every pre-existing caller/test that doesn't pass
    these gets identical behavior to before this was added.

    dpdp_consent_required (DPDP Act consent gate, db/schema.sql's own
    comment on hospitals.dpdp_consent_required): same "self-serve,
    defaults to off" treatment as require_patient_confirmation."""
    connector = connector or _DEFAULT_CONNECTOR
    connector.identify_contact(provider_user_id or phone, phone_number=phone, username=username)
    # Item 7 (Spec.md Section 0): a real production bug -- once a patient's
    # "Talk to Reception" request is open, the bot must go completely silent
    # for that phone (including the reset-keyword escape hatch below, which
    # is exactly what a patient typing "hi" mid-handoff was tripping) until
    # staff resolve it. Checked before anything else touches session state,
    # so a stale/expired session can't accidentally re-engage the bot either.
    #
    # Two-way threading follow-up: previously this just silenced the bot and
    # dropped the message -- it was written into core/session_store.py's generic,
    # hospital-agnostic HISTORY buffer (core/main.py's own doing, before this
    # function is even called) but nothing ever read that buffer, so a
    # patient's follow-up messages during an active handoff were effectively
    # lost to staff. Now recorded as a real inbound handoff_messages row
    # against the open handoff, so it shows up in the portal's thread.
    open_handoff = db.get_open_handoff(hospital_id, phone)
    if open_handoff is not None:
        message_text = reply.get("text") or reply.get("title") or f"[{reply.get('type')}]"
        db.add_handoff_message(hospital_id, open_handoff["id"], "inbound", message_text)
        logger.info(
            "Handoff active for hospital=%s phone=%s -- recorded in the thread, not routed to the bot",
            hospital_id, phone,
        )
        return
    enabled_features = enabled_features or []
    # Section 12.13: a hospital's own session_timeout_minutes (5-120) overrides
    # core/session_store.py's fixed 30-min default -- None (never customized) keeps
    # today's behavior exactly, since sessions.get() itself falls back to its
    # own constructor-time default when timeout_seconds isn't passed.
    timeout_seconds = session_timeout_minutes * 60 if session_timeout_minutes else None
    session = sessions.get(hospital_id, phone, timeout_seconds=timeout_seconds)
    state = session["state"]
    context = session["context"]
    language = session.get("language")
    if language not in SUPPORTED_LANGUAGES:
        language = None
    active_patient_id = session.get("active_patient_id")

    async def _enter_idle_here(lang: str | None) -> None:
        await _enter_idle(
            wa, sessions, phone, hospital_id, hospital_name, enabled_features, lang, connector,
            feature_labels=feature_labels, default_language=default_language,
            language_prompt_enabled=language_prompt_enabled,
            require_patient_confirmation=require_patient_confirmation,
            dpdp_consent_required=dpdp_consent_required,
        )

    # Items 3/5/6 (Spec.md Section 0): quick-action ids embedding a specific
    # appointment id -- attached to the booking-success message, the
    # duplicate-booking block message, and My Appointments' inline actions.
    # Checked BEFORE the reset-keyword/state dispatch below (and regardless
    # of the CURRENT session state) precisely because the message carrying
    # one of these may be tapped long after the session that sent it has
    # expired -- "reopen the chat later and it still works" is the whole
    # point. Re-validated fresh against this phone's own current upcoming
    # appointments (never trusted from the tapped id alone) -- an appointment
    # already cancelled/rescheduled/past falls through to normal routing
    # instead of silently acting on stale data.
    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == GOTO_MAIN_MENU:
            sessions.reset(hospital_id, phone)
            await _enter_idle_here(language)
            return
        manage_appt_id = parse_manage_id(rid, MANAGE_CANCEL_PREFIX)
        if manage_appt_id is not None:
            appt = next(
                (a for a in connector.get_upcoming_appointments(hospital_id, phone=phone) if a.id == manage_appt_id),
                None,
            )
            if appt:
                await start_cancel_flow_for_appointment(wa, sessions, phone, hospital_id, appt, language=language or "en")
                return
        manage_appt_id = parse_manage_id(rid, MANAGE_RESCHEDULE_PREFIX)
        if manage_appt_id is not None:
            appt = next(
                (a for a in connector.get_upcoming_appointments(hospital_id, phone=phone) if a.id == manage_appt_id),
                None,
            )
            if appt:
                await start_reschedule_flow_for_appointment(wa, sessions, phone, hospital_id, appt, connector, language=language or "en")
                return

    if state != STATE_IDLE and state not in FREE_TEXT_INPUT_STATES and is_reset_keyword(reply):
        sessions.reset(hospital_id, phone)
        await _enter_idle_here(language)
        return

    if state == STATE_AWAITING_LANGUAGE:
        await _handle_awaiting_language(
            wa, sessions, phone, hospital_id, reply, hospital_name, enabled_features, connector,
            feature_labels=feature_labels, default_language=default_language,
            require_patient_confirmation=require_patient_confirmation,
            dpdp_consent_required=dpdp_consent_required,
        )
        return

    if state == STATE_AWAITING_DPDP_CONSENT:
        await _handle_awaiting_dpdp_consent(
            wa, sessions, phone, hospital_id, reply, hospital_name, enabled_features, connector,
            language=language or "en", feature_labels=feature_labels, default_language=default_language,
            language_prompt_enabled=language_prompt_enabled,
            require_patient_confirmation=require_patient_confirmation,
            dpdp_consent_required=dpdp_consent_required,
        )
        return

    if state == STATE_AWAITING_REPORTS_MENU:
        await _handle_awaiting_reports_menu(
            wa, sessions, phone, hospital_id, reply, context, connector, language=language or "en",
        )
        return

    if state == STATE_AWAITING_REPORTS_DOCUMENT:
        await _handle_awaiting_reports_document(
            wa, sessions, phone, hospital_id, reply, context, language=language or "en",
        )
        return

    if state == patient_identity.STATE_AWAITING_CONSENT_ACTION:
        await patient_identity.handle_awaiting_consent_action(
            wa, sessions, phone, hospital_id, reply, context, connector, active_patient_id,
            privacy_notice_text=privacy_notice_text, language=language or "en",
        )
        return

    identity_handler = patient_identity._HANDLERS.get(state)
    if identity_handler is not None:
        await identity_handler(
            wa, sessions, phone, hospital_id, reply, context, connector,
            language=language or "en", closing_message_text=closing_message_text,
        )
        # If that action just fully resolved the active patient (state is
        # now IDLE), show the main menu immediately -- core/patient_identity.py
        # itself can't do this (it would need to import _send_dynamic_menu
        # back from here, a circular import; see that module's own
        # docstring), so the check lives here instead.
        after = sessions.get(hospital_id, phone, timeout_seconds=timeout_seconds)
        if after["state"] == STATE_IDLE:
            await _enter_idle_here(after.get("language", language))
        return

    booking_handler = _BOOKING_STATE_HANDLERS.get(state)
    if booking_handler is not None:
        await booking_handler(
            wa, sessions, phone, hospital_id, reply, context, connector,
            language=language or "en", closing_message_text=closing_message_text,
        )
        return

    if state == faq_flow.STATE_FAQ_ACTIVE:
        await faq_flow.handle_incoming(wa, sessions, phone, hospital_id, reply, hospital_name, connector, language=language or "en")
        return

    # IDLE, or any other unrecognized/stale state -> a tap matching an
    # enabled feature starts that feature; anything else (first contact,
    # free text, a tap for a feature this hospital hasn't enabled, a stale
    # id from before a feature was disabled) shows the unified menu (via
    # _enter_idle, which gates on language being chosen first, then patient
    # identity).
    if reply["type"] == "interactive_reply":
        # Main menu's own "Back" (confirmed with the user): opens Manage
        # Patients -- view/add/unlink, and switch which linked patient is
        # active (see core/patient_identity.py's own manage-patients-action
        # handler).
        if reply["id"] == MAIN_MENU_BACK_ROW and language is not None:
            await _start_manage_patients(wa, sessions, phone, hospital_id, connector, language)
            return
        # The single-linked-patient confirmation's own follow-up buttons
        # message (patient_identity._send_single_patient_confirm) -- sent
        # alongside the main menu list, from IDLE, not a dedicated state, so
        # these two ids are handled here rather than via _HANDLERS.
        if reply["id"] == patient_identity.ADD_PATIENT_ENTRY_ID and language is not None:
            await patient_identity._start_registration(wa, sessions, phone, hospital_id, connector, language)
            return
        if reply["id"] == patient_identity.BACK_ID and language is not None:
            sessions.set(hospital_id, phone, STATE_AWAITING_LANGUAGE, {})
            await _send_language_picker(wa, phone, default_language=default_language)
            return
        feature_key = _ROW_ID_TO_FEATURE.get(reply["id"])
        if feature_key is not None and feature_key in enabled_features and language is not None:
            await _start_feature(
                feature_key, wa, sessions, phone, hospital_id, hospital_name, connector, active_patient_id,
                language=language, business_hours_text=business_hours_text, privacy_notice_text=privacy_notice_text,
            )
            return

    sessions.reset(hospital_id, phone)
    await _enter_idle_here(language)

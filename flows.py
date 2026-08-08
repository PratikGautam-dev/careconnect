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
- IDLE (or an unrecognized/stale state): shows a WhatsApp list built from
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

All of REAL_FEATURES ("booking", "reschedule", "cancel", "faq",
"view_appointments", "hospital_info", "reception_handoff") are real, working
sub-flows -- there is no placeholder/"coming soon" tier anymore. "payment_link"
and "reports" were removed (not just hidden) since they were never built and
no tenant had either enabled; see Spec.md's progress log for the removal.

Section 12.11 (language selection): this module owns the ONE language-
selection decision point -- STATE_AWAITING_LANGUAGE, entered whenever a
session reaches true IDLE with no language chosen yet (first contact, or a
genuinely expired/new session; core/history.py's session store preserves an
already-chosen language across an in-conversation reset(), so this does NOT
re-ask after every completed action, only once per fresh conversation). Once
chosen, `language` is threaded down into every sub-flow (booking_flow.py,
faq_flow.py) this router delegates to, so the whole conversation -- not just
this module's own menu -- responds in the chosen language.
"""
import logging

import db.repository as db
from core.booking_flow import (
    _HANDLERS as _BOOKING_STATE_HANDLERS,
    _send_department_menu,
    _start_cancel_flow,
    _start_reschedule_flow,
    FREE_TEXT_INPUT_STATES,
    STATE_AWAITING_DEPARTMENT,
    STATE_IDLE,
)
from core.flow_common import cap_rows, is_reset_keyword
from core.translations import SUPPORTED_LANGUAGES, t
from core.whatsapp import WhatsAppClient
from connectors import Connector, Tier1Connector
import faq_flow

logger = logging.getLogger(__name__)

_DEFAULT_CONNECTOR = Tier1Connector()

STATE_AWAITING_LANGUAGE = "AWAITING_LANGUAGE"
LANGUAGE_ROW_EN = "lang_en"
LANGUAGE_ROW_HI = "lang_hi"
_LANGUAGE_ROW_TO_CODE = {LANGUAGE_ROW_EN: "en", LANGUAGE_ROW_HI: "hi"}

# feature key -> (menu row id, menu row title key into core/translations.py).
# Order here is the order rows appear in the main menu, matching the
# onboarding wizard's Patient Experience step (Section 14.6) and the
# reference design's own toggle-grid ordering.
_FEATURE_MENU = {
    "booking": ("menu_book", "feature_booking"),
    "reschedule": ("menu_reschedule", "feature_reschedule"),
    "cancel": ("menu_cancel", "feature_cancel"),
    "view_appointments": ("menu_view_appointments", "feature_view_appointments"),
    "hospital_info": ("menu_hospital_info", "feature_hospital_info"),
    "reception_handoff": ("menu_reception", "feature_reception_handoff"),
    "faq": ("menu_faq_bot", "feature_faq"),
}
_ROW_ID_TO_FEATURE = {row_id: key for key, (row_id, _title_key) in _FEATURE_MENU.items()}

# Every selectable feature is real and working -- no placeholder tier.
REAL_FEATURES = {"booking", "reschedule", "cancel", "faq", "view_appointments", "hospital_info", "reception_handoff"}
ALL_FEATURES = REAL_FEATURES


async def _send_language_picker(wa: WhatsAppClient, phone: str, default_language: str = "en") -> None:
    """Shown before anything else on a genuinely fresh conversation (see
    module docstring). Body text is bilingual on purpose -- we don't know
    the patient's language yet, so the prompt itself can't be in only one.

    Section 12.13: default_language (set via /portal/settings) decides which
    button is listed FIRST -- WhatsApp buttons have no concept of a
    "pre-selected" option, so leading with the hospital's preferred language
    is the only real way to "default to" it."""
    buttons = [
        {"id": LANGUAGE_ROW_EN, "title": t("language_picker_button_en", None)},
        {"id": LANGUAGE_ROW_HI, "title": t("language_picker_button_hi", None)},
    ]
    if default_language == "hi":
        buttons.reverse()
    await wa.send_buttons(to=phone, body_text=t("language_picker_body", None), buttons=buttons)


async def _send_dynamic_menu(
    wa: WhatsAppClient, phone: str, hospital_name: str, enabled_features: list[str], language: str = "en",
    feature_labels: dict[str, str] | None = None,
) -> None:
    feature_labels = feature_labels or {}
    rows = [
        # Section 12.13: a hospital's own custom label for this feature (set
        # via /portal/settings) wins over the fixed translations.py default --
        # custom labels are stored/entered once, in whatever language the
        # hospital typed them in (not per-session-language, unlike the fixed
        # defaults), so they're used as-is regardless of the patient's chosen
        # language.
        {"id": row_id, "title": feature_labels.get(key) or t(title_key, language)}
        for key, (row_id, title_key) in _FEATURE_MENU.items()
        if key in enabled_features
    ]
    if not rows:
        # A hospital with nothing enabled (mid-onboarding data issue, or a
        # brand-new row before enabled_features was ever set) -- graceful
        # patient-facing message, never an empty WhatsApp list send
        # (Phase 8 / Section 12.7's established discipline).
        await wa.send_text(phone, t("feature_menu_unavailable", language, hospital_name=hospital_name))
        return
    rows = cap_rows(rows, f"main menu for {hospital_name}")
    await wa.send_list(
        to=phone,
        body_text=t("welcome_menu", language, hospital_name=hospital_name),
        button_text=t("main_menu_button", language),
        sections=[{"title": t("main_menu_section_title", language), "rows": rows}],
    )


async def _enter_idle(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, hospital_name: str,
    enabled_features: list[str], language: str | None,
    feature_labels: dict[str, str] | None = None,
    default_language: str = "en", language_prompt_enabled: bool = True,
) -> None:
    """The one place that decides "does this session need the language
    picker, or does it already know what to show." Called everywhere the
    router used to jump straight to _send_dynamic_menu -- first contact, a
    reset keyword, a stale/unrecognized tap.

    Section 12.13: language_prompt_enabled=False (a hospital that only ever
    wants one language, set via /portal/settings) skips the picker entirely
    -- every fresh conversation goes straight to the menu in default_language,
    the same as if the patient had tapped that language on the picker."""
    if not language_prompt_enabled:
        sessions.set(hospital_id, phone, STATE_IDLE, {}, language=default_language)
        await _send_dynamic_menu(wa, phone, hospital_name, enabled_features, language=default_language, feature_labels=feature_labels)
        return
    if language is None:
        sessions.set(hospital_id, phone, STATE_AWAITING_LANGUAGE, {})
        await _send_language_picker(wa, phone, default_language=default_language)
        return
    await _send_dynamic_menu(wa, phone, hospital_name, enabled_features, language=language, feature_labels=feature_labels)


async def _handle_awaiting_language(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, hospital_name: str,
    enabled_features: list[str], feature_labels: dict[str, str] | None = None, default_language: str = "en",
) -> None:
    chosen = _LANGUAGE_ROW_TO_CODE.get(reply["id"]) if reply["type"] == "interactive_reply" else None
    if chosen is None:
        # Didn't tap a valid option -- re-show the picker (still bilingual,
        # we still don't know their language).
        sessions.set(hospital_id, phone, STATE_AWAITING_LANGUAGE, {})
        await _send_language_picker(wa, phone, default_language=default_language)
        return
    sessions.set(hospital_id, phone, STATE_IDLE, {}, language=chosen)
    await _send_dynamic_menu(wa, phone, hospital_name, enabled_features, language=chosen, feature_labels=feature_labels)


async def _send_view_appointments(
    wa: WhatsAppClient, phone: str, hospital_id: int, connector: Connector, language: str = "en",
) -> None:
    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    if not appointments:
        await wa.send_text(phone, t("view_appointments_list", language))
        return
    lines = [
        f"- {a.doctor_name} ({a.department_name}) — {a.scheduled_at.strftime('%a %d %b %Y, %H:%M')}"
        for a in appointments
    ]
    await wa.send_text(phone, t("view_appointments_header", language) + "\n".join(lines))


async def _start_feature(
    key: str,
    wa: WhatsAppClient,
    sessions,
    phone: str,
    hospital_id: int,
    hospital_name: str,
    connector: Connector,
    language: str = "en",
    business_hours_text: str | None = None,
) -> None:
    """Hands the conversation off to whichever feature was tapped from the
    unified menu. Real features either transition into an existing sub-flow's
    own state machine (booking/reschedule/cancel -> core/booking_flow.py,
    faq -> faq_flow.py's FAQ_ACTIVE loop) or are simple one-shot replies that
    immediately return to IDLE (view_appointments, hospital_info)."""
    if key == "booking":
        sessions.set(hospital_id, phone, STATE_AWAITING_DEPARTMENT, {})
        await _send_department_menu(wa, phone, hospital_id, connector, language=language)
        return
    if key == "reschedule":
        await _start_reschedule_flow(wa, sessions, phone, hospital_id, connector, language=language)
        return
    if key == "cancel":
        await _start_cancel_flow(wa, sessions, phone, hospital_id, connector, language=language)
        return
    if key == "faq":
        sessions.set(hospital_id, phone, faq_flow.STATE_FAQ_ACTIVE, {})
        await faq_flow.send_topic_menu(wa, phone, hospital_id, hospital_name, language=language)
        return
    if key == "view_appointments":
        sessions.reset(hospital_id, phone)
        await _send_view_appointments(wa, phone, hospital_id, connector, language=language)
        return
    if key == "hospital_info":
        sessions.reset(hospital_id, phone)
        # Section 12.13: a hospital's own business_hours_text (set via
        # /portal/settings), appended as an extra informational line -- purely
        # display, never enforced against real doctor slot availability.
        info_text = t("hospital_info_text", language)
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
        await wa.send_text(phone, t("reception_handoff_text", language))
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
    byte-for-byte the same fixed behavior as before this section."""
    connector = connector or _DEFAULT_CONNECTOR
    enabled_features = enabled_features or []
    # Section 12.13: a hospital's own session_timeout_minutes (5-120) overrides
    # core/history.py's fixed 30-min default -- None (never customized) keeps
    # today's behavior exactly, since sessions.get() itself falls back to its
    # own constructor-time default when timeout_seconds isn't passed.
    timeout_seconds = session_timeout_minutes * 60 if session_timeout_minutes else None
    session = sessions.get(hospital_id, phone, timeout_seconds=timeout_seconds)
    state = session["state"]
    context = session["context"]
    language = session.get("language")
    if language not in SUPPORTED_LANGUAGES:
        language = None

    if state != STATE_IDLE and state not in FREE_TEXT_INPUT_STATES and is_reset_keyword(reply):
        sessions.reset(hospital_id, phone)
        await _enter_idle(
            wa, sessions, phone, hospital_id, hospital_name, enabled_features, language,
            feature_labels=feature_labels, default_language=default_language,
            language_prompt_enabled=language_prompt_enabled,
        )
        return

    if state == STATE_AWAITING_LANGUAGE:
        await _handle_awaiting_language(
            wa, sessions, phone, hospital_id, reply, hospital_name, enabled_features,
            feature_labels=feature_labels, default_language=default_language,
        )
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
    # _enter_idle, which gates on language being chosen first).
    if reply["type"] == "interactive_reply":
        feature_key = _ROW_ID_TO_FEATURE.get(reply["id"])
        if feature_key is not None and feature_key in enabled_features and language is not None:
            await _start_feature(
                feature_key, wa, sessions, phone, hospital_id, hospital_name, connector,
                language=language, business_hours_text=business_hours_text,
            )
            return

    sessions.reset(hospital_id, phone)
    await _enter_idle(
        wa, sessions, phone, hospital_id, hospital_name, enabled_features, language,
        feature_labels=feature_labels, default_language=default_language,
        language_prompt_enabled=language_prompt_enabled,
    )

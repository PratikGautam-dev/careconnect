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
  (STATE_AWAITING_DEPARTMENT, STATE_AWAITING_SLOT, the cancel/reschedule
  states, ...): delegated STRAIGHT to booking_flow.py's existing per-state
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

Real vs. placeholder features (Section 14.5): "booking", "reschedule",
"cancel", "faq", "view_appointments", and "hospital_info" are real. "reception_handoff",
"payment_link", and "reports" are selectable in the onboarding wizard (so the
UI is accurate about what's coming) but reply with a "coming soon" message --
see _COMING_SOON_TEXT and _PLACEHOLDER_FEATURES below.
"""
import logging

from core.booking_flow import (
    _HANDLERS as _BOOKING_STATE_HANDLERS,
    _FAQ_TEXT as _HOSPITAL_INFO_TEXT,
    _send_department_menu,
    _start_cancel_flow,
    _start_reschedule_flow,
    STATE_AWAITING_DEPARTMENT,
    STATE_IDLE,
)
from core.flow_common import cap_rows, is_reset_keyword
from core.whatsapp import WhatsAppClient
from connectors import Connector, Tier1Connector
import faq_flow

logger = logging.getLogger(__name__)

_DEFAULT_CONNECTOR = Tier1Connector()

_COMING_SOON_TEXT = (
    "This feature is coming soon. In the meantime, please contact the hospital "
    "directly, or send any message to see what's available right now."
)

# feature key -> (menu row id, menu row title). Order here is the order rows
# appear in the main menu, matching the onboarding wizard's Patient Experience
# step (Section 14.6) and the reference design's own toggle-grid ordering.
_FEATURE_MENU = {
    "booking": ("menu_book", "Book Appointment"),
    "reschedule": ("menu_reschedule", "Reschedule Appointment"),
    "cancel": ("menu_cancel", "Cancel Appointment"),
    "view_appointments": ("menu_view_appointments", "My Appointments"),
    "hospital_info": ("menu_hospital_info", "Hospital Information"),
    "reception_handoff": ("menu_reception", "Talk to Reception"),
    "faq": ("menu_faq_bot", "FAQ / Information"),
    "payment_link": ("menu_payment", "Payment Link"),
    "reports": ("menu_reports", "Reports & Results"),
}
_ROW_ID_TO_FEATURE = {row_id: key for key, (row_id, _title) in _FEATURE_MENU.items()}

# Real, working features vs. selectable-but-not-built-yet placeholders
# (Section 14.5's explicit "flag which is which" requirement).
REAL_FEATURES = {"booking", "reschedule", "cancel", "faq", "view_appointments", "hospital_info"}
PLACEHOLDER_FEATURES = {"reception_handoff", "payment_link", "reports"}
ALL_FEATURES = REAL_FEATURES | PLACEHOLDER_FEATURES


async def _send_dynamic_menu(wa: WhatsAppClient, phone: str, hospital_name: str, enabled_features: list[str]) -> None:
    rows = [
        {"id": row_id, "title": title}
        for key, (row_id, title) in _FEATURE_MENU.items()
        if key in enabled_features
    ]
    if not rows:
        # A hospital with nothing enabled (mid-onboarding data issue, or a
        # brand-new row before enabled_features was ever set) -- graceful
        # patient-facing message, never an empty WhatsApp list send
        # (Phase 8 / Section 12.7's established discipline).
        await wa.send_text(
            phone, f"Sorry, {hospital_name} hasn't finished setting up WhatsApp yet. Please check back later."
        )
        return
    rows = cap_rows(rows, f"main menu for {hospital_name}")
    await wa.send_list(
        to=phone,
        body_text=f"Welcome to {hospital_name}! How can we help you today?",
        button_text="Main Menu",
        sections=[{"title": "Main Menu", "rows": rows}],
    )


async def _send_view_appointments(wa: WhatsAppClient, phone: str, hospital_id: int, connector: Connector) -> None:
    appointments = connector.get_upcoming_appointments(hospital_id, phone=phone)
    if not appointments:
        await wa.send_text(phone, "You don't have any upcoming appointments.")
        return
    lines = [
        f"- {a.doctor_name} ({a.department_name}) — {a.scheduled_at.strftime('%a %d %b %Y, %H:%M')}"
        for a in appointments
    ]
    await wa.send_text(phone, "Your upcoming appointments:\n\n" + "\n".join(lines))


async def _start_feature(
    key: str,
    wa: WhatsAppClient,
    sessions,
    phone: str,
    hospital_id: int,
    hospital_name: str,
    connector: Connector,
) -> None:
    """Hands the conversation off to whichever feature was tapped from the
    unified menu. Real features either transition into an existing sub-flow's
    own state machine (booking/reschedule/cancel -> core/booking_flow.py,
    faq -> faq_flow.py's FAQ_ACTIVE loop) or are simple one-shot replies that
    immediately return to IDLE (view_appointments, hospital_info). Placeholder
    features (Section 14.5) all get the same "coming soon" reply."""
    if key == "booking":
        sessions.set(hospital_id, phone, STATE_AWAITING_DEPARTMENT, {})
        await _send_department_menu(wa, phone, hospital_id, connector)
        return
    if key == "reschedule":
        await _start_reschedule_flow(wa, sessions, phone, hospital_id, connector)
        return
    if key == "cancel":
        await _start_cancel_flow(wa, sessions, phone, hospital_id, connector)
        return
    if key == "faq":
        sessions.set(hospital_id, phone, faq_flow.STATE_FAQ_ACTIVE, {})
        await faq_flow.send_topic_menu(wa, phone, hospital_id, hospital_name)
        return
    if key == "view_appointments":
        sessions.reset(hospital_id, phone)
        await _send_view_appointments(wa, phone, hospital_id, connector)
        return
    if key == "hospital_info":
        sessions.reset(hospital_id, phone)
        await wa.send_text(phone, _HOSPITAL_INFO_TEXT)
        return
    # PLACEHOLDER_FEATURES (reception_handoff, payment_link, reports) --
    # selectable in the wizard so the UI is honest about what's coming, but
    # not built yet (Section 14.5).
    sessions.reset(hospital_id, phone)
    await wa.send_text(phone, _COMING_SOON_TEXT)


async def handle_incoming(
    wa: WhatsAppClient,
    sessions,
    phone: str,
    hospital_id: int,
    reply: dict,
    hospital_name: str = "the hospital",
    connector: Connector | None = None,
    enabled_features: list[str] | None = None,
) -> None:
    """The real conversation entry point (SPEC Section 14.5) -- core/main.py
    calls this directly now, passing the resolved hospital's enabled_features
    alongside everything core/booking_flow.py's handle_incoming() already
    needed. Defaults enabled_features to [] (not "booking") so a caller that
    forgets to pass it gets an honest "nothing enabled" menu rather than a
    guessed one -- matching db.create_hospital()'s own default."""
    connector = connector or _DEFAULT_CONNECTOR
    enabled_features = enabled_features or []
    session = sessions.get(hospital_id, phone)
    state = session["state"]
    context = session["context"]

    if state != STATE_IDLE and is_reset_keyword(reply):
        sessions.reset(hospital_id, phone)
        await _send_dynamic_menu(wa, phone, hospital_name, enabled_features)
        return

    booking_handler = _BOOKING_STATE_HANDLERS.get(state)
    if booking_handler is not None:
        await booking_handler(wa, sessions, phone, hospital_id, reply, context, connector)
        return

    if state == faq_flow.STATE_FAQ_ACTIVE:
        await faq_flow.handle_incoming(wa, sessions, phone, hospital_id, reply, hospital_name, connector)
        return

    # IDLE, or any other unrecognized/stale state -> a tap matching an
    # enabled feature starts that feature; anything else (first contact,
    # free text, a tap for a feature this hospital hasn't enabled, a stale
    # id from before a feature was disabled) shows the unified menu.
    if reply["type"] == "interactive_reply":
        feature_key = _ROW_ID_TO_FEATURE.get(reply["id"])
        if feature_key is not None and feature_key in enabled_features:
            await _start_feature(feature_key, wa, sessions, phone, hospital_id, hospital_name, connector)
            return

    sessions.reset(hospital_id, phone)
    await _send_dynamic_menu(wa, phone, hospital_name, enabled_features)

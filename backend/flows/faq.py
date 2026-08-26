# faq_flow.py
"""
SPEC Section 14.5 (originally 14.2, under the single-flow_type model that
Section 14.5 replaced): the FAQ sub-flow. A hospital that enables the "faq"
feature (hospitals.enabled_features) gets a "FAQ / Information" row in the
unified main menu (flows.py); tapping it hands the conversation here for as
long as the patient keeps tapping topics.

Deliberately shallow: no state machine depth beyond one level (unlike
booking's department -> doctor -> slot -> confirm chain, Section 3.3) --
every incoming message while active (a topic tap, unrecognized free text)
shows the topic list; tapping a topic replies with that topic's configured
answer, then loops straight back to the topic list. The one bit of state that
DOES exist, STATE_FAQ_ACTIVE, exists purely so flows.py's router knows to
keep delegating subsequent messages here instead of falling back to the
unified main menu after every single message -- Section 14.2's original
version reset to true IDLE after every message, which was fine when FAQ was
its own exclusive top-level flow_type, but would have meant "tap a topic,
then anything else you send goes to the unified menu instead of the topic
list" once FAQ became one feature among several. A reset keyword (Section 0's
"stuck session" fix, via core/flow_common.py's is_reset_keyword()) is handled
by flows.py's router BEFORE it ever delegates here, so it always returns to
the top-level unified menu, not just this flow's own topic list -- this
module still needs no dedicated reset-keyword check of its own.

`connector` is accepted only to match the shared sub-flow call signature
flows.py delegates with -- FAQ flow does not use Section 12.6.2's connector
interface at all (no bookings, no Tier 1/2/3 relevance).

Reuses core/flow_common.py's cap_rows() (Meta's 10-row WhatsApp list limit,
Section 12.7's finding) rather than reimplementing it -- that bug was found
and fixed once already, in booking_flow.py; a second flow type is exactly
the case that extraction was for.

Section 12.11 (language selection): `language` is threaded through from
flows.py's router the same way every other sub-flow now takes it -- only the
bot's own fixed strings ("choose a topic", "View Topics", ...) are looked up
via core/translations.t(); a topic's configured answer_text is hospital-
entered content and is never auto-translated (same rule as everywhere else
in this feature).
"""
import db.repository as db
from flows.common import cap_rows
from core.translations import t
from core.whatsapp import WhatsAppClient

STATE_FAQ_ACTIVE = "FAQ_ACTIVE"
# Same id flows/router.py's own GOTO_MAIN_MENU uses -- intercepted globally
# in that module's handle_incoming, BEFORE any state dispatch (including the
# delegation into this module), so no local handling is needed here. Not
# imported from flows/booking/state.py (the value "goto_main_menu" is
# duplicated, not shared) to avoid a dependency this module's own docstring
# doesn't otherwise need -- FAQ has no booking/connector relationship at all.
GOTO_MAIN_MENU = "goto_main_menu"


async def send_topic_menu(
    wa: WhatsAppClient, phone: str, hospital_id: int, hospital_name: str, language: str = "en",
) -> None:
    """Public: flows.py calls this directly to kick off the FAQ sub-flow when
    a patient taps "FAQ / Information" from the unified main menu."""
    topics = db.get_faq_topics(hospital_id)
    if not topics:
        # Enabled the "faq" feature but no topics configured yet -- a real,
        # loud-in-logs-adjacent state (nothing to show a patient), but still a
        # graceful patient-facing message rather than an empty/broken list
        # send (same "never send Meta a zero-row list" discipline as
        # booking_flow.py's Phase 8 hardening).
        await wa.send_text(phone, t("faq_no_topics", language, hospital_name=hospital_name))
        return

    rows = [{"id": str(t_["id"]), "title": t_["topic_label"]} for t_ in topics]
    rows.append({"id": GOTO_MAIN_MENU, "title": t("back_to_menu_option", language)})
    rows = cap_rows(rows, f"FAQ topic menu for hospital {hospital_id}")
    await wa.send_list(
        to=phone,
        body_text=t("faq_topic_prompt", language, hospital_name=hospital_name),
        button_text=t("view_topics_button", language),
        sections=[{"title": t("topics_section_title", language), "rows": rows}],
    )


async def handle_incoming(
    wa: WhatsAppClient,
    sessions,
    phone: str,
    hospital_id: int,
    reply: dict,
    hospital_name: str = "the hospital",
    connector=None,
    language: str = "en",
) -> None:
    """Called by flows.py's router for every message while the session is in
    STATE_FAQ_ACTIVE. Stays in STATE_FAQ_ACTIVE after every message (rather
    than resetting to true IDLE) so the next message is routed back here too
    -- see the module docstring for why that matters now that FAQ is one
    feature among several, not an exclusive top-level flow_type."""
    sessions.set(hospital_id, phone, STATE_FAQ_ACTIVE, {})

    if reply["type"] == "interactive_reply":
        topic = db.find_faq_topic(hospital_id, reply["id"])
        if topic is not None:
            await wa.send_text(phone, topic["answer_text"])
            await send_topic_menu(wa, phone, hospital_id, hospital_name, language=language)
            return

    # Unrecognized/stale tap, or any other free text -- both show the same
    # topic list (Section 14.2: no deeper state, every reply loops back to
    # the topic menu).
    await send_topic_menu(wa, phone, hospital_id, hospital_name, language=language)

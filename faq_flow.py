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
"""
import db.repository as db
from core.flow_common import cap_rows
from core.whatsapp import WhatsAppClient

STATE_FAQ_ACTIVE = "FAQ_ACTIVE"


async def send_topic_menu(wa: WhatsAppClient, phone: str, hospital_id: int, hospital_name: str) -> None:
    """Public: flows.py calls this directly to kick off the FAQ sub-flow when
    a patient taps "FAQ / Information" from the unified main menu."""
    topics = db.get_faq_topics(hospital_id)
    if not topics:
        # Enabled the "faq" feature but no topics configured yet -- a real,
        # loud-in-logs-adjacent state (nothing to show a patient), but still a
        # graceful patient-facing message rather than an empty/broken list
        # send (same "never send Meta a zero-row list" discipline as
        # booking_flow.py's Phase 8 hardening).
        await wa.send_text(
            phone, f"Sorry, {hospital_name} hasn't set up any FAQ topics yet. Please check back later."
        )
        return

    rows = [{"id": str(t["id"]), "title": t["topic_label"]} for t in topics]
    rows = cap_rows(rows, f"FAQ topic menu for hospital {hospital_id}")
    await wa.send_list(
        to=phone,
        body_text=f"{hospital_name} — choose a topic to learn more:",
        button_text="View Topics",
        sections=[{"title": "Topics", "rows": rows}],
    )


async def handle_incoming(
    wa: WhatsAppClient,
    sessions,
    phone: str,
    hospital_id: int,
    reply: dict,
    hospital_name: str = "the hospital",
    connector=None,
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
            await send_topic_menu(wa, phone, hospital_id, hospital_name)
            return

    # Unrecognized/stale tap, or any other free text -- both show the same
    # topic list (Section 14.2: no deeper state, every reply loops back to
    # the topic menu).
    await send_topic_menu(wa, phone, hospital_id, hospital_name)

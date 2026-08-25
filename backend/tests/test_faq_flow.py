# tests/test_faq_flow.py
"""
SPEC Section 14.2: the FAQ flow's handler (faq_flow.py) -- direct unit tests
against handle_incoming(), same FakeWhatsAppClient pattern as
tests/test_booking_flow.py (records sends instead of hitting the network).
Covers: first-contact/welcome topic list, tapping a topic then looping back
to the topic list, unrecognized taps and free text falling back to the topic
list, a reset keyword mid-"loop" behaving the same way (Section 0's
"stuck session" fix applies here too, by construction -- see faq_flow.py's
module docstring for why no dedicated check is needed), the empty-topics
graceful message, and the shared _cap_rows() 10-row WhatsApp list cap.
"""
import pytest

import db.repository as db
from core.session_store import InMemorySessionStore
from flows.faq import handle_incoming

PHONE = "5491112345678"


class FakeWhatsAppClient:
    def __init__(self):
        self.sent = []  # list of ("text"|"list", kwargs)

    async def send_text(self, to, text):
        self.sent.append(("text", {"to": to, "text": text}))

    async def send_list(self, to, body_text, button_text, sections, header_text=None, footer_text=None):
        self.sent.append(("list", {"to": to, "body_text": body_text, "sections": sections}))


def text_reply(text):
    return {"type": "text", "text": text}


def tap(option_id, title=""):
    return {"type": "interactive_reply", "id": option_id, "title": title}


def _row_ids(kind_kwargs):
    return {row["id"] for section in kind_kwargs["sections"] for row in section["rows"]}


@pytest.mark.asyncio
async def test_first_contact_shows_welcome_and_topic_list(hospital_id):
    db.create_faq_topic(hospital_id, "Hours", "We're open Mon-Sat, 9-6.")
    db.create_faq_topic(hospital_id, "Location", "123 Main St.")
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), hospital_name="City Clinic")

    assert len(wa.sent) == 1
    kind, kwargs = wa.sent[0]
    assert kind == "list"
    assert "City Clinic" in kwargs["body_text"]
    labels = {row["title"] for section in kwargs["sections"] for row in section["rows"]}
    assert labels == {"Hours", "Location"}


@pytest.mark.asyncio
async def test_tapping_a_topic_replies_with_its_answer_then_loops_back_to_topic_list(hospital_id):
    topic = db.create_faq_topic(hospital_id, "Pricing", "Consultations start at $50.")
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(str(topic["id"])), hospital_name="City Clinic")

    assert len(wa.sent) == 2
    assert wa.sent[0] == ("text", {"to": PHONE, "text": "Consultations start at $50."})
    kind, kwargs = wa.sent[1]
    assert kind == "list"
    assert _row_ids(kwargs) == {str(topic["id"])}


@pytest.mark.asyncio
async def test_no_deeper_state_every_reply_loops_back_to_topic_menu(hospital_id):
    """Section 14.5: no state machine depth beyond one level -- the session
    always lands back in STATE_FAQ_ACTIVE (not a deeper state), which is what
    lets flows.py's router keep delegating subsequent messages here."""
    from flows.faq import STATE_FAQ_ACTIVE

    topic = db.create_faq_topic(hospital_id, "Hours", "9-6 daily.")
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_SLOT", {"doctor_id": "leftover-from-a-different-flow-type"})

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(str(topic["id"])))

    assert sessions.get(hospital_id, PHONE) == {"state": STATE_FAQ_ACTIVE, "context": {}}


@pytest.mark.asyncio
async def test_unrecognized_tap_falls_back_to_topic_list(hospital_id):
    db.create_faq_topic(hospital_id, "Hours", "9-6 daily.")
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("stale-or-cross-hospital-id"))

    assert len(wa.sent) == 1
    assert wa.sent[0][0] == "list"


@pytest.mark.asyncio
async def test_reset_keyword_mid_loop_still_shows_topic_list(hospital_id):
    """No dedicated reset-keyword check exists in faq_flow.py (see its module
    docstring) -- every non-topic-tap message, "hi" included, already falls
    through to the same topic-list behavior. This proves that's actually
    true, not just assumed."""
    db.create_faq_topic(hospital_id, "Hours", "9-6 daily.")
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("random unrelated free text"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("restart"))

    assert len(wa.sent) == 3
    for kind, kwargs in wa.sent:
        assert kind == "list"


@pytest.mark.asyncio
async def test_no_topics_configured_shows_graceful_message_not_empty_list(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), hospital_name="City Clinic")

    assert wa.sent == [("text", {
        "to": PHONE,
        "text": "Sorry, City Clinic hasn't set up any FAQ topics yet. Please check back later.",
    })]


@pytest.mark.asyncio
async def test_topic_list_capped_to_whatsapp_list_limit(hospital_id):
    from flows.common import MAX_LIST_ROWS

    for i in range(MAX_LIST_ROWS + 5):
        db.create_faq_topic(hospital_id, f"Topic {i}", f"Answer {i}")
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"))

    kind, kwargs = wa.sent[-1]
    rows = kwargs["sections"][0]["rows"]
    assert len(rows) == MAX_LIST_ROWS


@pytest.mark.asyncio
async def test_faq_topics_scoped_to_own_hospital(hospital_id, second_hospital_id):
    db.create_faq_topic(hospital_id, "Hospital A topic", "A's answer")
    db.create_faq_topic(second_hospital_id, "Hospital B topic", "B's answer")
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"))

    kind, kwargs = wa.sent[-1]
    labels = {row["title"] for section in kwargs["sections"] for row in section["rows"]}
    assert labels == {"Hospital A topic"}

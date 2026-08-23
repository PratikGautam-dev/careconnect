# tests/test_flows.py
"""
SPEC Section 14.5: the feature-toggle router (flows.py) -- supersedes Section
14.1's single flow_type dispatch. Covers, per the Section 14.5 test plan:
  - the IDLE menu only shows a tenant's enabled_features, in the fixed
    _FEATURE_MENU order, never anything unselected
  - a tenant with both "booking" and "faq" enabled can reach BOTH sub-flows
    in the same conversation, and a reset keyword mid-FAQ returns to the
    TOP-level unified menu, not just faq_flow's own topic list
  - tapping a row id for a feature this tenant hasn't enabled falls back to
    the menu rather than starting that feature (stale tap / disabled since)
  - reception_handoff (promoted to real, Section 14.5 follow-up) queues a
    handoff_requests row and replies with a real message
  - view_appointments and hospital_info (real, one-shot features)
  - a live webhook round-trip proving core/main.py actually calls this
    router end to end for a real (migrated) hospital row

Migration correctness itself (flow_type -> enabled_features backfill) is
covered separately in tests/test_enabled_features_migration.py.
"""
import hashlib
import hmac
import json
import os

import pytest

import db.repository as db
import flows
from core.history import InMemorySessionStore
from core.translations import t as translate

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")

from core.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

PHONE = "5491112345678"


class FakeWhatsAppClient:
    def __init__(self):
        self.sent = []  # list of ("text"|"list"|"buttons", kwargs)

    async def send_text(self, to, text):
        self.sent.append(("text", {"to": to, "text": text}))

    async def send_list(self, to, body_text, button_text, sections, header_text=None, footer_text=None):
        self.sent.append(("list", {"to": to, "body_text": body_text, "sections": sections}))

    async def send_buttons(self, to, body_text, buttons, header_text=None, footer_text=None):
        self.sent.append(("buttons", {"to": to, "body_text": body_text, "buttons": buttons}))


class FakeConnector:
    """Minimal stand-in for connectors.Connector -- only the methods the
    router's one-shot features (booking department listing, view_appointments)
    actually call."""
    def __init__(self, departments=None, appointments=None):
        self._departments = departments or []
        self._appointments = appointments or []

    def get_departments(self, hospital_id):
        return self._departments

    def get_upcoming_appointments(self, hospital_id, phone=None, offset_hours=None, now=None):
        return self._appointments


def text_reply(text):
    return {"type": "text", "text": text}


def tap(option_id, title=""):
    return {"type": "interactive_reply", "id": option_id, "title": title}


def _row_ids(kind_kwargs):
    return [row["id"] for section in kind_kwargs["sections"] for row in section["rows"]]


def _sessions_with_english_chosen(hospital_id, phone=PHONE):
    """Section 12.11: a genuinely fresh session now sees the language picker
    before anything else (covered separately below) -- every test in this
    file that isn't specifically about the language picker itself pre-seeds
    an already-chosen language, the same "returning within this session"
    shape a real conversation has after its first message, so the rest of
    the router's behavior (menu contents, feature dispatch, reset handling)
    can be tested independent of that one extra first step."""
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, phone, "IDLE", {}, language="en")
    return sessions


@pytest.mark.asyncio
async def test_menu_only_shows_enabled_features(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Clinic", connector=FakeConnector(),
        enabled_features=["booking", "faq"],
    )

    assert len(wa.sent) == 1
    kind, kwargs = wa.sent[0]
    assert kind == "list"
    assert _row_ids(kwargs) == ["menu_book", "menu_faq_bot", "menu_change_language"]


@pytest.mark.asyncio
async def test_unselected_features_dont_appear_in_menu(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        connector=FakeConnector(), enabled_features=["booking"],
    )

    kind, kwargs = wa.sent[0]
    ids = _row_ids(kwargs)
    assert "menu_faq_bot" not in ids
    assert "menu_reschedule" not in ids
    assert "menu_cancel" not in ids
    assert ids == ["menu_book", "menu_change_language"]


@pytest.mark.asyncio
async def test_no_features_enabled_shows_graceful_message_not_empty_list(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Clinic", connector=FakeConnector(), enabled_features=[],
    )

    assert wa.sent == [("text", {
        "to": PHONE,
        "text": "Sorry, City Clinic hasn't finished setting up WhatsApp yet. Please check back later.",
    })]


@pytest.mark.asyncio
async def test_dual_feature_tenant_can_access_both_booking_and_faq(hospital_id):
    """Section 14.5's central new capability: booking and faq are no longer
    mutually exclusive flow_types -- one hospital, one conversation, both
    sub-flows reachable in turn."""
    db.create_faq_topic(hospital_id, "Hours", "9-6 daily.")
    departments = db.get_departments(hospital_id)
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)
    connector = FakeConnector(departments=departments)
    enabled = ["booking", "faq"]

    # Tap "Book Appointment" -> enters booking_flow's own state machine.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=enabled)
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    # "Go back" navigation appends a BACK_ID row to the department menu.
    assert {d["id"] for d in departments} | {"nav_back"} == set(_row_ids(kwargs))
    assert sessions.get(hospital_id, PHONE)["state"] != "IDLE"

    # A reset keyword mid-booking returns to the TOP-level unified menu (not
    # booking_flow's own idea of "start over") -- new, deliberate Section
    # 14.5 behavior.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=enabled)
    kind, kwargs = wa.sent[-1]
    assert _row_ids(kwargs) == ["menu_book", "menu_faq_bot", "menu_change_language"]

    # Now tap "FAQ / Information" -> enters faq_flow's topic loop.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_faq_bot"), connector=connector, enabled_features=enabled)
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == [str(t["id"]) for t in db.get_faq_topics(hospital_id)]
    import faq_flow
    assert sessions.get(hospital_id, PHONE)["state"] == faq_flow.STATE_FAQ_ACTIVE

    # A reset keyword mid-FAQ ALSO returns to the top-level unified menu, not
    # just faq_flow's own topic list.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("restart"), connector=connector, enabled_features=enabled)
    kind, kwargs = wa.sent[-1]
    assert _row_ids(kwargs) == ["menu_book", "menu_faq_bot", "menu_change_language"]


@pytest.mark.asyncio
async def test_tap_for_disabled_feature_falls_back_to_menu(hospital_id):
    """A stale tap (e.g. from a menu sent before the hospital disabled a
    feature) for something not currently enabled must not start that
    feature -- it just re-shows the current menu."""
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_faq_bot"),
        connector=FakeConnector(), enabled_features=["booking"],
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == ["menu_book", "menu_change_language"]
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_view_appointments_feature(hospital_id):
    """Item 6 (Spec.md Section 0): "My Appointments" is now an interactive
    list (one row per appointment), not a plain-text dump -- tapping a row
    is covered separately below."""
    from datetime import datetime
    from types import SimpleNamespace

    appt = SimpleNamespace(
        id=501, doctor_name="Dr. Rao", department_name="Cardiology", scheduled_at=datetime(2026, 9, 1, 10, 0),
    )
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_view_appointments"),
        connector=FakeConnector(appointments=[appt]), enabled_features=["view_appointments"],
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    row = kwargs["sections"][0]["rows"][0]
    assert row["id"] == "appt_501"
    assert "Dr. Rao" in row["title"]
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_VIEW_APPOINTMENT_ACTION"


@pytest.mark.asyncio
async def test_view_appointments_no_upcoming_sends_plain_text(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_view_appointments"),
        connector=FakeConnector(appointments=[]), enabled_features=["view_appointments"],
    )

    assert wa.sent[-1][0] == "text"
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_tapping_an_appointment_in_my_appointments_shows_quick_actions(hospital_id):
    from datetime import datetime
    from types import SimpleNamespace

    appt = SimpleNamespace(
        id=502, doctor_name="Dr. Rao", department_name="Cardiology", doctor_id="doc1",
        department_id="cardiology", scheduled_at=datetime(2026, 9, 1, 10, 0),
    )
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)
    connector = FakeConnector(appointments=[appt])

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_view_appointments"),
        connector=connector, enabled_features=["view_appointments"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_VIEW_APPOINTMENT_ACTION"

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("appt_502"),
        connector=connector, enabled_features=["view_appointments"],
    )
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    button_ids = {b["id"] for b in kwargs["buttons"]}
    assert flows.GOTO_MAIN_MENU in button_ids
    assert "manage_cancel_502" in button_ids
    assert "manage_reschedule_502" in button_ids


@pytest.mark.asyncio
async def test_hospital_info_feature_sends_static_text(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_hospital_info"),
        connector=FakeConnector(), enabled_features=["hospital_info"],
    )

    assert wa.sent[-1][0] == "text"
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_reception_handoff_queues_request_and_replies(hospital_id):
    """reception_handoff (Section 14.5 follow-up) is real now: tapping it
    queues a handoff_requests row (reason='patient_requested') for the staff
    portal, and replies with a real message, not the placeholder text."""
    import db.repository as db

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reception"),
        connector=FakeConnector(), enabled_features=["reception_handoff"],
    )

    assert wa.sent[-1] == ("text", {"to": PHONE, "text": translate("reception_handoff_text", "en")})
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"

    open_handoffs = db.get_handoff_requests(hospital_id, status="open")
    assert any(h["phone"] == PHONE and h["reason"] == "patient_requested" for h in open_handoffs)


@pytest.mark.asyncio
async def test_bot_goes_silent_while_a_handoff_is_open(hospital_id):
    """Item 7 (Spec.md Section 0), real production bug reproduced: after
    "Talk to Reception" queues an open handoff_requests row, a patient saying
    "hi" (a reset keyword) must NOT get the bot's own menu response back --
    the bot goes completely silent for that phone until staff resolve the
    handoff, so replies genuinely route to the human queue instead."""
    import db.repository as db

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reception"),
        connector=FakeConnector(), enabled_features=["reception_handoff"],
    )
    assert len(db.get_handoff_requests(hospital_id, status="open")) == 1
    sent_before = len(wa.sent)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        connector=FakeConnector(), enabled_features=["reception_handoff", "booking"],
    )

    # Zero new outgoing messages -- neither a reset-keyword menu, nor
    # anything else the bot would normally send.
    assert len(wa.sent) == sent_before

    # A different, unrelated phone number is completely unaffected.
    wa2 = FakeWhatsAppClient()
    sessions2 = _sessions_with_english_chosen(hospital_id)
    await flows.handle_incoming(
        wa2, sessions2, "5491199999999", hospital_id, tap("menu_book"),
        connector=FakeConnector(), enabled_features=["booking"],
    )
    assert wa2.sent  # the bot responds normally for a phone with no open handoff


@pytest.mark.asyncio
async def test_messages_during_active_handoff_are_recorded_in_the_thread(hospital_id):
    """Real bug fix, follow-up to test_bot_goes_silent_while_a_handoff_is_open
    above: a patient's messages sent AFTER triggering a handoff (but before
    it's resolved) were previously just dropped -- silenced correctly, but
    never actually captured anywhere staff could see. Now recorded as real
    inbound handoff_messages rows against the open handoff, in order,
    alongside the original trigger message."""
    import db.repository as db

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reception"),
        connector=FakeConnector(), enabled_features=["reception_handoff"],
    )
    handoff = db.get_handoff_requests(hospital_id, status="open")[0]

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi, is anyone there?"),
        connector=FakeConnector(), enabled_features=["reception_handoff", "booking"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("I need to speak to someone urgently"),
        connector=FakeConnector(), enabled_features=["reception_handoff", "booking"],
    )

    thread = db.get_handoff_messages(hospital_id, handoff["id"])
    texts = [m["message_text"] for m in thread]
    assert texts == [
        "Patient tapped \"Talk to Reception\" from the main menu.",
        "hi, is anyone there?",
        "I need to speak to someone urgently",
    ]
    assert all(m["direction"] == "inbound" for m in thread)


@pytest.mark.asyncio
async def test_bot_resumes_normal_flow_after_handoff_resolved(hospital_id):
    """Item 2 of this follow-up (Spec.md Section 0): explicitly proves what
    was previously only true "by construction" -- resolve_handoff_request()
    flips status to 'resolved', and has_open_handoff()/get_open_handoff()
    both filter on status='open', so the very next message should reach
    normal bot logic again, not silence or another handoff-routed message."""
    import db.repository as db

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reception"),
        connector=FakeConnector(), enabled_features=["reception_handoff"],
    )
    handoff = db.get_handoff_requests(hospital_id, status="open")[0]

    # Silent while open (already covered above) -- confirm once more here too.
    sent_before = len(wa.sent)
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hello?"),
        connector=FakeConnector(), enabled_features=["reception_handoff", "booking"],
    )
    assert len(wa.sent) == sent_before

    resolved = db.resolve_handoff_request(hospital_id, handoff["id"])
    assert resolved is True

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        connector=FakeConnector(), enabled_features=["reception_handoff", "booking"],
    )

    # A real bot response this time -- the reset keyword "hi" reached normal
    # routing and showed the unified menu, not silence.
    assert len(wa.sent) == sent_before + 1
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert "menu_reception" in row_ids
    assert "menu_book" in row_ids

    # And the resolved handoff's thread is untouched by this -- "hi" after
    # resolution is a normal bot message, not another inbound handoff entry.
    thread = db.get_handoff_messages(hospital_id, handoff["id"])
    assert [m["message_text"] for m in thread] == [
        "Patient tapped \"Talk to Reception\" from the main menu.",
        "hello?",
    ]


@pytest.mark.asyncio
async def test_bot_resumes_for_a_stale_never_resolved_handoff(hospital_id):
    """"Bot stuck on Talk to Reception" follow-up (Spec.md Section 0): the
    real gap behind the reported bug -- an open handoff previously
    silenced the bot for that phone FOREVER if staff never got to it, with
    no escape (not even the reset-keyword hatch). Now, past
    db.repository._HANDOFF_STALE_MINUTES, the bot resumes on its own --
    covers the case staff genuinely forgot/never resolved it, not just the
    already-covered "staff resolved it" case above."""
    import db.repository as db
    from datetime import datetime, timedelta

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reception"),
        connector=FakeConnector(), enabled_features=["reception_handoff"],
    )
    handoff = db.get_handoff_requests(hospital_id, status="open")[0]

    # Never resolved by staff -- just goes stale with time.
    conn = db.get_connection()
    stale_at = datetime.now() - timedelta(minutes=90)
    conn.execute(
        "UPDATE handoff_requests SET created_at = ? WHERE id = ?",
        (stale_at.strftime("%Y-%m-%d %H:%M:%S"), handoff["id"]),
    )
    conn.commit()

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        connector=FakeConnector(), enabled_features=["reception_handoff", "booking"],
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert "menu_book" in row_ids

    # Still genuinely 'open' in the DB -- staff can still resolve it later,
    # this only stopped it from silencing the bot.
    assert db.get_handoff_requests(hospital_id, status="open")[0]["id"] == handoff["id"]


@pytest.mark.asyncio
async def test_change_language_menu_option_switches_mid_session(hospital_id):
    """Item 4 (Spec.md Section 0): "Change Language" is always offered on the
    main menu itself (not gated by enabled_features), and tapping it re-shows
    the picker without needing a full session reset -- picking Hindi there
    switches the very next menu to Hindi."""
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    # Any unrecognized message at IDLE shows the top-level unified menu.
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hello there"),
        connector=FakeConnector(), enabled_features=["booking"],
    )
    kind, kwargs = wa.sent[0]
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert flows.CHANGE_LANGUAGE_ROW in row_ids

    # Tap "Change Language" instead of a feature.
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(flows.CHANGE_LANGUAGE_ROW),
        connector=FakeConnector(), enabled_features=["booking"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_LANGUAGE"
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"

    # Pick Hindi -> menu re-shown in Hindi, session language actually changed.
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("lang_hi"),
        connector=FakeConnector(), enabled_features=["booking"],
    )
    assert sessions.get(hospital_id, PHONE)["language"] == "hi"
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert kwargs["body_text"] == translate("welcome_menu", "hi", hospital_name="the hospital")


@pytest.mark.asyncio
async def test_change_language_row_absent_when_picker_disabled(hospital_id):
    """A hospital that disabled the language picker entirely
    (language_prompt_enabled=False, Section 12.13) never sees "Change
    Language" either -- offering it would contradict the hospital's own
    single-language setting."""
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_book"),
        connector=FakeConnector(), enabled_features=["booking"], language_prompt_enabled=False,
    )
    kind, kwargs = wa.sent[0]
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert flows.CHANGE_LANGUAGE_ROW not in row_ids


def test_real_features_are_all_features():
    assert flows.REAL_FEATURES == flows.ALL_FEATURES
    assert "reception_handoff" in flows.REAL_FEATURES
    assert "payment_link" not in flows.ALL_FEATURES
    assert "reports" not in flows.ALL_FEATURES


# --- Section 12.11: language selection (flows.py owns this decision point) ---

@pytest.mark.asyncio
async def test_fresh_session_sees_language_picker_before_the_menu(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Clinic", connector=FakeConnector(), enabled_features=["booking"],
    )

    assert len(wa.sent) == 1
    kind, kwargs = wa.sent[0]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"lang_en", "lang_hi"}
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_LANGUAGE"
    assert session.get("language") is None


@pytest.mark.asyncio
async def test_selecting_english_then_shows_menu_in_english(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Clinic", connector=FakeConnector(), enabled_features=["booking"],
    )

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("lang_en"),
        hospital_name="City Clinic", connector=FakeConnector(), enabled_features=["booking"],
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert "City Clinic" in kwargs["body_text"]
    assert kwargs["body_text"] == translate("welcome_menu", "en", hospital_name="City Clinic")
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "IDLE"
    assert session["language"] == "en"


@pytest.mark.asyncio
async def test_selecting_hindi_then_shows_menu_in_hindi(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Clinic", connector=FakeConnector(), enabled_features=["booking"],
    )

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("lang_hi"),
        hospital_name="City Clinic", connector=FakeConnector(), enabled_features=["booking"],
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert kwargs["body_text"] == translate("welcome_menu", "hi", hospital_name="City Clinic")
    row = kwargs["sections"][0]["rows"][0]
    assert row["title"] == translate("feature_booking", "hi")
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "IDLE"
    assert session["language"] == "hi"


@pytest.mark.asyncio
async def test_invalid_tap_at_language_picker_reprompts_the_picker(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_LANGUAGE", {})

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("English please"),
        connector=FakeConnector(), enabled_features=["booking"],
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"lang_en", "lang_hi"}
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_LANGUAGE"
    assert session.get("language") is None


@pytest.mark.asyncio
async def test_language_persists_across_a_full_booking_flow_in_hindi(hospital_id):
    """Section 12.11's central persistence guarantee: once chosen, Hindi
    stays in effect through every booking_flow.py state -- department,
    doctor, date, time, name+age collection, confirmation -- not just the
    top-level menu flows.py itself renders. Section 12.12 restructured the
    slot step into date+time (age was briefly dropped, then restored by a
    Section 12.13 follow-up); this test follows the current sequence."""
    department = db.get_departments(hospital_id)[0]
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    connector = flows._DEFAULT_CONNECTOR

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("lang_hi"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    kind, kwargs = wa.sent[-1]
    assert kwargs["body_text"] == translate("select_department", "hi")

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    kind, kwargs = wa.sent[-1]
    assert kwargs["body_text"] == translate("select_doctor", "hi", department_name=department["name"])

    doctor = db.get_doctors(hospital_id, department["id"])[0]
    doctor_id = doctor["id"]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id), connector=connector, enabled_features=["booking"])
    kind, kwargs = wa.sent[-1]
    # doctor_name is hospital-entered content, never translated (already
    # includes "Dr." in English regardless of session language) -- only the
    # surrounding prompt text is Hindi.
    assert doctor["name"] in kwargs["body_text"] and "तारीख" in kwargs["body_text"]
    all_slots = db.get_slots(hospital_id, doctor_id)
    date_str = all_slots[0]["date"]

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str), connector=connector, enabled_features=["booking"])
    kind, kwargs = wa.sent[-1]
    assert kwargs["body_text"] == translate("select_time_slot", "hi")

    slot = [s for s in all_slots if s["date"] == date_str][0]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_NAME"
    kind, kwargs = wa.sent[-1]
    assert kwargs["text"] == translate("ask_patient_name", "hi")

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Ravi Kumar"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_AGE"
    kind, kwargs = wa.sent[-1]
    assert kwargs["text"] == translate("ask_patient_age", "hi", patient_name="Ravi Kumar")

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("34"), connector=connector, enabled_features=["booking"])
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_CONFIRMATION"
    assert session["language"] == "hi"
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert kwargs["body_text"] == translate(
        "confirm_booking_summary", "hi",
        department_name=session["context"]["department_name"],
        doctor_name=session["context"]["doctor_name"],
        date_label=session["context"]["date_label"],
        time_label=session["context"]["slot_time"],
        patient_name="Ravi Kumar", patient_age=34,
    )

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"), connector=connector, enabled_features=["booking"])
    kind, kwargs = wa.sent[-1]
    # Item 3 (Spec.md Section 0): success message is now buttons, not text.
    assert kind == "buttons"
    assert "सफलतापूर्वक" in kwargs["body_text"]
    # Item 8 (Spec.md Section 0): reference_id format is now APT-<DDMMMYY>-<NNN>.
    assert "APT-" in kwargs["body_text"]
    # Booked with the patient's name/age (Section 12.11's other half).
    patient = db.get_patient_by_phone(hospital_id, PHONE)
    assert patient["name"] == "Ravi Kumar"
    assert patient["age"] == 34
    # Reset to IDLE. Language-reset follow-up (Spec.md Section 0): a FULLY
    # COMPLETED booking now clears the chosen language too (was preserved
    # before this fix) -- the next fresh conversation shows the picker
    # again instead of assuming Hindi forever. See
    # test_language_resets_to_picker_after_a_completed_booking for the
    # dedicated test of this behavior itself.
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "IDLE"
    assert "language" not in session


@pytest.mark.asyncio
async def test_returning_patient_with_name_on_file_skips_name_prompt(hospital_id):
    """A patient who's already booked once (name on file) is never re-asked
    on a later booking -- the bot should "remember" them."""
    department = db.get_departments(hospital_id)[0]
    doctor_id = db.get_doctors(hospital_id, department["id"])[0]["id"]
    connector = flows._DEFAULT_CONNECTOR
    import db.connection as db_connection
    from db.repository import _upsert_patient
    _upsert_patient(db_connection.get_connection(), hospital_id, PHONE, "Priya Shah", 29)
    db_connection.get_connection().commit()

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)
    slot = db.get_slots(hospital_id, doctor_id)[0]
    sessions.set(hospital_id, PHONE, "AWAITING_TIME_SLOT", {
        "department_id": department["id"], "department_name": department["name"],
        "doctor_id": doctor_id, "doctor_name": "Dr. X",
        "date": slot["date"], "date_label": "Sat, Aug 8",
    }, language="en")

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]), connector=connector, enabled_features=["booking"])

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_CONFIRMATION"  # not AWAITING_PATIENT_NAME
    assert session["context"]["patient_name"] == "Priya Shah"
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "👤 *Patient:* Priya Shah" in kwargs["body_text"]


@pytest.mark.asyncio
async def test_name_age_skip_works_across_a_genuinely_new_session_object(hospital_id):
    """Item 10 (Spec.md Section 0): audits that the name/age skip isn't just
    a within-one-session-object convenience (Section 12.12's race-loser
    test covers THAT scenario separately) -- a completed booking in one
    InMemorySessionStore(), then a brand new InMemorySessionStore() instance
    (a genuinely new day/new session, same phone) must still skip straight
    to confirmation. connector.get_patient_info() is a pure DB lookup keyed
    on (hospital_id, phone), independent of session state, so this is
    expected to already work -- this test proves it rather than assuming it."""
    department = db.get_departments(hospital_id)[0]
    doctor_id = db.get_doctors(hospital_id, department["id"])[0]["id"]
    connector = flows._DEFAULT_CONNECTOR

    # Session #1: a full booking from scratch, collecting name/age for the
    # first time.
    wa1 = FakeWhatsAppClient()
    sessions1 = _sessions_with_english_chosen(hospital_id)
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap(doctor_id), connector=connector, enabled_features=["booking"])
    slots = db.get_slots(hospital_id, doctor_id)
    date_str = slots[0]["date"]
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap(date_str), connector=connector, enabled_features=["booking"])
    slot = [s for s in slots if s["date"] == date_str][0]
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap(slot["id"]), connector=connector, enabled_features=["booking"])
    assert sessions1.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_NAME"
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, text_reply("Priya Shah"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, text_reply("29"), connector=connector, enabled_features=["booking"])
    assert sessions1.get(hospital_id, PHONE)["state"] == "AWAITING_CONFIRMATION"
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap("confirm"), connector=connector, enabled_features=["booking"])
    assert wa1.sent[-1][0] == "buttons"  # booking success

    # Session #2: an entirely new session store (nothing shared with
    # sessions1's in-memory state -- the only thing carrying over is the DB
    # row _upsert_patient() wrote during session #1's booking), same phone,
    # a fresh booking for a DIFFERENT slot.
    wa2 = FakeWhatsAppClient()
    sessions2 = _sessions_with_english_chosen(hospital_id)
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap(doctor_id), connector=connector, enabled_features=["booking"])
    slots2 = db.get_slots(hospital_id, doctor_id)  # first slot is now booked, list has moved on
    date_str2 = slots2[0]["date"]
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap(date_str2), connector=connector, enabled_features=["booking"])
    slot2 = [s for s in slots2 if s["date"] == date_str2][0]
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap(slot2["id"]), connector=connector, enabled_features=["booking"])

    session2 = sessions2.get(hospital_id, PHONE)
    assert session2["state"] == "AWAITING_CONFIRMATION"  # NOT AWAITING_PATIENT_NAME
    assert session2["context"]["patient_name"] == "Priya Shah"
    assert session2["context"]["patient_age"] == 29
    kind, kwargs = wa2.sent[-1]
    assert kind == "buttons"
    assert "👤 *Patient:* Priya Shah" in kwargs["body_text"]
    assert "🎂 *Age:* 29" in kwargs["body_text"]


@pytest.mark.asyncio
async def test_language_resets_to_picker_after_a_completed_booking(hospital_id):
    """Language-reset follow-up (Spec.md Section 0). Before this fix,
    core/history.py's reset() (called after EVERY completed action --
    booking, cancel, decline, ...) preserved the chosen language
    unconditionally, so a patient was only ever asked once per session,
    indefinitely. Now specifically a FULLY COMPLETED booking clears it --
    the very next fresh interaction (after the success message) shows the
    language picker again, not a silent continuation in the same language."""
    department = db.get_departments(hospital_id)[0]
    doctor_id = db.get_doctors(hospital_id, department["id"])[0]["id"]
    connector = flows._DEFAULT_CONNECTOR

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id), connector=connector, enabled_features=["booking"])
    slots = db.get_slots(hospital_id, doctor_id)
    date_str = slots[0]["date"]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str), connector=connector, enabled_features=["booking"])
    slot = [s for s in slots if s["date"] == date_str][0]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Priya Shah"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("29"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"), connector=connector, enabled_features=["booking"])
    assert wa.sent[-1][0] == "buttons"  # booking success

    # Language was cleared -- session.get() no longer carries a "language" key.
    assert "language" not in sessions.get(hospital_id, PHONE)

    # The very next message (any message, not a special trigger) shows the
    # bilingual language picker again, not the menu directly.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hello"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_LANGUAGE"
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"lang_en", "lang_hi"}


@pytest.mark.asyncio
async def test_language_preserved_across_non_booking_resets(hospital_id):
    """The language-reset above is a narrow exception for a COMPLETED
    booking specifically -- every other reset() call site (declining a
    booking, cancelling an appointment, a stale-session reset, ...) still
    preserves the chosen language, per Section 12.11's original "ask once
    per fresh conversation" reasoning. Covers declining a booking (tap
    'cancel' at the confirmation step) as the representative non-completion
    reset."""
    department = db.get_departments(hospital_id)[0]
    doctor_id = db.get_doctors(hospital_id, department["id"])[0]["id"]
    connector = flows._DEFAULT_CONNECTOR

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id), connector=connector, enabled_features=["booking"])
    slots = db.get_slots(hospital_id, doctor_id)
    date_str = slots[0]["date"]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str), connector=connector, enabled_features=["booking"])
    slot = [s for s in slots if s["date"] == date_str][0]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Priya Shah"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("29"), connector=connector, enabled_features=["booking"])
    # Decline instead of confirming -- NOT a completed booking.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("cancel"), connector=connector, enabled_features=["booking"])

    assert sessions.get(hospital_id, PHONE)["language"] == "en"


@pytest.mark.asyncio
async def test_hindi_reset_keyword_escapes_mid_flow_and_stays_in_hindi(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_DATE", {
        "department_id": "x", "department_name": "X", "doctor_id": "y", "doctor_name": "Dr. Y",
    }, language="hi")

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("मेनू"),
        hospital_name="City Clinic", connector=FakeConnector(), enabled_features=["booking"],
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "list"  # straight back to the Hindi menu, not the language picker again
    assert kwargs["body_text"] == translate("welcome_menu", "hi", hospital_name="City Clinic")
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "IDLE"
    assert session["language"] == "hi"


@pytest.mark.asyncio
async def test_patient_name_matching_a_reset_keyword_accepted_via_the_router(hospital_id):
    """Same live-found bug as core/booking_flow.py's own test, but proven at
    flows.py's router level -- the actual production entry point core/main.py
    calls, which has its own separate reset-keyword short-circuit."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "AWAITING_PATIENT_NAME", {
        "department_name": "Cardiology", "doctor_name": "Dr. Anjali Rao",
        "date_label": "Sat, Aug 8", "slot_date": "2026-08-08", "slot_time": "10:00",
    }, language="en")

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hello"),
        connector=FakeConnector(), enabled_features=["booking"],
    )

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_PATIENT_AGE"  # not bounced to IDLE
    assert session["context"]["patient_name"] == "hello"


# --- Live webhook round-trip: proves core/main.py actually dispatches
# through flows.py's new router for a real (migrated) hospital row ---

def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _webhook_body(phone_number_id: str, from_phone: str, text: str = "hi") -> bytes:
    return json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": phone_number_id},
            "messages": [{"from": from_phone, "type": "text", "text": {"body": text}}],
        }}]}]
    }).encode()


def test_webhook_shows_migrated_booking_hospitals_menu(hospital_id, httpx_mock):
    """hospital_id's seeded row is exactly the flow_type='booking' -> migrated
    case (SPEC Section 14.5) -- proves the live webhook path shows its
    migrated enabled_features menu, not the old hardcoded 4-item one."""
    import core.main as m
    m.SESSIONS.set(hospital_id, "5490001234", "IDLE", {}, language="en")  # language already chosen -- see test_language_picker tests below for that step itself
    httpx_mock.add_response(
        url="https://graph.facebook.com/v22.0/123/messages",
        json={"messages": [{"id": "wamid.1"}]},
    )
    body = _webhook_body("123", "5490001234", "hi")
    resp = client.post("/webhook", content=body, headers={
        "X-Hub-Signature-256": _sign(body, "appsecret"),
        "Content-Type": "application/json",
    })
    assert resp.status_code == 200
    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    sent_body = json.loads(requests[0].content)
    assert "interactive" in sent_body
    row_ids = [row["id"] for section in sent_body["interactive"]["action"]["sections"] for row in section["rows"]]
    assert row_ids == ["menu_book", "menu_reschedule", "menu_cancel", "menu_hospital_info", "menu_change_language"]


def test_webhook_dispatches_faq_only_hospital_to_faq_topics(hospital_id, httpx_mock):
    h = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id, name=h.name, whatsapp_phone_number_id=h.whatsapp_phone_number_id,
        access_token=h.access_token, app_secret=h.app_secret, timezone=h.timezone,
        welcome_message_text=h.welcome_message_text, reminder_offsets_hours=h.reminder_offsets_hours,
        reminder_template_name=h.reminder_template_name, data_tier=h.data_tier,
        external_api_base_url=h.external_api_base_url, external_api_key=h.external_api_key,
        portal_password_hash=h.portal_password_hash, enabled_features=["faq"],
    )
    db.create_faq_topic(hospital_id, "Hours", "We're open Mon-Sat, 9-6.")

    import core.main as m
    m.SESSIONS.set(hospital_id, "5490001234", "IDLE", {}, language="en")  # language already chosen -- see test_language_picker tests below for that step itself

    # First contact: a faq-only tenant's IDLE menu has exactly one option --
    # tapping THAT is what hands the conversation to faq_flow.py, not first
    # contact itself (Section 14.5: faq is one feature among several now, not
    # an exclusive top-level flow_type entered automatically).
    httpx_mock.add_response(
        url="https://graph.facebook.com/v22.0/123/messages",
        json={"messages": [{"id": "wamid.menu"}]},
    )
    first_body = _webhook_body("123", "5490001234", "hi")
    first_resp = client.post("/webhook", content=first_body, headers={
        "X-Hub-Signature-256": _sign(first_body, "appsecret"),
        "Content-Type": "application/json",
    })
    assert first_resp.status_code == 200
    first_sent = json.loads(httpx_mock.get_requests()[-1].content)
    menu_row_ids = [row["id"] for section in first_sent["interactive"]["action"]["sections"] for row in section["rows"]]
    assert menu_row_ids == ["menu_faq_bot", "menu_change_language"]

    httpx_mock.add_response(
        url="https://graph.facebook.com/v22.0/123/messages",
        json={"messages": [{"id": "wamid.faq"}]},
    )
    tap_body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "123"},
            "messages": [{"from": "5490001234", "type": "interactive",
                          "interactive": {"type": "list_reply", "list_reply": {"id": "menu_faq_bot", "title": "FAQ / Information"}}}],
        }}]}]
    }).encode()
    tap_resp = client.post("/webhook", content=tap_body, headers={
        "X-Hub-Signature-256": _sign(tap_body, "appsecret"),
        "Content-Type": "application/json",
    })
    assert tap_resp.status_code == 200
    sent_body = json.loads(httpx_mock.get_requests()[-1].content)
    assert "interactive" in sent_body
    row_ids = [row["id"] for section in sent_body["interactive"]["action"]["sections"] for row in section["rows"]]
    assert row_ids == [str(t["id"]) for t in db.get_faq_topics(hospital_id)]
    assert "menu_book" not in row_ids

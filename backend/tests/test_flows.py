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
import flows.patient_identity as patient_identity
from core.session_store import InMemorySessionStore
from core.translations import t as translate
from core.translations.menu import FEATURE_BOOKING, RECEPTION_HANDOFF_TEXT, WELCOME_MENU
from core.translations.booking import (
    ASK_PATIENT_AGE,
    ASK_PATIENT_GENDER,
    ASK_PATIENT_NAME,
    CONFIRM_BOOKING_SUMMARY,
    SELECT_APPOINTMENT_TYPE,
    SELECT_DEPARTMENT,
    SELECT_DOCTOR,
    SELECT_TIME_SLOT,
)

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")

from main import app  # noqa: E402
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


_DEFAULT_FAKE_PATIENT = {
    "id": 1, "name": "Test Patient", "age": 30, "patient_display_id": "PAT-TEST-0001",
    "relationship_label": "Self",
}


class FakeConnector:
    """Minimal stand-in for connectors.Connector -- only the methods the
    router's one-shot features (booking department listing, view_appointments)
    actually call.

    CareConnect architecture doc alignment (Spec.md Section 0): patients
    defaults to ONE already-linked patient (not empty) -- since patient
    identity is now resolved BEFORE the main menu for every conversation,
    an empty default would mean every single test in this file (most of
    which are about menu/feature-dispatch behavior, not patient identity
    itself) would first hit the registration flow instead of the menu.
    Zero-friction single-patient auto-continue (Section 11's default, no
    confirmation) means a session starts fully resolved with no extra
    round-trip either way -- pass patients=[] explicitly for a test that
    genuinely wants the 0-linked-patients registration path, or a custom
    list for multi-patient scenarios."""
    def __init__(self, departments=None, appointments=None, patient_info=None, patients=None):
        self._departments = departments or []
        self._appointments = appointments or []
        # Patient identity/UX follow-up (Spec.md Section 0): _start_booking_flow
        # calls this before showing anything -- None (the default) means a
        # first-time patient, asked for name/age before department selection.
        self._patient_info = patient_info
        self._patients = [dict(_DEFAULT_FAKE_PATIENT)] if patients is None else patients
        self._consent = {}

    def identify_contact(self, provider_user_id, phone_number=None, username=None):
        return {"id": 1, "provider_user_id": provider_user_id, "phone_number": phone_number, "username": username}

    def get_max_active_patient_links(self):
        return 5

    def get_appointment_types(self, hospital_id):
        return [{"id": "new", "label": "New Consultation", "requires_consent": False, "requires_doctor_selection": True}]

    def get_departments(self, hospital_id):
        return self._departments

    def get_upcoming_appointments(self, hospital_id, phone=None, offset_hours=None, now=None):
        return self._appointments

    def get_appointments_in_range(self, hospital_id, care_connect_account_id, range_start, range_end, statuses=None):
        return self._appointments

    def get_patient_info(self, hospital_id, phone):
        return self._patient_info

    def list_active_patients(self, hospital_id, phone):
        return self._patients

    def create_patient_profile(self, hospital_id, phone, name, age, relationship_label=None, gender=None, contact_phone=None):
        next_id = (max((p["id"] for p in self._patients), default=0)) + 1
        patient = {
            "id": next_id, "name": name, "age": age, "gender": gender, "relationship_label": relationship_label,
            "patient_display_id": f"PAT-TEST-{next_id:04d}", "contact_phone": contact_phone or phone,
        }
        self._patients.append(patient)
        return patient

    def has_self_linked_patient(self, hospital_id, care_connect_account_id):
        return any(p.get("relationship_label") == "Self" for p in self._patients)

    def find_potential_duplicate_patient(self, hospital_id, name, contact_phone):
        return None

    def link_existing_patient(self, hospital_id, phone, patient_id, relationship_label=None):
        patient = {"id": patient_id, "name": "Linked Patient", "age": None, "patient_display_id": f"PAT-TEST-{patient_id:04d}", "relationship_label": relationship_label}
        self._patients.append(patient)
        return patient

    def unlink_patient(self, hospital_id, phone, patient_id):
        before = len(self._patients)
        self._patients = [p for p in self._patients if p["id"] != patient_id]
        return len(self._patients) < before

    def validate_active_patient_link(self, hospital_id, phone, patient_id):
        return any(p["id"] == patient_id for p in self._patients)

    def get_patient_link_consent(self, hospital_id, phone, patient_id):
        if not any(p["id"] == patient_id for p in self._patients):
            return None
        return self._consent.get(patient_id, {"service_consent": True, "marketing_consent": False})

    def set_marketing_consent(self, hospital_id, phone, patient_id, consented):
        if not any(p["id"] == patient_id for p in self._patients):
            return False
        current = self._consent.get(patient_id, {"service_consent": True, "marketing_consent": False})
        self._consent[patient_id] = {**current, "marketing_consent": consented}
        return True


def text_reply(text):
    return {"type": "text", "text": text}


def tap(option_id, title=""):
    return {"type": "interactive_reply", "id": option_id, "title": title}


def _row_ids(kind_kwargs):
    return [row["id"] for section in kind_kwargs["sections"] for row in section["rows"]]


def _last_list(wa):
    """UX follow-up (Spec.md Section 0): "Back" moved out of the list itself
    into its own follow-up buttons message sent right after -- this finds
    the list itself regardless of a trailing Back-button message."""
    for kind, kwargs in reversed(wa.sent):
        if kind == "list":
            return kwargs
    raise AssertionError("no list message was sent")


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

    assert len(wa.sent) == 2
    kind, kwargs = wa.sent[0]
    assert kind == "list"
    assert _row_ids(kwargs) == ["menu_book", "menu_faq_bot"]
    assert wa.sent[1][0] == "buttons"  # the follow-up "Back" (Manage Patients)


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
    assert ids == ["menu_book"]


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

    # CareConnect architecture doc alignment (Spec.md Section 0): patient
    # identity is now resolved before the FIRST menu is ever shown, not
    # lazily when "Book Appointment" is tapped -- FakeConnector's single
    # default linked patient auto-continues with zero friction, so the
    # very first message already lands on the resolved menu.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=enabled)
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"

    # Tap "Book Appointment" -> enters booking_flow's own state machine --
    # straight to appointment type selection (then department), since
    # name/age/relationship are already resolved.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=enabled)
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_APPOINTMENT_TYPE"
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"), connector=connector, enabled_features=enabled)
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"
    kwargs = _last_list(wa)
    assert {d["id"] for d in departments} == set(_row_ids(kwargs))
    # "Go back" navigation is its own follow-up buttons message now (Spec.md
    # Section 0's UX follow-up), not a row inside the department list.
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"nav_back"}
    assert sessions.get(hospital_id, PHONE)["state"] != "IDLE"

    # A reset keyword mid-booking returns to the TOP-level unified menu (not
    # booking_flow's own idea of "start over") -- new, deliberate Section
    # 14.5 behavior.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=enabled)
    kwargs = _last_list(wa)
    assert _row_ids(kwargs) == ["menu_book", "menu_faq_bot"]

    # Now tap "FAQ / Information" -> enters faq_flow's topic loop.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_faq_bot"), connector=connector, enabled_features=enabled)
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == [str(t["id"]) for t in db.get_faq_topics(hospital_id)] + ["goto_main_menu"]
    import flows.faq as faq_flow
    assert sessions.get(hospital_id, PHONE)["state"] == faq_flow.STATE_FAQ_ACTIVE

    # A reset keyword mid-FAQ ALSO returns to the top-level unified menu, not
    # just faq_flow's own topic list.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("restart"), connector=connector, enabled_features=enabled)
    kwargs = _last_list(wa)
    assert _row_ids(kwargs) == ["menu_book", "menu_faq_bot"]


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

    kwargs = _last_list(wa)
    assert _row_ids(kwargs) == ["menu_book"]
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

    connector = FakeConnector(appointments=[appt])
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_view_appointments"),
        connector=connector, enabled_features=["view_appointments"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_VIEW_APPOINTMENTS_RANGE"
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("view_appointments_range_upcoming"),
        connector=connector, enabled_features=["view_appointments"],
    )

    kwargs = _last_list(wa)
    row = kwargs["sections"][0]["rows"][0]
    assert row["id"] == "appt_501"
    assert "Dr. Rao" in row["title"]
    # A generic (not appointment-scoped) Main Menu/Cancel/Reschedule
    # follow-up menu is sent right after the list -- see _send_post_action_menu.
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"goto_main_menu", "menu_cancel", "menu_reschedule"}
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_VIEW_APPOINTMENT_ACTION"


@pytest.mark.asyncio
async def test_view_appointments_no_upcoming_sends_plain_text(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    connector = FakeConnector(appointments=[])
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_view_appointments"),
        connector=connector, enabled_features=["view_appointments"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("view_appointments_range_upcoming"),
        connector=connector, enabled_features=["view_appointments"],
    )

    assert wa.sent[-2][0] == "text"
    # A generic (not appointment-scoped) Main Menu/Cancel/Reschedule
    # follow-up menu is sent right after -- see _send_post_action_menu.
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert {b["id"] for b in kwargs["buttons"]} == {"goto_main_menu", "menu_cancel", "menu_reschedule"}
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
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("view_appointments_range_upcoming"),
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

    assert wa.sent[-1] == ("text", {"to": PHONE, "text": translate(RECEPTION_HANDOFF_TEXT, "en")})
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
    # routing and showed the unified menu, not silence. Two sends: the menu
    # list, then its own follow-up "Back" (Manage Patients) buttons message.
    assert len(wa.sent) == sent_before + 2
    kwargs = _last_list(wa)
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
    from datetime import datetime, timedelta, timezone

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reception"),
        connector=FakeConnector(), enabled_features=["reception_handoff"],
    )
    handoff = db.get_handoff_requests(hospital_id, status="open")[0]

    # Never resolved by staff -- just goes stale with time.
    conn = db.get_connection()
    stale_at = datetime.now(timezone.utc) - timedelta(minutes=90)
    conn.execute(
        "UPDATE handoff_requests SET created_at = ? WHERE id = ?",
        (stale_at.strftime("%Y-%m-%d %H:%M:%S"), handoff["id"]),
    )
    conn.commit()

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        connector=FakeConnector(), enabled_features=["reception_handoff", "booking"],
    )

    kwargs = _last_list(wa)
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert "menu_book" in row_ids

    # Still genuinely 'open' in the DB -- staff can still resolve it later,
    # this only stopped it from silencing the bot.
    assert db.get_handoff_requests(hospital_id, status="open")[0]["id"] == handoff["id"]


@pytest.mark.asyncio
async def test_change_language_is_never_shown_on_the_main_menu(hospital_id):
    """UX follow-up (Spec.md Section 0), per the user's explicit request:
    "Change Language" removed from the main menu entirely -- CHANGE_LANGUAGE_ROW
    is never appended anymore, regardless of language_prompt_enabled. The row
    id/handler are left in the code (harmless, unreachable from a fresh
    menu) but this proves the row itself is gone, in both the
    picker-enabled (the old default) and picker-disabled cases."""
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hello there"),
        connector=FakeConnector(), enabled_features=["booking"],
    )
    kind, kwargs = wa.sent[0]
    row_ids = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert flows.CHANGE_LANGUAGE_ROW not in row_ids

    wa2 = FakeWhatsAppClient()
    sessions2 = _sessions_with_english_chosen(hospital_id)
    await flows.handle_incoming(
        wa2, sessions2, PHONE, hospital_id, text_reply("hi"),
        connector=FakeConnector(), enabled_features=["booking"], language_prompt_enabled=False,
    )
    kind, kwargs = wa2.sent[0]
    row_ids2 = {row["id"] for section in kwargs["sections"] for row in section["rows"]}
    assert flows.CHANGE_LANGUAGE_ROW not in row_ids2


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

    kwargs = _last_list(wa)
    # CareConnect architecture doc alignment (Spec.md Section 0): the main
    # menu now leads with a "Patient: X / MRN: Y" header (Section 20) --
    # endswith() rather than == since this test is about the LANGUAGE the
    # welcome text renders in, not the header's own content.
    assert kwargs["body_text"].endswith(translate(WELCOME_MENU, "en", hospital_name="City Clinic"))
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

    kwargs = _last_list(wa)
    assert kwargs["body_text"].endswith(translate(WELCOME_MENU, "hi", hospital_name="City Clinic"))
    row = kwargs["sections"][0]["rows"][0]
    assert row["title"] == translate(FEATURE_BOOKING, "hi")
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
    stays in effect through every booking_flow.py state -- name+age
    collection, department, doctor, date, time, confirmation -- not just the
    top-level menu flows.py itself renders. Patient identity/UX follow-up
    (Spec.md Section 0), confirmed with the user: name/age is now collected
    FIRST, before department -- this test follows the current sequence."""
    department = db.get_departments(hospital_id)[0]
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    connector = flows._DEFAULT_CONNECTOR

    # CareConnect architecture doc alignment (Spec.md Section 0): a
    # genuinely fresh phone (0 linked patients) is now resolved BEFORE the
    # main menu is ever shown -- name/age/gender registration happens right
    # after language selection, not after tapping "Book Appointment".
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("lang_hi"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_BOOKING_FOR
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.BOOKING_FOR_SELF_ID), connector=connector, enabled_features=["booking"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_NAME
    kind, kwargs = wa.sent[-1]
    assert kwargs["text"] == translate(ASK_PATIENT_NAME, "hi")

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Ravi Kumar"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_AGE
    kind, kwargs = wa.sent[-1]
    assert kwargs["text"] == translate(ASK_PATIENT_AGE, "hi", patient_name="Ravi Kumar")

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("34"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_GENDER
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert kwargs["body_text"] == translate(ASK_PATIENT_GENDER, "hi")

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.GENDER_OTHER_ID), connector=connector, enabled_features=["booking"],
    )
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "IDLE"
    assert session["language"] == "hi"
    kwargs = _last_list(wa)
    assert kwargs["body_text"].endswith(translate(WELCOME_MENU, "hi", hospital_name="the hospital"))

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_APPOINTMENT_TYPE"
    kwargs = _last_list(wa)
    assert kwargs["body_text"] == translate(SELECT_APPOINTMENT_TYPE, "hi")

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"
    kwargs = _last_list(wa)
    assert kwargs["body_text"] == translate(SELECT_DEPARTMENT, "hi")

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    kwargs = _last_list(wa)
    assert kwargs["body_text"] == translate(SELECT_DOCTOR, "hi", department_name=department["name"])

    doctor = db.get_doctors(hospital_id, department["id"])[0]
    doctor_id = doctor["id"]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id), connector=connector, enabled_features=["booking"])
    kwargs = _last_list(wa)
    # doctor_name is hospital-entered content, never translated (already
    # includes "Dr." in English regardless of session language) -- only the
    # surrounding prompt text is Hindi.
    assert doctor["name"] in kwargs["body_text"] and "तारीख" in kwargs["body_text"]
    all_slots = db.get_slots(hospital_id, doctor_id)
    date_str = all_slots[0]["date"]

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str), connector=connector, enabled_features=["booking"])
    kwargs = _last_list(wa)
    assert kwargs["body_text"] == translate(SELECT_TIME_SLOT, "hi")

    # Picking a time now goes straight to confirmation -- name/age were
    # already collected up front.
    slot = [s for s in all_slots if s["date"] == date_str][0]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]), connector=connector, enabled_features=["booking"])
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_CONFIRMATION"
    assert session["language"] == "hi"
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert kwargs["body_text"] == translate(CONFIRM_BOOKING_SUMMARY, "hi",
        appointment_type_label=session["context"]["appointment_type_label"],
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
    # Item 8 (Spec.md Section 0): reference_id format is now APT-<DDMMYY>-<NNN>.
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
async def test_a_patients_row_without_a_linked_patient_still_asks_for_name(hospital_id):
    """Patient identity SEPARATION (Spec.md Section 0), superseding the
    earlier "ask name every time" round: _start_booking_flow now checks
    connector.list_active_patients() (patient_links), not a bare `patients`
    row -- a phone with a `patients` row created via the legacy
    _upsert_patient() path (the staff portal's own upsert-by-phone
    semantics, never creates a patient_links row) still has ZERO active
    linked patients, so it's asked for a name exactly like a genuinely
    first-time phone. This is the correct behavior, not a regression: a
    staff-created record isn't automatically "this WhatsApp number's own
    profile" without an explicit link."""
    connector = flows._DEFAULT_CONNECTOR
    import db.connection as db_connection
    from db.repository import _upsert_patient
    _upsert_patient(db_connection.get_connection(), hospital_id, PHONE, "Priya Shah", 29)
    db_connection.get_connection().commit()

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_english_chosen(hospital_id)

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])

    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_PATIENT_NAME"
    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "full name" in kwargs["text"].lower()


@pytest.mark.asyncio
async def test_a_linked_patient_is_remembered_across_a_genuinely_new_session_object(hospital_id):
    """Patient identity SEPARATION (Spec.md Section 0): "once per profile,
    then just select" -- superseding the earlier "ask name every time"
    round, confirmed with the user as the intended behavior now that real
    patient_links profiles exist. A phone with exactly one active linked
    patient auto-selects it with zero added friction, even across a brand
    new InMemorySessionStore() instance (a genuinely new day/new session,
    same phone) -- not just a within-one-session-object quirk."""
    department = db.get_departments(hospital_id)[0]
    doctor_id = db.get_doctors(hospital_id, department["id"])[0]["id"]
    connector = flows._DEFAULT_CONNECTOR

    # Session #1: a full booking from scratch, collecting name/age (creates
    # the patient's one profile via create_patient_profile()).
    wa1 = FakeWhatsAppClient()
    sessions1 = _sessions_with_english_chosen(hospital_id)
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    assert sessions1.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_NAME"
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, text_reply("Priya Shah"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, text_reply("29"), connector=connector, enabled_features=["booking"])
    assert sessions1.get(hospital_id, PHONE)["state"] == "AWAITING_APPOINTMENT_TYPE"
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap("new"), connector=connector, enabled_features=["booking"])
    assert sessions1.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap(doctor_id), connector=connector, enabled_features=["booking"])
    slots = db.get_slots(hospital_id, doctor_id)
    date_str = slots[0]["date"]
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap(date_str), connector=connector, enabled_features=["booking"])
    slot = [s for s in slots if s["date"] == date_str][0]
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap(slot["id"]), connector=connector, enabled_features=["booking"])
    assert sessions1.get(hospital_id, PHONE)["state"] == "AWAITING_CONFIRMATION"
    await flows.handle_incoming(wa1, sessions1, PHONE, hospital_id, tap("confirm"), connector=connector, enabled_features=["booking"])
    assert wa1.sent[-1][0] == "buttons"  # booking success

    # Session #2: an entirely new session store (nothing shared with
    # sessions1's in-memory state), same phone -- the one linked patient
    # from session #1 is auto-selected, straight to department selection,
    # no name/age re-asked.
    wa2 = FakeWhatsAppClient()
    sessions2 = _sessions_with_english_chosen(hospital_id)
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    session2 = sessions2.get(hospital_id, PHONE)
    assert session2["state"] == "AWAITING_APPOINTMENT_TYPE"
    assert session2["context"]["patient_name"] == "Priya Shah"
    assert session2["context"]["patient_age"] == 29
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap("new"), connector=connector, enabled_features=["booking"])
    assert sessions2.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"
    kind, kwargs = wa2.sent[-1]
    assert kind == "buttons"  # the department list's own follow-up Back button


@pytest.mark.asyncio
async def test_language_resets_to_picker_after_a_completed_booking(hospital_id):
    """Language-reset follow-up (Spec.md Section 0). Before this fix,
    core/session_store.py's reset() (called after EVERY completed action --
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
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Priya Shah"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("29"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id), connector=connector, enabled_features=["booking"])
    slots = db.get_slots(hospital_id, doctor_id)
    date_str = slots[0]["date"]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str), connector=connector, enabled_features=["booking"])
    slot = [s for s in slots if s["date"] == date_str][0]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]), connector=connector, enabled_features=["booking"])
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
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Priya Shah"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("29"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id), connector=connector, enabled_features=["booking"])
    slots = db.get_slots(hospital_id, doctor_id)
    date_str = slots[0]["date"]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str), connector=connector, enabled_features=["booking"])
    slot = [s for s in slots if s["date"] == date_str][0]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]), connector=connector, enabled_features=["booking"])
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

    kwargs = _last_list(wa)  # straight back to the Hindi menu, not the language picker again
    assert kwargs["body_text"].endswith(translate(WELCOME_MENU, "hi", hospital_name="City Clinic"))
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
    # Patient identity/UX follow-up (Spec.md Section 0): AWAITING_PATIENT_NAME
    # is now the very first interactive state (before department), so its
    # context is empty at this point in real usage.
    sessions.set(hospital_id, PHONE, "AWAITING_PATIENT_NAME", {}, language="en")

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
    # CareConnect architecture doc alignment (Spec.md Section 0): patient
    # identity is resolved before the main menu -- seed one linked patient
    # for this phone so first contact lands directly on the menu (the
    # zero-friction default), matching this test's own actual point.
    db.create_patient_profile(hospital_id, "5490001234", "Test Patient", 30, relationship_label="Self")
    import webhook.dispatch as m
    m.SESSIONS.set(hospital_id, "5490001234", "IDLE", {}, language="en")  # language already chosen -- see test_language_picker tests below for that step itself
    # Two outbound sends: the main menu list, then its own follow-up "Back"
    # (Manage Patients) buttons message.
    httpx_mock.add_response(
        url="https://graph.facebook.com/v22.0/123/messages",
        json={"messages": [{"id": "wamid.1"}]},
    )
    httpx_mock.add_response(
        url="https://graph.facebook.com/v22.0/123/messages",
        json={"messages": [{"id": "wamid.1b"}]},
    )
    body = _webhook_body("123", "5490001234", "hi")
    resp = client.post("/webhook", content=body, headers={
        "X-Hub-Signature-256": _sign(body, "appsecret"),
        "Content-Type": "application/json",
    })
    assert resp.status_code == 200
    requests = httpx_mock.get_requests()
    assert len(requests) == 2
    sent_body = json.loads(requests[0].content)
    assert "interactive" in sent_body
    row_ids = [row["id"] for section in sent_body["interactive"]["action"]["sections"] for row in section["rows"]]
    assert row_ids == ["menu_book", "menu_reschedule", "menu_cancel", "menu_hospital_info"]


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
    # CareConnect architecture doc alignment (Spec.md Section 0): see the
    # sibling test above for why this is seeded.
    db.create_patient_profile(hospital_id, "5490001234", "Test Patient", 30, relationship_label="Self")

    import webhook.dispatch as m
    m.SESSIONS.set(hospital_id, "5490001234", "IDLE", {}, language="en")  # language already chosen -- see test_language_picker tests below for that step itself

    # First contact: a faq-only tenant's IDLE menu has exactly one option --
    # tapping THAT is what hands the conversation to faq_flow.py, not first
    # contact itself (Section 14.5: faq is one feature among several now, not
    # an exclusive top-level flow_type entered automatically).
    # Two outbound sends: the main menu list, then its own follow-up "Back"
    # (Manage Patients) buttons message.
    httpx_mock.add_response(
        url="https://graph.facebook.com/v22.0/123/messages",
        json={"messages": [{"id": "wamid.menu"}]},
    )
    httpx_mock.add_response(
        url="https://graph.facebook.com/v22.0/123/messages",
        json={"messages": [{"id": "wamid.menu_back"}]},
    )
    first_body = _webhook_body("123", "5490001234", "hi")
    first_resp = client.post("/webhook", content=first_body, headers={
        "X-Hub-Signature-256": _sign(first_body, "appsecret"),
        "Content-Type": "application/json",
    })
    assert first_resp.status_code == 200
    first_sent = json.loads(httpx_mock.get_requests()[0].content)
    menu_row_ids = [row["id"] for section in first_sent["interactive"]["action"]["sections"] for row in section["rows"]]
    assert menu_row_ids == ["menu_faq_bot"]

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
    assert row_ids == [str(t["id"]) for t in db.get_faq_topics(hospital_id)] + ["goto_main_menu"]
    assert "menu_book" not in row_ids

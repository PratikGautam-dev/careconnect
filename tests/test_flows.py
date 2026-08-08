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
        self.sent = []  # list of ("text"|"list", kwargs)

    async def send_text(self, to, text):
        self.sent.append(("text", {"to": to, "text": text}))

    async def send_list(self, to, body_text, button_text, sections, header_text=None, footer_text=None):
        self.sent.append(("list", {"to": to, "body_text": body_text, "sections": sections}))


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


@pytest.mark.asyncio
async def test_menu_only_shows_enabled_features(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Clinic", connector=FakeConnector(),
        enabled_features=["booking", "faq"],
    )

    assert len(wa.sent) == 1
    kind, kwargs = wa.sent[0]
    assert kind == "list"
    assert _row_ids(kwargs) == ["menu_book", "menu_faq_bot"]


@pytest.mark.asyncio
async def test_unselected_features_dont_appear_in_menu(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

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
    sessions = InMemorySessionStore()

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
    sessions = InMemorySessionStore()
    connector = FakeConnector(departments=departments)
    enabled = ["booking", "faq"]

    # Tap "Book Appointment" -> enters booking_flow's own state machine.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=enabled)
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert {d["id"] for d in departments} == set(_row_ids(kwargs))
    assert sessions.get(hospital_id, PHONE)["state"] != "IDLE"

    # A reset keyword mid-booking returns to the TOP-level unified menu (not
    # booking_flow's own idea of "start over") -- new, deliberate Section
    # 14.5 behavior.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=enabled)
    kind, kwargs = wa.sent[-1]
    assert _row_ids(kwargs) == ["menu_book", "menu_faq_bot"]

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
    assert _row_ids(kwargs) == ["menu_book", "menu_faq_bot"]


@pytest.mark.asyncio
async def test_tap_for_disabled_feature_falls_back_to_menu(hospital_id):
    """A stale tap (e.g. from a menu sent before the hospital disabled a
    feature) for something not currently enabled must not start that
    feature -- it just re-shows the current menu."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_faq_bot"),
        connector=FakeConnector(), enabled_features=["booking"],
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == ["menu_book"]
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_view_appointments_feature(hospital_id):
    from datetime import datetime
    from types import SimpleNamespace

    appt = SimpleNamespace(
        doctor_name="Dr. Rao", department_name="Cardiology", scheduled_at=datetime(2026, 9, 1, 10, 0),
    )
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_view_appointments"),
        connector=FakeConnector(appointments=[appt]), enabled_features=["view_appointments"],
    )

    assert wa.sent[-1][0] == "text"
    assert "Dr. Rao" in wa.sent[-1][1]["text"]
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_hospital_info_feature_sends_static_text(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

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
    sessions = InMemorySessionStore()

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reception"),
        connector=FakeConnector(), enabled_features=["reception_handoff"],
    )

    assert wa.sent[-1] == ("text", {"to": PHONE, "text": flows._RECEPTION_HANDOFF_TEXT})
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"

    open_handoffs = db.get_handoff_requests(hospital_id, status="open")
    assert any(h["phone"] == PHONE and h["reason"] == "patient_requested" for h in open_handoffs)


def test_real_features_are_all_features():
    assert flows.REAL_FEATURES == flows.ALL_FEATURES
    assert "reception_handoff" in flows.REAL_FEATURES
    assert "payment_link" not in flows.ALL_FEATURES
    assert "reports" not in flows.ALL_FEATURES


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
    assert row_ids == [str(t["id"]) for t in db.get_faq_topics(hospital_id)]
    assert "menu_book" not in row_ids

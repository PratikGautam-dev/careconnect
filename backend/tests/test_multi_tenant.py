# tests/test_multi_tenant.py
"""
SPEC Section 12.2 / Phase 9: multi-tenant routing isolation.

hospital_id/second_hospital_id fixtures come from tests/conftest.py — every
test here gets a fresh DB with both the one "real" hospital (whatsapp_phone_number_id
"123" by default) and a second, entirely fake one (whatsapp_phone_number_id
"TEST_HOSPITAL_2_PHONE_ID") already seeded with distinct departments/doctors.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta

import pytest

import db.repository as db
from flows.booking import handle_incoming
from core.session_store import InMemorySessionStore

# Same defensive env-var setup as tests/test_main.py — core.main is only
# actually imported (and its module-level os.environ[...] reads executed)
# the first time any test file does so, so this must be safe regardless of
# which test module pytest happens to collect/import first.
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")
# DATABASE_URL is already pointed at the test Postgres instance by
# tests/conftest.py (loaded before this module).

from main import app  # noqa: E402  (must follow the env var setdefaults above)
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

PHONE = "5491112345678"  # deliberately the SAME phone used against both hospitals below


class FakeWhatsAppClient:
    def __init__(self):
        self.sent = []

    async def send_text(self, to, text):
        self.sent.append(("text", {"to": to, "text": text}))

    async def send_list(self, to, body_text, button_text, sections, header_text=None, footer_text=None):
        self.sent.append(("list", {"to": to, "body_text": body_text, "sections": sections}))

    async def send_buttons(self, to, body_text, buttons, header_text=None, footer_text=None):
        self.sent.append(("buttons", {"to": to, "body_text": body_text, "buttons": buttons}))


def tap(option_id, title=""):
    return {"type": "interactive_reply", "id": option_id, "title": title}


def text_reply(text):
    return {"type": "text", "text": text}


def _row_ids(kind_kwargs):
    return {row["id"] for section in kind_kwargs["sections"] for row in section["rows"]}


def _last_list(wa):
    """UX follow-up (Spec.md Section 0): "Back" moved out of the list itself
    into its own follow-up buttons message sent right after -- this finds
    the list itself regardless of a trailing Back-button message."""
    for kind, kwargs in reversed(wa.sent):
        if kind == "list":
            return kwargs
    raise AssertionError("no list message was sent")


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(b"appsecret", body, hashlib.sha256).hexdigest()


# --- Departments never leak across hospitals ---

@pytest.mark.asyncio
async def test_department_menu_isolated_between_hospitals(hospital_id, second_hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    # Patient identity/UX follow-up (Spec.md Section 0): name/age is asked
    # first now -- drive through it to reach the department list.
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Ravi Kumar"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("34"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"))
    hospital_a_depts = _row_ids(_last_list(wa))

    wa2 = FakeWhatsAppClient()
    sessions2 = InMemorySessionStore()
    await handle_incoming(wa2, sessions2, PHONE, second_hospital_id, tap("menu_book"))
    await handle_incoming(wa2, sessions2, PHONE, second_hospital_id, text_reply("Ravi Kumar"))
    await handle_incoming(wa2, sessions2, PHONE, second_hospital_id, text_reply("34"))
    await handle_incoming(wa2, sessions2, PHONE, second_hospital_id, tap("new"))
    hospital_b_depts = _row_ids(_last_list(wa2))

    assert hospital_a_depts == {"cardiology", "orthopedics", "general_medicine", "pediatrics"}
    assert hospital_b_depts == {"t2_neurology", "t2_dermatology"}
    assert hospital_a_depts.isdisjoint(hospital_b_depts)


@pytest.mark.asyncio
async def test_hospital_a_department_id_rejected_when_tapped_against_hospital_b(hospital_id, second_hospital_id):
    """Even if a patient's client somehow replayed hospital A's department row id
    against hospital B's conversation, it must not resolve — find_department()
    is scoped by hospital_id, not just id."""
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(second_hospital_id, PHONE, "AWAITING_DEPARTMENT", {})

    await handle_incoming(wa, sessions, PHONE, second_hospital_id, tap("cardiology"))  # hospital A's department id

    # Treated as an invalid/unrecognized tap -> re-prompt with the real
    # department list directly (item 8), not accepted.
    assert wa.sent[0][0] == "list"
    assert sessions.get(second_hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"


# --- Appointments never leak across hospitals' cancel/reschedule lists ---

@pytest.mark.asyncio
async def test_appointment_never_appears_in_other_hospitals_cancel_list(hospital_id, second_hospital_id):
    # Hospital A has an appointment for PHONE...
    db.create_appointment(hospital_id, PHONE, "cardiology", "doc_card_1", datetime.now() + timedelta(hours=24))

    # ...but the SAME phone number messaging hospital B sees no appointments to cancel.
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await handle_incoming(wa, sessions, PHONE, second_hospital_id, tap("menu_cancel"))

    # Item 9: the "nothing to cancel" message is now followed by the main menu.
    assert wa.sent[0] == ("text", {"to": PHONE, "text": "You don't have any upcoming appointments to cancel."})
    assert wa.sent[1][0] == "list"

    # Meanwhile hospital A's own cancel flow still sees it correctly.
    wa_a = FakeWhatsAppClient()
    sessions_a = InMemorySessionStore()
    await handle_incoming(wa_a, sessions_a, PHONE, hospital_id, tap("menu_cancel"))
    assert wa_a.sent[-1][0] == "list"


@pytest.mark.asyncio
async def test_appointment_never_appears_in_other_hospitals_reschedule_list(hospital_id, second_hospital_id):
    db.create_appointment(hospital_id, PHONE, "cardiology", "doc_card_1", datetime.now() + timedelta(hours=24))

    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    await handle_incoming(wa, sessions, PHONE, second_hospital_id, tap("menu_reschedule"))

    # Item 9: the "nothing to reschedule" message is now followed by the main menu.
    assert wa.sent[0] == ("text", {"to": PHONE, "text": "You don't have any upcoming appointments to reschedule."})
    assert wa.sent[1][0] == "list"


@pytest.mark.asyncio
async def test_appointment_id_from_hospital_a_rejected_if_replayed_against_hospital_b(hospital_id, second_hospital_id):
    """Same defense-in-depth check as the department test above, for the
    appt_<id> row ids used by the cancel/reschedule selection menus."""
    appt = db.create_appointment(hospital_id, PHONE, "cardiology", "doc_card_1", datetime.now() + timedelta(hours=24))

    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(second_hospital_id, PHONE, "AWAITING_CANCEL_SELECTION", {})

    await handle_incoming(wa, sessions, PHONE, second_hospital_id, tap(f"appt_{appt.id}"))

    # Hospital B has no appointments at all, so this looks exactly like "went
    # stale"/nothing to cancel -- either way, hospital A's appointment must not
    # get cancelled by a hospital-B conversation.
    assert db.get_appointment(hospital_id, appt.id).status == db.STATUS_BOOKED


# --- Conversation/session state never leaks across hospitals ---

@pytest.mark.asyncio
async def test_same_phone_has_independent_conversation_state_per_hospital():
    """SPEC Section 12.2: the session store is keyed by (hospital_id, phone) —
    the same patient mid-booking at hospital A must not resume that flow when
    messaging hospital B."""
    from core.session_store import InMemorySessionStore as Store
    sessions = Store()  # a single shared store, as core/main.py's SESSIONS actually is

    wa_a = FakeWhatsAppClient()
    await handle_incoming(wa_a, sessions, PHONE, 1, tap("menu_book"))
    # Patient identity/UX follow-up (Spec.md Section 0): name/age is asked
    # first now, before department selection.
    assert sessions.get(1, PHONE)["state"] == "AWAITING_PATIENT_NAME"

    # Hospital 2's conversation for the same phone starts completely fresh.
    wa_b = FakeWhatsAppClient()
    await handle_incoming(wa_b, sessions, PHONE, 2, text_reply("hi"))
    assert sessions.get(2, PHONE)["state"] == "IDLE"
    assert wa_b.sent[-1][0] == "list"  # got the main menu, not treated as an AWAITING_PATIENT_NAME reply

    # And hospital 1's state is untouched by hospital 2's conversation.
    assert sessions.get(1, PHONE)["state"] == "AWAITING_PATIENT_NAME"


# --- Unrecognized phone_number_id ---

def test_unrecognized_phone_number_id_ignored_without_crashing(httpx_mock):
    """A webhook for a phone_number_id that doesn't match any hospital in the
    database must be safely ignored: 200 OK, no processing, no outbound send —
    not a crash, not a silent default-hospital assumption."""
    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "SOME_UNKNOWN_NUMBER_NOBODY_OWNS"},
            "messages": [{"from": "919999999999", "type": "text", "text": {"body": "hi"}}],
        }}]}]
    }).encode()
    resp = client.post("/webhook", content=body,
                        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"})

    assert resp.status_code == 200
    assert len(httpx_mock.get_requests()) == 0  # nothing was ever sent


def test_recognized_phone_number_id_is_processed_normally(httpx_mock):
    """Sanity complement to the above: a *known* phone_number_id must still work,
    proving the unrecognized case isn't just "nothing ever gets processed"."""
    httpx_mock.add_response(url="https://graph.facebook.com/v22.0/123/messages", json={"messages": [{"id": "wamid.x"}]})
    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "123"},
            "messages": [{"from": "919999999995", "type": "text", "text": {"body": "hi"}}],
        }}]}]
    }).encode()
    resp = client.post("/webhook", content=body,
                        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"})

    assert resp.status_code == 200
    assert len(httpx_mock.get_requests()) == 1


def test_deactivated_hospital_phone_number_id_treated_as_unrecognized(hospital_id):
    """is_active=0 must be treated the same as "no such hospital" — not routed to."""
    import db.connection as db_connection
    conn = db_connection.get_connection()
    conn.execute("UPDATE hospitals SET is_active = 0 WHERE id = ?", (hospital_id,))
    conn.commit()

    assert db.find_hospital_by_phone_number_id("123") is None


# --- Per-hospital webhook signature validation ---

def _set_app_secret(hospital_id: int, secret: str) -> None:
    import db.connection as db_connection
    conn = db_connection.get_connection()
    conn.execute("UPDATE hospitals SET app_secret_ref = ? WHERE id = ?", (secret, hospital_id))
    conn.commit()


def test_hospital_a_secret_cannot_validate_a_payload_claiming_to_be_hospital_b(hospital_id, second_hospital_id, httpx_mock):
    """Each hospital has its own app_secret (SPEC Section 4/12.2). A payload
    claiming to be for hospital B's phone_number_id but signed with hospital
    A's secret must be rejected, even though both hospitals share this one
    webhook endpoint."""
    _set_app_secret(second_hospital_id, "hospital-b-real-secret")

    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "TEST_HOSPITAL_2_PHONE_ID"},  # claims to be hospital B
            "messages": [{"from": "919999999994", "type": "text", "text": {"body": "hi"}}],
        }}]}]
    }).encode()
    forged_sig = _sign(body)  # _sign() = hospital A's real secret ("appsecret"), not hospital B's

    resp = client.post("/webhook", content=body,
                        headers={"X-Hub-Signature-256": forged_sig, "Content-Type": "application/json"})

    assert resp.status_code == 403
    assert len(httpx_mock.get_requests()) == 0  # never got far enough to process/send anything


def test_hospital_b_own_secret_correctly_validates_its_own_payload(hospital_id, second_hospital_id, httpx_mock):
    """Sanity complement to the test above: hospital B's OWN secret correctly
    signs and passes for hospital B's own phone_number_id — proves this is
    genuine per-hospital validation, not "everything for hospital B fails"."""
    _set_app_secret(second_hospital_id, "hospital-b-real-secret")
    httpx_mock.add_response(url="https://graph.facebook.com/v22.0/TEST_HOSPITAL_2_PHONE_ID/messages", json={"messages": [{"id": "x"}]})

    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "TEST_HOSPITAL_2_PHONE_ID"},
            "messages": [{"from": "919999999993", "type": "text", "text": {"body": "hi"}}],
        }}]}]
    }).encode()
    real_sig = "sha256=" + hmac.new(b"hospital-b-real-secret", body, hashlib.sha256).hexdigest()

    resp = client.post("/webhook", content=body,
                        headers={"X-Hub-Signature-256": real_sig, "Content-Type": "application/json"})

    assert resp.status_code == 200
    assert len(httpx_mock.get_requests()) == 1


def test_hospital_with_no_app_secret_configured_rejects_all_signatures(second_hospital_id):
    """A hospital that hasn't had app_secret_ref set yet (e.g. mid-onboarding)
    must fail closed, not crash — see core/whatsapp.py:validate_webhook_signature."""
    # second_hospital_id's app_secret is NULL by default (seed_test_hospital doesn't set one).
    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "TEST_HOSPITAL_2_PHONE_ID"},
            "messages": [{"from": "919999999992", "type": "text", "text": {"body": "hi"}}],
        }}]}]
    }).encode()
    sig = "sha256=" + hmac.new(b"anything", body, hashlib.sha256).hexdigest()

    resp = client.post("/webhook", content=body,
                        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})

    assert resp.status_code == 403  # rejected cleanly, not a 500


# --- Reminders loop over active hospitals with each one's own data ---

@pytest.mark.asyncio
async def test_reminders_endpoint_sends_separately_to_each_active_hospital(hospital_id, second_hospital_id, httpx_mock):
    httpx_mock.add_response(url="https://graph.facebook.com/v22.0/123/messages", json={"messages": [{"id": "a"}]})
    httpx_mock.add_response(url="https://graph.facebook.com/v22.0/TEST_HOSPITAL_2_PHONE_ID/messages", json={"messages": [{"id": "b"}]})

    db.create_appointment(hospital_id, "111", "cardiology", "doc_card_1", datetime.now() + timedelta(hours=5))
    db.create_appointment(second_hospital_id, "222", "t2_neurology", "t2_doc_neuro_1", datetime.now() + timedelta(hours=5))

    resp = client.post("/internal/send-reminders", headers={"X-Internal-Secret": "internalsecret"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] == 2
    assert body["by_hospital"]["Default Hospital"] == 1
    assert body["by_hospital"]["Test Hospital 2"] == 1

    # Each hospital's reminder actually went to its own phone number, via its own number.
    requests = httpx_mock.get_requests()
    urls = {str(r.url) for r in requests}
    assert "https://graph.facebook.com/v22.0/123/messages" in urls
    assert "https://graph.facebook.com/v22.0/TEST_HOSPITAL_2_PHONE_ID/messages" in urls


# --- Connector dispatch (SPEC Section 12.6.2) at the webhook/reminder boundary ---

def _set_data_tier(hospital_id: int, tier: str) -> None:
    import db.connection as db_connection
    conn = db_connection.get_connection()
    conn.execute("UPDATE hospitals SET data_tier = ? WHERE id = ?", (tier, hospital_id))
    conn.commit()


def test_webhook_message_to_a_tier2_hospital_acks_200_without_crashing(second_hospital_id, httpx_mock):
    """A hospital configured for a tier with no real connector yet (Tier 2/3,
    SPEC Section 12.6) must not turn an incoming webhook into a 500 -- same
    "always ack Meta with 200" pattern as every other failure mode in
    core/main.py's webhook handler.

    A plain first "hi" only reaches the static main menu (STATE_IDLE never
    touches the connector at all), so this puts the session in
    AWAITING_DEPARTMENT first -- the tap that follows calls
    connector.get_departments() as the very first thing it does, before any
    send, so a ConnectorNotImplementedError here proves the "no crash" case
    with zero sends attempted, not just "some earlier state happened to not
    need the connector"."""
    import webhook.dispatch as m

    _set_app_secret(second_hospital_id, "hospital-b-secret")
    _set_data_tier(second_hospital_id, "tier2")
    phone = "919999999993"
    m.SESSIONS.set(second_hospital_id, phone, "AWAITING_DEPARTMENT", {})

    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "TEST_HOSPITAL_2_PHONE_ID"},
            "messages": [{"from": phone, "type": "interactive",
                          "interactive": {"type": "list_reply", "list_reply": {"id": "some_department", "title": ""}}}],
        }}]}]
    }).encode()
    sig = "sha256=" + hmac.new(b"hospital-b-secret", body, hashlib.sha256).hexdigest()

    resp = client.post("/webhook", content=body,
                        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})

    assert resp.status_code == 200
    assert len(httpx_mock.get_requests()) == 0  # failed before any send was attempted


@pytest.mark.asyncio
async def test_reminders_endpoint_skips_a_tier2_hospital_without_failing_others(hospital_id, second_hospital_id, httpx_mock):
    """One hospital with no working connector must not stop every other
    hospital's reminders from sending (SPEC Section 12.6.2)."""
    httpx_mock.add_response(url="https://graph.facebook.com/v22.0/123/messages", json={"messages": [{"id": "a"}]})
    _set_data_tier(second_hospital_id, "tier2")
    db.create_appointment(hospital_id, "111", "cardiology", "doc_card_1", datetime.now() + timedelta(hours=5))
    db.create_appointment(second_hospital_id, "222", "t2_neurology", "t2_doc_neuro_1", datetime.now() + timedelta(hours=5))

    resp = client.post("/internal/send-reminders", headers={"X-Internal-Secret": "internalsecret"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["by_hospital"]["Default Hospital"] == 1
    assert "Test Hospital 2" not in body["by_hospital"]  # skipped, not crashed

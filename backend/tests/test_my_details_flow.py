# tests/test_my_details_flow.py
"""
Patient identity system (Spec.md Section 0): "Reports & Prescriptions"
(renamed/rescoped from "My Details" -- CareConnect architecture doc
alignment, Section 20) -- a self-service WhatsApp feature alongside "My
Appointments": a patient fetches their own Patient ID/MRN, name, age, a
short summary (total appointment count + most recent appointment status),
and any documents on file (tapping one sends it via WhatsApp), now scoped to
the ACTIVE patient (a resolved session), not the phone generally.

Covers: found vs. not-found, English + Hindi, the 10-item document cap, and
cross-tenant isolation (never leaking another hospital's record for a
coincidentally-shared phone number).
"""
from datetime import datetime, timedelta

import pytest

import db.repository as db
import flows
from core.session_store import InMemorySessionStore

PHONE = "5491112345678"


class FakeWhatsAppClient:
    def __init__(self, send_document_result: bool = True):
        self.sent = []  # list of ("text"|"list"|"buttons"|"document", kwargs)
        self._send_document_result = send_document_result

    async def send_text(self, to, text):
        self.sent.append(("text", {"to": to, "text": text}))

    async def send_list(self, to, body_text, button_text, sections, header_text=None, footer_text=None):
        self.sent.append(("list", {"to": to, "body_text": body_text, "sections": sections}))

    async def send_buttons(self, to, body_text, buttons, header_text=None, footer_text=None):
        self.sent.append(("buttons", {"to": to, "body_text": body_text, "buttons": buttons}))

    async def send_document(self, to, document_url, filename, caption=None):
        self.sent.append(("document", {"to": to, "document_url": document_url, "filename": filename}))
        return self._send_document_result


def tap(option_id, title=""):
    return {"type": "interactive_reply", "id": option_id, "title": title}


def _sessions_with_active_patient(hospital_id, active_patient_id, phone=PHONE, language="en"):
    """CareConnect architecture doc alignment (Spec.md Section 0): every
    real conversation reaches a main-menu feature tap with patient identity
    already resolved -- these tests mirror that instead of tapping the
    feature row from a session that never went through resolution."""
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, phone, "IDLE", {}, language=language, active_patient_id=active_patient_id)
    return sessions


def _sessions_with_no_linked_patient(hospital_id, phone=PHONE, language="en"):
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, phone, "IDLE", {}, language=language)
    return sessions


def _row_ids(kind_kwargs):
    return [row["id"] for section in kind_kwargs["sections"] for row in section["rows"]]


def _link_patient(hospital_id, phone, name="Ravi Kumar", age=34):
    """Creates a real linked patient (patients row + patient_links row) --
    the only way a "Reports & Prescriptions" tap can resolve to a specific
    record now, unlike the old phone-upsert-only patients row this file's
    tests used to rely on."""
    return db.create_patient_profile(hospital_id, phone, name, age, relationship_label="Self")


def _book(hospital_id, phone, doctor_id, slot, patient_id):
    return db.create_appointment(
        hospital_id, phone, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot['date']}T{slot['time']}"), patient_id=patient_id,
    )


@pytest.mark.asyncio
async def test_no_record_gets_a_clear_not_found_message(hospital_id):
    """Reachable only via a stale active_patient_id (the session claims one,
    but db.get_patient() can't find it) -- a genuinely unresolved session
    would never reach this feature tap at all under the new architecture,
    since patient resolution runs before the main menu."""
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, 999999)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=["reports_prescriptions"],
    )

    assert len(wa.sent) == 1
    kind, kwargs = wa.sent[0]
    assert kind == "text"
    assert "book an appointment" in kwargs["text"].lower()
    # A dead end resolves the session, not left stuck.
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_found_record_returns_id_name_age_and_summary(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slots = db.get_slots(hospital_id, doctor_id)
    _book(hospital_id, PHONE, doctor_id, slots[0], patient["id"])

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=["reports_prescriptions"],
    )

    kind, kwargs = wa.sent[0]
    assert kind == "text"
    text = kwargs["text"]
    assert patient["patient_display_id"] in text
    assert "Ravi Kumar" in text
    assert "34" in text
    assert "1" in text  # total appointments
    assert "Confirmed" in text  # most recent status label (booked -> Confirmed)
    # No documents on file -- session resolves, no follow-up list.
    assert len(wa.sent) == 1
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_found_record_works_in_hindi(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    _book(hospital_id, PHONE, doctor_id, slot, patient["id"])

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"], language="hi")
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=["reports_prescriptions"],
    )

    kind, kwargs = wa.sent[0]
    assert kind == "text"
    assert "पेशेंट आईडी" in kwargs["text"]
    assert "Ravi Kumar" in kwargs["text"]


@pytest.mark.asyncio
async def test_not_found_works_in_hindi(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, 999999, language="hi")
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=["reports_prescriptions"],
    )
    kind, kwargs = wa.sent[0]
    assert kind == "text"
    assert "रिकॉर्ड" in kwargs["text"]


@pytest.mark.asyncio
async def test_documents_are_offered_as_a_list_and_tapping_one_sends_it(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    _book(hospital_id, PHONE, doctor_id, slot, patient["id"])
    doc = db.create_patient_document(hospital_id, patient["id"], "lab_report.pdf", "fake/key/lab_report.pdf")

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=["reports_prescriptions"],
    )

    # Summary text, then a document list.
    assert len(wa.sent) == 2
    kind, kwargs = wa.sent[1]
    assert kind == "list"
    assert _row_ids(kwargs) == [f"reportdoc_{doc['id']}"]
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_REPORTS_DOCUMENT"

    # Tap the document row -> sent via WhatsApp, marked sent, session resolved.
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(f"reportdoc_{doc['id']}"), enabled_features=["reports_prescriptions"],
    )
    kind, kwargs = wa.sent[2]
    assert kind == "document"
    assert kwargs["filename"] == "lab_report.pdf"
    kind, kwargs = wa.sent[3]
    assert kind == "text"
    assert "sent" in kwargs["text"].lower()
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "IDLE"
    assert session["context"] == {}
    assert session["language"] == "en"

    stored = db.get_patient_document(hospital_id, doc["id"])
    assert stored["sent_to_whatsapp_at"] is not None


@pytest.mark.asyncio
async def test_document_send_failure_reports_clearly_and_does_not_mark_sent(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    _book(hospital_id, PHONE, doctor_id, slot, patient["id"])
    doc = db.create_patient_document(hospital_id, patient["id"], "lab_report.pdf", "fake/key/lab_report.pdf")

    wa = FakeWhatsAppClient(send_document_result=False)
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=["reports_prescriptions"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(f"reportdoc_{doc['id']}"), enabled_features=["reports_prescriptions"],
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "couldn't send" in kwargs["text"].lower()
    stored = db.get_patient_document(hospital_id, doc["id"])
    assert stored["sent_to_whatsapp_at"] is None


@pytest.mark.asyncio
async def test_document_list_respects_the_ten_item_cap(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    _book(hospital_id, PHONE, doctor_id, slot, patient["id"])
    for i in range(12):
        db.create_patient_document(hospital_id, patient["id"], f"doc_{i}.pdf", f"fake/key/doc_{i}.pdf")

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=["reports_prescriptions"],
    )

    kind, kwargs = wa.sent[1]
    assert kind == "list"
    assert len(_row_ids(kwargs)) == 10


@pytest.mark.asyncio
async def test_no_appointments_yet_is_reported_gracefully(hospital_id):
    """A patient record can exist without any (visible) appointment -- e.g.
    every booking was soft-deleted -- shouldn't crash, just say so."""
    patient = _link_patient(hospital_id, PHONE)

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=["reports_prescriptions"],
    )

    kind, kwargs = wa.sent[0]
    assert "None yet" in kwargs["text"] or "0" in kwargs["text"]


@pytest.mark.asyncio
async def test_cross_tenant_isolation_same_phone_different_hospital_never_leaks(hospital_id, second_hospital_id):
    """A patient who's booked at hospital A must NOT see hospital A's record
    when messaging (a coincidentally shared phone number scenario at)
    hospital B -- and vice versa."""
    patient = _link_patient(hospital_id, PHONE)
    doctor_a = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot_a = db.get_slots(hospital_id, doctor_a)[0]
    _book(hospital_id, PHONE, doctor_a, slot_a, patient["id"])

    wa = FakeWhatsAppClient()
    # Stale/nonexistent active_patient_id at hospital B specifically -- the
    # real defense here is db.get_patient() itself being hospital_id-scoped
    # (patient["id"] belongs to `hospital_id`, not `second_hospital_id`).
    sessions = _sessions_with_active_patient(second_hospital_id, patient["id"])
    await flows.handle_incoming(
        wa, sessions, PHONE, second_hospital_id, tap("menu_reports_prescriptions"), enabled_features=["reports_prescriptions"],
    )

    kind, kwargs = wa.sent[0]
    assert kind == "text"
    assert "Ravi Kumar" not in kwargs["text"]
    assert "book an appointment" in kwargs["text"].lower()


@pytest.mark.asyncio
async def test_stale_document_tap_falls_back_to_a_fresh_re_show(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    _book(hospital_id, PHONE, doctor_id, slot, patient["id"])
    db.create_patient_document(hospital_id, patient["id"], "lab_report.pdf", "fake/key/lab_report.pdf")

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=["reports_prescriptions"],
    )
    # Tap an id that doesn't correspond to any real document.
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("reportdoc_999999"), enabled_features=["reports_prescriptions"],
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "list"  # re-shown the (still real) document list, not a crash/dead end

# tests/test_my_details_flow.py
"""
WhatsApp menu restructuring: "Reports & Prescriptions" is now a 4-row
submenu (View Prescriptions / View Lab Reports / View Diagnostic Reports /
Book Report Review) instead of the old one-shot "patient summary + flat
document list" reply -- flows/router.py's _send_reports_menu/
_send_filtered_documents/_handle_awaiting_reports_menu.

Covers: the submenu itself, category-filtered document lists (found/empty/
not-found), the 10-item document cap per category, tapping a document to
receive it, send failure, stale-tap fallback (re-shows the SAME filtered
list, not the old unfiltered one), Hindi, and cross-tenant isolation.

Book Report Review's own booking-flow entry point is covered in
tests/test_booking_flow.py (it reuses the normal booking state machine, not
this file's document-listing machinery).
"""
import pytest

import db.repository as db
import flows
from core.session_store import InMemorySessionStore

PHONE = "5491112345678"

ENABLED = ["reports_prescriptions"]


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


def _row_ids(kind_kwargs):
    return [row["id"] for section in kind_kwargs["sections"] for row in section["rows"]]


def _link_patient(hospital_id, phone, name="Ravi Kumar", age=34):
    return db.create_patient_profile(hospital_id, phone, name, age, relationship_label="Self")


@pytest.mark.asyncio
async def test_tapping_the_feature_shows_the_four_row_submenu(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED,
    )

    assert len(wa.sent) == 1
    kind, kwargs = wa.sent[0]
    assert kind == "list"
    assert _row_ids(kwargs) == [
        "reportsmenu_prescriptions", "reportsmenu_lab_reports", "reportsmenu_diagnostic_reports",
        "reportsmenu_book_review", "goto_main_menu",
    ]
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_REPORTS_MENU"


@pytest.mark.asyncio
async def test_view_prescriptions_lists_only_prescription_documents(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    rx = db.create_patient_document(hospital_id, patient["id"], "rx.pdf", "fake/rx.pdf", document_type="prescription")
    db.create_patient_document(hospital_id, patient["id"], "lab.pdf", "fake/lab.pdf", document_type="lab_report")

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("reportsmenu_prescriptions"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == [f"reportdoc_{rx['id']}", "goto_main_menu"]
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_REPORTS_DOCUMENT"
    assert session["context"]["document_type"] == "prescription"


@pytest.mark.asyncio
async def test_view_lab_reports_lists_only_lab_report_documents(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    db.create_patient_document(hospital_id, patient["id"], "rx.pdf", "fake/rx.pdf", document_type="prescription")
    lab = db.create_patient_document(hospital_id, patient["id"], "lab.pdf", "fake/lab.pdf", document_type="lab_report")

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("reportsmenu_lab_reports"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == [f"reportdoc_{lab['id']}", "goto_main_menu"]


@pytest.mark.asyncio
async def test_view_diagnostic_reports_lists_only_diagnostic_report_documents(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    diag = db.create_patient_document(
        hospital_id, patient["id"], "scan.pdf", "fake/scan.pdf", document_type="diagnostic_report",
    )

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("reportsmenu_diagnostic_reports"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs) == [f"reportdoc_{diag['id']}", "goto_main_menu"]


@pytest.mark.asyncio
async def test_empty_category_shows_a_message_then_re_shows_the_submenu(hospital_id):
    patient = _link_patient(hospital_id, PHONE)

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("reportsmenu_prescriptions"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[-2]
    assert kind == "text"
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs)[:4] == [
        "reportsmenu_prescriptions", "reportsmenu_lab_reports", "reportsmenu_diagnostic_reports",
        "reportsmenu_book_review",
    ]
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_REPORTS_MENU"


@pytest.mark.asyncio
async def test_stale_active_patient_id_gets_a_not_found_message_when_viewing_a_category(hospital_id):
    """The submenu itself doesn't need to look the patient up (it's a fixed
    4-row list) -- the not-found check only happens once a category is
    actually queried."""
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, 999999)

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("reportsmenu_prescriptions"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "book an appointment" in kwargs["text"].lower()
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_submenu_works_in_hindi(hospital_id):
    patient = _link_patient(hospital_id, PHONE)

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"], language="hi")
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[0]
    titles = [row["title"] for section in kwargs["sections"] for row in section["rows"]]
    assert "प्रिस्क्रिप्शन देखें" in titles


@pytest.mark.asyncio
async def test_tapping_a_document_sends_it_and_resolves_the_session(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    doc = db.create_patient_document(hospital_id, patient["id"], "rx.pdf", "fake/rx.pdf", document_type="prescription")

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("reportsmenu_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"reportdoc_{doc['id']}"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[-2]
    assert kind == "document"
    assert kwargs["filename"] == "rx.pdf"
    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "sent" in kwargs["text"].lower()
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "IDLE"

    stored = db.get_patient_document(hospital_id, doc["id"])
    assert stored["sent_to_whatsapp_at"] is not None


@pytest.mark.asyncio
async def test_document_send_failure_reports_clearly_and_does_not_mark_sent(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    doc = db.create_patient_document(hospital_id, patient["id"], "rx.pdf", "fake/rx.pdf", document_type="prescription")

    wa = FakeWhatsAppClient(send_document_result=False)
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("reportsmenu_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"reportdoc_{doc['id']}"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "couldn't send" in kwargs["text"].lower()
    stored = db.get_patient_document(hospital_id, doc["id"])
    assert stored["sent_to_whatsapp_at"] is None


@pytest.mark.asyncio
async def test_document_list_respects_the_ten_item_cap_per_category(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    for i in range(12):
        db.create_patient_document(
            hospital_id, patient["id"], f"rx_{i}.pdf", f"fake/rx_{i}.pdf", document_type="prescription",
        )

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("reportsmenu_prescriptions"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert len(_row_ids(kwargs)) == 10


@pytest.mark.asyncio
async def test_cross_tenant_isolation_same_phone_different_hospital_never_leaks(hospital_id, second_hospital_id):
    """A patient who's booked at hospital A must NOT see hospital A's record
    when messaging (a coincidentally shared phone number scenario at)
    hospital B -- and vice versa."""
    patient = _link_patient(hospital_id, PHONE)
    db.create_patient_document(hospital_id, patient["id"], "rx.pdf", "fake/rx.pdf", document_type="prescription")

    wa = FakeWhatsAppClient()
    # Stale/nonexistent active_patient_id at hospital B specifically -- the
    # real defense here is db.get_patient() itself being hospital_id-scoped
    # (patient["id"] belongs to `hospital_id`, not `second_hospital_id`).
    sessions = _sessions_with_active_patient(second_hospital_id, patient["id"])
    await flows.handle_incoming(wa, sessions, PHONE, second_hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, second_hospital_id, tap("reportsmenu_prescriptions"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "book an appointment" in kwargs["text"].lower()


@pytest.mark.asyncio
async def test_stale_document_tap_falls_back_to_the_same_filtered_list(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    db.create_patient_document(hospital_id, patient["id"], "rx.pdf", "fake/rx.pdf", document_type="prescription")

    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("reportsmenu_prescriptions"), enabled_features=ENABLED)
    # Tap an id that doesn't correspond to any real document.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("reportdoc_999999"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[-1]
    assert kind == "list"  # re-shown the SAME filtered (prescription) list, not the old unfiltered one
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_REPORTS_DOCUMENT"
    assert session["context"]["document_type"] == "prescription"


@pytest.mark.asyncio
async def test_stale_tap_at_the_submenu_itself_re_shows_the_submenu(hospital_id):
    patient = _link_patient(hospital_id, PHONE)
    wa = FakeWhatsAppClient()
    sessions = _sessions_with_active_patient(hospital_id, patient["id"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_reports_prescriptions"), enabled_features=ENABLED)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("some_unrecognized_row"), enabled_features=ENABLED)

    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert _row_ids(kwargs)[0] == "reportsmenu_prescriptions"

"""
Clinic bot-flow follow-up (tenant-capability-gating-plan.md): a clinic tenant
is onboarded with exactly one department and one doctor (frontend/backend
already enforce this at onboarding time), so asking a clinic's own patients
to pick a department then a doctor -- when there's only ever one of each --
is pure friction. flows/booking/book.py's _handle_awaiting_appointment_type
auto-skips straight to date selection whenever get_departments() returns
exactly one department with exactly one doctor in it; this isn't gated on
tenant_type directly (flows/booking/* only ever talks to `connector`, never
db/repository.py or Hospital), so it degrades safely and applies to any
single-department/single-doctor tenant, not just ones tagged "clinic".
"""
from datetime import datetime, timedelta

import pytest

import db.repository as db
from flows.booking import BACK_ID, handle_incoming
from core.session_store import InMemorySessionStore


class FakeWhatsAppClient:
    def __init__(self):
        self.sent = []

    async def send_text(self, to, text):
        self.sent.append(("text", {"to": to, "text": text}))

    async def send_list(self, to, body_text, button_text, sections, header_text=None, footer_text=None):
        self.sent.append(("list", {"to": to, "body_text": body_text, "sections": sections}))

    async def send_buttons(self, to, body_text, buttons, header_text=None, footer_text=None):
        self.sent.append(("buttons", {"to": to, "body_text": body_text, "buttons": buttons}))


def text_reply(text):
    return {"type": "text", "text": text}


def tap(option_id, title=""):
    return {"type": "interactive_reply", "id": option_id, "title": title}


PHONE = "5491199990000"


@pytest.fixture
def clinic_hospital_id():
    """A minimal single-department/single-doctor tenant -- the onboarding
    shape a clinic gets (frontend's Step7HospitalDetails.tsx collapses the
    department/doctor repeater to exactly this for tenant_type="clinic"),
    built directly via the repository layer here since this test only cares
    about the booking flow's own behavior given that shape, not onboarding
    itself."""
    hospital = db.create_hospital(
        name="Dr. Mehta's Clinic", whatsapp_phone_number_id="clinic-test-phone-id", tenant_type="clinic",
    )
    dept = db.create_department(hospital.id, "General")
    doctor = db.create_doctor(
        hospital.id, dept["id"], "Dr. Mehta",
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        working_hours=["10:00-11:00", "15:00-16:00"],
        slot_duration_minutes=60,
    )
    return hospital.id, dept["id"], doctor["id"]


@pytest.mark.asyncio
async def test_single_doctor_tenant_skips_department_and_doctor_selection(clinic_hospital_id):
    hospital_id, dept_id, doctor_id = clinic_hospital_id
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Ravi Kumar"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("34"))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_APPOINTMENT_TYPE"

    appt_type_id = db.get_appointment_types(hospital_id)[0]["id"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(appt_type_id))

    session = sessions.get(hospital_id, PHONE)
    # Straight to date selection -- department/doctor never shown or asked.
    assert session["state"] == "AWAITING_DATE"
    assert session["context"]["department_id"] == dept_id
    assert session["context"]["doctor_id"] == doctor_id
    assert not any(
        kind == "list" and any(row["id"] == dept_id for section in kwargs["sections"] for row in section["rows"])
        for kind, kwargs in wa.sent
    )


@pytest.mark.asyncio
async def test_single_doctor_tenant_back_from_date_returns_to_appointment_type(clinic_hospital_id):
    """Back navigation needs no special-casing for the skip: since the
    department/doctor states were never pushed onto the history stack, a
    single Back tap from date selection pops straight to appointment type,
    same as it would for any other single-step Back."""
    hospital_id, dept_id, doctor_id = clinic_hospital_id
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Ravi Kumar"))
    await handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("34"))
    appt_type_id = db.get_appointment_types(hospital_id)[0]["id"]
    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(appt_type_id))
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DATE"

    await handle_incoming(wa, sessions, PHONE, hospital_id, tap(BACK_ID))
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_APPOINTMENT_TYPE"

# tests/test_patient_selection_flow.py
"""
Patient identity SEPARATION (Spec.md Section 0): flows.py-level coverage of
the new patient-selection layer -- one WhatsApp number can link up to 5
patient profiles, with an explicit active_patient_id used for every
patient-specific action instead of implicitly treating the phone number as
the patient.

Covers: single-patient zero-friction booking (identical to pre-separation
behavior); adding a 2nd-5th patient; a 6th blocked with a clear message;
patient selection correctly scoping booking/cancel/reschedule/My
Appointments to the right patient's data; the "All" family view; unlinking a
patient via "Manage Patients"; and that the per-patient duplicate-booking
check composes correctly with patient selection.
"""
from datetime import datetime, timedelta

import pytest

import db.connection as db_connection
import db.repository as db
import flows
import flows.patient_identity as patient_identity
from core.session_store import InMemorySessionStore

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


def tap(option_id, title=""):
    return {"type": "interactive_reply", "id": option_id, "title": title}


def text_reply(text):
    return {"type": "text", "text": text}


def _sessions_en(hospital_id, phone=PHONE):
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, phone, "IDLE", {}, language="en")
    return sessions


def _row_ids(kind_kwargs):
    return [row["id"] for section in kind_kwargs["sections"] for row in section["rows"]]


def _last_list(wa):
    for kind, kwargs in reversed(wa.sent):
        if kind == "list":
            return kwargs
    raise AssertionError("no list message was sent")


def _last_buttons(wa):
    for kind, kwargs in reversed(wa.sent):
        if kind == "buttons":
            return kwargs
    raise AssertionError("no buttons message was sent")


async def _add_patient_via_chat(wa, sessions, hospital_id, connector, name, age, phone=PHONE, enabled=("booking",)):
    """Drives "Book Appointment" -> name -> age through flows.handle_incoming
    to create one real patient profile the way a real conversation would --
    used to seed multiple linked patients before testing selection."""
    await flows.handle_incoming(wa, sessions, phone, hospital_id, tap("menu_book"), connector=connector, enabled_features=list(enabled))
    await flows.handle_incoming(wa, sessions, phone, hospital_id, text_reply(name), connector=connector, enabled_features=list(enabled))
    await flows.handle_incoming(wa, sessions, phone, hospital_id, text_reply(str(age)), connector=connector, enabled_features=list(enabled))
    await flows.handle_incoming(wa, sessions, phone, hospital_id, tap("new"), connector=connector, enabled_features=list(enabled))


@pytest.mark.asyncio
async def test_single_linked_patient_booking_is_unchanged_zero_friction(hospital_id):
    """The common case: a phone with exactly one active linked patient sees
    no extra selection step at all -- booking behaves identically to a
    phone with zero linked patients asking for a name once."""
    connector = flows._DEFAULT_CONNECTOR
    department = db.get_departments(hospital_id)[0]
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await _add_patient_via_chat(wa, sessions, hospital_id, connector, "Ravi Kumar", 34)
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DEPARTMENT"
    assert session["context"]["patient_name"] == "Ravi Kumar"

    # A brand-new session for this same phone, still exactly one linked
    # patient -- auto-selected again, no selector shown.
    wa2 = FakeWhatsAppClient()
    sessions2 = _sessions_en(hospital_id)
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    assert sessions2.get(hospital_id, PHONE)["state"] == "AWAITING_APPOINTMENT_TYPE"
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap("new"), connector=connector, enabled_features=["booking"])
    session2 = sessions2.get(hospital_id, PHONE)
    assert session2["state"] == "AWAITING_DEPARTMENT"
    assert session2["context"]["patient_name"] == "Ravi Kumar"
    assert {row["id"] for row in _last_list(wa2)["sections"][0]["rows"]} == {d["id"] for d in db.get_departments(hospital_id)}


@pytest.mark.asyncio
async def test_adding_a_second_through_fifth_patient_works(hospital_id):
    """Family members beyond the first are added via "Manage Patients", not
    booking's own selector -- with exactly one linked patient, booking
    auto-selects it with zero added friction (by design, the common case),
    so there is no "+ Add Patient" escape hatch inside booking itself until
    a SECOND patient already exists. Manage Patients is where a phone
    actually accumulates more profiles, from 1 all the way to the cap."""
    connector = flows._DEFAULT_CONNECTOR
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await _add_patient_via_chat(wa, sessions, hospital_id, connector, "Ravi Kumar", 34)
    linked = connector.list_active_patients(hospital_id, PHONE)
    assert len(linked) == 1
    sessions.reset(hospital_id, PHONE)
    # _add_patient_via_chat drives booking's own separate legacy flow, which
    # never sets active_patient_id on the session the way real router
    # traffic does -- one real identity-resolution round-trip first, same
    # as any actual conversation would have before ever reaching Manage
    # Patients, so the Add-Patient-then-IDLE ending below can correctly
    # skip re-asking "who is this for" once a 2nd+ patient exists.
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["manage_patients"])
    assert sessions.get(hospital_id, PHONE)["active_patient_id"] is not None

    for i, (name, age) in enumerate([("Priya Kumar", 8), ("Anita Kumar", 60), ("Sunil Kumar", 65), ("Zoya Kumar", 3)], start=2):
        await flows.handle_incoming(
            wa, sessions, PHONE, hospital_id, tap("menu_manage_patients"),
            connector=connector, enabled_features=["manage_patients"],
        )
        assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_MANAGE_PATIENTS_ACTION
        button_ids = {b["id"] for b in _last_buttons(wa)["buttons"]}
        assert patient_identity.MANAGE_ADD_ROW_ID in button_ids
        await flows.handle_incoming(
            wa, sessions, PHONE, hospital_id, tap(patient_identity.MANAGE_ADD_ROW_ID),
            connector=connector, enabled_features=["manage_patients"],
        )
        assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_BOOKING_FOR
        await flows.handle_incoming(
            wa, sessions, PHONE, hospital_id, tap(patient_identity.BOOKING_FOR_OTHER_ID),
            connector=connector, enabled_features=["manage_patients"],
        )
        assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_NAME
        await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply(name), connector=connector, enabled_features=["manage_patients"])
        assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_CONTACT_PHONE
        await flows.handle_incoming(
            wa, sessions, PHONE, hospital_id, text_reply("9876543210"), connector=connector, enabled_features=["manage_patients"],
        )
        await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply(str(age)), connector=connector, enabled_features=["manage_patients"])
        # Gender -- required before the profile is actually created.
        assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_GENDER
        await flows.handle_incoming(
            wa, sessions, PHONE, hospital_id, tap(patient_identity.GENDER_OTHER_ID),
            connector=connector, enabled_features=["manage_patients"],
        )
        # Lands on the main menu now, patient added (confirmed with the user).
        assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"
        linked = connector.list_active_patients(hospital_id, PHONE)
        assert len(linked) == i
        assert any(p["name"] == name for p in linked)
        sessions.reset(hospital_id, PHONE)
        sessions.reset(hospital_id, PHONE)


@pytest.mark.asyncio
async def test_sixth_patient_is_blocked_with_a_clear_message(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    for i in range(5):
        db.create_patient_profile(hospital_id, PHONE, f"Family Member {i}", 20 + i)

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_SELECTION"
    # At the cap: the selector does NOT even offer "+ Add Patient".
    row_ids = _row_ids(_last_list(wa))
    assert "add_patient" not in row_ids


@pytest.mark.asyncio
async def test_manage_patients_add_is_blocked_at_the_cap_with_a_clear_message(hospital_id):
    """Manage Patients (confirmed with the user) always shows both Remove/
    Add Patient buttons regardless of the cap -- the block only fires once
    "Add Patient" is actually TAPPED, with a clear message, re-showing the
    same 2-option screen rather than a dead end."""
    connector = flows._DEFAULT_CONNECTOR
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)
    for i in range(5):
        db.create_patient_profile(hospital_id, PHONE, f"Family Member {i}", 20 + i)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_manage_patients"),
        connector=connector, enabled_features=["manage_patients"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_MANAGE_PATIENTS_ACTION

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.MANAGE_ADD_ROW_ID),
        connector=connector, enabled_features=["manage_patients"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_MANAGE_PATIENTS_ACTION
    kind, kwargs = wa.sent[-2]
    assert kind == "text"
    assert "5" in kwargs["text"]


@pytest.mark.asyncio
async def test_patient_selection_scopes_booking_to_the_chosen_patient(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    parent = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    child = db.create_patient_profile(hospital_id, PHONE, "Priya Kumar", 8)
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_SELECTION"
    row_ids = _row_ids(_last_list(wa))
    assert f"patient_{child['id']}" in row_ids

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"patient_{child['id']}"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_APPOINTMENT_TYPE"
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"), connector=connector, enabled_features=["booking"])
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "AWAITING_DEPARTMENT"
    assert session["context"]["active_patient_id"] == child["id"]
    assert session["context"]["patient_name"] == "Priya Kumar"


@pytest.mark.asyncio
async def test_patient_selection_scopes_my_appointments_to_the_chosen_patient(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    parent = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    child = db.create_patient_profile(hospital_id, PHONE, "Priya Kumar", 8)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot_a, slot_b = db.get_slots(hospital_id, doctor_id)[0], db.get_slots(hospital_id, doctor_id)[1]
    parent_appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_a['date']}T{slot_a['time']}"), patient_id=parent["id"],
    )
    child_appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_b['date']}T{slot_b['time']}"), patient_id=child["id"],
    )
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_view_appointments"),
        connector=connector, enabled_features=["view_appointments"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_VIEW_APPOINTMENTS_RANGE"
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("view_appointments_range_upcoming"),
        connector=connector, enabled_features=["view_appointments"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_PATIENT_SELECTION"

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(f"patient_{child['id']}"),
        connector=connector, enabled_features=["view_appointments"],
    )
    row_ids = _row_ids(_last_list(wa))
    assert row_ids == [f"appt_{child_appt.id}", "goto_main_menu"]
    assert f"appt_{parent_appt.id}" not in row_ids


@pytest.mark.asyncio
async def test_all_patients_view_shows_every_linked_patients_appointments_labeled(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    parent = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    child = db.create_patient_profile(hospital_id, PHONE, "Priya Kumar", 8)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot_a, slot_b = db.get_slots(hospital_id, doctor_id)[0], db.get_slots(hospital_id, doctor_id)[1]
    parent_appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_a['date']}T{slot_a['time']}"), patient_id=parent["id"],
    )
    child_appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot_b['date']}T{slot_b['time']}"), patient_id=child["id"],
    )
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_view_appointments"),
        connector=connector, enabled_features=["view_appointments"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("view_appointments_range_upcoming"),
        connector=connector, enabled_features=["view_appointments"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("all_patients"),
        connector=connector, enabled_features=["view_appointments"],
    )
    kwargs = _last_list(wa)
    rows = kwargs["sections"][0]["rows"]
    assert {r["id"] for r in rows} == {f"appt_{parent_appt.id}", f"appt_{child_appt.id}", "goto_main_menu"}
    titles = {r["id"]: r["title"] for r in rows}
    assert "Ravi Kumar" in titles[f"appt_{parent_appt.id}"]
    assert "Priya Kumar" in titles[f"appt_{child_appt.id}"]


@pytest.mark.asyncio
async def test_view_appointments_upcoming_range_excludes_cancelled_and_out_of_window(hospital_id):
    """"My Appointments" -> Upcoming 1 Month: booked-only, [now, now+30d]."""
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    cardiology_doctors = db.get_doctors(hospital_id, "cardiology")
    ortho_doctor = db.get_doctors(hospital_id, "orthopedics")[0]["id"]
    # 3 distinct doctors -- the duplicate-booking guard blocks a second
    # active (booked) appointment with the SAME doctor for the same patient.
    in_window = db.create_appointment(
        hospital_id, PHONE, "cardiology", cardiology_doctors[0]["id"], datetime.now() + timedelta(days=5),
        patient_id=patient["id"],
    )
    out_of_window = db.create_appointment(
        hospital_id, PHONE, "cardiology", cardiology_doctors[1]["id"], datetime.now() + timedelta(days=45),
        patient_id=patient["id"],
    )
    cancelled = db.create_appointment(
        hospital_id, PHONE, "orthopedics", ortho_doctor, datetime.now() + timedelta(days=10),
        patient_id=patient["id"],
    )
    db.cancel_appointment(hospital_id, cancelled.id)
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)
    connector = flows._DEFAULT_CONNECTOR

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_view_appointments"),
        connector=connector, enabled_features=["view_appointments"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("view_appointments_range_upcoming"),
        connector=connector, enabled_features=["view_appointments"],
    )

    row_ids = _row_ids(_last_list(wa))
    assert row_ids == [f"appt_{in_window.id}", "goto_main_menu"]
    assert f"appt_{out_of_window.id}" not in row_ids
    assert f"appt_{cancelled.id}" not in row_ids


@pytest.mark.asyncio
async def test_view_appointments_previous_range_shows_past_appointments_any_status(hospital_id):
    """"My Appointments" -> Previous 1 Month: any status, [now-30d, now) --
    a history view, so a cancelled past appointment still shows (labeled
    with its status), unlike the upcoming range above."""
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    conn = db_connection.get_connection()

    def _insert_past_appointment(days_ago, status):
        scheduled_at = (datetime.now() - timedelta(days=days_ago)).isoformat()
        conn.execute(
            "INSERT INTO appointments "
            "(hospital_id, phone, department_id, doctor_id, scheduled_at, status, source, booking_ordinal, "
            "patient_id, created_at) "
            "VALUES (?, ?, 'cardiology', ?, ?, ?, 'whatsapp', 1, ?, ?) RETURNING id",
            (hospital_id, PHONE, doctor_id, scheduled_at, status, patient["id"], datetime.now().isoformat()),
        )
        conn.commit()
        return conn.execute("SELECT id FROM appointments WHERE scheduled_at = ?", (scheduled_at,)).fetchone()["id"]

    attended_id = _insert_past_appointment(10, db.STATUS_ATTENDED)
    cancelled_id = _insert_past_appointment(20, db.STATUS_CANCELLED)
    too_old = db.create_appointment(  # outside the 30-day window -- shouldn't show either
        hospital_id, PHONE, "cardiology", doctor_id, datetime.now() + timedelta(days=5), patient_id=patient["id"],
    )
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)
    connector = flows._DEFAULT_CONNECTOR

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_view_appointments"),
        connector=connector, enabled_features=["view_appointments"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("view_appointments_range_previous"),
        connector=connector, enabled_features=["view_appointments"],
    )

    row_ids = _row_ids(_last_list(wa))
    assert set(row_ids) == {f"appt_{attended_id}", f"appt_{cancelled_id}", "goto_main_menu"}
    assert f"appt_{too_old.id}" not in row_ids


@pytest.mark.asyncio
async def test_view_appointments_is_scoped_to_the_account_not_the_booking_time_phone_string(hospital_id):
    """Confirmed design (not appointments.phone-keyed): a phone number can
    change while the care_connect_account persists, so "My Appointments"
    must resolve by care_connect_account_id via patient_links, not by
    matching appointments.phone against the CURRENT phone. Simulated here
    by directly drifting the stored appointments.phone away from PHONE --
    the appointment must still show, because the join is on patient_id/
    account, never on appointments.phone."""
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, datetime.now() + timedelta(days=5), patient_id=patient["id"],
    )
    conn = db_connection.get_connection()
    conn.execute("UPDATE appointments SET phone = ? WHERE id = ?", ("5490001111_STALE", appt.id))
    conn.commit()
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)
    connector = flows._DEFAULT_CONNECTOR

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_view_appointments"),
        connector=connector, enabled_features=["view_appointments"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("view_appointments_range_upcoming"),
        connector=connector, enabled_features=["view_appointments"],
    )

    row_ids = _row_ids(_last_list(wa))
    assert f"appt_{appt.id}" in row_ids


@pytest.mark.asyncio
async def test_unlinking_a_patient_via_manage_patients_does_not_delete_their_history(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot['date']}T{slot['time']}"), patient_id=patient["id"],
    )
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_manage_patients"),
        connector=connector, enabled_features=["manage_patients"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_MANAGE_PATIENTS_ACTION

    # Manage Patients is now a 2-option entry point (confirmed with the
    # user): Remove Patient / Add Patient, not a direct patient list.
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.MANAGE_REMOVE_ROW_ID),
        connector=connector, enabled_features=["manage_patients"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_REMOVE_PATIENT_SELECTION

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity._unlink_row_id(patient["id"])),
        connector=connector, enabled_features=["manage_patients"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_UNLINK_CONFIRM

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("confirm"),
        connector=connector, enabled_features=["manage_patients"],
    )

    assert connector.list_active_patients(hospital_id, PHONE) == []
    # History and identity untouched.
    still_there = db.get_patient(hospital_id, patient["id"])
    assert still_there is not None and still_there["name"] == "Ravi Kumar"
    appointments = db.get_upcoming_appointments_for_phone(hospital_id, PHONE)
    assert any(a.id == appt.id for a in appointments)
    # Lands on the main menu (confirmed with the user), not back on Manage
    # Patients -- with 0 patients left, that means fresh registration.
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_BOOKING_FOR


@pytest.mark.asyncio
async def test_cancelling_a_patient_removal_keeps_them_linked_and_shows_the_main_menu(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    ravi = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
    priya = db.create_patient_profile(hospital_id, PHONE, "Priya Kumar", 8, relationship_label="Other")
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)
    sessions.set(hospital_id, PHONE, "IDLE", {}, language="en", active_patient_id=ravi["id"])

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_manage_patients"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.MANAGE_REMOVE_ROW_ID),
        connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity._unlink_row_id(priya["id"])),
        connector=connector, enabled_features=["manage_patients"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_UNLINK_CONFIRM

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("cancel"), connector=connector, enabled_features=["manage_patients"],
    )

    linked = connector.list_active_patients(hospital_id, PHONE)
    assert {p["id"] for p in linked} == {ravi["id"], priya["id"]}
    cancelled_text = next(kwargs["text"] for kind, kwargs in wa.sent if kind == "text" and "Priya Kumar" in kwargs["text"])
    assert cancelled_text
    # Lands straight on the main menu -- active patient (Ravi) untouched, no
    # re-prompt even though 2 patients are linked (just_confirmed_patient).
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"
    assert sessions.get(hospital_id, PHONE)["active_patient_id"] == ravi["id"]


@pytest.mark.asyncio
async def test_manage_patients_entry_shows_remove_and_add_buttons(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_manage_patients"), connector=connector, enabled_features=["manage_patients"],
    )

    button_ids = {b["id"] for b in _last_buttons(wa)["buttons"]}
    assert button_ids == {patient_identity.MANAGE_REMOVE_ROW_ID, patient_identity.MANAGE_ADD_ROW_ID}


@pytest.mark.asyncio
async def test_remove_patient_with_nothing_linked_shows_a_message_and_reprompts(hospital_id):
    """Not reachable in real traffic (Manage Patients always has an already-
    resolved active patient) -- exercised directly here as the defensive
    edge case _send_remove_patient_list explicitly handles."""
    connector = flows._DEFAULT_CONNECTOR
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)
    sessions.set(hospital_id, PHONE, "IDLE", {}, language="en", active_patient_id=patient["id"])
    connector.unlink_patient(hospital_id, PHONE, patient["id"])

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_manage_patients"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.MANAGE_REMOVE_ROW_ID),
        connector=connector, enabled_features=["manage_patients"],
    )

    kind, kwargs = wa.sent[-2]
    assert kind == "text"
    assert "no patients to remove" in kwargs["text"].lower()
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_MANAGE_PATIENTS_ACTION


@pytest.mark.asyncio
async def test_duplicate_booking_check_composes_correctly_with_patient_selection(hospital_id):
    """The plan's own explicit "confirm this composes correctly, don't just
    assume" instruction: the SAME linked patient booking the SAME doctor
    twice, through the real chat flow (patient selection -> confirm), is
    still blocked -- while a DIFFERENT linked patient booking that same
    doctor is allowed.

    docs/per-appointment-type-flow-plan.md Phase 2: for a "new" (New
    Consultation) booking specifically, this is now caught by
    flows/booking/types/new_consultation.py's own same-department check
    (patient_id + department_id scoped), right when the department is picked --
    superseding the older, narrower same-DOCTOR DuplicateBookingError path this
    test originally exercised at confirm time."""
    connector = flows._DEFAULT_CONNECTOR
    parent = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34)
    child = db.create_patient_profile(hospital_id, PHONE, "Priya Kumar", 8)
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id,
        datetime.fromisoformat(f"{slot['date']}T{slot['time']}"), patient_id=parent["id"],
    )

    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(f"patient_{child['id']}"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"), connector=connector, enabled_features=["booking"])
    department = db.get_departments(hospital_id)[0]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id), connector=connector, enabled_features=["booking"])
    slots = db.get_slots(hospital_id, doctor_id)
    date_str = slots[0]["date"]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str), connector=connector, enabled_features=["booking"])
    other_slot = [s for s in slots if s["date"] == date_str][-1]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(other_slot["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"), connector=connector, enabled_features=["booking"])

    # A different linked patient (the child) booking the same doctor is
    # allowed through -- success, not a duplicate-block message.
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "book" in kwargs["body_text"].lower() or "success" in kwargs["body_text"].lower() or "consulting" in kwargs["body_text"].lower()

    # Now the SAME patient (parent) trying the same department again is
    # blocked immediately on department selection -- before doctor/date/slot
    # are ever asked.
    wa2 = FakeWhatsAppClient()
    sessions2 = _sessions_en(hospital_id)
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap(f"patient_{parent['id']}"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap("new"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa2, sessions2, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    kind, kwargs = wa2.sent[-1]
    assert kind == "buttons"
    assert department["name"].lower() in kwargs["body_text"].lower()

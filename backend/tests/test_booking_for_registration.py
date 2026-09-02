# tests/test_booking_for_registration.py
""""Myself / Someone Else" registration step (flows/patient_identity.py):
the new first question in patient registration -- "Myself" skips the
contact-number question and stores the messaging phone as the patient's own
contact (patients.phone); "Someone Else" asks for and stores that family
member's own 10-digit contact number instead. Also covers the "only one
Myself per account per hospital" rule (soft pre-check + hard,
advisory-locked backstop) and the staff-portal visit-stats join fix that
had to accompany repurposing patients.phone (db/repositories/patients.py's
_patients_with_visit_stats_stmt, now keyed on patient_id not phone).
"""
from datetime import datetime, timedelta

import pytest

import db.repository as db
import flows
import flows.patient_identity as patient_identity
from core.session_store import InMemorySessionStore

PHONE = "5491112345678"


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


def _last_list(wa):
    for kind, kwargs in reversed(wa.sent):
        if kind == "list":
            return kwargs
    raise AssertionError("no list message was sent")


def _sessions_en(hospital_id, phone=PHONE):
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, phone, "IDLE", {}, language="en")
    return sessions


async def _register_via_chat(wa, sessions, hospital_id, connector, phone, booking_for_id, name, contact_number=None, age=30):
    """Drives the real chat flow: "hi" -> Myself/Someone Else -> name ->
    [contact number, Someone Else only] -> age -> gender -> create."""
    await flows.handle_incoming(wa, sessions, phone, hospital_id, text_reply("hi"), connector=connector, enabled_features=["book_doctor_appointment"])
    await flows.handle_incoming(wa, sessions, phone, hospital_id, tap(booking_for_id), connector=connector, enabled_features=["book_doctor_appointment"])
    await flows.handle_incoming(wa, sessions, phone, hospital_id, text_reply(name), connector=connector, enabled_features=["book_doctor_appointment"])
    if booking_for_id == patient_identity.BOOKING_FOR_OTHER_ID:
        await flows.handle_incoming(
            wa, sessions, phone, hospital_id, text_reply(contact_number), connector=connector, enabled_features=["book_doctor_appointment"],
        )
    await flows.handle_incoming(wa, sessions, phone, hospital_id, text_reply(str(age)), connector=connector, enabled_features=["book_doctor_appointment"])
    await flows.handle_incoming(
        wa, sessions, phone, hospital_id, tap(patient_identity.GENDER_OTHER_ID), connector=connector, enabled_features=["book_doctor_appointment"],
    )


@pytest.mark.asyncio
async def test_registering_myself_skips_contact_question_and_uses_messaging_phone(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await _register_via_chat(wa, sessions, hospital_id, connector, PHONE, patient_identity.BOOKING_FOR_SELF_ID, "Ravi Kumar")

    linked = connector.list_active_patients(hospital_id, PHONE)
    assert len(linked) == 1
    assert linked[0]["relationship_label"] == "Self"
    patient = db.get_patient(hospital_id, linked[0]["id"])
    assert patient["phone"] == PHONE  # messaging phone used directly, never asked


@pytest.mark.asyncio
async def test_registering_someone_else_asks_for_and_stores_their_own_contact_number(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await _register_via_chat(
        wa, sessions, hospital_id, connector, PHONE, patient_identity.BOOKING_FOR_OTHER_ID, "Priya Kumar",
        contact_number="9876543210",
    )

    linked = connector.list_active_patients(hospital_id, PHONE)
    assert len(linked) == 1
    assert linked[0]["relationship_label"] == "Other"
    patient = db.get_patient(hospital_id, linked[0]["id"])
    # stored with the "91" country code prepended, same shape as a messaging phone
    assert patient["phone"] == "919876543210"


@pytest.mark.asyncio
async def test_invalid_contact_number_is_rejected_and_reprompted(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["book_doctor_appointment"])
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.BOOKING_FOR_OTHER_ID), connector=connector, enabled_features=["book_doctor_appointment"],
    )
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Priya Kumar"), connector=connector, enabled_features=["book_doctor_appointment"])
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_CONTACT_PHONE

    # Too short, letters, and a leading zero -- all rejected, state unchanged.
    for bad in ("12345", "98765abcde", "0123456789"):
        await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply(bad), connector=connector, enabled_features=["book_doctor_appointment"])
        assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_CONTACT_PHONE

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("9876543210"), connector=connector, enabled_features=["book_doctor_appointment"])
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_AGE


@pytest.mark.asyncio
async def test_second_registration_from_same_account_skips_the_question_and_locks_to_someone_else(hospital_id):
    """Soft pre-check (has_self_linked_patient): once an account has a
    "Myself" patient at this hospital, a later "Add Patient" for that same
    account never shows the Myself/Someone Else buttons again."""
    connector = flows._DEFAULT_CONNECTOR
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)
    await _register_via_chat(wa, sessions, hospital_id, connector, PHONE, patient_identity.BOOKING_FOR_SELF_ID, "Ravi Kumar")
    sessions.reset(hospital_id, PHONE)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_manage_patients"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.MANAGE_ADD_ROW_ID),
        connector=connector, enabled_features=["manage_patients"],
    )
    # Booking_for skipped entirely -- straight to the name question.
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_NAME
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("Priya Kumar"), connector=connector, enabled_features=["manage_patients"],
    )
    # Locked to "Someone Else" -- the contact-number question still fires.
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_CONTACT_PHONE
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("9876543210"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("8"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.GENDER_OTHER_ID),
        connector=connector, enabled_features=["manage_patients"],
    )
    linked = connector.list_active_patients(hospital_id, PHONE)
    assert {p["relationship_label"] for p in linked} == {"Self", "Other"}


def test_duplicate_detection_matches_on_name_and_contact_phone_not_age(hospital_id):
    """find_potential_duplicate_patient() -- confirmed with the user: exact
    name + exact contact phone (patients.phone), scoped to the hospital.
    Age is no longer part of the match at all: same name+phone with a
    DIFFERENT age still matches; same name+age with a DIFFERENT phone does
    NOT."""
    db.create_patient_profile(hospital_id, "5490009999", "Asha Rao", 45, relationship_label="Self")

    # Same name, same contact phone, DIFFERENT age -- still a match.
    match = db.find_potential_duplicate_patient(hospital_id, "Asha Rao", "5490009999")
    assert match is not None
    assert match["name"] == "Asha Rao"

    # Same name, same age, DIFFERENT contact phone -- no longer a match.
    no_match = db.find_potential_duplicate_patient(hospital_id, "Asha Rao", "1112223333")
    assert no_match is None


@pytest.mark.asyncio
async def test_readding_the_same_name_and_contact_from_your_own_phone_is_blocked_not_duplicated(hospital_id):
    """Bug: find_potential_duplicate_patient() used to exclude a patient
    already linked to the caller's own phone from its OWN duplicate search,
    so re-typing the exact same name+contact number from the SAME WhatsApp
    conversation silently created a brand-new, genuinely duplicate `patients`
    row every time (reported live: "Chandu" with the same 10-digit number
    added twice). Now the match still fires -- and since it's already
    linked to this phone, no new profile is created and no Link/Different
    choice is offered (Link would violate patient_links' own uniqueness
    constraint; Different would recreate the exact bug)."""
    connector = flows._DEFAULT_CONNECTOR
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await _register_via_chat(
        wa, sessions, hospital_id, connector, PHONE, patient_identity.BOOKING_FOR_OTHER_ID, "Chandu",
        contact_number="6200876670",
    )
    linked = connector.list_active_patients(hospital_id, PHONE)
    assert len(linked) == 1

    # Attempt to add "Chandu" / same contact number AGAIN, from the same
    # phone, via Manage Patients.
    sessions.reset(hospital_id, PHONE)
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_manage_patients"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.MANAGE_ADD_ROW_ID),
        connector=connector, enabled_features=["manage_patients"],
    )
    # The first "Chandu" was registered as "Other" (BOOKING_FOR_OTHER_ID
    # above, to give it its own contact number) -- the account has no "Self"
    # patient yet, so the Myself/Someone Else question fires again here too.
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.BOOKING_FOR_OTHER_ID),
        connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("Chandu"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("6200876670"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("30"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.GENDER_OTHER_ID),
        connector=connector, enabled_features=["manage_patients"],
    )

    # No second "Chandu" profile was created, and no Link/Different choice
    # was ever offered for it.
    linked = connector.list_active_patients(hospital_id, PHONE)
    assert len(linked) == 1
    assert not any(
        kind == "buttons" and patient_identity.DUPLICATE_LINK_ID in {b["id"] for b in kwargs["buttons"]}
        for kind, kwargs in wa.sent
    )
    assert any(kind == "text" and "Chandu" in kwargs["text"] for kind, kwargs in wa.sent)


def test_has_self_linked_patient_and_the_hard_advisory_locked_guard(hospital_id):
    """db.has_self_linked_patient() is the soft check the chat flow uses up
    front; db.create_patient_profile()'s own DuplicateSelfLinkError is the
    hard backstop under the SAME advisory lock as the active-links cap --
    exercised directly here (bypassing the chat flow) to prove it holds even
    if a caller never went through the soft check at all."""
    assert db.has_self_linked_patient(hospital_id, connect_account_id := db.get_or_create_account(PHONE, phone_number=PHONE)["id"]) is False

    db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
    assert db.has_self_linked_patient(hospital_id, connect_account_id) is True

    with pytest.raises(db.DuplicateSelfLinkError):
        db.create_patient_profile(hospital_id, PHONE, "Someone Else Entirely", 40, relationship_label="Self")


def test_portal_visit_stats_are_correct_for_a_someone_else_patient_booked_under_a_different_phone(hospital_id):
    """The join fix (_patients_with_visit_stats_stmt, now patient_id-keyed):
    before this fix, a "Someone Else" patient's own contact number
    (patients.phone) would never match appointments.phone (the parent's
    messaging number that actually booked), so the portal would have shown
    0 visits despite a real appointment existing."""
    patient = db.create_patient_profile(
        hospital_id, PHONE, "Priya Kumar", 8, relationship_label="Other", contact_phone="9876543210",
    )
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    appt = db.create_appointment(
        hospital_id, PHONE, "cardiology", doctor_id, datetime.now() + timedelta(days=3), patient_id=patient["id"],
    )

    listed = {p["id"]: p for p in db.list_patients(hospital_id)}[patient["id"]]
    assert listed["visit_count"] == 1
    assert listed["last_visit"] == appt.scheduled_at.isoformat()


@pytest.mark.asyncio
async def test_patient_list_never_shows_the_self_or_other_relationship_label(hospital_id):
    """relationship_label ("Self"/"Other") is internal bookkeeping -- it
    drives the one-Myself-per-account rule and the contact-number question,
    but must never appear in a patient-facing list row (confirmed with the
    user)."""
    connector = flows._DEFAULT_CONNECTOR
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)
    await _register_via_chat(wa, sessions, hospital_id, connector, PHONE, patient_identity.BOOKING_FOR_SELF_ID, "Chandan")
    sessions.reset(hospital_id, PHONE)
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_manage_patients"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.MANAGE_ADD_ROW_ID),
        connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("Chandu"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("6200876670"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("30"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.GENDER_OTHER_ID),
        connector=connector, enabled_features=["manage_patients"],
    )
    # Adding a patient now lands on the main menu, not a patient list --
    # Manage Patients' own patient list is the Remove Patient screen.
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_manage_patients"), connector=connector, enabled_features=["manage_patients"],
    )
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.MANAGE_REMOVE_ROW_ID),
        connector=connector, enabled_features=["manage_patients"],
    )

    kwargs = _last_list(wa)
    titles = [row["title"] for section in kwargs["sections"] for row in section["rows"]]
    assert "Chandan" in titles
    assert "Chandu" in titles
    assert not any("Self" in title or "Other" in title for title in titles)

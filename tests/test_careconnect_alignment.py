# tests/test_careconnect_alignment.py
"""
CareConnect architecture doc alignment (Spec.md Section 0) -- coverage for
what's genuinely NEW this round, on top of what tests/test_patient_links.py
and tests/test_patient_selection_flow.py (last round) and
tests/test_flows.py/test_hospital_settings.py (updated this round) already
cover:

  1. MRN header on the main menu (Section 20).
  2. Duplicate-patient detection before creating a new profile (Sections 8-10).
  3. Structured relationship field, rejecting anything outside the enum (Section 17).
  4. Optional single-linked-patient confirmation (hospitals.require_patient_confirmation,
     Section 11).
  5. Patient status BLOCKED excludes a patient from selection/resolution
     without touching their WhatsApp link (Section 18).
  6. Patient-context validation at the actual booking write, not just
     selection time (Section 14).
  7. Consent & Privacy: marketing-consent toggle, kept separate from
     service consent (Section 20).
"""
from datetime import datetime, timedelta

import pytest

import db.repository as db
import flows
import core.patient_identity as patient_identity
from core.history import InMemorySessionStore

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


def _sessions_en(hospital_id, phone=PHONE, active_patient_id=None):
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, phone, "IDLE", {}, language="en", active_patient_id=active_patient_id)
    return sessions


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


# --- 1. MRN header ---

@pytest.mark.asyncio
async def test_main_menu_shows_patient_name_and_mrn_header(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "IDLE", {}, language="en")

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["booking"])

    kwargs = _last_list(wa)
    assert "Ravi Kumar" in kwargs["body_text"]
    assert patient["patient_display_id"] in kwargs["body_text"]


# --- 2. Duplicate-patient detection ---

@pytest.mark.asyncio
async def test_duplicate_match_offers_link_existing_or_different_patient(hospital_id):
    """Exact name (normalized) + exact age match, among this hospital's
    active patients -- confirmed as the matching criteria with the user."""
    connector = flows._DEFAULT_CONNECTOR
    existing = db.create_patient_profile(hospital_id, "5490009999", "Asha Rao", 45, relationship_label="Self")
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)  # 0 linked patients on THIS phone -> registration

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_NAME
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Asha Rao"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("45"), connector=connector, enabled_features=["booking"])

    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_DUPLICATE_DECISION
    kwargs = _last_buttons(wa)
    assert existing["patient_display_id"] in kwargs["body_text"]
    button_ids = {b["id"] for b in kwargs["buttons"]}
    assert patient_identity.DUPLICATE_LINK_ID in button_ids
    assert patient_identity.DUPLICATE_DIFFERENT_ID in button_ids


@pytest.mark.asyncio
async def test_link_existing_reuses_the_same_mrn_not_a_new_one(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    existing = db.create_patient_profile(hospital_id, "5490009999", "Asha Rao", 45, relationship_label="Self")
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Asha Rao"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("45"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.DUPLICATE_LINK_ID), connector=connector, enabled_features=["booking"],
    )
    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_RELATIONSHIP
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("idrel_self"), connector=connector, enabled_features=["booking"])

    linked = connector.list_active_patients(hospital_id, PHONE)
    assert len(linked) == 1
    assert linked[0]["id"] == existing["id"]
    assert linked[0]["patient_display_id"] == existing["patient_display_id"]
    # No new patients row was created for this "link existing" choice --
    # same total patients count at this hospital as before.
    all_patients_count = db.get_connection().execute(
        "SELECT COUNT(*) AS c FROM patients WHERE hospital_id = ?", (hospital_id,),
    ).fetchone()["c"]
    assert all_patients_count == 1


@pytest.mark.asyncio
async def test_different_patient_creates_a_genuinely_new_profile(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    existing = db.create_patient_profile(hospital_id, "5490009999", "Asha Rao", 45, relationship_label="Self")
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Asha Rao"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("45"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.DUPLICATE_DIFFERENT_ID), connector=connector, enabled_features=["booking"],
    )
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("idrel_self"), connector=connector, enabled_features=["booking"])

    linked = connector.list_active_patients(hospital_id, PHONE)
    assert len(linked) == 1
    assert linked[0]["id"] != existing["id"]
    assert linked[0]["patient_display_id"] != existing["patient_display_id"]


@pytest.mark.asyncio
async def test_no_match_skips_straight_to_relationship_picker(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Someone Unique"), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("52"), connector=connector, enabled_features=["booking"])

    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_RELATIONSHIP


# --- 3. Structured relationship field ---

def test_relationship_options_enum_is_enforced_at_the_repository_layer(hospital_id):
    with pytest.raises(ValueError):
        db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Cousin")
    # A valid value from the enum works fine.
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Spouse")
    linked = db.get_active_patients_for_phone(hospital_id, PHONE)
    assert linked[0]["relationship_label"] == "Spouse"
    assert patient["id"] == linked[0]["id"]


# --- 4. Optional single-linked-patient confirmation ---

@pytest.mark.asyncio
async def test_single_patient_auto_continues_by_default(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
    hospital = db.get_hospital(hospital_id)
    assert hospital.require_patient_confirmation is False
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["booking"])

    # Straight to the menu -- no confirmation step shown.
    kind, kwargs = wa.sent[-1]
    assert kind == "list"
    assert sessions.get(hospital_id, PHONE)["state"] == "IDLE"


@pytest.mark.asyncio
async def test_single_patient_confirmation_shown_when_hospital_requires_it(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    h = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id, name=h.name, whatsapp_phone_number_id=h.whatsapp_phone_number_id,
        access_token=h.access_token, app_secret=h.app_secret, timezone=h.timezone,
        welcome_message_text=h.welcome_message_text, reminder_offsets_hours=h.reminder_offsets_hours,
        reminder_template_name=h.reminder_template_name, data_tier=h.data_tier,
        external_api_base_url=h.external_api_base_url, external_api_key=h.external_api_key,
        portal_password_hash=h.portal_password_hash, enabled_features=h.enabled_features,
        feature_labels=h.feature_labels, closing_message_text=h.closing_message_text,
        business_hours_text=h.business_hours_text, default_language=h.default_language,
        language_prompt_enabled=h.language_prompt_enabled, session_timeout_minutes=h.session_timeout_minutes,
        require_patient_confirmation=True,
    )
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    # require_patient_confirmation is passed explicitly here, same as
    # core/main.py's real webhook call site would (it reads hospital.
    # require_patient_confirmation off the just-updated row) -- handle_incoming()
    # itself takes it as a plain parameter, it doesn't re-read the hospital
    # row on every call.
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["booking"],
        require_patient_confirmation=True,
    )

    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_SINGLE_PATIENT_CONFIRM
    kwargs = _last_buttons(wa)
    assert "Ravi Kumar" in kwargs["body_text"]
    assert patient["patient_display_id"] in kwargs["body_text"]

    # Confirming proceeds to the menu.
    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.CONFIRM_YES), connector=connector, enabled_features=["booking"],
        require_patient_confirmation=True,
    )
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "IDLE"
    assert session["active_patient_id"] == patient["id"]


# --- 5. Patient status BLOCKED ---

def test_blocked_patient_is_excluded_from_active_patients_but_link_untouched(hospital_id):
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
    assert len(db.get_active_patients_for_phone(hospital_id, PHONE)) == 1

    updated = db.set_patient_status(hospital_id, patient["id"], db.PATIENT_STATUS_BLOCKED)
    assert updated["status"] == "blocked"

    # Excluded from selection now...
    assert db.get_active_patients_for_phone(hospital_id, PHONE) == []
    # ...but the link itself is completely untouched (still exists, active).
    link_row = db.get_connection().execute(
        "SELECT unlinked_at FROM patient_links WHERE hospital_id = ? AND patient_id = ?",
        (hospital_id, patient["id"]),
    ).fetchone()
    assert link_row["unlinked_at"] is None

    # Reactivating restores visibility with zero re-linking needed.
    db.set_patient_status(hospital_id, patient["id"], db.PATIENT_STATUS_ACTIVE)
    assert len(db.get_active_patients_for_phone(hospital_id, PHONE)) == 1


@pytest.mark.asyncio
async def test_blocked_patient_forces_registration_not_silent_use(hospital_id):
    """A phone whose only linked patient just got blocked must not silently
    keep using them -- it should behave like a phone with 0 usable
    patients (Section 6's registration flow), not error or hang."""
    connector = flows._DEFAULT_CONNECTOR
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
    db.set_patient_status(hospital_id, patient["id"], db.PATIENT_STATUS_BLOCKED)
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id)

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("hi"), connector=connector, enabled_features=["booking"])

    assert sessions.get(hospital_id, PHONE)["state"] == patient_identity.STATE_AWAITING_PATIENT_NAME


# --- 6. Patient-context validation at the actual write ---

def test_stale_active_patient_id_rejected_at_booking_write(hospital_id):
    """Section 14: re-validated right before the write, not just at
    selection time -- a link unlinked mid-conversation must not let the
    booking through."""
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
    db.unlink_patient(hospital_id, PHONE, patient["id"])

    assert db.validate_active_patient_link(hospital_id, PHONE, patient["id"]) is False


@pytest.mark.asyncio
async def test_booking_confirm_rejects_a_since_unlinked_patient(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    department = db.get_departments(hospital_id)[0]
    doctor_id = db.get_doctors(hospital_id, department["id"])[0]["id"]
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id, active_patient_id=patient["id"])

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(department["id"]), connector=connector, enabled_features=["booking"])
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id), connector=connector, enabled_features=["booking"])
    slots = db.get_slots(hospital_id, doctor_id)
    date_str = slots[0]["date"]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str), connector=connector, enabled_features=["booking"])
    slot = [s for s in slots if s["date"] == date_str][0]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(slot["id"]), connector=connector, enabled_features=["booking"])
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_CONFIRMATION"

    # The link is broken mid-flow (e.g. unlinked from another device/session).
    db.unlink_patient(hospital_id, PHONE, patient["id"])

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"), connector=connector, enabled_features=["booking"])

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert "no longer linked" in kwargs["text"].lower()
    # No appointment was created.
    assert db.get_upcoming_appointments_for_phone(hospital_id, PHONE) == []
    # Session was reset -- no longer trusting the stale active_patient_id.
    assert "active_patient_id" not in sessions.get(hospital_id, PHONE)


# --- 7. Consent & Privacy ---

def test_marketing_consent_toggle_is_independent_of_service_consent(hospital_id):
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
    consent = db.get_patient_link_consent(hospital_id, PHONE, patient["id"])
    assert consent == {"service_consent": True, "marketing_consent": False}

    assert db.set_marketing_consent(hospital_id, PHONE, patient["id"], True) is True
    consent = db.get_patient_link_consent(hospital_id, PHONE, patient["id"])
    # Service consent untouched by the marketing toggle.
    assert consent == {"service_consent": True, "marketing_consent": True}

    assert db.set_marketing_consent(hospital_id, PHONE, patient["id"], False) is True
    consent = db.get_patient_link_consent(hospital_id, PHONE, patient["id"])
    assert consent["marketing_consent"] is False


@pytest.mark.asyncio
async def test_consent_privacy_screen_shows_notice_and_toggles_marketing(hospital_id):
    connector = flows._DEFAULT_CONNECTOR
    h = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id, name=h.name, whatsapp_phone_number_id=h.whatsapp_phone_number_id,
        access_token=h.access_token, app_secret=h.app_secret, timezone=h.timezone,
        welcome_message_text=h.welcome_message_text, reminder_offsets_hours=h.reminder_offsets_hours,
        reminder_template_name=h.reminder_template_name, data_tier=h.data_tier,
        external_api_base_url=h.external_api_base_url, external_api_key=h.external_api_key,
        portal_password_hash=h.portal_password_hash, enabled_features=["consent_privacy"],
        feature_labels=h.feature_labels, closing_message_text=h.closing_message_text,
        business_hours_text=h.business_hours_text, default_language=h.default_language,
        language_prompt_enabled=h.language_prompt_enabled, session_timeout_minutes=h.session_timeout_minutes,
        privacy_notice_text="Custom hospital privacy notice.",
    )
    patient = db.create_patient_profile(hospital_id, PHONE, "Ravi Kumar", 34, relationship_label="Self")
    wa = FakeWhatsAppClient()
    sessions = _sessions_en(hospital_id, active_patient_id=patient["id"])

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_consent_privacy"), connector=connector, enabled_features=["consent_privacy"],
        privacy_notice_text="Custom hospital privacy notice.",
    )
    kwargs = _last_buttons(wa)
    assert "Custom hospital privacy notice." in kwargs["body_text"]
    assert "Disabled" in kwargs["body_text"]  # marketing off by default

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap(patient_identity.CONSENT_TOGGLE_MARKETING_ID),
        connector=connector, enabled_features=["consent_privacy"], privacy_notice_text="Custom hospital privacy notice.",
    )
    kwargs = _last_buttons(wa)
    assert "Enabled" in kwargs["body_text"]
    consent = db.get_patient_link_consent(hospital_id, PHONE, patient["id"])
    assert consent["marketing_consent"] is True

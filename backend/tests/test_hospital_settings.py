# tests/test_hospital_settings.py
"""
Section 12.13: self-serve bot customization beyond enabled_features' on/off
toggles -- feature_labels, closing_message_text, business_hours_text,
default_language/language_prompt_enabled, session_timeout_minutes. Every one
defaults to "no customization" so an untouched hospital behaves exactly as
before this section (covered incidentally by every pre-existing flows.py/
booking_flow.py test still passing unchanged) -- this file covers each
customization actually taking effect, plus cross-tenant isolation.
"""
from datetime import datetime, timedelta

import pytest

import db.repository as db
import flows
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


def text_reply(text):
    return {"type": "text", "text": text}


def tap(option_id, title=""):
    return {"type": "interactive_reply", "id": option_id, "title": title}


def _row_titles(kwargs):
    return [row["title"] for section in kwargs["sections"] for row in section["rows"]]


def _last_list(wa):
    """The main menu now always sends its own follow-up "Back" (switch
    patient) buttons message right after the list -- this finds the list
    itself regardless of that trailing message."""
    for kind, kwargs in reversed(wa.sent):
        if kind == "list":
            return kwargs
    raise AssertionError("no list message was sent")


def _english_session(hospital_id, phone=PHONE):
    sessions = InMemorySessionStore()
    sessions.set(hospital_id, phone, "IDLE", {}, language="en")
    return sessions


def _seed_default_patient(hospital_id, phone=PHONE):
    """CareConnect architecture doc alignment (Spec.md Section 0): patient
    identity is now resolved before the main menu -- seed one linked
    patient so these tests (about menu/settings behavior, not patient
    identity itself) land directly on the menu with zero friction."""
    return db.create_patient_profile(hospital_id, phone, "Test Patient", 30, relationship_label="Self")


# --- Feature menu labels ---

@pytest.mark.asyncio
async def test_custom_feature_label_overrides_default_in_menu(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _english_session(hospital_id)
    _seed_default_patient(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Hospital", enabled_features=["booking", "hospital_info"],
        feature_labels={"booking": "Schedule a consultation"},
    )

    kwargs = _last_list(wa)
    titles = _row_titles(kwargs)
    assert "Schedule a consultation" in titles
    assert "Book Appointment" not in titles
    # Untouched feature keeps its fixed default.
    assert "Hospital Information" in titles


@pytest.mark.asyncio
async def test_no_custom_label_falls_back_to_default(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _english_session(hospital_id)
    _seed_default_patient(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Hospital", enabled_features=["booking"],
        feature_labels={},
    )

    kwargs = _last_list(wa)
    assert _row_titles(kwargs) == ["Book Appointment"]


# --- Closing message ---

@pytest.mark.asyncio
async def test_closing_message_appended_after_booking_confirmed(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    department = db.get_departments(hospital_id)[0]
    doctor_id = db.get_doctors(hospital_id, department["id"])[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    sessions.set(hospital_id, PHONE, "AWAITING_CONFIRMATION", {
        "department_id": department["id"], "department_name": department["name"],
        "doctor_id": doctor_id, "doctor_name": "Dr. X",
        "date_label": "Sat, Aug 8", "slot_date": slot["date"], "slot_time": slot["time"],
        "patient_name": "Ravi Kumar",
    }, language="en")

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("confirm"),
        closing_message_text="Thank you for choosing City Hospital. For emergencies, call 102.",
    )

    kind, kwargs = wa.sent[-1]
    # Item 3 (Spec.md Section 0): success message is now buttons, not text.
    assert kind == "buttons"
    assert "appointment confirmed" in kwargs["body_text"].lower()
    assert kwargs["body_text"].endswith("Thank you for choosing City Hospital. For emergencies, call 102.")


@pytest.mark.asyncio
async def test_no_closing_message_configured_leaves_standard_text_unchanged(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    department = db.get_departments(hospital_id)[0]
    doctor_id = db.get_doctors(hospital_id, department["id"])[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    sessions.set(hospital_id, PHONE, "AWAITING_CONFIRMATION", {
        "department_id": department["id"], "department_name": department["name"],
        "doctor_id": doctor_id, "doctor_name": "Dr. X",
        "date_label": "Sat, Aug 8", "slot_date": slot["date"], "slot_time": slot["time"],
        "patient_name": "Ravi Kumar",
    }, language="en")

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("confirm"))

    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "Appointment Confirmed" in kwargs["body_text"]
    assert kwargs["body_text"].rstrip().endswith("We look forward to seeing you.")  # no extra appended block


@pytest.mark.asyncio
async def test_closing_message_appended_after_cancel_confirmed(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    appt = db.create_appointment(hospital_id, PHONE, "cardiology", "doc_card_1", datetime.now() + timedelta(hours=5))
    sessions.set(hospital_id, PHONE, "AWAITING_CANCEL_CONFIRM", {"appointment_id": appt.id}, language="en")

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("confirm"),
        closing_message_text="We hope to see you again soon.",
    )

    kind, kwargs = wa.sent[-2]
    assert "cancelled" in kwargs["text"].lower()
    assert kwargs["text"].endswith("We hope to see you again soon.")


# --- Business hours ---

@pytest.mark.asyncio
async def test_business_hours_text_shown_in_hospital_info_reply(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _english_session(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_hospital_info"),
        enabled_features=["hospital_info"], business_hours_text="Mon-Sat, 9am-8pm",
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "text"
    assert kwargs["text"].endswith("Mon-Sat, 9am-8pm")


@pytest.mark.asyncio
async def test_no_business_hours_configured_leaves_hospital_info_reply_unchanged(hospital_id):
    from core.translations import t
    from core.translations.menu import HOSPITAL_INFO_TEXT

    wa = FakeWhatsAppClient()
    sessions = _english_session(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, tap("menu_hospital_info"),
        enabled_features=["hospital_info"],
    )

    kind, kwargs = wa.sent[-1]
    # Byte-for-byte the fixed default -- nothing appended when
    # business_hours_text isn't set (the default text itself already
    # mentions example "Mon-Sat" hours, so that substring alone isn't a safe
    # thing to assert the ABSENCE of; exact equality is the real test).
    assert kwargs["text"] == t(HOSPITAL_INFO_TEXT, "en")


# --- Default language / language prompt skip ---

@pytest.mark.asyncio
async def test_language_prompt_disabled_skips_picker_and_uses_default_language(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()
    _seed_default_patient(hospital_id)

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Hospital", enabled_features=["booking"],
        default_language="hi", language_prompt_enabled=False,
    )

    kwargs = _last_list(wa)  # straight to the menu, never the picker
    assert "कृपया एक विकल्प चुनें" in kwargs["body_text"]
    session = sessions.get(hospital_id, PHONE)
    assert session["state"] == "IDLE"
    assert session["language"] == "hi"


@pytest.mark.asyncio
async def test_language_prompt_enabled_by_default_still_shows_picker(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Hospital", enabled_features=["booking"],
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_LANGUAGE"


@pytest.mark.asyncio
async def test_default_language_hindi_lists_hindi_button_first_on_picker(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = InMemorySessionStore()

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Hospital", enabled_features=["booking"], default_language="hi",
    )

    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert kwargs["buttons"][0]["id"] == "lang_hi"


# --- Session timeout ---

class _SpySessionStore(InMemorySessionStore):
    """Records every timeout_seconds actually passed to .get() -- proves
    flows.py's session_timeout_minutes kwarg reaches the store correctly
    converted to seconds, without needing a real sleep-based timing test."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_calls: list[int | None] = []

    def get(self, hospital_id, phone, timeout_seconds=None):
        self.get_calls.append(timeout_seconds)
        return super().get(hospital_id, phone, timeout_seconds=timeout_seconds)


@pytest.mark.asyncio
async def test_session_timeout_minutes_is_converted_to_seconds_and_passed_to_the_store(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _SpySessionStore()

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Hospital", enabled_features=["booking"], session_timeout_minutes=15,
    )

    assert sessions.get_calls == [15 * 60]


@pytest.mark.asyncio
async def test_no_custom_timeout_leaves_store_default_untouched(hospital_id):
    wa = FakeWhatsAppClient()
    sessions = _SpySessionStore()

    await flows.handle_incoming(
        wa, sessions, PHONE, hospital_id, text_reply("hi"),
        hospital_name="City Hospital", enabled_features=["booking"],
    )

    assert sessions.get_calls == [None]  # falls back to the store's own constructor default


def test_session_timeout_minutes_actually_changes_expiry_behavior(hospital_id):
    import time
    sessions = InMemorySessionStore(timeout_seconds=30 * 60)
    sessions.set(hospital_id, PHONE, "AWAITING_DEPARTMENT", {}, language="en")
    time.sleep(1.1)

    # The same elapsed time is "not expired" under the real 30-min default
    # but IS expired under a 1-second override passed straight to .get() --
    # this is the actual timeout math flows.py's plumbing (proven above)
    # relies on.
    assert sessions.get(hospital_id, PHONE)["state"] == "AWAITING_DEPARTMENT"
    assert sessions.get(hospital_id, PHONE, timeout_seconds=1)["state"] == "IDLE"


# --- Cross-tenant isolation ---

@pytest.mark.asyncio
async def test_settings_customization_does_not_leak_across_hospitals(hospital_id, second_hospital_id):
    h = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id, name=h.name, whatsapp_phone_number_id=h.whatsapp_phone_number_id,
        access_token=h.access_token, app_secret=h.app_secret, timezone=h.timezone,
        welcome_message_text=h.welcome_message_text, reminder_offsets_hours=h.reminder_offsets_hours,
        reminder_template_name=h.reminder_template_name, data_tier=h.data_tier,
        external_api_base_url=h.external_api_base_url, external_api_key=h.external_api_key,
        portal_password_hash=h.portal_password_hash, enabled_features=h.enabled_features,
        feature_labels={"booking": "Custom Hospital A Label"},
        closing_message_text="Hospital A's own closing message.",
        business_hours_text="Hospital A hours",
        default_language="hi", language_prompt_enabled=False,
        session_timeout_minutes=15,
    )

    updated_a = db.get_hospital(hospital_id)
    untouched_b = db.get_hospital(second_hospital_id)

    assert updated_a.feature_labels == {"booking": "Custom Hospital A Label"}
    assert updated_a.closing_message_text == "Hospital A's own closing message."
    assert updated_a.business_hours_text == "Hospital A hours"
    assert updated_a.default_language == "hi"
    assert updated_a.language_prompt_enabled is False
    assert updated_a.session_timeout_minutes == 15

    # Hospital B never touched -- every field stays at its untouched default.
    assert untouched_b.feature_labels == {}
    assert untouched_b.closing_message_text is None
    assert untouched_b.business_hours_text is None
    assert untouched_b.default_language == "en"
    assert untouched_b.language_prompt_enabled is True
    assert untouched_b.session_timeout_minutes is None


# --- Editing unrelated settings never wipes existing customization ---

@pytest.mark.asyncio
async def test_editing_welcome_message_never_wipes_existing_customizations(hospital_id):
    """The same 'every caller passes the hospital's own current value through
    explicitly' discipline enabled_features already relies on (db/repository.py's
    update_hospital docstring) -- an edit to something else (e.g. the old
    portal.py HTML settings form, or an admin edit-tenant save) must never
    silently reset a hospital's Section 12.13 customizations back to defaults."""
    h = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id, name=h.name, whatsapp_phone_number_id=h.whatsapp_phone_number_id,
        access_token=h.access_token, app_secret=h.app_secret, timezone=h.timezone,
        welcome_message_text=h.welcome_message_text, reminder_offsets_hours=h.reminder_offsets_hours,
        reminder_template_name=h.reminder_template_name, data_tier=h.data_tier,
        external_api_base_url=h.external_api_base_url, external_api_key=h.external_api_key,
        portal_password_hash=h.portal_password_hash, enabled_features=h.enabled_features,
        feature_labels={"booking": "Original Label"}, closing_message_text="Original closing.",
        business_hours_text="Original hours", default_language="hi", language_prompt_enabled=False,
        session_timeout_minutes=20,
    )

    # Now simulate an unrelated edit (e.g. admin/onboarding.py's edit-tenant
    # route) that passes hospital.<field> through unchanged, same pattern
    # this session added to every real call site.
    h2 = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id, name=h2.name, whatsapp_phone_number_id=h2.whatsapp_phone_number_id,
        access_token=h2.access_token, app_secret=h2.app_secret, timezone=h2.timezone,
        welcome_message_text="A brand-new welcome message.", reminder_offsets_hours=h2.reminder_offsets_hours,
        reminder_template_name=h2.reminder_template_name, data_tier=h2.data_tier,
        external_api_base_url=h2.external_api_base_url, external_api_key=h2.external_api_key,
        portal_password_hash=h2.portal_password_hash, enabled_features=h2.enabled_features,
        feature_labels=h2.feature_labels, closing_message_text=h2.closing_message_text,
        business_hours_text=h2.business_hours_text, default_language=h2.default_language,
        language_prompt_enabled=h2.language_prompt_enabled, session_timeout_minutes=h2.session_timeout_minutes,
    )

    final = db.get_hospital(hospital_id)
    assert final.welcome_message_text == "A brand-new welcome message."
    assert final.feature_labels == {"booking": "Original Label"}
    assert final.closing_message_text == "Original closing."
    assert final.business_hours_text == "Original hours"
    assert final.default_language == "hi"
    assert final.language_prompt_enabled is False
    assert final.session_timeout_minutes == 20


# --- Follow-up settings: hospital_settings table (docs/per-appointment-type-
# flow-plan.md Phase 2 Step 2 follow-up), not columns on `hospitals` ---

def _confirmation_context(appointment_type_id="new"):
    return {
        "appointment_type_id": appointment_type_id, "appointment_type_label": "New Consultation",
        "department_name": "Cardiology", "doctor_name": "Dr. X", "date_label": "Sat, Aug 8",
        "slot_time": "10:00 AM", "patient_name": "Ravi Kumar", "patient_age": 34,
    }


@pytest.mark.asyncio
async def test_no_configured_new_consultation_fee_omits_the_fee_line(hospital_id):
    from flows.booking.messages import _send_confirmation

    wa = FakeWhatsAppClient()
    await _send_confirmation(wa, PHONE, hospital_id, _confirmation_context(), language="en")
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    assert "Consultation Fee" not in kwargs["body_text"]


@pytest.mark.asyncio
async def test_configured_new_consultation_fee_shows_on_confirm_card(hospital_id):
    from flows.booking.messages import _send_confirmation

    db.update_hospital_settings(hospital_id, followup_validity_days=None, followup_fee=None, new_consultation_fee=500)
    wa = FakeWhatsAppClient()
    await _send_confirmation(wa, PHONE, hospital_id, _confirmation_context(), language="en")
    kind, kwargs = wa.sent[-1]
    assert "💰 Consultation Fee: ₹500" in kwargs["body_text"]


@pytest.mark.asyncio
async def test_new_consultation_fee_not_shown_for_other_appointment_types(hospital_id):
    """new_consultation_fee is New-Consultation-specific -- a hospital
    configuring it must not make it appear on a tele-consultation's (or any
    other type's) confirm card, which shares the same generic template."""
    from flows.booking.messages import _send_confirmation

    db.update_hospital_settings(hospital_id, followup_validity_days=None, followup_fee=None, new_consultation_fee=500)
    wa = FakeWhatsAppClient()
    await _send_confirmation(wa, PHONE, hospital_id, _confirmation_context(appointment_type_id="tele"), language="en")
    kind, kwargs = wa.sent[-1]
    assert "Consultation Fee" not in kwargs["body_text"]

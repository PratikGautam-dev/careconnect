import pytest

from core.translations import STRINGS, SUPPORTED_LANGUAGES, t
from core.translations.booking import (
    BOOKING_CONFIRMED,
    CONFIRM_BOOKING_SUMMARY,
    CONFIRM_BUTTON,
    CONSULTATION_FEE_LINE,
)
from core.translations.common import PLEASE_CHOOSE


def test_every_key_has_every_supported_language():
    for key, variants in STRINGS.items():
        assert set(variants.keys()) == SUPPORTED_LANGUAGES, f"{key} missing a language variant"


def test_t_returns_english_for_english():
    assert t(CONFIRM_BUTTON, "en") == "Confirm"


def test_t_returns_hindi_for_hindi():
    assert t(CONFIRM_BUTTON, "hi") == "पुष्टि करें"


def test_t_falls_back_to_english_for_unset_language():
    assert t(CONFIRM_BUTTON, None) == "Confirm"


def test_t_falls_back_to_english_for_unsupported_language():
    assert t(CONFIRM_BUTTON, "fr") == "Confirm"


def test_t_formats_kwargs_in_both_languages():
    assert t("feature_menu_unavailable", "en", hospital_name="City Hospital") == (
        "Sorry, City Hospital hasn't finished setting up WhatsApp yet. Please check back later."
    )
    assert "City Hospital" in t("feature_menu_unavailable", "hi", hospital_name="City Hospital")


def test_t_without_kwargs_does_not_attempt_formatting():
    # A template with no {placeholders} must round-trip untouched even if it
    # contains literal braces or percent signs some day -- str.format() is
    # only invoked when kwargs are actually passed.
    assert t(PLEASE_CHOOSE, "en") == "Please choose an option from the list above"


def test_button_and_row_title_strings_respect_whatsapp_length_limits():
    """Meta hard-limits interactive BUTTON titles to 20 chars and LIST ROW
    titles to 24 (core/translations.py's own module docstring flags this as
    unenforced elsewhere) -- this test is the enforcement, covering every
    string used as a button/row title in either language."""
    button_keys = [
        "language_picker_button_en", "language_picker_button_hi", "main_menu_button",
        "view_departments_button", "view_doctors_button", "view_slots_button",
        "view_dates_button", "view_times_button",
        "confirm_button", "cancel_button", "view_appointments_button", "view_topics_button",
        "view_appointments_range_previous_button", "view_appointments_range_upcoming_button",
        # "Go back" navigation: back_option is a button ONLY now (the
        # confirmation card's 3rd button, and the department/doctor/date/time
        # menus' own follow-up Back-button message, Spec.md Section 0's UX
        # follow-up) -- never a list-row title anymore.
        "back_option", "view_change_options_button",
        # Patient identity SEPARATION (Spec.md Section 0): list "button_text"
        # labels share the same 20-char limit as interactive buttons.
        "patient_selector_button", "manage_patients_button",
        "booking_for_self_button", "booking_for_other_button",
        # CareConnect architecture doc alignment (Spec.md Section 0): row
        # AND button dual-use keys (manage_patients_short, back_to_menu_option)
        # checked against the stricter 20-char button limit, which also
        # satisfies the looser 24-char row limit they're reused for.
        "duplicate_link_button", "duplicate_different_button", "ask_relationship_button",
        "manage_patients_short", "back_to_menu_option",
        "consent_marketing_enable", "consent_marketing_disable",
    ]
    for key in button_keys:
        for lang in SUPPORTED_LANGUAGES:
            text = STRINGS[key][lang]
            assert len(text) <= 20, f"{key}[{lang}] = {text!r} exceeds WhatsApp's 20-char button limit ({len(text)} chars)"

    row_title_keys = [
        "feature_booking", "feature_reschedule", "feature_cancel", "feature_view_appointments",
        "feature_hospital_info", "feature_reception_handoff", "feature_faq",
        "book_appointment_short", "reschedule_short", "cancel_short", "faq_short",
        "change_department_option", "change_doctor_option",
        "change_date_option", "change_time_option", "feature_change_language",
        # Patient identity SEPARATION (Spec.md Section 0).
        "feature_manage_patients", "add_patient_option", "all_patients_option",
        # CareConnect architecture doc alignment (Spec.md Section 0).
        "feature_reports_prescriptions", "feature_consent_privacy",
        "relationship_self", "relationship_mother", "relationship_father", "relationship_son",
        "relationship_daughter", "relationship_spouse", "relationship_guardian", "relationship_other",
    ]
    for key in row_title_keys:
        for lang in SUPPORTED_LANGUAGES:
            text = STRINGS[key][lang]
            assert len(text) <= 24, f"{key}[{lang}] = {text!r} exceeds WhatsApp's 24-char row-title limit ({len(text)} chars)"


def test_confirmation_card_renders_structured_markdown_in_both_languages():
    """Confirmation-card restyle (confirmed with the user): "Emoji Label:
    value" lines (plain, no *bold* per field -- just the *Confirm Booking
    Details:* heading), a Patient Code line (patient_display_id, fetched by
    the caller and passed in as patient_code), and a fee_line (built by the
    caller via CONSULTATION_FEE_LINE when hospital_settings.
    new_consultation_fee is configured, "" otherwise -- see
    flows/booking/messages.py's _send_confirmation) -- must render correctly
    (and identically in shape) in both languages."""
    fee_line_en = t(CONSULTATION_FEE_LINE, "en", amount=800)
    summary_en = t(CONFIRM_BOOKING_SUMMARY, "en",
        appointment_type_label="New Consultation",
        department_name="Cardiology", doctor_name="Anjali Rao", date_label="Sat, Aug 8",
        time_label="10:00", patient_name="Ravi Kumar", patient_age=34, patient_code="DCCP-2026-00020",
        fee_line=fee_line_en,
    )
    assert "*Confirm Booking Details:*" in summary_en
    assert "👤 Patient: Ravi Kumar" in summary_en
    assert "🆔 Patient Id: DCCP-2026-00020" in summary_en
    assert "🎂 Age: 34" in summary_en
    assert "📋 Appointment Type: New Consultation" in summary_en
    assert "🏥 Department: Cardiology" in summary_en
    assert "👨‍⚕️ Doctor: Anjali Rao" in summary_en
    assert "📅 Date: Sat, Aug 8" in summary_en
    assert "🕐 Time: 10:00" in summary_en
    assert "💰 Consultation Fee: ₹800" in summary_en
    # Item 10 (Spec.md Section 0): patient name/code/age must come FIRST,
    # ahead of department/doctor/date/time.
    assert summary_en.index("Patient:") < summary_en.index("Department:")
    assert summary_en.index("Age:") < summary_en.index("Doctor:")

    # fee_line="" (hospital hasn't configured a fee, or not a New Consultation
    # booking): the line is omitted entirely, not shown as a fake ₹0.
    summary_no_fee = t(CONFIRM_BOOKING_SUMMARY, "en",
        appointment_type_label="New Consultation",
        department_name="Cardiology", doctor_name="Anjali Rao", date_label="Sat, Aug 8",
        time_label="10:00", patient_name="Ravi Kumar", patient_age=34, patient_code="DCCP-2026-00020",
        fee_line="",
    )
    assert "Consultation Fee" not in summary_no_fee

    summary_hi = t(CONFIRM_BOOKING_SUMMARY, "hi",
        appointment_type_label="New Consultation",
        department_name="Cardiology", doctor_name="Anjali Rao", date_label="Sat, Aug 8",
        time_label="10:00", patient_name="Ravi Kumar", patient_age=34, patient_code="DCCP-2026-00020",
        fee_line=t(CONSULTATION_FEE_LINE, "hi", amount=800),
    )
    assert "Cardiology" in summary_hi and "Ravi Kumar" in summary_hi and "DCCP-2026-00020" in summary_hi

    confirmed_en = t(
        BOOKING_CONFIRMED, "en", reference_id="apt_1754650184123", patient_name="Ravi Kumar",
        department_name="Cardiology", doctor_name="Dr. Anjali Rao", date_label="Saturday, 08 August 2026",
        time_label="10:00 AM",
    )
    assert "✅ *Appointment Confirmed*" in confirmed_en
    assert "Appointment ID: apt_1754650184123" in confirmed_en

    confirmed_hi = t(
        BOOKING_CONFIRMED, "hi", reference_id="apt_1754650184123", patient_name="Ravi Kumar",
        department_name="Cardiology", doctor_name="Dr. Anjali Rao", date_label="Saturday, 08 August 2026",
        time_label="10:00 AM",
    )
    assert "✅" in confirmed_hi and "apt_1754650184123" in confirmed_hi

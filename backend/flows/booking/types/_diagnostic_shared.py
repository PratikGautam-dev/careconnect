# flows/booking/types/_diagnostic_shared.py
"""Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5):
test -> resource-linked date/time -> confirm. Shared by diagnostic.py and
lab.py -- they're structurally identical, differing only in which
`diagnostic_tests.category` they list (which is exactly their own
appointment_type_id, "diagnostic"/"lab", read back off context).

Test/variant merge: a test carries exactly one price on itself now (no
separate diagnostic_test_variants row to pick between), so there's no
variant-selection step anymore -- picking a test goes straight to date
selection.

messages.py/book.py imports are lazy (inside functions), same
cycle-avoidance reason daycare.py/followup.py already use: this module ->
types.registry -> this module."""
import db.repository as db
from core.translations import t
from core.translations.booking import (
    DIAGNOSTIC_AMOUNT_LINE,
    DIAGNOSTIC_BOOKING_CONFIRMED,
    DIAGNOSTIC_CONFIRMATION_SUMMARY,
    DIAGNOSTIC_TESTS_SECTION_TITLE,
    NO_DIAGNOSTIC_TESTS_CONFIGURED,
    SELECT_DIAGNOSTIC_TEST,
    VIEW_TESTS_BUTTON,
)
from core.translations.common import BACK_OPTION
from core.translations.menu import MAIN_MENU_BUTTON
from core.whatsapp import WhatsAppClient

from flows.booking.state import (
    BACK_ID, GOTO_MAIN_MENU, STATE_AWAITING_APPOINTMENT_TYPE, STATE_AWAITING_CONFIRMATION, STATE_AWAITING_DATE,
    STATE_AWAITING_DIAGNOSTIC_TEST, STATE_AWAITING_TIME_SLOT,
    _HISTORY_KEY, _push_history,
)
from flows.booking.types.base import TypeFlow

_STEPS = (
    STATE_AWAITING_DIAGNOSTIC_TEST, STATE_AWAITING_DATE, STATE_AWAITING_TIME_SLOT, STATE_AWAITING_CONFIRMATION,
)


async def _send_no_tests_screen(wa, phone: str, hospital_id: int, sessions, context: dict, connector, language: str) -> None:
    """Mirrors followup.py's _send_no_eligible_screen -- no tests configured
    for this category yet, so back out to the appointment-type list rather
    than a dead end."""
    from flows.booking.messages import _send_appointment_type_menu

    sessions.set(hospital_id, phone, STATE_AWAITING_APPOINTMENT_TYPE, context)
    await _send_appointment_type_menu(
        wa, phone, hospital_id, connector, language=language, category=context.get("appointment_type_category"),
        body_text_override=t(NO_DIAGNOSTIC_TESTS_CONFIGURED, language),
    )
    await wa.send_buttons(
        to=phone,
        body_text="​",
        buttons=[
            {"id": BACK_ID, "title": t(BACK_OPTION, language)},
            {"id": GOTO_MAIN_MENU, "title": t(MAIN_MENU_BUTTON, language)},
        ],
    )


async def _send_test_menu(wa: WhatsAppClient, phone: str, hospital_id: int, category: str, connector, language: str = "en") -> None:
    from flows.booking.messages import _send_back_button

    tests = connector.get_diagnostic_tests(hospital_id, category)
    rows = [{"id": str(test["id"]), "title": test["name"]} for test in tests]
    await wa.send_list(
        to=phone,
        body_text=t(SELECT_DIAGNOSTIC_TEST, language),
        button_text=t(VIEW_TESTS_BUTTON, language),
        sections=[{"title": t(DIAGNOSTIC_TESTS_SECTION_TITLE, language), "rows": rows}],
    )
    await _send_back_button(wa, phone, language=language)


async def _on_diagnostic_type_selected(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector, context: dict, language: str = "en",
) -> None:
    """TypeFlow.on_selected hook: replaces the normal "auto-resolve a
    resource, go to steps[0]" behavior (book.py's _proceed_with_appointment_
    type) -- test selection has to come BEFORE any resource is picked, since
    which resource applies depends on which test was chosen."""
    category = context["appointment_type_id"]
    tests = connector.get_diagnostic_tests(hospital_id, category)
    if not tests:
        await _send_no_tests_screen(wa, phone, hospital_id, sessions, context, connector, language)
        return
    history = _push_history(context, STATE_AWAITING_APPOINTMENT_TYPE)
    new_context = {**context, _HISTORY_KEY: history}
    sessions.set(hospital_id, phone, STATE_AWAITING_DIAGNOSTIC_TEST, new_context)
    await _send_test_menu(wa, phone, hospital_id, category, connector, language=language)


async def resolve_resource_and_advance_to_date(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, resource_id: "int | None",
    resource_name: "str | None", connector, language: str = "en",
) -> None:
    """Checks resource_id (a diagnostic_tests.id -- tests/resources merged
    into one entity, a test IS the schedulable resource) has open slots, then
    advances straight to date selection. Shared by Diagnostic Test's
    single-item flow (_handle_awaiting_diagnostic_test below) and Lab Test's
    basket flow (flows/booking/types/lab.py) -- both bind exactly one test
    per booking, just sourced differently (the one selected test vs. the
    first basket item). Diagnostic tests never have a department (migration
    0035 made appointments.department_id nullable for exactly this reason).

    Confirmed with the user directly: no test linked, or a genuinely-
    configured test with zero CURRENT slots, both just mean "not available
    right now" -- the SAME "no slots available" treatment an unconfigured
    doctor already gets elsewhere in this app (a doctor with no working
    hours set simply generates zero slots). This deliberately no longer
    falls back to book.py's _first_available_resource (silently borrowing an
    unrelated doctor's calendar) -- a lab/diagnostic test's availability must
    reflect its OWN capacity, never a doctor's."""
    from flows.booking.messages import _notify_no_slots_available, _send_date_menu

    if resource_id is None or not connector.get_available_resource_slots(hospital_id, resource_id):
        display_name = resource_name or context.get("appointment_type_label", "this test")
        await _notify_no_slots_available(wa, sessions, hospital_id, phone, display_name, language=language)
        return
    new_context = {
        **context,
        "resource_id": resource_id, "doctor_id": None, "doctor_name": resource_name,
        "department_id": None, "department_name": "",
    }
    sessions.set(hospital_id, phone, STATE_AWAITING_DATE, new_context)
    await _send_date_menu(wa, phone, hospital_id, None, resource_name, connector, language=language, resource_id=resource_id)


async def _handle_awaiting_diagnostic_test(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    from flows.booking.messages import _handle_back_navigation

    category = context.get("appointment_type_id")
    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        tests = connector.get_diagnostic_tests(hospital_id, category)
        # Row ids are the test's integer id, stringified -- str() both sides,
        # same reasoning daycare.py's duration-option lookup documents (a
        # WhatsApp reply id is always a string).
        test = next((test for test in tests if str(test["id"]) == reply["id"]), None)
        if test is not None:
            new_context = {
                **context,
                "diagnostic_test_id": test["id"], "diagnostic_test_name": test["name"],
                "diagnostic_price": test.get("price"),
                _HISTORY_KEY: _push_history(context, STATE_AWAITING_DIAGNOSTIC_TEST),
            }
            await resolve_resource_and_advance_to_date(
                wa, sessions, phone, hospital_id, new_context, test["id"], test["name"], connector, language=language,
            )
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_DIAGNOSTIC_TEST, context)
    await _send_test_menu(wa, phone, hospital_id, category, connector, language=language)


async def _on_diagnostic_booking_confirmed(appointment, connector, context: dict) -> None:
    """Fresh booking only -- context["diagnostic_test_id"] is set by
    _handle_awaiting_diagnostic_test right before confirmation. A
    reschedule's context never has it (that flow only re-asks date/time):
    Tier1Connector.reschedule_booking() already carries the ORIGINAL
    appointment's own diagnostic fields onto the new row at creation time,
    so this is correctly a no-op for that call site."""
    test_id = context.get("diagnostic_test_id")
    if test_id is not None:
        connector.set_appointment_diagnostic_label_and_price(
            appointment.hospital_id, appointment.id,
            context.get("diagnostic_test_name"), context.get("diagnostic_price"),
        )


def _build_diagnostic_confirmation_summary(context: dict, hospital_id: int) -> str:
    """TypeFlow.build_confirmation_summary hook -- the spec's Step 6 review
    card."""
    language = context.get("language", "en")
    patient = db.get_patient(hospital_id, context.get("active_patient_id"))
    hospital = db.get_hospital(hospital_id)
    price = context.get("diagnostic_price")
    amount_line = ""
    if price is not None:
        amount = int(price) if price == int(price) else price
        amount_line = t(DIAGNOSTIC_AMOUNT_LINE, language, amount=amount)
    return t(
        DIAGNOSTIC_CONFIRMATION_SUMMARY, language,
        appointment_type_label=context.get("appointment_type_label"),
        patient_name=context.get("patient_name"),
        patient_code=(patient.get("patient_display_id") if patient else None) or "—",
        test_name=context.get("diagnostic_test_name"),
        hospital_name=hospital.name if hospital else "",
        date_label=context.get("date_label"), time_label=context.get("slot_time"),
        amount_line=amount_line,
    )


def _build_diagnostic_success_summary(appointment, context: dict, hospital_id: int) -> str:
    """TypeFlow.build_success_summary hook -- the spec's Step 3.3 confirmation."""
    language = context.get("language", "en")
    return t(
        DIAGNOSTIC_BOOKING_CONFIRMED, language,
        appointment_type_label=context.get("appointment_type_label"),
        reference_id=appointment.reference_id,
        patient_name=context.get("patient_name"),
        test_name=context.get("diagnostic_test_name"),
        date_label=appointment.scheduled_at.strftime("%d %b %Y"),
        time_label=appointment.scheduled_at.strftime("%I:%M %p"),
    )


def make_flow(type_id: str) -> TypeFlow:
    """diagnostic.py/lab.py both call this with their own type_id -- every
    handler above derives which category to query from
    context["appointment_type_id"] (identical to diagnostic_tests.category),
    so there's exactly one implementation shared by both types."""
    return TypeFlow(
        type_id=type_id,
        steps=_STEPS,
        on_selected=_on_diagnostic_type_selected,
        on_booking_confirmed=_on_diagnostic_booking_confirmed,
        build_confirmation_summary=_build_diagnostic_confirmation_summary,
        build_success_summary=_build_diagnostic_success_summary,
    )

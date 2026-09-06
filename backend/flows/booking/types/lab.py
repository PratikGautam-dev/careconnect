# flows/booking/types/lab.py
"""Lab Test Phase 2 follow-up (business spec Sections 4.1-4.4): unlike
Diagnostic Test (_diagnostic_shared.py -- one test, one machine, one slot),
Lab Test is a multi-test BASKET with its own collection-method (visit vs.
home sample collection, serviceability-gated)/address steps before date/time,
an itemized price review, and a post-booking report lifecycle (see
db.set_lab_status / portal/routes/documents.py's upload-triggered
"report_ready" notification). No longer shares an implementation with
diagnostic.py -- the shapes are genuinely different (one item vs. a basket)
and reuse would mean branching every handler on "is this a basket or not,"
which is worse than two small dedicated flows sharing only the pieces that
are actually identical (the catalog fetch/no-tests screen and the
resource-resolution-then-date-menu tail, both imported from
_diagnostic_shared.py).

messages.py imports are lazy (inside functions), same cycle-avoidance reason
_diagnostic_shared.py/daycare.py/followup.py already use."""
import db.repository as db
from core.translations import t
from core.translations.booking import (
    ASK_COLLECTION_ADDRESS,
    ASK_COLLECTION_ADDRESS_WITH_SUGGESTION,
    ASK_COLLECTION_PINCODE,
    COLLECTION_HOME_BUTTON,
    COLLECTION_VISIT_BUTTON,
    DIAGNOSTIC_TESTS_SECTION_TITLE,
    DIAGNOSTIC_VARIANTS_SECTION_TITLE,
    LAB_BOOKING_CONFIRMED,
    LAB_CONFIRMATION_SUMMARY,
    LAB_DONE_BUTTON,
    LAB_FASTING_LINE,
    LAB_HOME_COLLECTION_LINE,
    LAB_TEST_ADDED_PROMPT,
    LAB_TEST_CHARGES_LINE,
    LAB_TOTAL_LINE,
    NOT_SERVICEABLE_PINCODE,
    NO_DIAGNOSTIC_TESTS_CONFIGURED,
    SELECT_COLLECTION_METHOD,
    SELECT_DIAGNOSTIC_VARIANT,
    SELECT_LAB_TEST,
    TRY_ANOTHER_PINCODE_BUTTON,
    VIEW_TESTS_BUTTON,
    VIEW_VARIANTS_BUTTON,
)
from core.translations.common import BACK_OPTION
from core.translations.menu import MAIN_MENU_BUTTON
from core.whatsapp import WhatsAppClient

from flows.booking.state import (
    BACK_ID, GOTO_MAIN_MENU, STATE_AWAITING_APPOINTMENT_TYPE, STATE_AWAITING_COLLECTION_ADDRESS,
    STATE_AWAITING_COLLECTION_METHOD, STATE_AWAITING_COLLECTION_PINCODE, STATE_AWAITING_CONFIRMATION,
    STATE_AWAITING_DATE, STATE_AWAITING_LAB_TEST, STATE_AWAITING_LAB_TEST_VARIANT,
    STATE_AWAITING_TIME_SLOT, _HISTORY_KEY, _push_history,
)
from flows.booking.types.base import TypeFlow

# Left out of _STEPS on purpose (same precedent as followup.py's own
# STATE_AWAITING_FOLLOWUP_SELECTION): these are "detour" states reached only
# through this module's own on_selected-driven chain, never through
# TypeFlow.next_step()'s flat forward walk. STATE_AWAITING_COLLECTION_METHOD
# IS included -- messages.py's change-selection menu uses flow.has_step() on
# it to decide whether to offer "Change Collection Method".
_STEPS = (STATE_AWAITING_COLLECTION_METHOD, STATE_AWAITING_DATE, STATE_AWAITING_TIME_SLOT, STATE_AWAITING_CONFIRMATION)

COLLECTION_VISIT_ID = "collection_visit"
COLLECTION_HOME_ID = "collection_home"
LAB_DONE_ID = "lab_done"
TRY_ANOTHER_PINCODE_ID = "try_another_pincode"


def _basket(context: dict) -> list[dict]:
    return context.get("lab_basket") or []


def _basket_resource_id(context: dict) -> "str | None":
    return next((item["resource_id"] for item in _basket(context) if item.get("resource_id")), None)


async def _send_no_tests_screen(wa, phone: str, hospital_id: int, sessions, context: dict, connector, language: str) -> None:
    """Mirrors _diagnostic_shared.py's own version -- kept as a thin local
    copy rather than importing it, since that one hardcodes
    STATE_AWAITING_DIAGNOSTIC_TEST-shaped resend behavior it doesn't need
    here; the body (no active tests -> back to appointment-type list) is
    otherwise identical."""
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


async def _send_lab_test_menu(
    wa: WhatsAppClient, phone: str, hospital_id: int, connector, basket: list[dict], language: str = "en",
    body_text_override: str | None = None,
) -> None:
    """Excludes tests already in the basket -- re-adding the same test would
    just be confusing (and there's no "quantity" concept here). Skips the
    list message once every configured test is already in the basket
    (WhatsApp's list type can't render zero rows sensibly), falling back to
    just body_text_override as plain text if given.

    WhatsApp menu restructuring follow-up (confirmed with the user): once
    the basket has at least one item, the follow-up buttons message offers
    "Done, Continue" alongside "Back" -- picking another test happens
    straight from this same list (re-shown after every add, via
    _add_to_basket_and_prompt below), not a separate "would you like to add
    another test?" detour screen first."""
    already_added = {item["diagnostic_test_id"] for item in basket if item.get("diagnostic_test_id") is not None}
    tests = [t_ for t_ in connector.get_diagnostic_tests(hospital_id, "lab") if t_["id"] not in already_added]
    if tests:
        rows = [{"id": str(test["id"]), "title": test["name"]} for test in tests]
        await wa.send_list(
            to=phone,
            body_text=body_text_override or t(SELECT_LAB_TEST, language),
            button_text=t(VIEW_TESTS_BUTTON, language),
            sections=[{"title": t(DIAGNOSTIC_TESTS_SECTION_TITLE, language), "rows": rows}],
        )
    elif body_text_override:
        await wa.send_text(phone, body_text_override)
    buttons = [{"id": BACK_ID, "title": t(BACK_OPTION, language)}]
    if basket:
        buttons.append({"id": LAB_DONE_ID, "title": t(LAB_DONE_BUTTON, language)})
    await wa.send_buttons(to=phone, body_text="​", buttons=buttons)


async def _send_lab_variant_menu(wa: WhatsAppClient, phone: str, test: dict, language: str = "en") -> None:
    from flows.booking.messages import _send_back_button

    rows = [{"id": str(v["id"]), "title": v["label"]} for v in test["variants"]]
    await wa.send_list(
        to=phone,
        body_text=t(SELECT_DIAGNOSTIC_VARIANT, language, test_name=test["name"]),
        button_text=t(VIEW_VARIANTS_BUTTON, language),
        sections=[{"title": t(DIAGNOSTIC_VARIANTS_SECTION_TITLE, language), "rows": rows}],
    )
    await _send_back_button(wa, phone, language=language)


async def _on_lab_type_selected(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector, context: dict, language: str = "en",
) -> None:
    """TypeFlow.on_selected hook: test selection has to come before any
    resource is picked (which resource applies depends on the basket)."""
    tests = connector.get_diagnostic_tests(hospital_id, "lab")
    if not tests:
        await _send_no_tests_screen(wa, phone, hospital_id, sessions, context, connector, language)
        return
    history = _push_history(context, STATE_AWAITING_APPOINTMENT_TYPE)
    new_context = {**context, "lab_basket": [], _HISTORY_KEY: history}
    sessions.set(hospital_id, phone, STATE_AWAITING_LAB_TEST, new_context)
    await _send_lab_test_menu(wa, phone, hospital_id, connector, [], language=language)


async def _add_to_basket_and_prompt(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, context: dict, test: dict, variant: dict,
    connector, language: str = "en",
) -> None:
    item = {
        "diagnostic_test_id": test["id"], "diagnostic_test_variant_id": variant["id"],
        "test_label": test["name"], "variant_label": variant["label"], "price": variant.get("price"),
        "resource_id": test.get("resource_id"), "preparation_instructions": variant.get("preparation_instructions"),
    }
    basket = [*_basket(context), item]
    new_context = {**context, "lab_basket": basket}
    sessions.set(hospital_id, phone, STATE_AWAITING_LAB_TEST, new_context)
    item_label = test["name"] if variant["label"].lower() == "standard" else f"{test['name']} - {variant['label']}"
    await _send_lab_test_menu(
        wa, phone, hospital_id, connector, basket, language=language,
        body_text_override=t(LAB_TEST_ADDED_PROMPT, language, item_label=item_label),
    )


async def _handle_awaiting_lab_test(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    from flows.booking.messages import _handle_back_navigation

    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        if reply["id"] == LAB_DONE_ID and _basket(context):
            history = _push_history(context, STATE_AWAITING_LAB_TEST)
            new_context = {**context, _HISTORY_KEY: history}
            sessions.set(hospital_id, phone, STATE_AWAITING_COLLECTION_METHOD, new_context)
            await _send_collection_method_menu(wa, phone, language=language)
            return
        already_added = {item["diagnostic_test_id"] for item in _basket(context) if item.get("diagnostic_test_id") is not None}
        tests = [t_ for t_ in connector.get_diagnostic_tests(hospital_id, "lab") if t_["id"] not in already_added]
        test = next((t_ for t_ in tests if str(t_["id"]) == reply["id"]), None)
        if test is not None:
            base_context = {
                **context, "_lab_pending_test_id": test["id"],
                _HISTORY_KEY: _push_history(context, STATE_AWAITING_LAB_TEST),
            }
            variants = test["variants"]
            if len(variants) == 1:
                await _add_to_basket_and_prompt(wa, sessions, phone, hospital_id, base_context, test, variants[0], connector, language=language)
                return
            sessions.set(hospital_id, phone, STATE_AWAITING_LAB_TEST_VARIANT, base_context)
            await _send_lab_variant_menu(wa, phone, test, language=language)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_LAB_TEST, context)
    await _send_lab_test_menu(wa, phone, hospital_id, connector, _basket(context), language=language)


async def _handle_awaiting_lab_test_variant(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    from flows.booking.messages import _handle_back_navigation

    test_id = context.get("_lab_pending_test_id")
    # Never trust a stashed list -- re-fetch fresh, same discipline every
    # other list step in this codebase follows.
    tests = connector.get_diagnostic_tests(hospital_id, "lab")
    test = next((t_ for t_ in tests if t_["id"] == test_id), None)
    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        if test is not None:
            variant = next((v for v in test["variants"] if str(v["id"]) == reply["id"]), None)
            if variant is not None:
                await _add_to_basket_and_prompt(wa, sessions, phone, hospital_id, context, test, variant, connector, language=language)
                return
    if test is None:
        # The test itself was deactivated/removed mid-flow.
        sessions.set(hospital_id, phone, STATE_AWAITING_LAB_TEST, context)
        await _send_lab_test_menu(wa, phone, hospital_id, connector, _basket(context), language=language)
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_LAB_TEST_VARIANT, context)
    await _send_lab_variant_menu(wa, phone, test, language=language)


async def _send_collection_method_menu(wa: WhatsAppClient, phone: str, language: str = "en") -> None:
    await wa.send_buttons(
        to=phone,
        body_text=t(SELECT_COLLECTION_METHOD, language),
        buttons=[
            {"id": COLLECTION_VISIT_ID, "title": t(COLLECTION_VISIT_BUTTON, language)},
            {"id": COLLECTION_HOME_ID, "title": t(COLLECTION_HOME_BUTTON, language)},
            {"id": BACK_ID, "title": t(BACK_OPTION, language)},
        ],
    )


async def _handle_awaiting_collection_method(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    from flows.booking.messages import _handle_back_navigation
    from flows.booking.types._diagnostic_shared import resolve_resource_and_advance_to_date

    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        if reply["id"] == COLLECTION_VISIT_ID:
            new_context = {
                **context, "collection_method": "visit",
                "collection_pincode": None, "collection_address": None, "home_collection_charge": None,
                _HISTORY_KEY: _push_history(context, STATE_AWAITING_COLLECTION_METHOD),
            }
            await resolve_resource_and_advance_to_date(
                wa, sessions, phone, hospital_id, new_context, _basket_resource_id(new_context), connector, language=language,
            )
            return
        if reply["id"] == COLLECTION_HOME_ID:
            new_context = {
                **context, "collection_method": "home",
                _HISTORY_KEY: _push_history(context, STATE_AWAITING_COLLECTION_METHOD),
            }
            sessions.set(hospital_id, phone, STATE_AWAITING_COLLECTION_PINCODE, new_context)
            await wa.send_text(phone, t(ASK_COLLECTION_PINCODE, language))
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_COLLECTION_METHOD, context)
    await _send_collection_method_menu(wa, phone, language=language)


async def _handle_awaiting_collection_pincode(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Free-text step (same "no Back offered" convention as patient name/age)
    -- the fallback buttons shown on a non-serviceable PIN are handled here
    too, since core/flows/router.py delivers a button tap through this same
    state's handler regardless of whether the previous message was text or
    buttons."""
    from flows.booking.types._diagnostic_shared import resolve_resource_and_advance_to_date

    if reply["type"] == "interactive_reply" and reply["id"] == COLLECTION_VISIT_ID:
        new_context = {
            **context, "collection_method": "visit",
            "collection_pincode": None, "collection_address": None, "home_collection_charge": None,
        }
        await resolve_resource_and_advance_to_date(
            wa, sessions, phone, hospital_id, new_context, _basket_resource_id(new_context), connector, language=language,
        )
        return
    if reply["type"] == "text" and reply["text"].strip():
        pincode = reply["text"].strip()
        if connector.is_pincode_serviceable(hospital_id, pincode):
            charge = db.get_hospital_settings(hospital_id)["home_collection_charge"]
            new_context = {**context, "collection_pincode": pincode, "home_collection_charge": charge}
            sessions.set(hospital_id, phone, STATE_AWAITING_COLLECTION_ADDRESS, new_context)
            await _send_collection_address_prompt(wa, phone, hospital_id, new_context, language=language)
            return
        sessions.set(hospital_id, phone, STATE_AWAITING_COLLECTION_PINCODE, context)
        await wa.send_buttons(
            to=phone,
            body_text=t(NOT_SERVICEABLE_PINCODE, language),
            buttons=[
                {"id": COLLECTION_VISIT_ID, "title": t(COLLECTION_VISIT_BUTTON, language)},
                {"id": TRY_ANOTHER_PINCODE_ID, "title": t(TRY_ANOTHER_PINCODE_BUTTON, language)},
            ],
        )
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_COLLECTION_PINCODE, context)
    await wa.send_text(phone, t(ASK_COLLECTION_PINCODE, language))


async def _send_collection_address_prompt(wa: WhatsAppClient, phone: str, hospital_id: int, context: dict, language: str = "en") -> None:
    patient = db.get_patient(hospital_id, context.get("active_patient_id"))
    suggestion = patient.get("address") if patient else None
    if suggestion:
        await wa.send_text(phone, t(ASK_COLLECTION_ADDRESS_WITH_SUGGESTION, language, address=suggestion))
    else:
        await wa.send_text(phone, t(ASK_COLLECTION_ADDRESS, language))


async def _handle_awaiting_collection_address(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    from flows.booking.types._diagnostic_shared import resolve_resource_and_advance_to_date

    if reply["type"] == "text" and reply["text"].strip():
        text = reply["text"].strip()
        if text.lower() == "same":
            patient = db.get_patient(hospital_id, context.get("active_patient_id"))
            address = (patient.get("address") if patient else None) or text
        else:
            address = text
        new_context = {**context, "collection_address": address}
        await resolve_resource_and_advance_to_date(
            wa, sessions, phone, hospital_id, new_context, _basket_resource_id(new_context), connector, language=language,
        )
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_COLLECTION_ADDRESS, context)
    await _send_collection_address_prompt(wa, phone, hospital_id, context, language=language)


def _fasting_block(basket: list[dict], language: str) -> str:
    """Union of non-blank preparation_instructions across the basket,
    de-duplicated -- omitted entirely if none of the selected tests need any
    (per the spec's own "don't show generic fasting instructions if the
    selected tests don't require fasting" rule)."""
    seen: list[str] = []
    for item in basket:
        instructions = (item.get("preparation_instructions") or "").strip()
        if instructions and instructions not in seen:
            seen.append(instructions)
    if not seen:
        return ""
    return t(LAB_FASTING_LINE, language, instructions="; ".join(seen))


def _amount_block(basket: list[dict], home_collection_charge, language: str) -> str:
    prices = [item["price"] for item in basket if item.get("price") is not None]
    if not prices and home_collection_charge is None:
        return ""
    test_total = sum(prices)
    block = ""
    if prices:
        amount = int(test_total) if test_total == int(test_total) else test_total
        block += t(LAB_TEST_CHARGES_LINE, language, amount=amount)
    if home_collection_charge:
        amount = int(home_collection_charge) if home_collection_charge == int(home_collection_charge) else home_collection_charge
        block += t(LAB_HOME_COLLECTION_LINE, language, amount=amount)
    total = test_total + (home_collection_charge or 0)
    amount = int(total) if total == int(total) else total
    block += t(LAB_TOTAL_LINE, language, amount=amount)
    return block


def _tests_block(basket: list[dict]) -> str:
    lines = []
    for item in basket:
        label = item["test_label"] if item["variant_label"].lower() == "standard" else f"{item['test_label']} - {item['variant_label']}"
        lines.append(f"🧪 {label}")
    return "\n".join(lines) + "\n" if lines else ""


def _collection_line(context: dict, language: str) -> str:
    if context.get("collection_method") == "home":
        address = context.get("collection_address") or ""
        return f"🏠 Collection: Home Sample Collection\n📍 Address: {address}\n" if language != "hi" else \
            f"🏠 कलेक्शन: होम सैंपल कलेक्शन\n📍 पता: {address}\n"
    return "🏥 Collection: Visit Hospital/Lab\n" if language != "hi" else "🏥 कलेक्शन: अस्पताल/लैब जाएं\n"


def _build_lab_confirmation_summary(context: dict, hospital_id: int) -> str:
    """TypeFlow.build_confirmation_summary hook -- the spec's Step 6 itemized
    review card."""
    language = context.get("language", "en")
    patient = db.get_patient(hospital_id, context.get("active_patient_id"))
    basket = _basket(context)
    return t(
        LAB_CONFIRMATION_SUMMARY, language,
        appointment_type_label=context.get("appointment_type_label"),
        patient_name=context.get("patient_name"),
        patient_code=(patient.get("patient_display_id") if patient else None) or "—",
        tests_block=_tests_block(basket),
        collection_line=_collection_line(context, language),
        date_label=context.get("date_label"), time_label=context.get("slot_time"),
        amount_block=_amount_block(basket, context.get("home_collection_charge"), language),
        fasting_block=_fasting_block(basket, language),
    )


def _build_lab_success_summary(appointment, context: dict, hospital_id: int) -> str:
    """TypeFlow.build_success_summary hook -- the spec's post-booking
    confirmation; the report-lifecycle notification itself is sent later,
    separately, when staff upload the actual report (portal/routes/documents.py)."""
    language = context.get("language", "en")
    return t(
        LAB_BOOKING_CONFIRMED, language,
        appointment_type_label=context.get("appointment_type_label"),
        reference_id=appointment.reference_id,
        patient_name=context.get("patient_name"),
        test_count=len(_basket(context)),
        collection_line=_collection_line(context, language),
        date_label=appointment.scheduled_at.strftime("%d %b %Y"),
        time_label=appointment.scheduled_at.strftime("%I:%M %p"),
    )


async def _on_lab_booking_confirmed(appointment, connector, context: dict) -> None:
    """Fresh booking only -- context["lab_basket"] is only ever set by
    on_selected's chain, never by the reschedule flow (Tier1Connector.
    reschedule_booking() carries the basket forward itself, via
    repo.copy_lab_basket(), directly at appointment-creation time), so this
    is correctly a no-op for that call site (same pattern daycare/diagnostic
    use for their own on_booking_confirmed hooks)."""
    basket = context.get("lab_basket")
    if not basket:
        return
    basket_items = [
        {
            "diagnostic_test_id": item.get("diagnostic_test_id"), "diagnostic_test_variant_id": item.get("diagnostic_test_variant_id"),
            "test_label": item["test_label"], "variant_label": item["variant_label"],
            "price": item.get("price"), "preparation_instructions": item.get("preparation_instructions"),
        }
        for item in basket
    ]
    connector.set_appointment_lab_order_details(
        appointment.hospital_id, appointment.id, context.get("collection_method"), context.get("collection_address"),
        context.get("collection_pincode"), context.get("home_collection_charge"), basket_items,
    )


FLOW = TypeFlow(
    type_id="lab",
    steps=_STEPS,
    on_selected=_on_lab_type_selected,
    on_booking_confirmed=_on_lab_booking_confirmed,
    build_confirmation_summary=_build_lab_confirmation_summary,
    build_success_summary=_build_lab_success_summary,
)

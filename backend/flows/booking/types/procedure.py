# flows/booking/types/procedure.py
"""Daycare/Procedure rebuild: replaces the old duration-picker flow
(flows/booking/types/daycare.py, deleted) entirely. Step 1 picks a procedure
from its own catalog (category + booking mode) instead of a
department/doctor; from there the flow forks:

- INSTANT_BOOKING: straight into the normal STATE_AWAITING_DATE/TIME_SLOT/
  CONFIRMATION steps, reused as-is (book.py's _get_slots()/_send_date_menu/
  _send_time_menu already branch on a `procedure_id` the same way they
  already branch on Diagnostic/Lab's `resource_id`) -- confirming creates
  the appointment (with its N bed/chair/equipment/staff resources reserved
  atomically) via connector.create_procedure_booking().
- APPROVAL_REQUIRED: a dedicated pre-send review screen
  (STATE_AWAITING_PROCEDURE_REQUEST_CONFIRM, this module's own handler,
  never reaching STATE_AWAITING_CONFIRMATION at all) creates a REQUESTED row
  with no slot chosen yet (connector.create_procedure_request()). Once staff
  approve it (portal/routes/bookings.py), a proactive WhatsApp message with
  a quick-action button resumes the SAME appointment straight into
  STATE_AWAITING_DATE (context["_procedure_appointment_id"] tells book.py's
  _create_booking_and_notify to update that existing row in place, via
  connector.confirm_procedure_appointment(), instead of creating a new one).

messages.py imports are lazy (inside functions), same cycle-avoidance reason
_diagnostic_shared.py/lab.py/followup.py already use."""
import db.repository as db
from core.translations import t
from core.translations.booking import (
    BOOKING_NOT_CONFIRMED,
    CANCEL_BUTTON,
    CONFIRM_BUTTON,
    NO_PROCEDURES_CONFIGURED,
    PROCEDURES_SECTION_TITLE,
    PROCEDURE_APPROVED,
    PROCEDURE_BOOKING_CONFIRMED,
    PROCEDURE_CONFIRMATION_SUMMARY,
    PROCEDURE_ESTIMATE_LINE,
    PROCEDURE_INSTRUCTIONS_LINE,
    PROCEDURE_ORDER_REFERENCE_LINE,
    PROCEDURE_REQUEST_CONFIRM_SUMMARY,
    PROCEDURE_REQUEST_SUBMITTED,
    PROCEDURE_RESCHEDULE_REQUESTED,
    PROCEDURE_RESCHEDULE_REQUEST_PROMPT,
    SELECT_PROCEDURE,
    VIEW_PROCEDURES_BUTTON,
)
from core.translations.common import BACK_OPTION
from core.translations.menu import MAIN_MENU_BUTTON
from core.whatsapp import WhatsAppClient

from flows.booking.state import (
    BACK_ID, CONFIRM_NO, CONFIRM_YES, GOTO_MAIN_MENU, STATE_AWAITING_APPOINTMENT_TYPE,
    STATE_AWAITING_DATE, STATE_AWAITING_PROCEDURE, STATE_AWAITING_PROCEDURE_REQUEST_CONFIRM,
    STATE_AWAITING_PROCEDURE_RESCHEDULE_DATE, STATE_AWAITING_PROCEDURE_RESCHEDULE_SLOT,
    _HISTORY_KEY, _date_label, _find_by_id, _push_history,
)
from flows.booking.types.base import TypeFlow

# Left flat (only Step 1) on purpose, same "detour states reached only
# through this module's own chain" precedent lab.py's basket steps
# establish: instant bookings continue through the ordinary shared
# STATE_AWAITING_DATE/TIME_SLOT/CONFIRMATION steps (not listed here, since
# they're not THIS type's own extra steps), and approval-required bookings
# detour through STATE_AWAITING_PROCEDURE_REQUEST_CONFIRM instead, never
# reaching STATE_AWAITING_CONFIRMATION at all.
_STEPS = (STATE_AWAITING_PROCEDURE,)


def _instructions_text(instructions: list[dict]) -> str:
    return "; ".join(i["instruction_text"] for i in instructions if i.get("instruction_text"))


def _estimate_line(price_min, price_max, language: str) -> str:
    if price_min is None and price_max is None:
        return ""
    if price_min is not None and price_max is not None and price_min != price_max:
        amount = f"{price_min:g}–{price_max:g}"
    else:
        value = price_min if price_min is not None else price_max
        amount = f"{value:g}"
    return t(PROCEDURE_ESTIMATE_LINE, language, amount=amount)


async def _send_procedure_menu(wa: WhatsAppClient, phone: str, hospital_id: int, connector, language: str = "en") -> None:
    from flows.booking.messages import _send_back_button

    procedures = connector.get_procedures(hospital_id)
    rows = [{"id": str(p["id"]), "title": p["name"]} for p in procedures]
    await wa.send_list(
        to=phone,
        body_text=t(SELECT_PROCEDURE, language),
        button_text=t(VIEW_PROCEDURES_BUTTON, language),
        sections=[{"title": t(PROCEDURES_SECTION_TITLE, language), "rows": rows}],
    )
    await _send_back_button(wa, phone, language=language)


async def _send_no_procedures_screen(wa, phone: str, hospital_id: int, sessions, context: dict, connector, language: str) -> None:
    """Mirrors lab.py's own _send_no_tests_screen -- no active procedures
    configured, back to the appointment-type list rather than a dead end."""
    from flows.booking.messages import _send_appointment_type_menu

    sessions.set(hospital_id, phone, STATE_AWAITING_APPOINTMENT_TYPE, context)
    await _send_appointment_type_menu(
        wa, phone, hospital_id, connector, language=language, category=context.get("appointment_type_category"),
        body_text_override=t(NO_PROCEDURES_CONFIGURED, language),
    )
    await wa.send_buttons(
        to=phone,
        body_text="​",
        buttons=[
            {"id": BACK_ID, "title": t(BACK_OPTION, language)},
            {"id": GOTO_MAIN_MENU, "title": t(MAIN_MENU_BUTTON, language)},
        ],
    )


async def _on_procedure_type_selected(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, connector, context: dict, language: str = "en",
) -> None:
    """TypeFlow.on_selected: Step 1 shows the procedure catalog instead of
    department selection."""
    procedures = connector.get_procedures(hospital_id)
    if not procedures:
        await _send_no_procedures_screen(wa, phone, hospital_id, sessions, context, connector, language)
        return
    history = _push_history(context, STATE_AWAITING_APPOINTMENT_TYPE)
    new_context = {**context, _HISTORY_KEY: history}
    sessions.set(hospital_id, phone, STATE_AWAITING_PROCEDURE, new_context)
    await _send_procedure_menu(wa, phone, hospital_id, connector, language=language)


def _resolve_department(connector, hospital_id: int, procedure: dict) -> tuple[str | None, str]:
    """Same "resource has no department configured -> fall back to the
    hospital's first one" precedent _diagnostic_shared.py's
    resolve_resource_and_advance_to_date() already establishes."""
    department_id = procedure.get("department_id")
    if department_id:
        dept = next((d for d in connector.get_departments(hospital_id) if d["id"] == department_id), None)
        if dept:
            return department_id, dept["name"]
    departments = connector.get_departments(hospital_id)
    if departments:
        return departments[0]["id"], departments[0]["name"]
    return None, ""


async def _handle_awaiting_procedure(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    from flows.booking.messages import _handle_back_navigation, _notify_no_slots_available, _send_date_menu

    if reply["type"] == "interactive_reply":
        if reply["id"] == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        procedures = connector.get_procedures(hospital_id)
        procedure = next((p for p in procedures if str(p["id"]) == reply["id"]), None)
        if procedure is not None:
            department_id, department_name = _resolve_department(connector, hospital_id, procedure)
            base_context = {
                **context,
                "procedure_id": procedure["id"], "procedure_name": procedure["name"],
                "procedure_estimated_price_min": procedure.get("estimated_price_min"),
                "procedure_estimated_price_max": procedure.get("estimated_price_max"),
                "procedure_instructions": _instructions_text(procedure.get("instructions") or []),
                "department_id": department_id, "department_name": department_name,
                "doctor_id": None, "doctor_name": procedure["name"],
                _HISTORY_KEY: _push_history(context, STATE_AWAITING_PROCEDURE),
            }
            if procedure["booking_mode"] == "approval_required":
                # Re-picking a procedure the patient already has an open
                # request for resumes it instead of creating a duplicate --
                # an APPROVED one skips straight to date/time (this
                # appointment already exists; confirming it updates that row
                # in place via connector.confirm_procedure_appointment(),
                # see book.py's context["_procedure_appointment_id"] branch).
                pending = connector.get_pending_procedure_request(hospital_id, phone, procedure["id"])
                if pending is not None and pending.procedure_status == "APPROVED":
                    resume_context = {**base_context, "_procedure_appointment_id": pending.id}
                    if not connector.get_procedure_available_slots(hospital_id, procedure["id"]):
                        await _notify_no_slots_available(wa, sessions, hospital_id, phone, procedure["name"], language=language)
                        return
                    sessions.set(hospital_id, phone, STATE_AWAITING_DATE, resume_context)
                    await _send_date_menu(
                        wa, phone, hospital_id, None, procedure["name"], connector, language=language,
                        procedure_id=procedure["id"],
                    )
                    return
                if pending is not None:
                    await wa.send_text(phone, t(PROCEDURE_REQUEST_SUBMITTED, language))
                    sessions.reset(hospital_id, phone)
                    return
                sessions.set(hospital_id, phone, STATE_AWAITING_PROCEDURE_REQUEST_CONFIRM, base_context)
                await _send_procedure_request_confirm(wa, phone, hospital_id, base_context, language=language)
                return
            if not connector.get_procedure_available_slots(hospital_id, procedure["id"]):
                await _notify_no_slots_available(wa, sessions, hospital_id, phone, procedure["name"], language=language)
                return
            sessions.set(hospital_id, phone, STATE_AWAITING_DATE, base_context)
            await _send_date_menu(
                wa, phone, hospital_id, None, procedure["name"], connector, language=language,
                procedure_id=procedure["id"],
            )
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_PROCEDURE, context)
    await _send_procedure_menu(wa, phone, hospital_id, connector, language=language)


async def _send_procedure_request_confirm(wa: WhatsAppClient, phone: str, hospital_id: int, context: dict, language: str = "en") -> None:
    language = context.get("language", language)
    summary = t(
        PROCEDURE_REQUEST_CONFIRM_SUMMARY, language,
        patient_name=context.get("patient_name"),
        procedure_name=context.get("procedure_name"),
        estimate_line=_estimate_line(
            context.get("procedure_estimated_price_min"), context.get("procedure_estimated_price_max"), language,
        ),
        instructions_line=(
            t(PROCEDURE_INSTRUCTIONS_LINE, language, instructions=context["procedure_instructions"])
            if context.get("procedure_instructions") else ""
        ),
    )
    await wa.send_buttons(
        to=phone,
        body_text=summary,
        buttons=[
            {"id": CONFIRM_YES, "title": t(CONFIRM_BUTTON, language)},
            {"id": CONFIRM_NO, "title": t(CANCEL_BUTTON, language)},
            {"id": BACK_ID, "title": t(BACK_OPTION, language)},
        ],
    )


async def _handle_awaiting_procedure_request_confirm(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    """Step 3's own confirm-before-sending screen -- CONFIRM_YES here creates
    the REQUESTED row and ends the flow; it never reaches book.py's generic
    _handle_awaiting_confirmation/_create_booking_and_notify at all (no real
    slot exists yet to confirm)."""
    from flows.booking.messages import _handle_back_navigation

    if reply["type"] == "interactive_reply":
        rid = reply["id"]
        if rid == BACK_ID:
            await _handle_back_navigation(wa, sessions, phone, hospital_id, context, connector, language=language)
            return
        if rid == CONFIRM_NO:
            await wa.send_text(phone, t(BOOKING_NOT_CONFIRMED, language))
            sessions.reset(hospital_id, phone)
            return
        if rid == CONFIRM_YES:
            connector.create_procedure_request(
                hospital_id, phone, context["procedure_id"],
                patient_name=context.get("patient_name"), patient_age=context.get("patient_age"),
                patient_id=context.get("active_patient_id"),
            )
            summary = t(PROCEDURE_REQUEST_SUBMITTED, language)
            if closing_message_text:
                summary = f"{summary}\n\n{closing_message_text}"
            await wa.send_text(phone, summary)
            sessions.reset(hospital_id, phone, keep_language=False, keep_active_patient=False)
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_PROCEDURE_REQUEST_CONFIRM, context)
    await _send_procedure_request_confirm(wa, phone, hospital_id, context, language=language)


def _build_procedure_confirmation_summary(context: dict, hospital_id: int) -> str:
    """TypeFlow.build_confirmation_summary hook -- Step 7's review card
    (instant-booking path only; approval-required never reaches this)."""
    language = context.get("language", "en")
    patient = db.get_patient(hospital_id, context.get("active_patient_id"))
    order_reference = context.get("procedure_order_reference")
    return t(
        PROCEDURE_CONFIRMATION_SUMMARY, language,
        appointment_type_label=context.get("appointment_type_label"),
        patient_name=context.get("patient_name"),
        patient_code=(patient.get("patient_display_id") if patient else None) or "—",
        procedure_name=context.get("procedure_name"),
        order_reference_line=(t(PROCEDURE_ORDER_REFERENCE_LINE, language, order_reference=order_reference) if order_reference else ""),
        department_name=context.get("department_name"),
        date_label=context.get("date_label"), time_label=context.get("slot_time"),
        estimate_line=_estimate_line(
            context.get("procedure_estimated_price_min"), context.get("procedure_estimated_price_max"), language,
        ),
        instructions_line=(
            t(PROCEDURE_INSTRUCTIONS_LINE, language, instructions=context["procedure_instructions"])
            if context.get("procedure_instructions") else ""
        ),
    )


def _build_procedure_success_summary(appointment, context: dict, hospital_id: int) -> str:
    """TypeFlow.build_success_summary hook -- the spec's exact confirmation
    shape (instant-booking path, and the post-approval resume-to-confirm
    path, both land here since both ultimately call
    _create_booking_and_notify)."""
    language = context.get("language", "en")
    return t(
        PROCEDURE_BOOKING_CONFIRMED, language,
        reference_id=appointment.reference_id,
        patient_name=context.get("patient_name"),
        procedure_name=appointment.procedure_name or context.get("procedure_name"),
        department_name=appointment.department_name,
        date_label=appointment.scheduled_at.strftime("%d %b %Y"),
        time_label=appointment.scheduled_at.strftime("%I:%M %p"),
    )


FLOW = TypeFlow(
    type_id="daycare",
    steps=_STEPS,
    on_selected=_on_procedure_type_selected,
    build_confirmation_summary=_build_procedure_confirmation_summary,
    build_success_summary=_build_procedure_success_summary,
)


# --- "Request Reschedule" (approval-required procedures only) ---
# A deliberately separate, self-contained mini-flow, not a retrofit of
# flows/booking/reschedule.py's own generic date/time handlers: those always
# end by calling connector.reschedule_booking() (move NOW, no approval gate)
# -- an approval-required procedure's reschedule must instead only ever
# WRITE the desired slot (connector.request_procedure_reschedule()) and wait
# for a portal action to actually move it. Entered from
# reschedule.py::_start_reschedule_flow_for_appointment's own
# `appt.procedure_id is not None` branch.

async def _start_procedure_reschedule_request(wa: WhatsAppClient, sessions, phone: str, hospital_id: int, appt, connector, language: str = "en") -> None:
    from flows.booking.messages import _notify_no_slots_available, _send_date_menu

    if not connector.get_procedure_available_slots(hospital_id, appt.procedure_id):
        await _notify_no_slots_available(wa, sessions, hospital_id, phone, appt.procedure_name or "", language=language)
        return
    await wa.send_text(phone, t(PROCEDURE_RESCHEDULE_REQUEST_PROMPT, language))
    new_context = {
        "reschedule_appointment_id": appt.id, "procedure_id": appt.procedure_id,
        "procedure_name": appt.procedure_name, "doctor_id": None, "doctor_name": appt.procedure_name or "",
    }
    sessions.set(hospital_id, phone, STATE_AWAITING_PROCEDURE_RESCHEDULE_DATE, new_context)
    await _send_date_menu(
        wa, phone, hospital_id, None, appt.procedure_name or "", connector, language=language,
        procedure_id=appt.procedure_id,
    )


async def _handle_awaiting_procedure_reschedule_date(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    from flows.booking.messages import _send_date_menu, _send_main_menu, _send_time_menu

    procedure_id = context.get("procedure_id")
    if procedure_id is None or context.get("reschedule_appointment_id") is None:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    if reply["type"] == "interactive_reply":
        available_dates = {s["date"] for s in connector.get_procedure_available_slots(hospital_id, procedure_id)}
        if reply["id"] in available_dates:
            new_context = {**context, "date": reply["id"], "date_label": _date_label(reply["id"])}
            sessions.set(hospital_id, phone, STATE_AWAITING_PROCEDURE_RESCHEDULE_SLOT, new_context)
            await _send_time_menu(
                wa, phone, hospital_id, None, reply["id"], connector, language=language, procedure_id=procedure_id,
            )
            return
    sessions.set(hospital_id, phone, STATE_AWAITING_PROCEDURE_RESCHEDULE_DATE, context)
    await _send_date_menu(
        wa, phone, hospital_id, None, context.get("doctor_name", ""), connector, language=language,
        procedure_id=procedure_id,
    )


async def _handle_awaiting_procedure_reschedule_slot(
    wa: WhatsAppClient, sessions, phone: str, hospital_id: int, reply: dict, context: dict, connector,
    language: str = "en", closing_message_text: str | None = None,
) -> None:
    from datetime import datetime as _datetime

    from flows.booking.messages import _send_date_menu, _send_main_menu, _send_time_menu

    procedure_id = context.get("procedure_id")
    appointment_id = context.get("reschedule_appointment_id")
    date_str = context.get("date")
    if procedure_id is None or appointment_id is None or not date_str:
        sessions.reset(hospital_id, phone)
        await _send_main_menu(wa, phone, "the hospital", language=language)
        return
    if reply["type"] == "interactive_reply":
        slot = _find_by_id(connector.get_procedure_available_slots(hospital_id, procedure_id), reply["id"])
        if slot and slot["date"] == date_str:
            connector.request_procedure_reschedule(hospital_id, appointment_id, _datetime.fromisoformat(slot["id"]))
            summary = t(PROCEDURE_RESCHEDULE_REQUESTED, language)
            if closing_message_text:
                summary = f"{summary}\n\n{closing_message_text}"
            await wa.send_text(phone, summary)
            sessions.reset(hospital_id, phone)
            return
    if not any(s["date"] == date_str for s in connector.get_procedure_available_slots(hospital_id, procedure_id)):
        sessions.set(hospital_id, phone, STATE_AWAITING_PROCEDURE_RESCHEDULE_DATE, context)
        await _send_date_menu(
            wa, phone, hospital_id, None, context.get("doctor_name", ""), connector, language=language,
            procedure_id=procedure_id,
        )
        return
    sessions.set(hospital_id, phone, STATE_AWAITING_PROCEDURE_RESCHEDULE_SLOT, context)
    await _send_time_menu(
        wa, phone, hospital_id, None, date_str, connector, language=language, procedure_id=procedure_id,
    )

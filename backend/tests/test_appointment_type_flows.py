# tests/test_appointment_type_flows.py
"""Unit tests for flows/booking/types/registry.py -- docs/per-appointment-type-flow-plan.md
Phase 1. No DB/connector needed, pure lookup logic."""
from flows.booking.state import (
    STATE_AWAITING_CONFIRMATION, STATE_AWAITING_DATE, STATE_AWAITING_DAYCARE_DURATION, STATE_AWAITING_DEPARTMENT,
    STATE_AWAITING_DIAGNOSTIC_TEST, STATE_AWAITING_DIAGNOSTIC_VARIANT, STATE_AWAITING_TIME_SLOT,
)
from flows.booking.types.base import FULL_FLOW, NO_DOCTOR_FLOW
from flows.booking.types.registry import get_type_flow


def test_known_types_resolve_to_their_own_flow():
    assert get_type_flow("new").steps == FULL_FLOW
    assert get_type_flow("tele").steps == FULL_FLOW
    assert get_type_flow("second_opinion").steps == FULL_FLOW
    # Phase 2 Step 5: Diagnostic Test/Lab Test insert a test+variant pick
    # BEFORE date/time (not NO_DOCTOR_FLOW verbatim) -- see
    # flows/booking/types/_diagnostic_shared.py, shared by both.
    diagnostic_steps = (
        STATE_AWAITING_DIAGNOSTIC_TEST, STATE_AWAITING_DIAGNOSTIC_VARIANT, STATE_AWAITING_DATE,
        STATE_AWAITING_TIME_SLOT, STATE_AWAITING_CONFIRMATION,
    )
    assert get_type_flow("diagnostic").steps == diagnostic_steps
    assert get_type_flow("lab").steps == diagnostic_steps
    assert get_type_flow("diagnostic").on_selected is not None
    assert get_type_flow("diagnostic").on_booking_confirmed is not None
    assert get_type_flow("lab").on_selected is not None
    assert get_type_flow("lab").on_booking_confirmed is not None
    # docs/per-appointment-type-flow-plan.md Phase 2 Step 2: Follow-up
    # auto-selects department/doctor via its own on_selected hook (the
    # patient's last attended appointment) instead of asking -- `steps`
    # reads the same as NO_DOCTOR_FLOW so shared bookkeeping (messages.py's
    # change-selection menu) correctly hides "Change Department"/"Change
    # Doctor" for it too.
    assert get_type_flow("followup").steps == NO_DOCTOR_FLOW
    assert get_type_flow("followup").on_selected is not None
    # docs/per-appointment-type-flow-plan.md Phase 2 Step 3: Tele-consultation
    # attaches a video-call link via on_booking_confirmed, with its step list
    # completely unchanged (still FULL_FLOW) -- confirmed above already.
    assert get_type_flow("tele").on_booking_confirmed is not None
    # Phase 2 Step 4: Daycare's step list is FULL_FLOW plus one extra step
    # (duration) between time-slot and confirmation -- its own
    # on_booking_confirmed hook persists the chosen duration.
    assert get_type_flow("daycare").steps == (*FULL_FLOW[:-1], STATE_AWAITING_DAYCARE_DURATION, STATE_AWAITING_CONFIRMATION)
    assert get_type_flow("daycare").has_step(STATE_AWAITING_TIME_SLOT)
    assert get_type_flow("daycare").on_booking_confirmed is not None
    for type_id in ("new", "followup", "second_opinion"):
        assert get_type_flow(type_id).on_booking_confirmed is None


def test_unknown_type_id_falls_back_to_full_flow():
    """A hospital-custom appointment type not in the built-in catalog must
    get the safe, fully-generic pipeline rather than crashing."""
    flow = get_type_flow("some_future_custom_type")
    assert flow.steps == FULL_FLOW


def test_none_type_id_falls_back_to_full_flow():
    assert get_type_flow(None).steps == FULL_FLOW


def test_first_step_and_has_step():
    full = get_type_flow("new")
    assert full.first_step() == STATE_AWAITING_DEPARTMENT
    assert full.has_step(STATE_AWAITING_DEPARTMENT)

    # followup.py's own steps are still NO_DOCTOR_FLOW verbatim (unlike
    # diagnostic/lab, which insert a test+variant pick before it) -- see
    # test_known_types_resolve_to_their_own_flow above.
    no_doctor = get_type_flow("followup")
    assert no_doctor.first_step() == STATE_AWAITING_DATE
    assert not no_doctor.has_step(STATE_AWAITING_DEPARTMENT)
    assert no_doctor.has_step(STATE_AWAITING_CONFIRMATION)

    diagnostic = get_type_flow("diagnostic")
    assert diagnostic.first_step() == STATE_AWAITING_DIAGNOSTIC_TEST
    assert not diagnostic.has_step(STATE_AWAITING_DEPARTMENT)
    assert diagnostic.has_step(STATE_AWAITING_CONFIRMATION)


def test_next_step():
    # Every FULL_FLOW type: time-slot -> confirmation directly.
    assert get_type_flow("new").next_step(STATE_AWAITING_TIME_SLOT) == STATE_AWAITING_CONFIRMATION
    # Daycare: time-slot -> duration -> confirmation.
    assert get_type_flow("daycare").next_step(STATE_AWAITING_TIME_SLOT) == STATE_AWAITING_DAYCARE_DURATION
    assert get_type_flow("daycare").next_step(STATE_AWAITING_DAYCARE_DURATION) == STATE_AWAITING_CONFIRMATION
    # Already at/past the last step, or an unrecognized state: safe fallback.
    assert get_type_flow("new").next_step(STATE_AWAITING_CONFIRMATION) == STATE_AWAITING_CONFIRMATION
    assert get_type_flow("new").next_step("SOME_UNKNOWN_STATE") == STATE_AWAITING_CONFIRMATION

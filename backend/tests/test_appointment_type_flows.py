# tests/test_appointment_type_flows.py
"""Unit tests for flows/booking/types/registry.py -- docs/per-appointment-type-flow-plan.md
Phase 1. No DB/connector needed, pure lookup logic."""
from flows.booking.state import STATE_AWAITING_CONFIRMATION, STATE_AWAITING_DATE, STATE_AWAITING_DEPARTMENT
from flows.booking.types.base import FULL_FLOW, NO_DOCTOR_FLOW
from flows.booking.types.registry import get_type_flow


def test_known_types_resolve_to_their_own_flow():
    assert get_type_flow("new").steps == FULL_FLOW
    assert get_type_flow("tele").steps == FULL_FLOW
    assert get_type_flow("second_opinion").steps == FULL_FLOW
    assert get_type_flow("daycare").steps == FULL_FLOW
    assert get_type_flow("diagnostic").steps == NO_DOCTOR_FLOW
    assert get_type_flow("lab").steps == NO_DOCTOR_FLOW
    # docs/per-appointment-type-flow-plan.md Phase 2 Step 2: Follow-up
    # auto-selects department/doctor via its own on_selected hook (the
    # patient's last attended appointment) instead of asking -- `steps`
    # reads the same as NO_DOCTOR_FLOW so shared bookkeeping (messages.py's
    # change-selection menu) correctly hides "Change Department"/"Change
    # Doctor" for it too.
    assert get_type_flow("followup").steps == NO_DOCTOR_FLOW
    assert get_type_flow("followup").on_selected is not None


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

    no_doctor = get_type_flow("lab")
    assert no_doctor.first_step() == STATE_AWAITING_DATE
    assert not no_doctor.has_step(STATE_AWAITING_DEPARTMENT)
    assert no_doctor.has_step(STATE_AWAITING_CONFIRMATION)

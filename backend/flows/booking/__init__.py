# flows/booking/__init__.py
"""
ARCHITECTURE_PLAN.md Phase 3b: core/booking_flow.py (1873 ln) has been
physically split into this package:

  state.py             STATE_* constants, FREE_TEXT_INPUT_STATES, the
                        step-history stack, row-id encode/decode helpers
  messages.py           WA message/menu builders shared across sub-flows
                        (patient selector, slot-taken recovery, back
                        navigation, appointment selection, confirmation)
  book.py               the booking sub-flow's own state handlers
  cancel.py             the cancel sub-flow
  reschedule.py          the reschedule sub-flow
  view_appointments.py   the "My Appointments" view/manage sub-flow
  manage_patients.py     view/add/unlink linked patients
  dispatch.py            _HANDLERS + handle_incoming() -- the module's own
                        standalone entry point, superseded for real traffic
                        by flows/router.py but still exercised directly by
                        tests/test_booking_flow.py and friends

This module re-exports the combined public surface so every existing
`from flows.booking import X` call site (flows/router.py) keeps working,
plus the handful of names tests still import directly (some historically
underscore-prefixed, kept as-is here rather than renamed mid-move).
"""
from flows.booking.state import (
    BACK_ID,
    CHANGE_APPOINTMENT_TYPE,
    CHANGE_DATE,
    CHANGE_DEPARTMENT,
    CHANGE_DOCTOR,
    CHANGE_TIME,
    FREE_TEXT_INPUT_STATES,
    GOTO_MAIN_MENU,
    MANAGE_CANCEL_PREFIX,
    MANAGE_RESCHEDULE_PREFIX,
    STATE_IDLE,
    _date_label,
    _manage_cancel_id as manage_cancel_id,
    _manage_reschedule_id as manage_reschedule_id,
    _parse_manage_id as parse_manage_id,
    _MAX_LIST_ROWS,
)
from flows.booking.book import _start_booking_flow as start_booking_flow
from flows.booking.cancel import (
    _start_cancel_flow as start_cancel_flow,
    _start_cancel_flow_for_appointment as start_cancel_flow_for_appointment,
)
from flows.booking.reschedule import (
    _start_reschedule_flow as start_reschedule_flow,
    _start_reschedule_flow_for_appointment as start_reschedule_flow_for_appointment,
)
from flows.booking.view_appointments import _start_view_appointments_flow as start_view_appointments_flow
from flows.booking.dispatch import _HANDLERS as HANDLERS, handle_incoming  # noqa: F401

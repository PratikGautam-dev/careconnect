# flows/booking/types/base.py
"""TypeFlow: the ordered steps one appointment type goes through, plus
optional per-type hooks. Step handlers stay shared (book.py/messages.py);
only which ones apply, and any extra behavior, is per-type."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

from flows.booking.state import (
    STATE_AWAITING_CONFIRMATION, STATE_AWAITING_DATE, STATE_AWAITING_DEPARTMENT, STATE_AWAITING_DOCTOR,
    STATE_AWAITING_TIME_SLOT,
)

# (connector, hospital_id, patient_id, department_id, scheduled_at) -> a
# translations.py key blocking the booking, or None if no conflict.
BookingValidator = Callable[[object, int, "int | None", "str | None", datetime], "str | None"]

# (connector, hospital_id, patient_id, department_id) -> a translations.py key
# blocking department selection, or None. Runs right when a department is
# picked -- checks that don't need scheduled_at, so the patient sees the
# conflict immediately instead of after picking doctor/date/slot.
DepartmentValidator = Callable[[object, int, "int | None", str], "str | None"]

# (wa, sessions, phone, hospital_id, connector, new_context, language) -> None.
# Fully replaces the default "go to flow.first_step()" behavior.
OnSelectedHook = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class TypeFlow:
    type_id: str
    steps: tuple[str, ...]
    # Optional check run right before booking creation. None = nothing extra.
    validate_booking: BookingValidator | None = None
    # Optional check run right when a department is picked. None = nothing extra.
    validate_department: DepartmentValidator | None = None
    # Optional override for what happens right after this type is picked.
    # None = use the normal steps-driven behavior.
    on_selected: OnSelectedHook | None = None

    def first_step(self) -> str:
        return self.steps[0]

    def has_step(self, state: str) -> bool:
        return state in self.steps


# The original pipeline: new, followup, tele, second_opinion, daycare.
FULL_FLOW = (
    STATE_AWAITING_DEPARTMENT, STATE_AWAITING_DOCTOR, STATE_AWAITING_DATE, STATE_AWAITING_TIME_SLOT,
    STATE_AWAITING_CONFIRMATION,
)

# No department/doctor step: diagnostic, lab (and followup, via on_selected).
NO_DOCTOR_FLOW = (STATE_AWAITING_DATE, STATE_AWAITING_TIME_SLOT, STATE_AWAITING_CONFIRMATION)

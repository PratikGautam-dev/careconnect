# flows/booking/types/second_opinion.py
"""Second Opinion: unchanged flow. Phase 2: optional document-upload step
before confirmation. Shares the "one active appointment per department"
department-selection check with new/tele/daycare -- see
base.existing_department_appointment."""
from flows.booking.types.base import FULL_FLOW, TypeFlow, existing_department_appointment

FLOW = TypeFlow(type_id="second_opinion", steps=FULL_FLOW, validate_department=existing_department_appointment)

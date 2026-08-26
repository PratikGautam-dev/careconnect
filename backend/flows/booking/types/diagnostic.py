# flows/booking/types/diagnostic.py
"""Diagnostic: skips department/doctor selection. book.py auto-resolves a
resource via _first_available_resource. Phase 2: add a real test/panel step."""
from flows.booking.types.base import NO_DOCTOR_FLOW, TypeFlow

FLOW = TypeFlow(type_id="diagnostic", steps=NO_DOCTOR_FLOW)

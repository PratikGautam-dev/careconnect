# flows/booking/types/lab.py
"""Lab: same treatment as diagnostic.py -- skips department/doctor
selection. Phase 2: add a real test/panel step."""
from flows.booking.types.base import NO_DOCTOR_FLOW, TypeFlow

FLOW = TypeFlow(type_id="lab", steps=NO_DOCTOR_FLOW)

# flows/booking/types/daycare.py
"""Daycare: unchanged flow. Phase 2: date-range/duration step instead of
a single time-slot."""
from flows.booking.types.base import FULL_FLOW, TypeFlow

FLOW = TypeFlow(type_id="daycare", steps=FULL_FLOW)

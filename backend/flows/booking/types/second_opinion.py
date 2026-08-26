# flows/booking/types/second_opinion.py
"""Second Opinion: unchanged flow. Phase 2: optional document-upload step
before confirmation."""
from flows.booking.types.base import FULL_FLOW, TypeFlow

FLOW = TypeFlow(type_id="second_opinion", steps=FULL_FLOW)

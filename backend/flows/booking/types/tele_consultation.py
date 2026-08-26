# flows/booking/types/tele_consultation.py
"""Tele-consultation: unchanged flow. Phase 2: attach a video-call link
to the booking notification."""
from flows.booking.types.base import FULL_FLOW, TypeFlow

FLOW = TypeFlow(type_id="tele", steps=FULL_FLOW)

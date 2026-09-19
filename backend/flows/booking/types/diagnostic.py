# flows/booking/types/diagnostic.py
"""Diagnostic Test: test -> resource-linked date/time -> confirm. See
_diagnostic_shared.py for
the actual implementation, shared with lab.py."""
from flows.booking.types._diagnostic_shared import make_flow

FLOW = make_flow("diagnostic")

# flows/booking/types/diagnostic.py
"""Diagnostic Test (docs/per-appointment-type-flow-plan.md Phase 2 Step 5):
test -> variant -> resource-linked date/time -> confirm. See
_diagnostic_shared.py for the actual implementation, shared with lab.py."""
from flows.booking.types._diagnostic_shared import make_flow

FLOW = make_flow("diagnostic")

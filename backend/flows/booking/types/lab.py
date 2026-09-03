# flows/booking/types/lab.py
"""Lab Test: same treatment as diagnostic.py -- see _diagnostic_shared.py."""
from flows.booking.types._diagnostic_shared import make_flow

FLOW = make_flow("lab")

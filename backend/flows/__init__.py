# flows/__init__.py
"""
flows/router.py is the feature-toggle router;
flows/common.py is the shared cap_rows/is_reset_keyword helpers;
flows/faq.py is the FAQ sub-flow; flows/patient_identity/
is the patient registration/selection/consent flow (see its own __init__.py
for the submodule breakdown); flows/booking/ is the public re-export
surface for core/booking_flow.py's state machine.

This module re-exports flows/router.py's public surface (via a lazy
module __getattr__, PEP 562) so every existing `import flows` /
`from flows import X` call site keeps working unchanged. Lazy on purpose:
core/booking_flow.py imports flows.common (a leaf module with no further
deps), and flows.router imports flows.booking, which imports
core/booking_flow.py back -- an eager `from flows.router import *` here
would run at `flows.common` import time too (Python always runs a
package's __init__.py before any of its submodules), completing that
cycle while core/booking_flow.py is still mid-execution. Deferring the
router import to first attribute access means whichever of the two
(core.booking_flow or flows.router) gets imported first finishes
initializing before the other one is ever touched.
"""


def __getattr__(name):
    import flows.router as _router

    try:
        return getattr(_router, name)
    except AttributeError:
        raise AttributeError(f"module 'flows' has no attribute {name!r}") from None

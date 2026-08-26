# flows/booking/types/registry.py
"""Maps an `appointment_types.id` to its `TypeFlow` -- the one place
book.py/messages.py look up which shared steps a given type's booking goes
through. A hospital-custom type id not in this built-in catalog falls back
to FULL_FLOW (today's original pipeline) rather than crashing -- an
unrecognized type gets the safe, fully-generic flow until it's given its own
module here."""
from flows.booking.types import daycare, diagnostic, followup, lab, new_consultation, second_opinion, tele_consultation
from flows.booking.types.base import FULL_FLOW, TypeFlow

TYPE_FLOWS: dict[str, TypeFlow] = {
    flow.FLOW.type_id: flow.FLOW
    for flow in (new_consultation, followup, tele_consultation, second_opinion, daycare, diagnostic, lab)
}

_DEFAULT_FLOW = TypeFlow(type_id="__default__", steps=FULL_FLOW)


def get_type_flow(appointment_type_id: str | None) -> TypeFlow:
    if appointment_type_id is None:
        return _DEFAULT_FLOW
    return TYPE_FLOWS.get(appointment_type_id, _DEFAULT_FLOW)

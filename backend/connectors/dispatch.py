# connectors/dispatch.py
"""The single connector dispatch point (SPEC Section 12.6.2). core/main.py
calls get_connector_for_hospital exactly once per hospital resolution — in
the webhook handler right after resolving the hospital, and once per
hospital in the reminder/slot loops — and passes the resulting connector
down; core/booking_flow.py and reminders/scheduler.py never inspect
hospital.data_tier themselves.

ARCHITECTURE_PLAN.md Phase 2: split out of the former single connectors.py
module."""
from db.models import Hospital

from connectors.base import Connector, ConnectorNotImplementedError
from connectors.tier1 import Tier1Connector
from connectors.tier2 import Tier2Connector
from connectors.tier3 import Tier3Connector

# Stateless singletons — see connectors/base.py's module docstring for why
# one instance per tier (not per hospital) is sufficient.
_TIER1 = Tier1Connector()
_TIER2 = Tier2Connector()
_TIER3 = Tier3Connector()

_CONNECTORS_BY_TIER: dict[str, Connector] = {
    "tier1": _TIER1,
    "tier2": _TIER2,
    "tier3": _TIER3,
}


def get_connector_for_hospital(hospital: Hospital) -> Connector:
    connector = _CONNECTORS_BY_TIER.get(hospital.data_tier)
    if connector is None:
        raise ConnectorNotImplementedError(
            f'Unrecognized data_tier "{hospital.data_tier}" for hospital {hospital.id} — '
            f'expected one of {sorted(_CONNECTORS_BY_TIER)}.'
        )
    return connector

# connectors/__init__.py
"""
ARCHITECTURE_PLAN.md Phase 2: connectors.py split into a package —
connectors/base.py (the Connector ABC, the shared "not implemented yet"
stub base, and ConnectorNotImplementedError), connectors/tier1.py
(Tier1Connector, the only tier with a real implementation),
connectors/tier2.py / tier3.py (stubs), and connectors/dispatch.py
(get_connector_for_hospital, the single per-hospital dispatch point).

This module re-exports the public surface so every existing call site
(`from connectors import Connector, Tier1Connector`, etc.) keeps working
unchanged.
"""
from db.models import Appointment, DuplicateBookingError, Hospital, TooManyLinkedPatientsError
from db.repositories.patients import GENDER_OPTIONS, RELATIONSHIP_OPTIONS  # noqa: F401 -- re-exported, see module docstring below
# Re-exported (Appointment/DuplicateBookingError/Hospital/
# RELATIONSHIP_OPTIONS/TooManyLinkedPatientsError above) so core/booking_flow.py
# and core/patient_identity.py can import them from here without importing
# db/repository.py directly — SPEC Section 12.6.2's connector-only boundary.
# max_active_patient_links is NOT re-exported as a raw constant anymore --
# it's a global platform-admin-editable value now (db/repositories/
# platform_settings.py), read via Connector.get_max_active_patient_links()
# at the point of use instead, same "not per-hospital, still Connector-gated"
# treatment identify_contact already gets.

from connectors.base import Connector, ConnectorNotImplementedError, _UnimplementedTierConnector  # noqa: F401
from connectors.dispatch import get_connector_for_hospital  # noqa: F401
from connectors.tier1 import Tier1Connector  # noqa: F401
from connectors.tier2 import Tier2Connector  # noqa: F401
from connectors.tier3 import Tier3Connector  # noqa: F401

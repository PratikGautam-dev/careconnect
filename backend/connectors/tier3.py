# connectors/tier3.py
"""SPEC Section 12.6 Tier 3 — direct database connection. Stubbed on
purpose: a manually-assisted, case-by-case engagement, not something to
build generically ahead of a real hospital needing it. ARCHITECTURE_PLAN.md
Phase 2: split out of the former single connectors.py module."""
from connectors.base import _UnimplementedTierConnector


class Tier3Connector(_UnimplementedTierConnector):
    _tier_label = "Tier 3 (direct database connection)"

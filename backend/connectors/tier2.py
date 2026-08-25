# connectors/tier2.py
"""SPEC Section 12.6 Tier 2 — integration against a hospital's existing API.
Stubbed on purpose: build only once a real Tier 2 hospital exists, against
their actual documented API shape. ARCHITECTURE_PLAN.md Phase 2: split out
of the former single connectors.py module."""
from connectors.base import _UnimplementedTierConnector


class Tier2Connector(_UnimplementedTierConnector):
    _tier_label = "Tier 2 (external API integration)"

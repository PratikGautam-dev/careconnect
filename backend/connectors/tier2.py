# connectors/tier2.py
"""Tier 2 — integration against a hospital's existing API.
Stubbed on purpose: build only once a real Tier 2 hospital exists, against
their actual documented API shape."""
from connectors.base import _UnimplementedTierConnector


class Tier2Connector(_UnimplementedTierConnector):
    _tier_label = "Tier 2 (external API integration)"

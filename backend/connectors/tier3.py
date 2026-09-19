# connectors/tier3.py
"""Tier 3 — direct database connection. Stubbed on
purpose: a manually-assisted, case-by-case engagement, not something to
build generically ahead of a real hospital needing it."""
from connectors.base import _UnimplementedTierConnector


class Tier3Connector(_UnimplementedTierConnector):
    _tier_label = "Tier 3 (direct database connection)"

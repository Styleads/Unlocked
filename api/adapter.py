"""
api/adapter.py — Canonical adapter bridging Member 1 discovery schemas to Member 2 contracts.
"""
from discovery_agent.adapter import (
    adapt_m1_to_m2_scheme,
    adapt_m1_to_m2_schemes,
    to_canonical_scheme,
    to_canonical_schemes,
)

__all__ = [
    "adapt_m1_to_m2_scheme",
    "adapt_m1_to_m2_schemes",
    "to_canonical_scheme",
    "to_canonical_schemes",
]


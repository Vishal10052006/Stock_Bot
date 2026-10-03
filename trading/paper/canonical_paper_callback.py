"""Backward-compatible import shim for the V1 manual decision authority.

The implementation intentionally lives in trading.live. This module remains
only so legacy paper/runtime imports do not break during the migration.
"""

from trading.live.manual_decision import (
    CanonicalLiveDecision,
    build_live_money_decision,
)

__all__ = [
    "CanonicalLiveDecision",
    "build_live_money_decision",
]

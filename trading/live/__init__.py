"""Live-market decision authority.

The V1 manual real-money decision path lives under trading.live.
This namespace never owns broker execution.
"""

from .manual_decision import CanonicalLiveDecision, build_live_money_decision
from .signal_engine import (
    LiveSignalBlockReason,
    LiveSignalEvent,
    LiveSignalEngine,
    LiveSignalStatus,
)

__all__ = [
    "CanonicalLiveDecision",
    "build_live_money_decision",
    "LiveSignalBlockReason",
    "LiveSignalEvent",
    "LiveSignalEngine",
    "LiveSignalStatus",
]

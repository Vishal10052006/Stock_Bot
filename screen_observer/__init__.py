"""Screen Observer foundation.

References:
- STOCK_BOT Screen Intelligence roadmap: S00-S12.
- TRADING_SPECIFICATION.md: timestamp/causality requirements.
- monitoring/monitoring_contract.py: observation-only authority boundary.
"""

from .contracts import (
    CandleObservation,
    ChartObservation,
    ScreenConfidence,
    ScreenObservation,
    VisualContext,
    WindowObservation,
)
from .observer import ScreenObserver

__all__ = [
    "CandleObservation",
    "ChartObservation",
    "ScreenConfidence",
    "ScreenObservation",
    "VisualContext",
    "WindowObservation",
    "ScreenObserver",
]

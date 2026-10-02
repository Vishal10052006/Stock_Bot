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
from .runtime import ScreenEvent, ScreenObserverRuntime
from .window_provider import LinuxWindowProvider
from .analysis import build_screen_analysis_context
from .validation import ScreenValidationResult, validate_screen_observation
from .confidence import (\n    calculate_screen_confidence,\n    screen_confidence_state,\n    screen_is_usable,\n    validate_screen_confidence,\n)
from .context import build_visual_context
from .evidence import CandleVisualEvidence, IndicatorEvidence, ScreenAnalysisContext, TimeframeEvidence

__all__ = [
    "CandleObservation",
    "ChartObservation",
    "ScreenConfidence",
    "ScreenObservation",
    "VisualContext",
    "WindowObservation",
    "ScreenObserver",
    "ScreenEvent",
    "ScreenObserverRuntime",
    "LinuxWindowProvider",
    "CandleVisualEvidence",
    "IndicatorEvidence",
    "TimeframeEvidence",
    "ScreenAnalysisContext",
    "build_visual_context",
    "calculate_screen_confidence",
    "screen_is_usable",
    "build_screen_analysis_context",
    "ScreenValidationResult",
    "validate_screen_observation",
]

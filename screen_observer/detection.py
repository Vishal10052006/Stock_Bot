"""Window and TradingView-region detection.

S02/S03 deliberately use explicit window metadata first. OS-specific window
enumeration is an adapter concern and is not coupled to the core contract.
"""

from __future__ import annotations

import re
from typing import Iterable

from .contracts import ChartObservation, WindowObservation


_TRADINGVIEW_RE = re.compile(r"tradingview", re.IGNORECASE)


class WindowDetector:
    def __init__(self, applications: Iterable[str] = ("tradingview",)) -> None:
        self.applications = tuple(item.lower() for item in applications)

    def select(self, windows: Iterable[WindowObservation]) -> WindowObservation | None:
        candidates = tuple(windows)
        for window in candidates:
            haystack = f"{window.application} {window.title}".lower()
            if any(token in haystack for token in self.applications):
                return window
        return None


class TradingViewRegionDetector:
    """Baseline S03 region detector.

    When the target window is known, its interior is treated as the chart
    candidate. Later CV work can replace this implementation without changing
    downstream contracts.
    """

    def detect(self, window: WindowObservation | None) -> ChartObservation:
        if window is None:
            return ChartObservation(detected=False)

        # Reserve a small header band for TradingView controls/ticker metadata.
        header = min(120, max(24, window.height // 8))
        return ChartObservation(
            detected=True,
            left=window.left,
            top=window.top + header,
            width=window.width,
            height=window.height - header,
            confidence=0.60,
        )

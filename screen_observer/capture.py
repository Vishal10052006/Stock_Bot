"""Screen capture and scheduling adapters.

S00/S01 implementation is dependency-light. The real desktop backend is loaded
lazily so importing STOCK_BOT does not require a GUI session.

Reference:
- Screen Intelligence roadmap: S00 Screen capture, S01 Capture scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Protocol

import pandas as pd


class CaptureBackend(Protocol):
    def capture(self, region: tuple[int, int, int, int] | None = None) -> Any:
        """Capture the desktop or a rectangular region."""


class MSSCaptureBackend:
    """Linux/Windows/macOS capture backend using python-mss."""

    def capture(self, region: tuple[int, int, int, int] | None = None) -> Any:
        try:
            import mss
        except ImportError as exc:
            raise RuntimeError(
                "Screen capture requires python-mss. Install "
                "requirements-screen-observer.txt."
            ) from exc

        with mss.mss() as session:
            monitor = (
                {
                    "left": region[0],
                    "top": region[1],
                    "width": region[2],
                    "height": region[3],
                }
                if region
                else session.monitors[1]
            )
            return session.grab(monitor)


@dataclass(frozen=True, slots=True)
class CaptureSchedule:
    interval: timedelta

    def __post_init__(self) -> None:
        if self.interval.total_seconds() <= 0:
            raise ValueError("capture interval must be positive")


class CaptureScheduler:
    """Deterministic scheduler; orchestration is intentionally external."""

    def __init__(self, schedule: CaptureSchedule) -> None:
        self.schedule = schedule

    def due(self, *, now: pd.Timestamp, last_capture: pd.Timestamp | None) -> bool:
        now = pd.Timestamp(now)
        if now.tzinfo is None:
            raise ValueError("scheduler timestamps must be timezone-aware")
        if last_capture is None:
            return True
        last_capture = pd.Timestamp(last_capture)
        if last_capture.tzinfo is None:
            raise ValueError("last_capture must be timezone-aware")
        return now - last_capture >= self.schedule.interval

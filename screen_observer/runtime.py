"""Continuous Screen Observer runtime.

S00/S01 orchestration layer for live desktop observation.

The runtime is observation-only:
- it captures and interprets the screen;
- it stores the latest observation/context;
- it emits visual-state change events;
- it never creates trading orders or bypasses Strategy/Risk/Execution.

The vision pipeline remains in ScreenObserver. This module only provides the
continuous lifecycle and change-detection seam needed by the Jarvis-style
desktop observer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import threading
from typing import Callable, Iterable, Protocol

import pandas as pd

from .capture import CaptureSchedule
from .contracts import ScreenObservation, VisualContext, WindowObservation
from .observer import ScreenObserver
from .window_provider import LinuxWindowProvider


class WindowProvider(Protocol):
    def __call__(self) -> Iterable[WindowObservation]:
        """Return the currently visible windows."""


@dataclass(frozen=True, slots=True)
class ScreenEvent:
    """Immutable event emitted when meaningful visual state changes."""

    event_type: str
    observed_at: pd.Timestamp
    context: VisualContext
    target_window: WindowObservation | None = None


class ScreenObserverRuntime:
    """Continuously observe the desktop and publish visual-state changes."""

    def __init__(
        self,
        *,
        observer: ScreenObserver | None = None,
        interval: timedelta = timedelta(seconds=1),
        window_provider: WindowProvider | None = None,
        on_event: Callable[[ScreenEvent], None] | None = None,
    ) -> None:
        self.observer = observer or ScreenObserver()
        self.schedule = CaptureSchedule(interval)
        self.window_provider = window_provider or LinuxWindowProvider()
        self.on_event = on_event

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        self._latest_observation: ScreenObservation | None = None
        self._latest_context: VisualContext | None = None
        self._last_signature: tuple[object, ...] | None = None
        self._last_error: Exception | None = None
        self._last_target_signature: tuple[object, ...] | None = None

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    @property
    def paused(self) -> bool:
        return self._pause_event.is_set()

    @property
    def latest_observation(self) -> ScreenObservation | None:
        with self._lock:
            return self._latest_observation

    @property
    def latest_visual_context(self) -> VisualContext | None:
        with self._lock:
            return self._latest_context

    @property
    def last_error(self) -> Exception | None:
        with self._lock:
            return self._last_error

    def start(self) -> None:
        """Start one background observation loop; repeated starts are harmless."""
        if self.running:
            return

        self._stop_event.clear()
        self._pause_event.clear()
        self._wake_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="stock-bot-screen-observer",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float | None = 5.0) -> None:
        """Stop the background loop and wait for clean termination."""
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        if thread is not None and not thread.is_alive():
            self._thread = None

    def pause(self) -> None:
        """Pause observation without destroying the latest state."""
        self._pause_event.set()
        self._wake_event.set()

    def resume(self) -> None:
        """Resume observation."""
        self._pause_event.clear()
        self._wake_event.set()

    def observe_once(self) -> ScreenObservation:
        """Capture and interpret the screen exactly once."""
        observed_at = pd.Timestamp.now(tz="UTC")
        windows = tuple(self.window_provider())
        observation = self.observer.observe(
            observed_at=observed_at,
            windows=windows,
        )
        context = self.observer.to_visual_context(observation)
        signature = self._context_signature(context)

        target = observation.target_window
        target_signature = self._target_signature(target)

        with self._lock:
            self._latest_observation = observation
            self._latest_context = context
            self._last_error = None
            previous_signature = self._last_signature
            previous_target_signature = self._last_target_signature
            self._last_signature = signature
            self._last_target_signature = target_signature

        if previous_target_signature is None and target_signature is not None:
            self._emit("TARGET_WINDOW_FOUND", context, target)
        elif previous_target_signature is not None and target_signature is None:
            self._emit("TARGET_WINDOW_LOST", context, None)
        elif (
            previous_target_signature is not None
            and target_signature is not None
            and target_signature != previous_target_signature
        ):
            self._emit("TARGET_WINDOW_CHANGED", context, target)

        if previous_signature is None:
            self._emit("SCREEN_CONNECTED", context, target)
        elif signature != previous_signature:
            self._emit("VISUAL_CONTEXT_CHANGED", context, target)

        return observation

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if not self._pause_event.is_set():
                try:
                    self.observe_once()
                except Exception as exc:  # runtime must survive one bad capture
                    with self._lock:
                        self._last_error = exc

            self._wake_event.wait(self.schedule.interval.total_seconds())
            self._wake_event.clear()

    def _emit(
        self,
        event_type: str,
        context: VisualContext,
        target_window: WindowObservation | None = None,
    ) -> None:
        callback = self.on_event
        if callback is not None:
            callback(
                ScreenEvent(
                    event_type=event_type,
                    observed_at=context.observed_at,
                    context=context,
                    target_window=target_window,
                )
            )

    @staticmethod
    def _target_signature(
        target: WindowObservation | None,
    ) -> tuple[object, ...] | None:
        if target is None:
            return None
        return (
            target.application,
            target.title,
            target.left,
            target.top,
            target.width,
            target.height,
        )

    @staticmethod
    def _context_signature(context: VisualContext) -> tuple[object, ...]:
        """Return only meaningful state, excluding volatile timestamps."""
        candles = context.candle_observation
        return (
            context.symbol,
            context.timeframe,
            context.indicators,
            context.chart_detected,
            candles.bullish,
            candles.bearish,
        )

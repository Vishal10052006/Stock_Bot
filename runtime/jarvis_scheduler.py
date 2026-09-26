"""M20.6 safe scheduler for the JARVIS lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time as time_module
from typing import Callable

from .jarvis import JarvisLifecycle, LifecyclePhase


@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    poll_seconds: float = 30.0
    max_iterations: int | None = None

    def __post_init__(self) -> None:
        if self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        if self.max_iterations is not None and self.max_iterations <= 0:
            raise ValueError("max_iterations must be positive when provided")


class JarvisScheduler:
    """Run at most one lifecycle phase per polling interval.

    The scheduler is deliberately process-local and dependency-free. A future
    service/cron wrapper can call run_once() without changing lifecycle logic.
    """

    def __init__(
        self,
        lifecycle: JarvisLifecycle,
        *,
        config: SchedulerConfig | None = None,
        clock: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.lifecycle = lifecycle
        self.config = config or SchedulerConfig()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.sleeper = sleeper or time_module.sleep
        self._last_phase: LifecyclePhase | None = None
        self._last_date: object | None = None

    def run_once(self) -> object:
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("scheduler clock must return timezone-aware datetime")

        local_date = now.astimezone(self.lifecycle.timezone).date()
        phase = self.lifecycle.phase_for(now)

        # Prevent repeated execution of the same phase during one local day.
        if self._last_date == local_date and self._last_phase is phase:
            return {
                "status": "ALREADY_RUN",
                "phase": phase.value,
                "live_broker_order_submission": False,
            }

        result = self.lifecycle.run_phase(phase, now=now)
        self._last_date = local_date
        self._last_phase = phase
        return result

    def run_forever(self) -> None:
        iterations = 0
        while (
            self.config.max_iterations is None
            or iterations < self.config.max_iterations
        ):
            self.run_once()
            iterations += 1
            self.sleeper(self.config.poll_seconds)

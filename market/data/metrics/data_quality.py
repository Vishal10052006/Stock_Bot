"""Operational metrics for the real-time market-data pipeline.

The metrics layer is provider-neutral and records data-quality and
connectivity observations without modifying canonical MarketEvent objects.

Reference:
    ROADMAP_STOCK-BOT.pdf — Phase 3, Real-Time Data Pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from statistics import mean

from market.data.validation import EventValidationResult


@dataclass(frozen=True, slots=True)
class DataQualitySnapshot:
    """Immutable snapshot of current real-time data-quality metrics."""

    events_received: int
    events_accepted: int
    events_rejected: int
    stale_events: int
    duplicate_events: int

    latency_sample_count: int
    latency_avg_ms: float | None
    latency_min_ms: float | None
    latency_max_ms: float | None
    latency_p95_ms: float | None

    clock_skew_events: int

    connection_failures: int
    reconnect_attempts: int
    reconnect_successes: int
    reconnect_failures: int

    missing_data_gaps: int


class DataQualityMetrics:
    """Collect operational metrics for the live market-data pipeline.

    This class is intentionally stateful but provider-independent. It does
    not validate events itself; it records the result produced by the
    MarketEventValidator.

    Missing-data gaps are recorded explicitly by the caller because a tick
    stream does not necessarily have a fixed event cadence.
    """

    def __init__(self) -> None:
        """Initialize all counters and latency samples."""
        self._events_received = 0
        self._events_accepted = 0
        self._events_rejected = 0
        self._stale_events = 0
        self._duplicate_events = 0

        self._latency_samples_ms: list[float] = []
        self._clock_skew_events = 0

        self._connection_failures = 0
        self._reconnect_attempts = 0
        self._reconnect_successes = 0
        self._reconnect_failures = 0

        self._missing_data_gaps = 0

    def record_validation(
        self,
        result: EventValidationResult,
    ) -> None:
        """Record one event-validation result."""
        self._events_received += 1

        self._latency_samples_ms.append(result.latency_ms)

        if result.valid:
            self._events_accepted += 1
        else:
            self._events_rejected += 1

        if result.stale:
            self._stale_events += 1

        if result.duplicate:
            self._duplicate_events += 1

        if result.latency_ms < 0:
            self._clock_skew_events += 1

    def record_connection_failure(self) -> None:
        """Record one provider connection failure."""
        self._connection_failures += 1

    def record_reconnect_attempt(self) -> None:
        """Record one reconnect attempt."""
        self._reconnect_attempts += 1

    def record_reconnect_success(self) -> None:
        """Record one successful reconnect."""
        self._reconnect_successes += 1

    def record_reconnect_failure(self) -> None:
        """Record one failed reconnect cycle."""
        self._reconnect_failures += 1

    def record_missing_data_gap(self) -> None:
        """Record one explicitly detected missing-data gap."""
        self._missing_data_gaps += 1

    @staticmethod
    def _percentile(
        values: list[float],
        percentile: float,
    ) -> float | None:
        """Return a simple nearest-rank percentile."""
        if not values:
            return None

        ordered = sorted(values)
        rank = ceil(percentile * len(ordered))
        index = max(0, rank - 1)

        return ordered[index]

    def snapshot(self) -> DataQualitySnapshot:
        """Return an immutable snapshot of all collected metrics."""
        samples = list(self._latency_samples_ms)

        return DataQualitySnapshot(
            events_received=self._events_received,
            events_accepted=self._events_accepted,
            events_rejected=self._events_rejected,
            stale_events=self._stale_events,
            duplicate_events=self._duplicate_events,
            latency_sample_count=len(samples),
            latency_avg_ms=mean(samples) if samples else None,
            latency_min_ms=min(samples) if samples else None,
            latency_max_ms=max(samples) if samples else None,
            latency_p95_ms=self._percentile(samples, 0.95),
            clock_skew_events=self._clock_skew_events,
            connection_failures=self._connection_failures,
            reconnect_attempts=self._reconnect_attempts,
            reconnect_successes=self._reconnect_successes,
            reconnect_failures=self._reconnect_failures,
            missing_data_gaps=self._missing_data_gaps,
        )

    def reset(self) -> None:
        """Reset all operational metrics."""
        self.__init__()

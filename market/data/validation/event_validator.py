"""Validation utilities for canonical real-time market events.

The validator operates after provider-specific normalization and before
downstream feature/signal processing.

Reference:
    ROADMAP_STOCK-BOT.pdf — Phase 3, Real-Time Data Pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from market.data.events import MarketEvent


@dataclass(frozen=True, slots=True)
class EventValidationResult:
    """Result of validating one canonical market event."""

    valid: bool
    stale: bool
    duplicate: bool
    latency_ms: float
    reason: str | None = None


class MarketEventValidator:
    """Validate freshness, timestamps, latency and duplicate events.

    This class deliberately does not modify ``MarketEvent`` instances.
    Validation is an independent boundary between ingestion and downstream
    trading logic.
    """

    def __init__(
        self,
        *,
        max_event_age_seconds: float = 5.0,
        max_future_skew_seconds: float = 2.0,
    ) -> None:
        """Configure event freshness and clock-skew thresholds."""
        if max_event_age_seconds <= 0:
            raise ValueError("max_event_age_seconds must be > 0")

        if max_future_skew_seconds < 0:
            raise ValueError("max_future_skew_seconds must be >= 0")

        self.max_event_age_seconds = max_event_age_seconds
        self.max_future_skew_seconds = max_future_skew_seconds

        # Event IDs already accepted by this validator.
        self._seen_event_ids: set[str] = set()

    @staticmethod
    def _utc_now() -> datetime:
        """Return the current timezone-aware UTC timestamp."""
        return datetime.now(timezone.utc)

    @staticmethod
    def _latency_ms(
        event: MarketEvent,
        now: datetime,
    ) -> float:
        """Calculate ingestion latency from exchange to receipt."""
        exchange_timestamp = event.exchange_timestamp.astimezone(timezone.utc)
        received_timestamp = event.received_timestamp.astimezone(timezone.utc)

        return (
            received_timestamp - exchange_timestamp
        ).total_seconds() * 1000.0

    def validate(
        self,
        event: MarketEvent,
        *,
        now: datetime | None = None,
    ) -> EventValidationResult:
        """Validate one canonical market event.

        Validation checks:

        1. Event must be a canonical ``MarketEvent``.
        2. Exchange timestamp must not be too far in the future.
        3. Event must not be older than the configured freshness threshold.
        4. Calculated latency must not be negative beyond clock-skew tolerance.
        5. Duplicate event IDs are rejected.

        The optional ``now`` argument makes the validator deterministic in
        unit tests.
        """
        if not isinstance(event, MarketEvent):
            raise TypeError("event must be a MarketEvent")

        current_time = (
            now.astimezone(timezone.utc)
            if now is not None
            else self._utc_now()
        )

        exchange_timestamp = event.exchange_timestamp.astimezone(timezone.utc)

        latency_ms = self._latency_ms(event, current_time)

        future_limit = current_time + timedelta(
            seconds=self.max_future_skew_seconds
        )

        if exchange_timestamp > future_limit:
            return EventValidationResult(
                valid=False,
                stale=False,
                duplicate=False,
                latency_ms=latency_ms,
                reason="exchange timestamp is too far in the future",
            )

        age_seconds = (
            current_time - exchange_timestamp
        ).total_seconds()

        if age_seconds > self.max_event_age_seconds:
            return EventValidationResult(
                valid=False,
                stale=True,
                duplicate=False,
                latency_ms=latency_ms,
                reason="event is stale",
            )

        if latency_ms < -self.max_future_skew_seconds * 1000.0:
            return EventValidationResult(
                valid=False,
                stale=False,
                duplicate=False,
                latency_ms=latency_ms,
                reason="negative event latency exceeds clock-skew tolerance",
            )

        if event.event_id in self._seen_event_ids:
            return EventValidationResult(
                valid=False,
                stale=False,
                duplicate=True,
                latency_ms=latency_ms,
                reason="duplicate event",
            )

        self._seen_event_ids.add(event.event_id)

        return EventValidationResult(
            valid=True,
            stale=False,
            duplicate=False,
            latency_ms=latency_ms,
        )

    def reset(self) -> None:
        """Clear duplicate-detection state."""
        self._seen_event_ids.clear()

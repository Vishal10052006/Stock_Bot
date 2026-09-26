"""Operational evidence for an M20 shadow session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from market.data.metrics import DataQualitySnapshot


@dataclass(slots=True)
class ShadowHealth:
    """Mutable session counters independent of trading authority."""

    started_at: datetime
    candles_completed: int = 0

    def record_candle(self) -> None:
        """Record one completed shadow candle."""
        self.candles_completed += 1

    def snapshot(self, metrics: DataQualitySnapshot) -> dict[str, object]:
        """Return a JSON-serializable operational snapshot."""
        now = datetime.now(timezone.utc)
        return {
            "mode": "SHADOW",
            "live_broker_order_submission": False,
            "started_at": self.started_at.isoformat(),
            "observed_at": now.isoformat(),
            "candles_completed": self.candles_completed,
            "events_received": metrics.events_received,
            "events_accepted": metrics.events_accepted,
            "events_rejected": metrics.events_rejected,
            "stale_events": metrics.stale_events,
            "duplicate_events": metrics.duplicate_events,
            "latency_sample_count": metrics.latency_sample_count,
            "latency_avg_ms": metrics.latency_avg_ms,
            "latency_p95_ms": metrics.latency_p95_ms,
            "connection_failures": metrics.connection_failures,
            "reconnect_attempts": metrics.reconnect_attempts,
            "reconnect_successes": metrics.reconnect_successes,
            "reconnect_failures": metrics.reconnect_failures,
            "missing_data_gaps": metrics.missing_data_gaps,
        }

"""Append-only evidence for one M20 shadow session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from monitoring.journal import MonitoringEvent, MonitoringJournal


@dataclass(slots=True)
class ShadowSessionJournal:
    """Record M20 lifecycle/evidence events under one session identity."""

    journal: MonitoringJournal
    session_id: str

    @classmethod
    def open(cls, path: str | Path, *, session_id: str | None = None) -> "ShadowSessionJournal":
        return cls(
            journal=MonitoringJournal(path),
            session_id=session_id or str(uuid.uuid4()),
        )

    def record(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        severity: str = "INFO",
        timestamp: datetime | None = None,
    ) -> MonitoringEvent:
        """Append one deterministic monitoring event for this shadow session."""
        event = MonitoringEvent.create(
            event_type=event_type,
            source="m20-shadow-runtime",
            payload=payload,
            severity=severity,
            correlation_id=self.session_id,
            timestamp=timestamp or datetime.now(timezone.utc),
        )
        self.journal.append(event)
        return event

    def start(self, *, symbols: tuple[str, ...]) -> MonitoringEvent:
        return self.record(
            event_type="SHADOW_SESSION_STARTED",
            payload={
                "mode": "SHADOW",
                "symbols": list(symbols),
                "live_broker_order_submission": False,
            },
        )

    def candle(self, *, symbol: str, timestamp: datetime) -> MonitoringEvent:
        return self.record(
            event_type="SHADOW_CANDLE_COMPLETED",
            payload={
                "symbol": symbol,
                "timestamp": timestamp.astimezone(timezone.utc).isoformat(),
            },
            timestamp=timestamp,
        )

    def stop(self, *, evidence: dict[str, Any]) -> MonitoringEvent:
        return self.record(
            event_type="SHADOW_SESSION_STOPPED",
            payload={
                "evidence": evidence,
                "live_broker_order_submission": False,
            },
        )

    def events(self) -> tuple[MonitoringEvent, ...]:
        return self.journal.replay(correlation_id=self.session_id)

    def evidence(self) -> dict[str, Any]:
        events = self.events()
        return {
            "session_id": self.session_id,
            "event_count": len(events),
            "event_fingerprints": [event.fingerprint for event in events],
            "live_broker_order_submission": False,
        }

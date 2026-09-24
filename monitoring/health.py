"""M-1 component heartbeat and health tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from monitoring.models import ComponentHealth, SystemHealth


@dataclass(frozen=True, slots=True)
class Heartbeat:
    """Latest heartbeat for a named component."""

    component: str
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.component.strip():
            raise ValueError("component must not be empty")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("heartbeat timestamp must be timezone-aware")


class HealthMonitor:
    """Track component heartbeats without owning execution decisions."""

    def __init__(self) -> None:
        self._heartbeats: dict[str, Heartbeat] = {}

    def heartbeat(
        self,
        component: str,
        *,
        timestamp: datetime | None = None,
    ) -> Heartbeat:
        """Record the latest component heartbeat."""
        event = Heartbeat(
            component=component.strip(),
            timestamp=timestamp or datetime.now(timezone.utc),
        )
        self._heartbeats[event.component] = event
        return event

    def health(
        self,
        *,
        now: datetime | None = None,
        timeout_seconds: float = 30.0,
        expected_components: tuple[str, ...] = (),
    ) -> SystemHealth:
        """Build health from heartbeat freshness."""
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        current = now or datetime.now(timezone.utc)
        states: dict[str, ComponentHealth] = {}

        names = tuple(dict.fromkeys(expected_components + tuple(self._heartbeats)))
        for name in names:
            heartbeat = self._heartbeats.get(name)
            if heartbeat is None:
                states[name] = ComponentHealth.UNKNOWN
                continue
            age = (current - heartbeat.timestamp).total_seconds()
            states[name] = (
                ComponentHealth.HEALTHY
                if age <= timeout_seconds
                else ComponentHealth.FAILED
            )

        if any(value is ComponentHealth.FAILED for value in states.values()):
            overall = ComponentHealth.FAILED
        elif any(value is ComponentHealth.UNKNOWN for value in states.values()):
            overall = ComponentHealth.DEGRADED
        else:
            overall = ComponentHealth.HEALTHY

        ages = [
            (current - heartbeat.timestamp).total_seconds()
            for heartbeat in self._heartbeats.values()
        ]
        max_age = max(ages) if ages else None
        return SystemHealth(
            timestamp=current,
            overall=overall,
            components=states,
            heartbeat_age_seconds=max_age,
        )

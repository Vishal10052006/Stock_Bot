"""Alert routing and duplicate suppression for STOCK_BOT."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable

from monitoring.models import Alert, AlertSeverity


@dataclass(frozen=True, slots=True)
class AlertPolicy:
    """Routing policy for a class of monitoring alerts."""

    severity: AlertSeverity
    cooldown_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")


class AlertManager:
    """Route alerts while suppressing repeated identical conditions.

    Suppression is a notification concern only. The underlying telemetry is
    still persisted by MonitoringStore.
    """

    def __init__(
        self,
        *,
        default_cooldown_seconds: float = 60.0,
        sink: Callable[[Alert], None] | None = None,
    ) -> None:
        if default_cooldown_seconds < 0:
            raise ValueError("default_cooldown_seconds must be non-negative")
        self.default_cooldown_seconds = default_cooldown_seconds
        self.sink = sink
        self._last_emitted: dict[str, datetime] = {}

    def should_emit(
        self,
        alert: Alert,
        *,
        now: datetime | None = None,
        cooldown_seconds: float | None = None,
    ) -> bool:
        """Return whether a repeated alert should be externally emitted."""
        current = now or datetime.now(timezone.utc)
        previous = self._last_emitted.get(self._dedupe_key(alert))
        if previous is None:
            return True

        cooldown = (
            self.default_cooldown_seconds
            if cooldown_seconds is None
            else cooldown_seconds
        )
        if cooldown < 0:
            raise ValueError("cooldown_seconds must be non-negative")
        return current - previous >= timedelta(seconds=cooldown)

    def route(
        self,
        alert: Alert,
        *,
        now: datetime | None = None,
        cooldown_seconds: float | None = None,
    ) -> bool:
        """Route an alert to the configured sink when not suppressed."""
        current = now or alert.timestamp
        if not self.should_emit(
            alert,
            now=current,
            cooldown_seconds=cooldown_seconds,
        ):
            return False

        self._last_emitted[self._dedupe_key(alert)] = current
        if self.sink is not None:
            self.sink(alert)
        return True

    @staticmethod
    def _dedupe_key(alert: Alert) -> str:
        return "|".join(
            (
                alert.code,
                alert.source,
                alert.severity.value,
                alert.correlation_id or "",
            )
        )

"""M20.6 JARVIS daily lifecycle orchestrator.

The orchestrator is a deterministic control plane around existing STOCK_BOT
components. It sequences lifecycle phases, records failures, and always keeps
broker order submission disabled in SHADOW/PAPER modes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Callable, Mapping, Any
from zoneinfo import ZoneInfo

from .mode import RuntimeSafety


class LifecyclePhase(str, Enum):
    BOOT = "BOOT"
    PRE_OPEN = "PRE_OPEN"
    MARKET_ACTIVE = "MARKET_ACTIVE"
    MARKET_CLOSE = "MARKET_CLOSE"
    POST_MARKET = "POST_MARKET"
    NIGHT_RESEARCH = "NIGHT_RESEARCH"
    MORNING_BRIEF = "MORNING_BRIEF"


@dataclass(frozen=True, slots=True)
class LifecycleWindow:
    start: time
    end: time

    def contains(self, value: time) -> bool:
        if self.start <= self.end:
            return self.start <= value < self.end
        return value >= self.start or value < self.end


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    phase: LifecyclePhase
    started_at: datetime
    completed_at: datetime
    status: str
    error: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class JarvisLifecycle:
    """Safe daily lifecycle state machine."""

    safety: RuntimeSafety
    timezone_name: str = "Asia/Kolkata"
    hooks: dict[LifecyclePhase, Callable[[], Mapping[str, Any] | None]] = field(
        default_factory=dict
    )
    history: list[LifecycleResult] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.safety.assert_safe()

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    def run_phase(
        self,
        phase: LifecyclePhase,
        *,
        now: datetime | None = None,
    ) -> LifecycleResult:
        """Execute exactly one lifecycle phase and fail closed on errors."""
        self.safety.assert_safe()
        started = self._normalize_now(now)
        hook = self.hooks.get(phase)
        if hook is None:
            result = LifecycleResult(
                phase=phase,
                started_at=started,
                completed_at=started,
                status="SKIPPED_NO_HOOK",
                evidence={"live_broker_order_submission": False},
            )
            self.history.append(result)
            return result

        try:
            payload = dict(hook() or {})
            payload["live_broker_order_submission"] = False
            completed = datetime.now(timezone.utc)
            result = LifecycleResult(
                phase=phase,
                started_at=started,
                completed_at=completed,
                status="COMPLETED",
                evidence=payload,
            )
        except Exception as exc:
            completed = datetime.now(timezone.utc)
            result = LifecycleResult(
                phase=phase,
                started_at=started,
                completed_at=completed,
                status="FAILED_CLOSED",
                error=f"{type(exc).__name__}: {exc}",
                evidence={"live_broker_order_submission": False},
            )
        self.history.append(result)
        return result

    def run_daily(
        self,
        *,
        now: datetime | None = None,
        phases: tuple[LifecyclePhase, ...] | None = None,
    ) -> tuple[LifecycleResult, ...]:
        """Run the requested daily sequence in canonical order."""
        selected = phases or tuple(LifecyclePhase)
        results = []
        for phase in selected:
            result = self.run_phase(phase, now=now)
            results.append(result)
            if result.status == "FAILED_CLOSED":
                break
        return tuple(results)

    def phase_for(self, now: datetime | None = None) -> LifecyclePhase:
        """Resolve the current IST lifecycle phase."""
        local = self._normalize_now(now).astimezone(self.timezone).time()
        if time(0, 0) <= local < time(8, 45):
            return LifecyclePhase.MORNING_BRIEF
        if time(8, 45) <= local < time(9, 15):
            return LifecyclePhase.PRE_OPEN
        if time(9, 15) <= local < time(15, 30):
            return LifecyclePhase.MARKET_ACTIVE
        if time(15, 30) <= local < time(16, 30):
            return LifecyclePhase.MARKET_CLOSE
        if time(16, 30) <= local < time(21, 0):
            return LifecyclePhase.POST_MARKET
        return LifecyclePhase.NIGHT_RESEARCH

    def run_current_phase(self, *, now: datetime | None = None) -> LifecycleResult:
        return self.run_phase(self.phase_for(now), now=now)

    def dashboard(self) -> dict[str, Any]:
        """Return operator-facing lifecycle state without trading authority."""
        latest = self.history[-1] if self.history else None
        return {
            "mode": self.safety.mode,
            "live_broker_order_submission": False,
            "latest_phase": latest.phase.value if latest else None,
            "latest_status": latest.status if latest else None,
            "history_count": len(self.history),
            "failed_closed_count": sum(
                item.status == "FAILED_CLOSED" for item in self.history
            ),
        }

    def _normalize_now(self, now: datetime | None) -> datetime:
        value = now or datetime.now(timezone.utc)
        if value.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return value.astimezone(timezone.utc)

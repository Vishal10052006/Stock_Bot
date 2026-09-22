"""Independent global risk lock."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class KillSwitchState:
    """Immutable snapshot of the global risk lock."""
    active: bool = False
    reason: str = ""
    activated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.active and not self.reason:
            raise ValueError("an active kill switch requires a reason")
        if self.activated_at is not None and self.activated_at.tzinfo is None:
            raise ValueError("activated_at must be timezone-aware")


class KillSwitch:
    """Deterministic controller with no broker access."""

    def __init__(self) -> None:
        self._state = KillSwitchState()

    @property
    def state(self) -> KillSwitchState:
        return self._state

    def activate(self, reason: str, *, at: datetime | None = None) -> KillSwitchState:
        """Activate the lock."""
        if not reason or not reason.strip():
            raise ValueError("kill-switch reason must not be empty")
        timestamp = at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("kill-switch timestamp must be timezone-aware")
        self._state = KillSwitchState(True, reason.strip(), timestamp)
        return self._state

    def reset(self) -> KillSwitchState:
        """Reset the in-process lock explicitly."""
        self._state = KillSwitchState()
        return self._state

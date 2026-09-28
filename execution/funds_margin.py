"""Provider-neutral observation-only funds and margin snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math


@dataclass(frozen=True, slots=True)
class FundsMarginSnapshot:
    """Immutable broker/account funds observation; never an execution authority."""

    timestamp: datetime
    available_cash: float
    used_margin: float = 0.0
    available_margin: float = 0.0
    total_margin: float = 0.0
    source: str = "paper"

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        values = (
            self.available_cash,
            self.used_margin,
            self.available_margin,
            self.total_margin,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("funds and margin values must be finite")
        if any(value < 0 for value in values):
            raise ValueError("funds and margin values must be non-negative")
        if self.available_margin > self.total_margin + 1e-12:
            raise ValueError("available_margin cannot exceed total_margin")
        if self.used_margin > self.total_margin + 1e-12:
            raise ValueError("used_margin cannot exceed total_margin")
        if not self.source.strip():
            raise ValueError("source must be non-empty")

    @property
    def margin_utilization(self) -> float:
        """Return used/total margin, or zero when no margin is allocated."""
        if self.total_margin == 0:
            return 0.0
        return self.used_margin / self.total_margin

    def evidence(self) -> dict[str, object]:
        """Return non-secret observation evidence only."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "available_cash": self.available_cash,
            "used_margin": self.used_margin,
            "available_margin": self.available_margin,
            "total_margin": self.total_margin,
            "margin_utilization": self.margin_utilization,
            "source": self.source,
            "observation_only": True,
            "live_broker_order_submission": False,
        }


__all__ = ["FundsMarginSnapshot"]

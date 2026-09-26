"""Provider-neutral funds and margin snapshot.

Observation-only contract for account capacity. This layer does not calculate
broker-specific margin rules and does not grant order authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite


@dataclass(frozen=True, slots=True)
class FundsMarginSnapshot:
    """Immutable point-in-time funds/margin capacity."""

    timestamp: datetime
    available_cash: float
    used_margin: float = 0.0
    available_margin: float = 0.0
    total_margin: float = 0.0
    source: str = "paper"

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("funds timestamp must be timezone-aware")

        for name, value in (
            ("available_cash", self.available_cash),
            ("used_margin", self.used_margin),
            ("available_margin", self.available_margin),
            ("total_margin", self.total_margin),
        ):
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
            if float(value) < 0:
                raise ValueError(f"{name} must be non-negative")

        if self.available_margin > self.total_margin + 1e-12:
            raise ValueError("available_margin cannot exceed total_margin")
        if self.used_margin > self.total_margin + 1e-12:
            raise ValueError("used_margin cannot exceed total_margin")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")

        object.__setattr__(self, "source", self.source.strip().lower())

    @property
    def margin_utilization(self) -> float:
        """Return used/total margin; zero when no margin is provisioned."""
        if self.total_margin == 0:
            return 0.0
        return self.used_margin / self.total_margin

    def evidence(self) -> dict[str, object]:
        """Return non-secret capacity evidence."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "available_cash": self.available_cash,
            "used_margin": self.used_margin,
            "available_margin": self.available_margin,
            "total_margin": self.total_margin,
            "margin_utilization": self.margin_utilization,
            "source": self.source,
            "live_broker_order_submission": False,
        }


__all__ = ["FundsMarginSnapshot"]

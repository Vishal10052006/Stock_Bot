"""Stable Market Bot contracts.

Market Bot describes market state. It does not make trading decisions,
approve risk, size positions, or execute orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MarketState:
    """Immutable descriptive market state at one causal timestamp."""

    timestamp: datetime
    benchmark: str
    regime: str | None = None
    regime_probability: float | None = None
    trend_state: str | None = None
    trend_strength: float | None = None
    range_state: str | None = None
    volatility_state: str | None = None
    breadth_state: str | None = None
    sector_state: str | None = None
    rotation_state: str | None = None
    correlation_state: str | None = None
    liquidity_state: str | None = None
    strength_state: str | None = None
    transition_state: str | None = None
    quality: float | None = None
    provenance: str = "market_bot"
    version: str = "market-bot-v1"

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if not self.benchmark.strip():
            raise ValueError("benchmark must not be empty")

        for name in ("regime_probability", "trend_strength", "quality"):
            value = getattr(self, name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")

        object.__setattr__(self, "benchmark", self.benchmark.strip().upper())
        object.__setattr__(self, "provenance", self.provenance.strip())
        object.__setattr__(self, "version", self.version.strip())


MarketContext = MarketState

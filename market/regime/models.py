"""Models and constants for Phase 6 market-regime detection."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MarketRegime(str, Enum):
    """Deterministic Phase 6 market states."""

    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"


REGIME_OUTPUT_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "regime",
    "regime_probability",
)


@dataclass(frozen=True)
class RegimeConfig:
    """Frozen, explicit rules for the Phase 6 v1 detector.

    Thresholds are configuration, not learned from the full historical
    sample. Any later threshold fitting must be performed only inside the
    training portion of a walk-forward split.
    """

    trend_return_threshold: float = 0.0025
    trend_confirmation_threshold: float = 0.0005
    range_return_threshold: float = 0.0010
    volatility_baseline_window: int = 20
    high_volatility_ratio: float = 1.50
    low_volatility_ratio: float = 0.75
    min_probability: float = 0.50

    def __post_init__(self) -> None:
        if self.trend_return_threshold <= 0:
            raise ValueError("trend_return_threshold must be positive")
        if self.trend_confirmation_threshold <= 0:
            raise ValueError("trend_confirmation_threshold must be positive")
        if self.range_return_threshold < 0:
            raise ValueError("range_return_threshold must be non-negative")
        if self.volatility_baseline_window < 2:
            raise ValueError("volatility_baseline_window must be at least 2")
        if not self.high_volatility_ratio > 1.0:
            raise ValueError("high_volatility_ratio must be greater than 1")
        if not 0.0 < self.low_volatility_ratio < 1.0:
            raise ValueError("low_volatility_ratio must be between 0 and 1")
        if not 0.0 <= self.min_probability <= 1.0:
            raise ValueError("min_probability must be between 0 and 1")

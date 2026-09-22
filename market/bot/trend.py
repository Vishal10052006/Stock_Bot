"""MB-02 deterministic, causal market trend engine."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class MarketTrend:
    """Descriptive trend state for one timestamp."""

    state: str
    strength: float
    slope: float
    price_vs_fast_ma: float
    price_vs_slow_ma: float
    fast_ma_vs_slow_ma: float
    return_fast: float
    return_slow: float


@dataclass(frozen=True, slots=True)
class MarketTrendConfig:
    """Deterministic MB-02 parameters."""

    fast_window: int = 20
    slow_window: int = 50
    slope_window: int = 20
    return_window: int = 20
    strong_threshold: float = 0.60

    def __post_init__(self) -> None:
        for name in ("fast_window", "slow_window", "slope_window", "return_window"):
            value = getattr(self, name)
            if value < 2:
                raise ValueError(f"{name} must be >= 2")
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        if not 0.0 < self.strong_threshold <= 1.0:
            raise ValueError("strong_threshold must be within (0, 1]")


class MarketTrendEngine:
    """Compute descriptive market trend without future information."""

    def __init__(self, config: MarketTrendConfig | None = None) -> None:
        self.config = config or MarketTrendConfig()

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return causal trend columns aligned to input timestamps.

        Required columns: timestamp and close.
        Rolling calculations use only current and earlier rows.
        """
        required = {"timestamp", "close"}
        missing = required.difference(data.columns)
        if missing:
            raise ValueError(f"missing required columns: {sorted(missing)}")

        frame = data.loc[:, ["timestamp", "close"]].copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")

        if frame["timestamp"].duplicated().any():
            raise ValueError("timestamp values must be unique")
        if not frame["timestamp"].is_monotonic_increasing:
            raise ValueError("timestamp must be monotonically increasing")

        close = frame["close"]

        fast_ma = close.rolling(
            self.config.fast_window,
            min_periods=self.config.fast_window,
        ).mean()
        slow_ma = close.rolling(
            self.config.slow_window,
            min_periods=self.config.slow_window,
        ).mean()

        frame["trend_fast_ma"] = fast_ma
        frame["trend_slow_ma"] = slow_ma
        frame["trend_price_vs_fast_ma"] = close / fast_ma - 1.0
        frame["trend_price_vs_slow_ma"] = close / slow_ma - 1.0
        frame["trend_fast_ma_vs_slow_ma"] = fast_ma / slow_ma - 1.0
        frame["trend_return_fast"] = close.pct_change(self.config.return_window)
        frame["trend_return_slow"] = close.pct_change(self.config.slow_window)
        frame["trend_slope"] = slow_ma.pct_change(self.config.slope_window)

        alignment = np.sign(frame["trend_fast_ma_vs_slow_ma"].fillna(0.0))
        slope_sign = np.sign(frame["trend_slope"].fillna(0.0))
        price_sign = np.sign(frame["trend_price_vs_slow_ma"].fillna(0.0))

        score = (alignment + slope_sign + price_sign) / 3.0
        frame["trend_strength"] = score.abs().clip(0.0, 1.0)

        state = pd.Series("UNAVAILABLE", index=frame.index, dtype="object")
        ready = (
            frame["trend_fast_ma"].notna()
            & frame["trend_slow_ma"].notna()
            & frame["trend_slope"].notna()
        )

        state.loc[ready & (score >= self.config.strong_threshold)] = "UP"
        state.loc[ready & (score <= -self.config.strong_threshold)] = "DOWN"
        state.loc[ready & (score.abs() < self.config.strong_threshold)] = "MIXED"

        frame["trend_state"] = state
        return frame


def calculate_market_trend(
    data: pd.DataFrame,
    config: MarketTrendConfig | None = None,
) -> pd.DataFrame:
    """Functional MB-02 entry point."""
    return MarketTrendEngine(config).calculate(data)

"""MB-04 causal volatility regime engine."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .validation import validate_ohlcv_frame


@dataclass(frozen=True, slots=True)
class VolatilityConfig:
    short_window: int = 10
    long_window: int = 20
    baseline_window: int = 60
    low_ratio: float = 0.80
    high_ratio: float = 1.25

    def __post_init__(self) -> None:
        if min(self.short_window, self.long_window, self.baseline_window) < 2:
            raise ValueError("volatility windows must be >= 2")
        if not 0 < self.low_ratio < 1 < self.high_ratio:
            raise ValueError("volatility ratios must satisfy low < 1 < high")


class VolatilityEngine:
    def __init__(self, config: VolatilityConfig | None = None) -> None:
        self.config = config or VolatilityConfig()

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        frame = validate_ohlcv_frame(data)
        close = pd.to_numeric(frame["close"], errors="coerce")
        returns = close.pct_change()
        realized = returns.rolling(self.config.long_window, min_periods=self.config.long_window).std() * np.sqrt(252.0)
        short = returns.rolling(self.config.short_window, min_periods=self.config.short_window).std() * np.sqrt(252.0)
        baseline = realized.rolling(
            self.config.baseline_window,
            min_periods=self.config.baseline_window,
        ).median().shift(1)
        ratio = realized.div(baseline.replace(0.0, np.nan))
        state = pd.Series("UNAVAILABLE", index=frame.index, dtype="object")
        state.loc[ratio <= self.config.low_ratio] = "LOW"
        state.loc[(ratio > self.config.low_ratio) & (ratio < self.config.high_ratio)] = "NORMAL"
        state.loc[ratio >= self.config.high_ratio] = "HIGH"
        frame["volatility_level"] = realized
        frame["volatility_short"] = short
        frame["volatility_baseline"] = baseline
        frame["volatility_ratio"] = ratio
        frame["volatility_state"] = state
        return frame


def calculate_volatility(data: pd.DataFrame, config: VolatilityConfig | None = None) -> pd.DataFrame:
    return VolatilityEngine(config).calculate(data)

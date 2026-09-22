"""MB-02 causal multi-horizon market trend engine."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .validation import validate_ohlcv_frame


@dataclass(frozen=True, slots=True)
class TrendConfig:
    fast_window: int = 20
    slow_window: int = 50
    slope_window: int = 20
    return_window: int = 20
    strong_threshold: float = 2 / 3

    def __post_init__(self) -> None:
        if self.fast_window < 2 or self.slow_window < 3 or self.fast_window >= self.slow_window:
            raise ValueError("invalid trend windows")
        if self.slope_window < 2 or self.return_window < 1:
            raise ValueError("invalid trend lookbacks")


class TrendEngine:
    """Calculate descriptive trend without future observations."""

    def __init__(self, config: TrendConfig | None = None) -> None:
        self.config = config or TrendConfig()

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        frame = validate_ohlcv_frame(data)
        close = pd.to_numeric(frame["close"], errors="coerce")
        fast = close.rolling(self.config.fast_window, min_periods=self.config.fast_window).mean()
        slow = close.rolling(self.config.slow_window, min_periods=self.config.slow_window).mean()
        frame["trend_fast_ma"] = fast
        frame["trend_slow_ma"] = slow
        frame["trend_price_vs_fast_ma"] = close.div(fast).sub(1.0)
        frame["trend_price_vs_slow_ma"] = close.div(slow).sub(1.0)
        frame["trend_fast_ma_vs_slow_ma"] = fast.div(slow).sub(1.0)
        frame["trend_return"] = close.pct_change(self.config.return_window)
        frame["trend_slope"] = slow.pct_change(self.config.slope_window)

        score = (
            np.sign(frame["trend_fast_ma_vs_slow_ma"].fillna(0.0))
            + np.sign(frame["trend_slope"].fillna(0.0))
            + np.sign(frame["trend_price_vs_slow_ma"].fillna(0.0))
        ) / 3.0
        ready = fast.notna() & slow.notna() & frame["trend_slope"].notna()
        frame["trend_strength"] = score.abs().clip(0.0, 1.0)
        state = pd.Series("UNAVAILABLE", index=frame.index, dtype="object")
        state.loc[ready & (score >= self.config.strong_threshold)] = "UP"
        state.loc[ready & (score <= -self.config.strong_threshold)] = "DOWN"
        state.loc[ready & (score.abs() < self.config.strong_threshold)] = "MIXED"
        frame["trend_state"] = state
        return frame


def calculate_trend(data: pd.DataFrame, config: TrendConfig | None = None) -> pd.DataFrame:
    return TrendEngine(config).calculate(data)

"""MB-03 causal range/trend structure engine."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .validation import validate_ohlcv_frame


@dataclass(frozen=True, slots=True)
class StructureConfig:
    lookback: int = 20
    compression_window: int = 20
    trend_threshold: float = 0.004
    compression_quantile: float = 0.30


class StructureEngine:
    """Classify price behavior as TRENDING, RANGING, or UNAVAILABLE."""

    def __init__(self, config: StructureConfig | None = None) -> None:
        self.config = config or StructureConfig()

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        frame = validate_ohlcv_frame(data, ("timestamp", "close"))
        close = pd.to_numeric(frame["close"], errors="coerce")
        rolling_high = close.rolling(self.config.lookback, min_periods=self.config.lookback).max()
        rolling_low = close.rolling(self.config.lookback, min_periods=self.config.lookback).min()
        width = rolling_high.div(rolling_low).sub(1.0)
        directional = close.pct_change(self.config.lookback).abs()
        width_baseline = width.rolling(
            self.config.compression_window,
            min_periods=self.config.compression_window,
        ).median().shift(1)

        frame["range_high"] = rolling_high
        frame["range_low"] = rolling_low
        frame["range_width"] = width
        frame["range_directional_move"] = directional
        frame["range_compressed"] = width < width_baseline * (1.0 + self.config.compression_quantile)

        ready = rolling_high.notna() & rolling_low.notna() & directional.notna()
        state = pd.Series("UNAVAILABLE", index=frame.index, dtype="object")
        state.loc[ready & (directional >= self.config.trend_threshold)] = "TRENDING"
        state.loc[ready & (directional < self.config.trend_threshold)] = "RANGING"
        frame["range_state"] = state

        direction = pd.Series("NEUTRAL", index=frame.index, dtype="object")
        direction.loc[ready & (close > close.shift(self.config.lookback))] = "UP"
        direction.loc[ready & (close < close.shift(self.config.lookback))] = "DOWN"
        frame["structure_direction"] = direction
        return frame


def calculate_structure(data: pd.DataFrame, config: StructureConfig | None = None) -> pd.DataFrame:
    return StructureEngine(config).calculate(data)

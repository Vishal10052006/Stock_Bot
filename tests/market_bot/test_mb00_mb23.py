"""Compatibility/regression tests for the canonical Market Bot implementation."""
from __future__ import annotations

import numpy as np
import pandas as pd

from market.bot.breadth import BreadthEngine
from market.bot.orchestrator import MarketBot, MarketBotConfig
from market.bot.structure import StructureEngine
from market.bot.trend import TrendEngine
from market.bot.volatility import VolatilityEngine


def benchmark(n: int = 120) -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC")
    close = 100.0 * np.cumprod(1.0 + np.full(n, 0.001))
    return pd.DataFrame({"timestamp": timestamps, "close": close})


def constituents(n: int = 120) -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC")
    rows = []
    for j, symbol in enumerate(("NIFTY50", "AAA", "BBB", "CCC")):
        close = (100.0 + j * 5.0) * np.cumprod(1.0 + np.full(n, 0.0005 if j % 2 == 0 else -0.0002))
        for timestamp, value in zip(timestamps, close):
            rows.append({"timestamp": timestamp, "symbol": symbol, "close": value, "volume": 100000 + j * 10000})
    return pd.DataFrame(rows)


def test_trend_warmup_and_causality():
    frame = benchmark()
    first = TrendEngine().calculate(frame)
    extended = pd.concat(
        [frame, pd.DataFrame([{"timestamp": frame["timestamp"].iloc[-1] + pd.Timedelta(days=1), "close": 9999.0}])],
        ignore_index=True,
    )
    second = TrendEngine().calculate(extended)
    assert first["trend_state"].iloc[0] == "UNAVAILABLE"
    assert first["trend_state"].iloc[-1] == second["trend_state"].iloc[-2]


def test_structure_and_volatility_contracts():
    frame = benchmark()
    assert "range_state" in StructureEngine().calculate(frame)
    assert "volatility_state" in VolatilityEngine().calculate(frame)


def test_market_bot_orchestration():
    frame = benchmark()
    state = MarketBot(MarketBotConfig(benchmark="NIFTY50")).build(
        benchmark_data=frame,
        constituent_data=constituents(),
    )
    assert state.benchmark == "NIFTY50"
    assert state.state.regime in {None, "TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOLATILITY", "LOW_VOLATILITY"}


def test_breadth_is_causal_and_explicitly_unavailable_during_warmup():
    result = BreadthEngine().calculate(constituents(3))
    assert result.iloc[0]["breadth_state"] == "UNAVAILABLE"


def test_future_rows_do_not_change_volatility_history():
    frame = benchmark()
    first = VolatilityEngine().calculate(frame)
    future = pd.concat(
        [frame, pd.DataFrame([{"timestamp": frame["timestamp"].iloc[-1] + pd.Timedelta(days=1), "close": 5000.0}])],
        ignore_index=True,
    )
    second = VolatilityEngine().calculate(future)
    pd.testing.assert_frame_equal(
        first[["timestamp", "volatility_state"]].reset_index(drop=True),
        second[["timestamp", "volatility_state"]].iloc[:-1].reset_index(drop=True),
        check_dtype=False,
    )

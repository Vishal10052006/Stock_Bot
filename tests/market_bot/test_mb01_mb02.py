"""MB-01 and MB-02 contract tests."""

from datetime import date

import pandas as pd
import pytest

from market.bot.trend import MarketTrendEngine
from market.bot.universe import MarketBenchmark, MarketUniverse


def test_market_universe_canonicalizes_symbols():
    universe = MarketUniverse(
        as_of=date(2026, 9, 21),
        exchange="nse",
        symbols=("TCS", "RELIANCE", "INFY"),
        policy_version="MB-01-v1",
        source="test",
    )
    assert universe.symbols == ("INFY", "RELIANCE", "TCS")
    assert universe.contains("tcs")


def test_market_benchmark_is_descriptive():
    benchmark = MarketBenchmark(symbol="NIFTY 50", exchange="nse")
    assert benchmark.symbol == "NIFTY 50"
    assert benchmark.exchange == "NSE"


def _trend_frame(n: int = 120) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC")
    close = pd.Series(range(100, 100 + n), dtype=float)
    return pd.DataFrame({"timestamp": ts, "close": close})


def test_mb02_trend_becomes_available_after_warmup():
    result = MarketTrendEngine().calculate(_trend_frame())
    assert result["trend_state"].iloc[0] == "UNAVAILABLE"
    assert (result["trend_state"] == "UP").any()
    assert result["trend_strength"].dropna().between(0.0, 1.0).all()


def test_mb02_rejects_unsorted_timestamps():
    frame = _trend_frame().iloc[::-1].reset_index(drop=True)
    with pytest.raises(ValueError, match="monotonically increasing"):
        MarketTrendEngine().calculate(frame)


def test_mb02_future_rows_do_not_change_history():
    base = _trend_frame()
    future = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                base["timestamp"].iloc[-1] + pd.Timedelta(days=1),
                periods=20,
                freq="D",
                tz="UTC",
            ),
            "close": range(1000, 1020),
        }
    )

    first = MarketTrendEngine().calculate(base)
    combined = MarketTrendEngine().calculate(
        pd.concat([base, future], ignore_index=True)
    )

    cols = [
        "trend_fast_ma",
        "trend_slow_ma",
        "trend_price_vs_fast_ma",
        "trend_price_vs_slow_ma",
        "trend_fast_ma_vs_slow_ma",
        "trend_return_fast",
        "trend_return_slow",
        "trend_slope",
        "trend_strength",
        "trend_state",
    ]

    pd.testing.assert_frame_equal(
        first[cols],
        combined.loc[: len(base) - 1, cols],
        check_dtype=False,
    )

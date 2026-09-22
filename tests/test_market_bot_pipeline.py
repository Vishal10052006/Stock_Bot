"""End-to-end Market Bot -> AB-30 composition tests."""
from __future__ import annotations

import numpy as np
import pandas as pd

from market.bot.orchestrator import MarketBot, MarketBotConfig
from trading.market_bot_pipeline import build_market_analysis_from_market_bot


def _benchmark(rows: int = 40) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-09-20 09:15:00+05:30",
        periods=rows,
        freq="5min",
    )
    close = 100.0 * np.cumprod(1.0 + np.full(rows, 0.001))
    return pd.DataFrame({"timestamp": timestamps, "close": close})


def _candles(rows: int = 40) -> pd.DataFrame:
    benchmark = _benchmark(rows)
    close = benchmark["close"].to_numpy()
    return pd.DataFrame({
        "timestamp": benchmark["timestamp"],
        "symbol": ["RELIANCE"] * rows,
        "open": close,
        "high": close + 0.20,
        "low": close - 0.15,
        "close": close,
        "volume": [1000 + (index * 10) for index in range(rows)],
    })


def test_market_bot_context_feeds_frozen_ab30_without_duplicate_regime_logic():
    benchmark = _benchmark()
    context = MarketBot(
        MarketBotConfig(benchmark="NIFTY", data_version="market-test")
    ).build(benchmark_data=benchmark)

    result = build_market_analysis_from_market_bot(
        _candles(),
        symbol="RELIANCE",
        benchmark_history=benchmark,
        market_context=context,
    )

    assert result.analysis.symbol == "RELIANCE"
    assert not result.features.empty
    assert not result.regime.empty
    assert result.analysis.timestamp == result.features.iloc[-1]["timestamp"]
    assert result.analysis.provenance["market_bot"]["market_version"] == context.metadata.market_version
    assert result.analysis.provenance["market_bot"]["data_version"] == "market-test"


def test_market_bot_ab30_composition_rejects_stale_snapshot_endpoint():
    benchmark = _benchmark()
    stale_history = benchmark.iloc[:-1].copy()
    context = MarketBot(
        MarketBotConfig(benchmark="NIFTY")
    ).build(benchmark_data=benchmark)

    try:
        build_market_analysis_from_market_bot(
            _candles(),
            symbol="RELIANCE",
            benchmark_history=stale_history,
            market_context=context,
        )
    except ValueError as exc:
        assert "endpoint" in str(exc)
    else:
        raise AssertionError("stale MarketContext snapshot must fail closed")


def test_market_bot_ab30_composition_rejects_context_after_candle_endpoint():
    benchmark = _benchmark()
    context = MarketBot(
        MarketBotConfig(benchmark="NIFTY")
    ).build(benchmark_data=benchmark)

    candles = _candles().iloc[:-1].copy()

    try:
        build_market_analysis_from_market_bot(
            candles,
            symbol="RELIANCE",
            benchmark_history=benchmark,
            market_context=context,
        )
    except ValueError as exc:
        assert "future" in str(exc)
    else:
        raise AssertionError(
            "MarketContext after the analysis candle endpoint must fail closed"
        )

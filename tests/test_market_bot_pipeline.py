"""End-to-end Market Bot -> AB-30 composition tests."""
from __future__ import annotations

import numpy as np
import pandas as pd

from market.bot.orchestrator import MarketBot, MarketBotConfig
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from monitoring.runtime import MonitoringRuntime
from trading.runtime_pipeline import TradingResearchRuntime
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


def test_shared_runtime_composition_carries_market_analysis_prediction_and_paper_telemetry():
    from tests.test_analysis_prediction_integration import _training_frame

    benchmark = _benchmark()
    context = MarketBot(
        MarketBotConfig(benchmark="NIFTY", data_version="market-test")
    ).build(benchmark_data=benchmark)

    X_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    model = LogisticOutcomeModel()
    model.fit(preprocessor.fit_transform(X_train), y_train)

    runtime = TradingResearchRuntime(monitoring=MonitoringRuntime())
    result, prediction = runtime.market_analysis_and_prediction(
        _candles(),
        symbol="RELIANCE",
        benchmark_history=benchmark,
        market_context=context,
        model=model,
        preprocessor=preprocessor,
    )

    paper_rows = pd.DataFrame([{
        "timestamp": "2026-09-20T10:00:00Z",
        "symbol": "RELIANCE",
        "close": 110.0,
        "regime": "TREND",
        "regime_probability": 0.9,
        "vwap_distance_pct": 0.01,
        "rvol_20": 1.5,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }])
    runtime.paper_decisions(paper_rows)
    payload = runtime.report()

    assert result.analysis.symbol == "RELIANCE"
    assert prediction.symbol == "RELIANCE"
    assert "analysis.completeness" in payload["metrics"]
    assert "model.prediction_count" in payload["metrics"]
    assert "strategy.decisions" in payload["metrics"]
    assert "risk.equity" in payload["metrics"]

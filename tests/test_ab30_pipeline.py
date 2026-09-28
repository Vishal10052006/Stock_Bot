"""AB-30 tests for the real Phase 4 -> 5 -> 6 -> Analysis path."""
from __future__ import annotations

import pandas as pd

from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from monitoring.runtime import MonitoringRuntime

from trading.ab30_pipeline import (
    MarketAnalysisPipelineError,
    build_market_analysis,
    build_market_analysis_and_prediction,
)


def _candles(rows: int = 40) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-09-20 09:15:00+05:30",
        periods=rows,
        freq="5min",
    )
    close = [100.0 + (index * 0.25) for index in range(rows)]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["RELIANCE"] * rows,
            "open": close,
            "high": [value + 0.20 for value in close],
            "low": [value - 0.15 for value in close],
            "close": close,
            "volume": [1000 + (index * 10) for index in range(rows)],
        }
    )


def _market_context(rows: int = 40) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-09-20 09:15:00+05:30",
        periods=rows,
        freq="5min",
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "market_return_1": [0.001] * rows,
            "market_return_3": [0.006] * rows,
            "market_return_12": [0.025] * rows,
            "market_volatility_20": [0.015] * rows,
        }
    )


def test_ab30_real_market_pipeline_reaches_analysis_context() -> None:
    result = build_market_analysis(
        _candles(),
        symbol="RELIANCE",
        market_context=_market_context(),
    )

    assert result.indicators.shape[0] == 40
    assert result.features.shape[0] == 40
    assert not result.features.empty
    assert not result.regime.empty
    assert result.analysis.symbol == "RELIANCE"
    assert result.analysis.timestamp == result.features.iloc[-1]["timestamp"]
    assert result.analysis.analysis_version == "v1.0"


def test_ab30_requires_market_context_for_phase6_regime() -> None:
    try:
        build_market_analysis(
            _candles(),
            symbol="RELIANCE",
        )
    except MarketAnalysisPipelineError as exc:
        assert "requires market context" in str(exc)
    else:
        raise AssertionError("missing market context must fail closed")


def test_ab30_market_to_prediction_uses_shared_monitoring_runtime() -> None:
    from tests.test_analysis_prediction_integration import _training_frame

    X_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    model = LogisticOutcomeModel()
    model.fit(preprocessor.fit_transform(X_train), y_train)

    runtime = MonitoringRuntime()
    result, prediction = build_market_analysis_and_prediction(
        _candles(),
        symbol="RELIANCE",
        model=model,
        preprocessor=preprocessor,
        market_context=_market_context(),
        monitoring=runtime,
    )

    payload = runtime.dashboard()
    assert result.analysis.symbol == "RELIANCE"
    assert prediction.symbol == "RELIANCE"
    assert prediction.model_version == "phase9-logistic-v1"
    assert "analysis.completeness" in payload["metrics"]
    assert "model.prediction_count" in payload["metrics"]
    assert "model.prediction_max_probability" in payload["metrics"]

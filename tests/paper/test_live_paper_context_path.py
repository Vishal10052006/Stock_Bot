"""Regression tests for canonical live Analysis -> Prediction -> Paper wiring."""

import pandas as pd

from intelligence.analysis.contracts import AnalysisContext
from ml.integration.analysis_prediction import PredictionContext
from ml.models.logistic import MODEL_CLASSES
from trading.paper.live_loop import LivePaperEngine, LivePaperSessionConfig
from trading.strategy.models import StrategyDecision, StrategyDirection


class _CaptureStrategy:
    def __init__(self):
        self.value = None

    def decide(self, strategy_input):
        self.value = strategy_input
        return (
            StrategyDecision(
                timestamp=strategy_input.timestamp,
                symbol=strategy_input.symbol,
                direction=StrategyDirection.NO_TRADE,
                strategy_version="STRAT-test",
                rationale="test no-trade boundary",
            ),
            None,
        )


def _analysis(ts):
    return AnalysisContext(
        timestamp=ts,
        symbol="RELIANCE",
        technical_context={},
        structure_context={},
        volume_context={},
        volatility_context={},
        market_context={"available": True},
        sector_context={},
        relative_performance={},
        research_context={},
        feature_vector={
            "vwap_distance_pct": 0.1,
            "rvol_20": 1.2,
            "higher_high": True,
            "higher_low": True,
            "lower_low": False,
            "lower_high": False,
        },
        analytical_direction="BULLISH",
        analytical_state="ALIGNED",
        data_version="upstox-live",
        feature_version="v1.0",
    )


def _prediction(ts):
    probabilities = pd.DataFrame(
        [[0.65, 0.15, 0.20]],
        columns=list(MODEL_CLASSES),
    )
    return PredictionContext(
        timestamp=ts,
        symbol="RELIANCE",
        probabilities=probabilities,
        predicted_class=str(probabilities.iloc[0].idxmax()),
        model_version="phase9-live-test",
        feature_version="v1.0",
        analysis_version="v1.0",
    )


def test_live_paper_uses_canonical_analysis_and_prediction():
    timestamp = pd.Timestamp("2026-09-29T10:00:00+05:30")
    engine = LivePaperEngine(
        LivePaperSessionConfig(
            experiment_id="CONTEXT-001",
            symbol="RELIANCE",
            target_trades=1,
        )
    )
    capture = _CaptureStrategy()
    engine.strategy_engine = capture

    candle = {
        "timestamp": timestamp,
        "symbol": "RELIANCE",
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1000.0,
    }

    outcomes = engine.on_candle_with_context(
        candle,
        analysis=_analysis(timestamp),
        prediction=_prediction(timestamp),
        regime="TREND_UP",
        regime_probability=0.85,
    )

    assert outcomes == []
    assert capture.value is not None
    assert capture.value.prediction.model_version == "phase9-live-test"
    assert capture.value.analysis_context.analysis_version == "v1.0"
    assert capture.value.decision_features["rvol_20"] == 1.2
    assert capture.value.regime == "TREND_UP"


def test_live_paper_rejects_misaligned_prediction_timestamp():
    timestamp = pd.Timestamp("2026-09-29T10:00:00+05:30")
    engine = LivePaperEngine(
        LivePaperSessionConfig(symbol="RELIANCE", target_trades=1)
    )
    candle = {
        "timestamp": timestamp,
        "symbol": "RELIANCE",
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1000.0,
    }

    try:
        engine.on_candle_with_context(
            candle,
            analysis=_analysis(timestamp),
            prediction=_prediction(timestamp + pd.Timedelta(minutes=5)),
            regime="TREND_UP",
            regime_probability=0.85,
        )
    except ValueError as exc:
        assert "prediction timestamp" in str(exc)
    else:
        raise AssertionError("misaligned prediction must be rejected")

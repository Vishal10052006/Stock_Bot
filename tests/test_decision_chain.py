"""AB-29 end-to-end decision-chain tests."""
from __future__ import annotations

import pandas as pd

from execution.trading_execution import ExecutionAuthorizationStatus
from intelligence.analysis.contracts import AnalysisInput
from intelligence.analysis.engine import AnalysisEngine
from ml.integration.analysis_prediction import PredictionContext
from trading.decision_chain import build_decision_chain
from trading.risk.gate import RiskDecisionStatus
from trading.strategy.models import StrategyDirection


def _analysis() -> object:
    features = {
        "rsi_14": 62.0,
        "macd_histogram": 1.2,
        "roc_14": 0.4,
        "vwap_distance_pct": 0.8,
        "ema_9_20_distance_pct": 0.2,
        "ema_20_50_distance_pct": 0.5,
        "rvol_20": 1.4,
        "volume_change_1": 0.2,
        "atr_normalized": 0.01,
        "bb_width_normalized": 0.02,
        "realized_volatility_20": 0.015,
        "higher_high": True,
        "higher_low": True,
        "lower_high": False,
        "lower_low": False,
        "retest_up": True,
        "retest_down": False,
    }
    return AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
            symbol="RELIANCE",
            features=features,
            data_version="test-v1",
            feature_version="v1.0",
        )
    )


def _prediction(analysis: object) -> PredictionContext:
    return PredictionContext(
        timestamp=analysis.timestamp,
        symbol=analysis.symbol,
        probabilities=pd.DataFrame(
            [[0.70, 0.10, 0.20]],
            columns=["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"],
        ),
        predicted_class="LONG_SUCCESS",
        model_version="phase9-test-v1",
        feature_version="v1.0",
        analysis_version="v1.0",
    )


def _decision_features() -> pd.Series:
    return pd.Series(
        {
            "vwap_distance_pct": 0.8,
            "rvol_20": 1.4,
            "higher_high": True,
            "higher_low": True,
            "lower_low": False,
            "lower_high": False,
        }
    )


def test_ab29_full_chain_reaches_execution_authorization() -> None:
    analysis = _analysis()
    prediction = _prediction(analysis)

    chain = build_decision_chain(
        analysis,
        prediction,
        decision_features=_decision_features(),
        regime="TREND_UP",
        regime_probability=0.82,
    )

    assert chain.strategy.direction is StrategyDirection.LONG
    assert chain.risk.status is RiskDecisionStatus.APPROVED
    assert chain.execution.status is ExecutionAuthorizationStatus.AUTHORIZED


def test_ab29_failed_strategy_stops_before_execution() -> None:
    analysis = _analysis()
    prediction = _prediction(analysis)

    features = _decision_features()
    features["vwap_distance_pct"] = -0.1

    chain = build_decision_chain(
        analysis,
        prediction,
        decision_features=features,
        regime="TREND_UP",
        regime_probability=0.82,
    )

    assert chain.strategy.direction is StrategyDirection.NO_TRADE
    assert chain.risk.status is RiskDecisionStatus.REJECTED
    assert chain.execution.status is ExecutionAuthorizationStatus.BLOCKED


def test_ab29_timestamp_mismatch_is_rejected() -> None:
    analysis = _analysis()
    prediction = _prediction(analysis)
    prediction = PredictionContext(
        timestamp=analysis.timestamp + pd.Timedelta(minutes=5),
        symbol=analysis.symbol,
        probabilities=prediction.probabilities,
        predicted_class=prediction.predicted_class,
        model_version=prediction.model_version,
        feature_version=prediction.feature_version,
        analysis_version=prediction.analysis_version,
    )

    try:
        build_decision_chain(
            analysis,
            prediction,
            decision_features=_decision_features(),
            regime="TREND_UP",
            regime_probability=0.82,
        )
    except ValueError as exc:
        assert "timestamp" in str(exc)
    else:
        raise AssertionError("timestamp mismatch must be rejected")

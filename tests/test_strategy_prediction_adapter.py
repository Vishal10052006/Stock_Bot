"""AB-26 tests: PredictionContext must feed existing deterministic strategy rules."""
from __future__ import annotations

import numpy as np
import pandas as pd

from intelligence.analysis.contracts import AnalysisInput
from intelligence.analysis.engine import AnalysisEngine
from ml.integration.analysis_prediction import PredictionContext
from trading.strategy.models import StrategyDirection
from trading.strategy.prediction_adapter import strategy_from_prediction


def _prediction() -> PredictionContext:
    probabilities = pd.DataFrame(
        [[0.70, 0.10, 0.20]],
        columns=["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"],
    )
    return PredictionContext(
        timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
        symbol="RELIANCE",
        probabilities=probabilities,
        predicted_class="LONG_SUCCESS",
        model_version="phase9-test-v1",
        feature_version="v1.0",
        analysis_version="v1.0",
    )


def _decision_features(**overrides: object) -> pd.Series:
    values: dict[str, object] = {
        "vwap_distance_pct": 0.8,
        "rvol_20": 1.4,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }
    values.update(overrides)
    return pd.Series(values)


def test_ab26_reuses_existing_strategy_contract() -> None:
    """Model probabilities do not bypass deterministic Phase 8 rules."""
    decision = strategy_from_prediction(
        _prediction(),
        decision_features=_decision_features(),
        regime="TREND_UP",
        regime_probability=0.82,
    )

    assert decision.direction is StrategyDirection.LONG
    assert decision.strategy_version == "v1.0"
    assert "TREND_UP" in decision.rationale


def test_ab26_model_prediction_does_not_force_trade() -> None:
    """A LONG_SUCCESS probability cannot override failed strategy conditions."""
    decision = strategy_from_prediction(
        _prediction(),
        decision_features=_decision_features(vwap_distance_pct=-0.2),
        regime="TREND_UP",
        regime_probability=0.82,
    )

    assert decision.direction is StrategyDirection.NO_TRADE

"""Final Analysis Bot authority-boundary integration tests."""
from __future__ import annotations

import numpy as np
import pandas as pd

from intelligence.analysis.integration import build_analysis_context
from ml.integration.analysis_prediction import predict_from_analysis
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.models import BOOLEAN_FEATURES, NUMERIC_FEATURES
from ml.preprocessing.pipeline import FeaturePreprocessor
from trading.risk.gate import RiskDecisionStatus, evaluate_strategy_risk
from trading.strategy.models import StrategyDirection
from trading.strategy.prediction_adapter import strategy_from_prediction


def _feature_row() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-09-20 10:25:00+05:30")],
            "symbol": ["RELIANCE"],
            "close": [150.0],
            "ema_9": [149.0],
            "ema_20": [148.0],
            "ema_50": [145.0],
            "rsi_14": [62.0],
            "macd_histogram": [1.2],
            "roc_14": [0.4],
            "vwap_distance_pct": [0.8],
            "atr_14": [1.5],
            "bb_width": [3.0],
            "realized_volatility_20": [0.015],
            "rvol_20": [1.4],
            "volume_change_1": [0.2],
            "distance_to_support_pct": [1.0],
            "distance_to_resistance_pct": [-0.5],
            "previous_day_high": [151.0],
            "previous_day_low": [145.0],
            "opening_range_high": [150.5],
            "opening_range_low": [147.0],
            "opening_range_width": [3.5],
            "swing_high": [150.5],
            "swing_low": [146.0],
            "retest_up": [True],
            "retest_down": [False],
            "retest_distance_pct": [0.2],
            "higher_high": [True],
            "lower_low": [False],
            "higher_low": [True],
            "lower_high": [False],
            "market_return_1": [0.01],
            "market_return_3": [0.02],
            "market_return_12": [0.04],
            "market_volatility_20": [0.012],
            "sector_return_1": [0.03],
            "sector_return_3": [0.05],
            "sector_return_12": [0.08],
            "sector_volatility_20": [0.018],
        }
    )


def _training_frame(rows: int = 12) -> tuple[pd.DataFrame, pd.Series]:
    data: dict[str, list[object]] = {}
    for index, column in enumerate(NUMERIC_FEATURES):
        data[column] = [
            float(index + row + 1) / 100.0 for row in range(rows)
        ]
    for index, column in enumerate(sorted(BOOLEAN_FEATURES)):
        data[column] = [bool((index + row) % 2) for row in range(rows)]
    labels = pd.Series(
        ["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"] * (rows // 3)
        + ["LONG_SUCCESS"] * (rows % 3),
        name="label",
    )
    return pd.DataFrame(data), labels


def test_market_and_sector_contexts_are_separate() -> None:
    context = build_analysis_context(
        _feature_row(),
        data_version="market-test-v1",
    )

    assert context.market_context["market_return_1"] == 0.01
    assert context.sector_context["sector_return_1"] == 0.03
    assert "sector_return_1" not in context.market_context
    assert "market_return_1" not in context.sector_context


def test_analysis_prediction_strategy_risk_authority_chain() -> None:
    X_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    transformed = preprocessor.fit_transform(X_train)

    model = LogisticOutcomeModel()
    model.fit(transformed, y_train)

    analysis = build_analysis_context(
        _feature_row(),
        regime_dataset=pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-09-20 10:25:00+05:30")],
                "regime": ["TREND_UP"],
                "regime_probability": [0.82],
            }
        ),
        data_version="market-test-v1",
    )

    prediction = predict_from_analysis(
        analysis,
        model=model,
        preprocessor=preprocessor,
    )

    assert np.isfinite(prediction.probabilities.to_numpy()).all()

    decision_features = _feature_row().iloc[0].drop(
        labels=["timestamp", "symbol"],
    )
    strategy = strategy_from_prediction(
        prediction,
        decision_features=decision_features,
        regime="TREND_UP",
        regime_probability=0.82,
    )

    assert strategy.direction is StrategyDirection.LONG

    risk = evaluate_strategy_risk(strategy)
    assert risk.status is RiskDecisionStatus.APPROVED
    assert risk.strategy_direction is StrategyDirection.LONG

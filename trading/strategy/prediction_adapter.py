"""AB-26 adapter from Phase 9 PredictionContext to baseline StrategyDecision.

Prediction probabilities are evidence for strategy evaluation. The existing
Phase 8 baseline strategy remains the only source of LONG/SHORT/NO_TRADE
direction decisions.
"""
from __future__ import annotations

import pandas as pd

from ml.integration.analysis_prediction import PredictionContext
from .baseline import evaluate_row
from .models import BaselineStrategyConfig, StrategyDecision


def strategy_from_prediction(
    prediction: PredictionContext,
    *,
    decision_features: pd.Series,
    regime: str,
    regime_probability: float,
    config: BaselineStrategyConfig | None = None,
) -> StrategyDecision:
    """Evaluate existing strategy rules with PredictionContext attached.

    The baseline strategy is intentionally not rewritten to use model
    probabilities yet. AB-26 establishes the interface while preserving the
    deterministic Phase 8 contract and avoiding an implicit strategy change.
    """
    if not isinstance(prediction, PredictionContext):
        raise TypeError("prediction must be a PredictionContext")
    if not isinstance(decision_features, pd.Series):
        raise TypeError("decision_features must be a pandas Series")

    row = decision_features.copy()
    row["timestamp"] = prediction.timestamp
    row["symbol"] = prediction.symbol
    row["regime"] = regime
    row["regime_probability"] = regime_probability

    decision = evaluate_row(row, config=config)
    return decision

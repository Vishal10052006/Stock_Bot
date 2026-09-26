"""AB-29 end-to-end decision-chain orchestration.

Composes the existing boundaries without replacing their responsibilities:
AnalysisContext -> PredictionContext -> StrategyDecision -> RiskDecision ->
ExecutionAuthorization.

No broker call is performed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from execution.trading_execution import (
    ExecutionAuthorization,
    authorize_risk_decision,
)
from intelligence.analysis.contracts import AnalysisContext
from ml.integration.analysis_prediction import PredictionContext
from trading.risk.gate import RiskDecision, evaluate_strategy_risk
from trading.strategy.models import BaselineStrategyConfig, StrategyDecision
from trading.strategy.prediction_adapter import strategy_from_prediction


@dataclass(frozen=True, slots=True)
class DecisionChain:
    """Auditable output for one end-to-end analytical decision."""

    analysis: AnalysisContext
    prediction: PredictionContext
    strategy: StrategyDecision
    risk: RiskDecision
    execution: ExecutionAuthorization

    def __post_init__(self) -> None:
        """Enforce identity and timestamp continuity across boundaries."""
        timestamp = self.analysis.timestamp
        symbol = self.analysis.symbol

        for component in (
            self.prediction,
            self.strategy,
            self.risk,
            self.execution,
        ):
            if component.timestamp != timestamp:
                raise ValueError("decision chain timestamp mismatch")
            if component.symbol != symbol:
                raise ValueError("decision chain symbol mismatch")


def build_decision_chain(
    analysis: AnalysisContext,
    prediction: PredictionContext,
    *,
    decision_features: pd.Series,
    regime: str,
    regime_probability: float,
    strategy_config: BaselineStrategyConfig | None = None,
    risk_enabled: bool = True,
) -> DecisionChain:
    """Compose the existing downstream contracts in causal order."""
    if not isinstance(analysis, AnalysisContext):
        raise TypeError("analysis must be an AnalysisContext")
    if not isinstance(prediction, PredictionContext):
        raise TypeError("prediction must be a PredictionContext")
    if prediction.timestamp != analysis.timestamp:
        raise ValueError("prediction timestamp must equal analysis timestamp")
    if prediction.symbol != analysis.symbol:
        raise ValueError("prediction symbol must equal analysis symbol")

    strategy = strategy_from_prediction(
        prediction,
        decision_features=decision_features,
        regime=regime,
        regime_probability=regime_probability,
        config=strategy_config,
    )
    risk = evaluate_strategy_risk(
        strategy,
        risk_enabled=risk_enabled,
    )
    execution = authorize_risk_decision(risk)

    return DecisionChain(
        analysis=analysis,
        prediction=prediction,
        strategy=strategy,
        risk=risk,
        execution=execution,
    )

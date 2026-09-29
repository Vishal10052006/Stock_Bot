"""Canonical Strategy -> Risk -> Paper callback for live candles.

This module consumes the already-produced PredictionContext/AnalysisContext and
uses the existing Strategy Engine, Strategy -> Candidate adapter, Risk Engine,
ExecutionAuthorization contract, and paper runtime. No broker/network order
path is reachable from this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from execution.trading_execution import (
    ExecutionAuthorizationStatus,
    authorize_risk_decision,
)
from ml.integration.analysis_prediction import PredictionContext
from trading.paper.live_loop import LivePaperEngine
from trading.risk.engine import RiskEngine
from trading.risk.pipeline import evaluate_strategy_candidate_risk
from trading.strategy.candidate_adapter import build_candidate_from_strategy
from trading.strategy.engine import StrategyEngine
from trading.strategy.models import StrategyDecision, StrategyDirection, StrategyInput


@dataclass(frozen=True, slots=True)
class CanonicalPaperDecision:
    """Auditable downstream result for one candle."""

    prediction: PredictionContext
    strategy: StrategyDecision
    risk_status: str
    risk_reason: str
    paper_order_status: str | None
    trade_id: str | None


def execute_prediction_to_paper(
    prediction: PredictionContext,
    analysis: Any,
    candle: Any,
    paper_engine: LivePaperEngine,
    *,
    strategy_engine: StrategyEngine | None = None,
    risk_engine: RiskEngine | None = None,
) -> CanonicalPaperDecision:
    """Evaluate canonical Prediction -> Strategy -> Risk -> Paper.

    The handler adapts the AnalysisContext feature vector into StrategyInput,
    materializes a TradeCandidate for actionable decisions, passes that
    candidate through the authoritative RiskEngine, and submits only the exact
    risk-approved quantity to the existing paper runtime.
    """
    if not isinstance(prediction, PredictionContext):
        raise TypeError("prediction must be PredictionContext")
    if not isinstance(paper_engine, LivePaperEngine):
        raise TypeError("paper_engine must be LivePaperEngine")

    timestamp = pd.Timestamp(prediction.timestamp)
    symbol = prediction.symbol
    features = dict(analysis.feature_vector)

    market_context = getattr(analysis, "market_context", {})
    regime = str(
        market_context.get("regime")
        or getattr(analysis, "analytical_direction", "UNKNOWN")
    )
    regime_probability = float(
        market_context.get("regime_probability")
        if market_context.get("regime_probability") is not None
        else 0.0
    )

    strategy_input = StrategyInput(
        timestamp=timestamp,
        symbol=symbol,
        decision_features=features,
        prediction=prediction,
        analysis_context=analysis,
        market_context=market_context,
        research_context=getattr(analysis, "research_context", None),
        regime=regime,
        regime_probability=regime_probability,
        versions={
            "analysis": getattr(analysis, "analysis_version", "v1.0"),
            "feature": getattr(analysis, "feature_version", "v1.0"),
            "data": getattr(analysis, "data_version", "unknown"),
            "model": prediction.model_version,
            "market": (
                getattr(analysis, "provenance", {})
                .get("market_bot", {})
                .get("market_version", "market-bot-v1.0")
            ),
        },
    )

    strategy_engine = strategy_engine or StrategyEngine()
    strategy_decision, _trace = strategy_engine.decide(strategy_input)

    if strategy_decision.direction is StrategyDirection.NO_TRADE:
        return CanonicalPaperDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status="NOT_ENTERED",
            risk_reason=strategy_decision.rationale,
            paper_order_status=None,
            trade_id=None,
        )

    row = pd.Series(features)
    row["timestamp"] = timestamp
    row["symbol"] = symbol

    # Candidate validation happens before any paper order is submitted.
    try:
        candidate = build_candidate_from_strategy(strategy_decision, row)
    except (TypeError, ValueError) as exc:
        return CanonicalPaperDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status="CANDIDATE_REJECTED",
            risk_reason=str(exc),
            paper_order_status=None,
            trade_id=None,
        )

    equity, realized_pnl, unrealized_pnl, gross_exposure = (
        paper_engine.runtime.account_snapshot({symbol: float(candle.close)})
    )
    risk_engine = risk_engine or RiskEngine()

    assessment = evaluate_strategy_candidate_risk(
        strategy_decision,
        row,
        risk_engine,
        available_equity=equity,
        day_start_equity=paper_engine.config.initial_equity,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        open_positions=len(paper_engine.runtime.positions),
        trades_today=len(paper_engine._submitted_orders),
        gross_exposure=gross_exposure,
        symbol_already_open=paper_engine.exit_engine.has_open_position(symbol),
        liquidity_available=True,
        kill_switch_active=False,
    )

    risk_decision = assessment.decision
    if risk_decision.status is not RiskDecisionStatus.APPROVED:
        return CanonicalPaperDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status=risk_decision.status.value,
            risk_reason=risk_decision.reason,
            paper_order_status=None,
            trade_id=None,
        )

    authorization = authorize_risk_decision(
        risk_decision,
        risk_decision_id=(
            f"{timestamp.isoformat()}:{symbol}:{risk_decision.risk_version}"
        ),
    )

    if authorization.status is not ExecutionAuthorizationStatus.AUTHORIZED:
        return CanonicalPaperDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status=risk_decision.status.value,
            risk_reason=authorization.reason,
            paper_order_status=None,
            trade_id=None,
        )

    order = paper_engine.runtime.submit(
        authorization,
        price=float(candle.close),
        quantity=risk_decision.approved_quantity,
    )

    if order.status.value != "FILLED":
        return CanonicalPaperDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status=risk_decision.status.value,
            risk_reason="Paper runtime rejected the authorized order.",
            paper_order_status=order.status.value,
            trade_id=None,
        )

    # The risk candidate owns the initial stop. Risk owns the target multiple.
    target_multiple = risk_engine.config.target_multiple_r
    if candidate.direction.value == "LONG":
        target_price = candidate.entry_price + (
            candidate.stop_distance * target_multiple
        )
    else:
        target_price = candidate.entry_price - (
            candidate.stop_distance * target_multiple
        )

    trade_id = (
        f"TR-{paper_engine.config.experiment_id}-"
        f"{len(paper_engine._submitted_orders) + 1:03d}"
    )

    paper_engine.exit_engine.open_position(
        order,
        stop_price=candidate.stop_price,
        target_price=target_price,
        trade_id=trade_id,
        strategy_version=strategy_decision.strategy_version,
        model_version=prediction.model_version,
        risk_version=risk_decision.risk_version,
        regime=strategy_decision.regime,
    )
    paper_engine._submitted_orders.append(order)

    return CanonicalPaperDecision(
        prediction=prediction,
        strategy=strategy_decision,
        risk_status=risk_decision.status.value,
        risk_reason=risk_decision.reason,
        paper_order_status=order.status.value,
        trade_id=trade_id,
    )

__all__ = [
    "CanonicalPaperDecision",
    "execute_prediction_to_paper",
]

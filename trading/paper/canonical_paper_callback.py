"""Canonical Strategy -> Risk -> Safety -> Paper callback for live candles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any

import pandas as pd

from execution.safety import SafetyBlock, SafetyState
from execution.trading_execution import (
    ExecutionAuthorizationStatus,
    authorize_risk_decision,
)
from ml.integration.analysis_prediction import PredictionContext
from trading.ab30_pipeline import MarketAnalysisResult
from trading.paper.live_loop import LivePaperEngine
from trading.risk.engine import RiskEngine
from trading.risk.gate import RiskDecisionStatus
from trading.risk.pipeline import evaluate_strategy_candidate_risk
from trading.strategy.candidate_adapter import build_candidate_from_strategy
from trading.strategy.engine import StrategyEngine
from trading.strategy.models import StrategyDecision, StrategyDirection, StrategyInput


@dataclass(frozen=True, slots=True)
class CanonicalLiveDecision:
    """Auditable downstream result for one candle."""

    prediction: PredictionContext
    strategy: StrategyDecision
    risk_status: str
    risk_reason: str
    paper_order_status: str | None
    trade_id: str | None
    research_context: Any | None = None
    market_context: Any | None = None


def _session_open(timestamp: pd.Timestamp) -> bool:
    """Return whether a new intraday entry is allowed at this decision time."""
    local = pd.Timestamp(timestamp).tz_convert("Asia/Kolkata")
    return time(9, 15) <= local.time() < time(15, 15)


def build_live_money_decision(
    prediction: PredictionContext,
    analysis_result: MarketAnalysisResult,
    candle: Any,
    risk_engine: RiskEngine,
    *,
    available_equity: float,
    day_start_equity: float,
) -> CanonicalLiveDecision:
    """Build a real-money manual BUY/SELL decision without submitting an order.

    This is the live decision boundary used by V1. It performs Strategy and
    Risk evaluation, but deliberately stops before any broker/order operation.
    The human reviewer is responsible for the real-money BUY/SELL action.
    """
    if not isinstance(prediction, PredictionContext):
        raise TypeError("prediction must be PredictionContext")
    if not isinstance(analysis_result, MarketAnalysisResult):
        raise TypeError("analysis_result must be MarketAnalysisResult")
    if not isinstance(risk_engine, RiskEngine):
        raise TypeError("risk_engine must be RiskEngine")

    analysis = analysis_result.analysis
    timestamp = pd.Timestamp(prediction.timestamp)
    symbol = prediction.symbol

    feature_row = analysis_result.features.loc[
        pd.to_datetime(analysis_result.features["timestamp"], utc=True) == timestamp
    ]
    if feature_row.empty:
        raise ValueError("canonical feature row is missing at prediction timestamp")
    features = feature_row.iloc[-1].to_dict()

    regime_row = analysis_result.regime.loc[
        pd.to_datetime(analysis_result.regime["timestamp"], utc=True) == timestamp
    ]
    if regime_row.empty:
        raise ValueError("canonical regime row is missing at prediction timestamp")
    regime = regime_row.iloc[-1]["regime"]
    regime_probability = regime_row.iloc[-1]["regime_probability"]
    if pd.isna(regime) or pd.isna(regime_probability):
        return CanonicalLiveDecision(
            prediction=prediction,
            strategy=StrategyDecision(
                timestamp=timestamp,
                symbol=symbol,
                direction=StrategyDirection.NO_TRADE,
                strategy_version=risk_engine.config.strategy_version,
                rationale="Canonical regime is not yet available.",
            ),
            risk_status="NOT_ENTERED",
            risk_reason="Canonical regime is not yet available.",
            paper_order_status=None,
            trade_id=None,
            research_context=getattr(analysis, "research_context", None),
            market_context=getattr(analysis, "market_context", None),
        )

    strategy_input = StrategyInput(
        timestamp=timestamp,
        symbol=symbol,
        decision_features=features,
        prediction=prediction,
        analysis_context=analysis,
        market_context=getattr(analysis, "market_context", None),
        research_context=getattr(analysis, "research_context", None),
        regime=str(regime),
        regime_probability=float(regime_probability),
        versions={
            "analysis": getattr(analysis, "analysis_version", "v1.0"),
            "feature": getattr(analysis, "feature_version", "v1.0"),
            "data": getattr(analysis, "data_version", "unknown"),
            "model": prediction.model_version,
            "market": analysis.provenance.get("market_bot", {}).get(
                "market_version",
                "market-bot-v1.0",
            ),
        },
    )

    strategy_engine = StrategyEngine()
    strategy_decision, _trace = strategy_engine.decide(strategy_input)
    if strategy_decision.direction is StrategyDirection.NO_TRADE:
        return CanonicalLiveDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status="NOT_ENTERED",
            risk_reason=strategy_decision.rationale,
            paper_order_status=None,
            trade_id=None,
            research_context=getattr(analysis, "research_context", None),
            market_context=getattr(analysis, "market_context", None),
        )

    raw_row = analysis_result.indicators.loc[
        pd.to_datetime(analysis_result.indicators["timestamp"], utc=True) == timestamp
    ]
    if raw_row.empty:
        raise ValueError("canonical indicator row is missing at strategy timestamp")

    row_data = raw_row.iloc[-1].to_dict()
    row_data.update(features)
    row_data["timestamp"] = timestamp
    row_data["symbol"] = symbol
    row = pd.Series(row_data)

    try:
        candidate = build_candidate_from_strategy(strategy_decision, row)
    except (TypeError, ValueError) as exc:
        return CanonicalLiveDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status="CANDIDATE_REJECTED",
            risk_reason=str(exc),
            paper_order_status=None,
            trade_id=None,
            research_context=getattr(analysis, "research_context", None),
            market_context=getattr(analysis, "market_context", None),
        )

    assessment = evaluate_strategy_candidate_risk(
        strategy_decision,
        row,
        risk_engine,
        available_equity=float(available_equity),
        day_start_equity=float(day_start_equity),
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        open_positions=0,
        trades_today=0,
        gross_exposure=0.0,
        symbol_already_open=False,
        liquidity_available=True,
        kill_switch_active=False,
    )
    risk_decision = assessment.decision
    if risk_decision.status is not RiskDecisionStatus.APPROVED:
        return CanonicalLiveDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status=risk_decision.status.value,
            risk_reason=risk_decision.reason,
            paper_order_status=None,
            trade_id=None,
            research_context=getattr(analysis, "research_context", None),
            market_context=getattr(analysis, "market_context", None),
        )

    return CanonicalLiveDecision(
        prediction=prediction,
        strategy=strategy_decision,
        risk_status=risk_decision.status.value,
        risk_reason=risk_decision.reason,
        paper_order_status="MANUAL_BUY_SELL_REQUIRED",
        trade_id=None,
        research_context=getattr(analysis, "research_context", None),
        market_context=getattr(analysis, "market_context", None),
    )


__all__ = [
    "CanonicalLiveDecision",
    "build_live_money_decision",
    "execute_prediction_to_paper",
]

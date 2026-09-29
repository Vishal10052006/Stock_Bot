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
class CanonicalPaperDecision:
    """Auditable downstream result for one candle."""

    prediction: PredictionContext
    strategy: StrategyDecision
    risk_status: str
    risk_reason: str
    paper_order_status: str | None
    trade_id: str | None


def _session_open(timestamp: pd.Timestamp) -> bool:
    """Return whether a new intraday entry is allowed at this decision time."""
    local = pd.Timestamp(timestamp).tz_convert("Asia/Kolkata")
    return time(9, 15) <= local.time() < time(15, 15)


def execute_prediction_to_paper(
    prediction: PredictionContext,
    analysis_result: MarketAnalysisResult,
    candle: Any,
    paper_engine: LivePaperEngine,
    *,
    strategy_engine: StrategyEngine | None = None,
    risk_engine: RiskEngine | None = None,
) -> CanonicalPaperDecision:
    """Evaluate canonical Prediction -> Strategy -> Risk -> Safety -> Paper."""
    if not isinstance(prediction, PredictionContext):
        raise TypeError("prediction must be PredictionContext")
    if not isinstance(analysis_result, MarketAnalysisResult):
        raise TypeError("analysis_result must be MarketAnalysisResult")
    if not isinstance(paper_engine, LivePaperEngine):
        raise TypeError("paper_engine must be LivePaperEngine")

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
        return CanonicalPaperDecision(
            prediction=prediction,
            strategy=StrategyDecision(
                timestamp=timestamp,
                symbol=symbol,
                direction=StrategyDirection.NO_TRADE,
                strategy_version=paper_engine.strategy_engine.config.strategy_version,
                rationale="Canonical regime is not yet available.",
            ),
            risk_status="NOT_ENTERED",
            risk_reason="Canonical regime is not yet available.",
            paper_order_status=None,
            trade_id=None,
        )

    regime = str(regime)
    regime_probability = float(regime_probability)

    strategy_input = StrategyInput(
        timestamp=timestamp,
        symbol=symbol,
        decision_features=features,
        prediction=prediction,
        analysis_context=analysis,
        market_context=getattr(analysis, "market_context", None),
        research_context=getattr(analysis, "research_context", None),
        regime=regime,
        regime_probability=regime_probability,
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

    strategy_engine = strategy_engine or paper_engine.strategy_engine
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
        return CanonicalPaperDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status="CANDIDATE_REJECTED",
            risk_reason=str(exc),
            paper_order_status=None,
            trade_id=None,
        )

    safety = paper_engine.safety_gate.evaluate(
        SafetyState(
            stale_data=False,
            data_quality_ok=True,
            session_open=_session_open(timestamp),
            live_execution_enabled=False,
        )
    )
    if safety.block not in (SafetyBlock.NONE, SafetyBlock.LIVE_LOCKED):
        return CanonicalPaperDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status=safety.block.value,
            risk_reason=safety.reason,
            paper_order_status=None,
            trade_id=None,
        )

    risk_engine = risk_engine or paper_engine.risk_engine
    equity, realized_pnl, unrealized_pnl, gross_exposure = (
        paper_engine.runtime.account_snapshot({symbol: float(candle.close)})
    )

    assessment = evaluate_strategy_candidate_risk(
        strategy_decision,
        row,
        risk_engine,
        available_equity=equity,
        day_start_equity=paper_engine.config.initial_equity,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        open_positions=len(paper_engine.runtime.positions),
        trades_today=paper_engine.submitted_order_count,
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
        risk_decision_id=f"{timestamp.isoformat()}:{symbol}:{risk_decision.risk_version}",
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

    target_multiple = risk_engine.config.target_multiple_r
    if candidate.direction.value == "LONG":
        target_price = candidate.entry_price + candidate.stop_distance * target_multiple
    else:
        target_price = candidate.entry_price - candidate.stop_distance * target_multiple

    trade_id = (
        f"TR-{paper_engine.config.experiment_id}-"
        f"{paper_engine.submitted_order_count + 1:03d}"
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
    paper_engine.register_submitted_order(order)

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

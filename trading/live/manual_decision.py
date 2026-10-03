"""V1 real-market manual BUY/SELL decision authority.

This module is deliberately outside trading.paper. It evaluates the existing
Strategy and Risk authorities and returns an auditable manual-review result.
It never creates, submits, modifies, or cancels a broker order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from ml.integration.analysis_prediction import PredictionContext
from trading.ab30_pipeline import MarketAnalysisResult
from trading.risk.engine import RiskEngine
from trading.risk.gate import RiskDecisionStatus
from trading.risk.pipeline import evaluate_strategy_candidate_risk
from trading.strategy.candidate_adapter import build_candidate_from_strategy
from trading.strategy.engine import StrategyEngine
from trading.strategy.models import StrategyDecision, StrategyDirection, StrategyInput

from .risk_context import LiveManualRiskContext


@dataclass(frozen=True, slots=True)
class CanonicalLiveDecision:
    """Auditable downstream result for one real-market decision timestamp."""

    prediction: PredictionContext
    strategy: StrategyDecision
    risk_status: str
    risk_reason: str
    manual_execution_status: str | None
    trade_id: str | None
    research_context: Any | None = None
    market_context: Any | None = None
    risk_context: LiveManualRiskContext | None = None


def _risk_context_block(
    prediction: PredictionContext,
    analysis: Any,
    strategy: StrategyDecision,
    reason: str,
) -> CanonicalLiveDecision:
    """Build a safe non-actionable decision when account state is unavailable."""
    return CanonicalLiveDecision(
        prediction=prediction,
        strategy=strategy,
        risk_status="RISK_CONTEXT_UNAVAILABLE",
        risk_reason=reason,
        manual_execution_status=None,
        trade_id=None,
        research_context=getattr(analysis, "research_context", None),
        market_context=getattr(analysis, "market_context", None),
        risk_context=None,
    )


def build_live_money_decision(
    prediction: PredictionContext,
    analysis_result: MarketAnalysisResult,
    candle: Any,
    risk_engine: RiskEngine,
    *,
    risk_context: LiveManualRiskContext | None,
) -> CanonicalLiveDecision:
    """Evaluate Strategy and Risk for a real-money manual review.

    A verified decision-time LiveManualRiskContext is mandatory for an
    actionable result. Missing or stale account state produces a safety block;
    this function never substitutes paper-account defaults or synthetic state.
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

    candle_timestamp = pd.Timestamp(getattr(candle, "timestamp", None))
    candle_symbol = str(getattr(candle, "symbol", "")).strip().upper()
    if candle_timestamp != timestamp or candle_symbol != symbol.upper():
        raise ValueError(
            "candle must match prediction timestamp and symbol exactly"
        )

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
                strategy_version=StrategyEngine().config.strategy_version,
                rationale="Canonical regime is not yet available.",
            ),
            risk_status="NOT_ENTERED",
            risk_reason="Canonical regime is not yet available.",
            manual_execution_status=None,
            trade_id=None,
            research_context=getattr(analysis, "research_context", None),
            market_context=getattr(analysis, "market_context", None),
            risk_context=None,
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
            manual_execution_status=None,
            trade_id=None,
            research_context=getattr(analysis, "research_context", None),
            market_context=getattr(analysis, "market_context", None),
            risk_context=None,
        )

    if risk_context is None:
        return _risk_context_block(
            prediction,
            analysis,
            strategy_decision,
            "Decision-time account/portfolio risk context was not supplied.",
        )

    observed_at = pd.Timestamp.now(tz="UTC")
    context_error = risk_context.validation_error(
        observed_at=observed_at,
        decision_timestamp=timestamp,
    )
    if context_error is not None:
        return _risk_context_block(
            prediction,
            analysis,
            strategy_decision,
            context_error,
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
        build_candidate_from_strategy(strategy_decision, row)
    except (TypeError, ValueError) as exc:
        return CanonicalLiveDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status="CANDIDATE_REJECTED",
            risk_reason=str(exc),
            manual_execution_status=None,
            trade_id=None,
            research_context=getattr(analysis, "research_context", None),
            market_context=getattr(analysis, "market_context", None),
            risk_context=risk_context,
        )

    assessment = evaluate_strategy_candidate_risk(
        strategy_decision,
        row,
        risk_engine,
        available_equity=risk_context.available_equity,
        day_start_equity=risk_context.day_start_equity,
        available_cash=risk_context.available_cash,
        peak_equity=risk_context.peak_equity,
        realized_pnl=risk_context.realized_pnl,
        unrealized_pnl=risk_context.unrealized_pnl,
        open_positions=risk_context.open_positions,
        trades_today=risk_context.trades_today,
        gross_exposure=risk_context.gross_exposure,
        symbol_already_open=risk_context.symbol_already_open,
        position_context=risk_context.position_context,
        liquidity_available=risk_context.liquidity_available,
        kill_switch_active=risk_context.kill_switch_active,
        sector=risk_context.sector,
        symbol_exposure=risk_context.symbol_exposure,
        sector_exposure=risk_context.sector_exposure,
        pairwise_correlation=risk_context.pairwise_correlation,
        atr=risk_context.atr,
        high_volatility=risk_context.high_volatility,
        market_data_valid=risk_context.market_data_valid,
        system_ready=risk_context.system_ready,
        kill_switch_state=risk_context.kill_switch_state,
    )
    risk_decision = assessment.decision
    if risk_decision.status is not RiskDecisionStatus.APPROVED:
        return CanonicalLiveDecision(
            prediction=prediction,
            strategy=strategy_decision,
            risk_status=risk_decision.status.value,
            risk_reason=risk_decision.reason,
            manual_execution_status=None,
            trade_id=None,
            research_context=getattr(analysis, "research_context", None),
            market_context=getattr(analysis, "market_context", None),
            risk_context=risk_context,
        )

    return CanonicalLiveDecision(
        prediction=prediction,
        strategy=strategy_decision,
        risk_status=risk_decision.status.value,
        risk_reason=risk_decision.reason,
        manual_execution_status="MANUAL_BUY_SELL_REQUIRED",
        trade_id=None,
        research_context=getattr(analysis, "research_context", None),
        market_context=getattr(analysis, "market_context", None),
        risk_context=risk_context,
    )


__all__ = [
    "CanonicalLiveDecision",
    "LiveManualRiskContext",
    "build_live_money_decision",
]

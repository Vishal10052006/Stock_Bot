"""Strategy-to-Risk candidate evaluation boundary.

This module converts an actionable StrategyDecision into a causal
TradeCandidate and passes that candidate through the deterministic
RiskEngine. It contains no broker or execution logic.
"""

from __future__ import annotations;

import pandas as pd

from trading.strategy.models import StrategyDecision, StrategyDirection
from trading.signals.models import CandidateConfig

from .engine import RiskAssessment, RiskEngine, RiskInput
from .gate import RiskDecision, RiskDecisionStatus
from trading.strategy.models import StrategyDirection


def evaluate_strategy_candidate_risk(
    decision: StrategyDecision,
    row: pd.Series,
    risk_engine: RiskEngine,
    *,
    available_equity: float,
    day_start_equity: float,
    realized_pnl: float,
    unrealized_pnl: float,
    open_positions: int,
    trades_today: int,
    gross_exposure: float,
    symbol_already_open: bool,
    liquidity_available: bool = True,
    kill_switch_active: bool = False,
    candidate_config: CandidateConfig | None = None,
    risk_enabled: bool = True,
) -> RiskAssessment:
    """Evaluate one StrategyDecision through candidate construction and Risk."""
    if not isinstance(decision, StrategyDecision):
        raise TypeError("decision must be a StrategyDecision")
    if not isinstance(row, pd.Series):
        raise TypeError("row must be a pandas Series")
    if not isinstance(risk_engine, RiskEngine):
        raise TypeError("risk_engine must be a RiskEngine")

    if decision.direction is StrategyDirection.NO_TRADE:
        return _rejected(
            decision,
            "Strategy produced NO_TRADE; risk engine not entered.",
        )

    if not risk_enabled:
        return _rejected(
            decision,
            "Global risk gate is disabled.",
        )

    from trading.strategy.candidate_adapter import build_candidate_from_strategy

    try:
        candidate = build_candidate_from_strategy(
            decision,
            row,
            config=candidate_config,
        )
    except (TypeError, ValueError) as exc:
        return _rejected(
            decision,
            f"Candidate construction failed: {exc}",
        )

    return risk_engine.evaluate(
        RiskInput(
            timestamp=pd.Timestamp(decision.timestamp),
            symbol=decision.symbol,
            candidate=candidate,
            available_equity=available_equity,
            day_start_equity=day_start_equity,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            open_positions=open_positions,
            trades_today=trades_today,
            gross_exposure=gross_exposure,
            symbol_already_open=symbol_already_open,
            liquidity_available=liquidity_available,
            kill_switch_active=kill_switch_active,
        )
    )


def _rejected(
    decision: StrategyDecision,
    reason: str,
) -> RiskAssessment:
    """Return an auditable rejection without authorizing execution."""
    return RiskAssessment(
        decision=RiskDecision(
            timestamp=decision.timestamp,
            symbol=decision.symbol,
            status=RiskDecisionStatus.REJECTED,
            strategy_direction=decision.direction,
            reason=reason,
            risk_version="RISK-v1.0",
        )
    )

"""AB-27 tests for StrategyDecision -> Risk gate."""
from __future__ import annotations

import pandas as pd

from trading.risk.gate import RiskDecisionStatus, evaluate_strategy_risk
from trading.strategy.models import StrategyDecision, StrategyDirection


def _decision(direction: StrategyDirection) -> StrategyDecision:
    return StrategyDecision(
        timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
        symbol="RELIANCE",
        direction=direction,
        strategy_version="v1.0",
        rationale="test",
    )


def test_ab27_long_strategy_can_pass_risk_gate() -> None:
    result = evaluate_strategy_risk(_decision(StrategyDirection.LONG))
    assert result.status is RiskDecisionStatus.APPROVED
    assert result.strategy_direction is StrategyDirection.LONG


def test_ab27_no_trade_is_rejected() -> None:
    result = evaluate_strategy_risk(_decision(StrategyDirection.NO_TRADE))
    assert result.status is RiskDecisionStatus.REJECTED


def test_ab27_disabled_global_gate_rejects_direction() -> None:
    result = evaluate_strategy_risk(
        _decision(StrategyDirection.SHORT),
        risk_enabled=False,
    )
    assert result.status is RiskDecisionStatus.REJECTED

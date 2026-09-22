"""Risk Engine R0-R20 tests.

These tests are intentionally deterministic and adversarial. They verify
hard safety boundaries before any production integration is considered.
"""
from __future__ import annotations

import pandas as pd
import pytest

from config.risk_policy import RISK_POLICY_V1
from trading.risk.contracts import (
    MarketRiskContext,
    PortfolioRiskState,
    RiskDecisionStatus,
    RiskReasonCode,
)
from trading.risk.engine import RiskEngine, RiskEvaluationInput
from trading.risk.heat import calculate_portfolio_heat
from trading.risk.kill_switch import KillSwitch
from trading.signals.models import CandidateDirection, TradeCandidate


def _candidate(*, direction: CandidateDirection = CandidateDirection.LONG) -> TradeCandidate:
    return TradeCandidate(
        timestamp=pd.Timestamp("2026-09-22 10:00:00+05:30"),
        symbol="RELIANCE",
        direction=direction,
        entry_price=100.0,
        stop_price=98.0 if direction is CandidateDirection.LONG else 102.0,
        policy_version="structure_atr_v1.0",
    )


def _portfolio(**overrides) -> PortfolioRiskState:
    values = dict(
        timestamp=pd.Timestamp("2026-09-22 10:00:00+05:30"),
        starting_equity=100_000.0,
        equity=100_000.0,
        available_cash=100_000.0,
        recent_pnl=0.0 if False else 0.0,
        entries_today=0,
        open_positions=0,
        gross_exposure=0.0,
        net_exposure=0.0,
        open_trade_risk=0.0,
        symbol_exposure={},
        sector_exposure={},
        peak_equity=100_000.0,
    )
    values.pop("recent_pnl", None)
    values.update(overrides)
    return PortfolioRiskState(**values)


def _market(**overrides) -> MarketRiskContext:
    values = dict(
        timestamp=pd.Timestamp("2026-09-22 10:00:00+05:30"),
        session_open=pd.Timestamp("2026-09-22 09:15:00+05:30"),
        session_close=pd.Timestamp("2026-09-22 15:30:00+05:30"),
        is_market_open=True,
        recent_volume=10_000_000.0,
        sector="ENERGY",
        volatility_regime="NORMAL",
    )
    values.update(overrides)
    return MarketRiskContext(**values)


def test_risk_engine_approves_valid_candidate() -> None:
    engine = RiskEngine(policy=RISK_POLICY_V1)
    result = engine.evaluate(
        RiskEvaluationInput(
            candidate=_candidate(),
            portfolio=_portfolio(),
            market=_market(),
            target_price=103.0,
            sector="ENERGY",
        )
    )

    assert result.status in {
        RiskDecisionStatus.APPROVED,
        RiskDecisionStatus.REDUCED,
    }
    assert result.approved_quantity > 0
    assert result.approved_notional > 0
    assert result.planned_risk > 0


def test_position_size_is_risk_first() -> None:
    engine = RiskEngine(policy=RISK_POLICY_V1)
    result = engine.evaluate(
        RiskEvaluationInput(
            candidate=_candidate(),
            portfolio=_portfolio(),
            market=_market(),
            target_price=103.0,
        )
    )

    # Initial risk budget is ₹500; with ₹2/share stop distance,
    # raw risk-first size is at most 250 shares before other caps.
    assert result.approved_quantity <= 250


def test_daily_loss_limit_is_hard_rejection() -> None:
    engine = RiskEngine(policy=RISK_POLICY_V1)
    result = engine.evaluate(
        RiskEvaluationInput(
            candidate=_candidate(),
            portfolio=_portfolio(realized_pnl_today=-1500.0),
            market=_market(),
        )
    )

    assert result.status is RiskDecisionStatus.REJECTED
    assert RiskReasonCode.DAILY_LOSS_LIMIT in result.reason_codes
    assert result.approved_quantity == 0


def test_open_position_limit_is_hard_rejection() -> None:
    engine = RiskEngine(policy=RISK_POLICY_V1)
    result = engine.evaluate(
        RiskEvaluationInput(
            candidate=_candidate(),
            portfolio=_portfolio(open_positions=3),
            market=_market(),
        )
    )

    assert result.status is RiskDecisionStatus.REJECTED
    assert RiskReasonCode.MAX_OPEN_POSITIONS in result.reason_codes


def test_entries_per_day_limit_is_hard_rejection() -> None:
    engine = RiskEngine(policy=RISK_POLICY_V1)
    result = engine.evaluate(
        RiskEvaluationInput(
            candidate=_candidate(),
            portfolio=_portfolio(entries_today=5),
            market=_market(),
        )
    )

    assert result.status is RiskDecisionStatus.REJECTED
    assert RiskReasonCode.MAX_ENTRIES_PER_DAY in result.reason_codes


def test_gross_exposure_cap_reduces_or_rejects() -> None:
    engine = RiskEngine(policy=RISK_POLICY_V1)
    result = engine.evaluate(
        RiskEvaluationInput(
            candidate=_candidate(),
            portfolio=_portfolio(gross_exposure=74_900.0),
            market=_market(),
        )
    )

    assert result.status in {
        RiskDecisionStatus.REDUCED,
        RiskDecisionStatus.REJECTED,
    }
    assert result.approved_notional <= 100.0


def test_stale_context_fails_closed() -> None:
    engine = RiskEngine(policy=RISK_POLICY_V1)
    result = engine.evaluate(
        RiskEvaluationInput(
            candidate=_candidate(),
            portfolio=_portfolio(
                timestamp=pd.Timestamp("2026-09-22 09:00:00+05:30")
            ),
            market=_market(),
        )
    )

    assert result.status is RiskDecisionStatus.REJECTED
    assert RiskReasonCode.STALE_CONTEXT in result.reason_codes


def test_missing_liquidity_fails_closed() -> None:
    engine = RiskEngine(policy=RISK_POLICY_V1)
    result = engine.evaluate(
        RiskEvaluationInput(
            candidate=_candidate(),
            portfolio=_portfolio(),
            market=_market(recent_volume=None),
        )
    )

    assert result.status is RiskDecisionStatus.REJECTED
    assert RiskReasonCode.MISSING_REQUIRED_CONTEXT in result.reason_codes


def test_kill_switch_blocks_trade() -> None:
    switch = KillSwitch()
    switch.activate("manual emergency stop")
    engine = RiskEngine(policy=RISK_POLICY_V1, kill_switch=switch)

    result = engine.evaluate(
        RiskEvaluationInput(
            candidate=_candidate(),
            portfolio=_portfolio(),
            market=_market(),
        )
    )

    assert result.status is RiskDecisionStatus.REJECTED
    assert RiskReasonCode.KILL_SWITCH_ACTIVE in result.reason_codes


def test_heat_is_component_wise_and_transparent() -> None:
    state = _portfolio(
        gross_exposure=50_000.0,
        net_exposure=20_000.0,
        open_trade_risk=250.0,
        realized_pnl_today=-500.0,
        unrealized_pnl_today=-100.0,
        open_positions=2,
        entries_today=2,
        peak_equity=100_000.0,
        equity=99_400.0,
    )
    heat = calculate_portfolio_heat(state, RISK_POLICY_V1)

    assert heat.trade_risk_utilization == pytest.approx(0.5)
    assert heat.gross_exposure_utilization == pytest.approx(50_000 / 75_000)
    assert heat.daily_loss_utilization == pytest.approx(600 / 1500)
    assert heat.open_position_utilization == pytest.approx(2 / 3)


def test_short_direction_has_signed_net_exposure() -> None:
    engine = RiskEngine(policy=RISK_POLICY_V1)
    result = engine.evaluate(
        RiskEvaluationInput(
            candidate=_candidate(direction=CandidateDirection.SHORT),
            portfolio=_portfolio(),
            market=_market(),
        )
    )

    assert result.status in {
        RiskDecisionStatus.APPROVED,
        RiskDecisionStatus.REDUCED,
    }
    assert result.net_exposure_after < 0


def test_reason_and_policy_lineage_are_recorded() -> None:
    engine = RiskEngine(policy=RISK_POLICY_V1)
    result = engine.evaluate(
        RiskEvaluationInput(
            candidate=_candidate(),
            portfolio=_portfolio(),
            market=_market(),
        )
    )

    assert result.decision_id.startswith("risk-")
    assert result.risk_policy_version == "risk_v1.0"
    assert result.candidate_policy_version == "structure_atr_v1.0"
    assert result.reason_codes
    assert result.provenance["engine"] == "trading.risk.engine"

"""PAPER-07 / E16 backtest-integration certification.

Certifies that historical replay uses the canonical execution authorization
boundary and the same execution assumptions as paper execution. The harness
does not introduce a second execution model and never contacts a live broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from backtesting.broker_simulator import BrokerSimulator, BrokerSimulatorConfig
from backtesting.engine import BacktestConfig, HistoricalBacktestEngine
from execution.production import ExecutionAssumptions, assert_execution_backtest_parity
from execution.trading_execution import ExecutionAuthorizationStatus
from trading.strategy.models import StrategyDirection


@dataclass(frozen=True, slots=True)
class BacktestIntegrationCase:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class BacktestIntegrationReport:
    cases: tuple[BacktestIntegrationCase, ...]

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)

    @property
    def failed(self) -> tuple[BacktestIntegrationCase, ...]:
        return tuple(case for case in self.cases if not case.passed)


def _row(timestamp: str, *, close: float = 100.0, regime: str = "TREND_UP") -> dict:
    return {
        "timestamp": timestamp,
        "symbol": "ITC",
        "close": close,
        "high": close,
        "low": close,
        "regime": regime,
        "regime_probability": 0.90,
        "vwap_distance_pct": 1.0,
        "rvol_20": 1.5,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
        "atr_14": 2.0,
        "support_20": close - 2.0,
        "resistance_20": close + 2.0,
        "volume": 10_000_000.0,
    }


def _case(name: str, check: Callable[[], None]) -> BacktestIntegrationCase:
    try:
        check()
    except Exception as exc:
        return BacktestIntegrationCase(
            name, False, f"{type(exc).__name__}: {exc}"
        )
    return BacktestIntegrationCase(name, True, "PASS")


def run_backtest_integration_certification() -> BacktestIntegrationReport:
    """Run deterministic E16 certification."""

    def authorized_path_uses_canonical_boundary() -> None:
        rows = pd.DataFrame([
            _row("2026-01-01 09:15:00+05:30", close=100.0),
            _row("2026-01-01 09:20:00+05:30", close=101.0),
        ])
        result = HistoricalBacktestEngine().run(rows)

        assert len(result.steps) == 2
        assert len(result.orders) == 1
        step = result.steps[0]
        assert step.authorization.status is ExecutionAuthorizationStatus.AUTHORIZED
        assert step.authorization.symbol == "ITC"
        assert step.authorization.approved_quantity == result.orders[0].quantity
        assert result.orders[0].status.value == "FILLED"

    def no_trade_stays_no_trade() -> None:
        rows = pd.DataFrame([
            _row("2026-01-01 09:15:00+05:30", regime="RANGE"),
        ])
        result = HistoricalBacktestEngine().run(rows)
        assert result.orders == ()
        assert result.steps[0].authorization.status is not ExecutionAuthorizationStatus.AUTHORIZED

    def backtest_costs_match_execution_assumptions() -> None:
        simulator = BrokerSimulator(
            config=BrokerSimulatorConfig(slippage_bps=5.0, fee_bps=2.0)
        )
        assumptions = ExecutionAssumptions(
            slippage_bps=simulator.runtime.config.slippage_bps,
            fee_bps=simulator.runtime.config.fee_bps,
        )
        assert_execution_backtest_parity(assumptions, ExecutionAssumptions(5.0, 2.0))

    def assumption_mismatch_fails_closed() -> None:
        try:
            assert_execution_backtest_parity(
                ExecutionAssumptions(5.0, 2.0),
                ExecutionAssumptions(6.0, 2.0),
            )
        except ValueError as exc:
            assert "mismatch" in str(exc)
            return
        raise AssertionError("execution/backtest mismatch was accepted")

    def chronology_and_causality_are_preserved() -> None:
        rows = pd.DataFrame([
            _row("2026-01-01 09:20:00+05:30", close=101.0),
            _row("2026-01-01 09:15:00+05:30", close=100.0),
        ])
        result = HistoricalBacktestEngine().run(rows)
        timestamps = [step.timestamp for step in result.steps]
        assert timestamps == sorted(timestamps)
        assert result.steps[0].timestamp == pd.Timestamp("2026-01-01 09:15:00+05:30")

    def risk_quantity_is_not_replaced_by_backtest_config() -> None:
        rows = pd.DataFrame([
            _row("2026-01-01 09:15:00+05:30"),
            _row("2026-01-01 09:20:00+05:30", close=101.0),
        ])
        result = HistoricalBacktestEngine(
            config=BacktestConfig(quantity=1.0)
        ).run(rows)
        assert result.orders
        assert result.orders[0].quantity == result.steps[0].authorization.approved_quantity
        assert result.orders[0].quantity != 1.0

    cases = (
        _case("authorized_path_uses_canonical_boundary", authorized_path_uses_canonical_boundary),
        _case("no_trade_stays_no_trade", no_trade_stays_no_trade),
        _case("backtest_costs_match_execution_assumptions", backtest_costs_match_execution_assumptions),
        _case("assumption_mismatch_fails_closed", assumption_mismatch_fails_closed),
        _case("chronology_and_causality_are_preserved", chronology_and_causality_are_preserved),
        _case("risk_quantity_is_not_replaced_by_backtest_config", risk_quantity_is_not_replaced_by_backtest_config),
    )
    return BacktestIntegrationReport(cases)


__all__ = [
    "BacktestIntegrationCase",
    "BacktestIntegrationReport",
    "run_backtest_integration_certification",
]

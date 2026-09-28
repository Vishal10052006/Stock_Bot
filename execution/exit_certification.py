"""PAPER-04 approved exit execution certification.

The backtest layer determines when stop/target/time exit conditions occur.
This harness certifies the downstream execution boundary: an approved exit
closes or reduces the observed position exactly as authorized.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import pandas as pd

from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
from execution.engine import ExecutionEngine, OrderStatus, PositionSnapshot
from execution.trading_execution import ExecutionAuthorization, ExecutionAuthorizationStatus
from trading.strategy.models import StrategyDirection

TS = pd.Timestamp("2026-09-27T10:00:00+05:30")

@dataclass(frozen=True, slots=True)
class ExitExecutionCase:
    name: str
    passed: bool
    detail: str

@dataclass(frozen=True, slots=True)
class ExitExecutionReport:
    cases: tuple[ExitExecutionCase, ...]
    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)
    @property
    def failed(self) -> tuple[ExitExecutionCase, ...]:
        return tuple(case for case in self.cases if not case.passed)

def _authorization(direction, quantity, *, decision_id, reason):
    return ExecutionAuthorization(
        timestamp=TS,
        symbol="ITC",
        direction=direction,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason=reason,
        risk_version="RISK-v1.0",
        approved_quantity=quantity,
        approved_notional=quantity * 100.0,
        risk_decision_id=decision_id,
    )

def _case(name: str, check: Callable[[], None]) -> ExitExecutionCase:
    try:
        check()
    except Exception as exc:
        return ExitExecutionCase(name, False, f"{type(exc).__name__}: {exc}")
    return ExitExecutionCase(name, True, "PASS")

def run_exit_execution_certification() -> ExitExecutionReport:
    """Run the deterministic PAPER-04 exit-execution matrix."""

    def full_long_stop_exit():
        adapter = PaperBrokerAdapter(config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0), price_provider=lambda _order: 100.0)
        engine = ExecutionEngine(adapter)
        entry_auth = _authorization(StrategyDirection.LONG, 100.0, decision_id="paper04-entry-long", reason="entry")
        assert engine.submit(ExecutionEngine.from_authorization(entry_auth, decision_id="paper04-entry-long")).filled
        position = adapter.positions()[0]
        exit_auth = _authorization(StrategyDirection.SHORT, 100.0, decision_id="paper04-stop-long", reason="approved stop exit")
        result = engine.submit(ExecutionEngine.from_exit_authorization(exit_auth, decision_id="paper04-stop-long", position=position))
        assert result.snapshot.status is OrderStatus.FILLED
        assert adapter.positions() == ()

    def full_short_target_exit():
        adapter = PaperBrokerAdapter(config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0), price_provider=lambda _order: 100.0)
        engine = ExecutionEngine(adapter)
        entry_auth = _authorization(StrategyDirection.SHORT, 80.0, decision_id="paper04-entry-short", reason="entry")
        assert engine.submit(ExecutionEngine.from_authorization(entry_auth, decision_id="paper04-entry-short")).filled
        position = adapter.positions()[0]
        assert position.quantity == -80.0
        exit_auth = _authorization(StrategyDirection.LONG, 80.0, decision_id="paper04-target-short", reason="approved target exit")
        result = engine.submit(ExecutionEngine.from_exit_authorization(exit_auth, decision_id="paper04-target-short", position=position))
        assert result.filled
        assert adapter.positions() == ()

    def partial_long_time_exit():
        adapter = PaperBrokerAdapter(config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0), price_provider=lambda _order: 100.0)
        engine = ExecutionEngine(adapter)
        entry_auth = _authorization(StrategyDirection.LONG, 100.0, decision_id="paper04-entry-partial", reason="entry")
        assert engine.submit(ExecutionEngine.from_authorization(entry_auth, decision_id="paper04-entry-partial")).filled
        position = adapter.positions()[0]
        exit_auth = _authorization(StrategyDirection.SHORT, 40.0, decision_id="paper04-time-partial", reason="approved maximum-holding-time exit")
        result = engine.submit(ExecutionEngine.from_exit_authorization(exit_auth, decision_id="paper04-time-partial", position=position, quantity=40.0))
        assert result.filled
        assert adapter.positions() == (PositionSnapshot("ITC", 60.0, 100.0),)

    def partial_short_exit():
        adapter = PaperBrokerAdapter(config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0), price_provider=lambda _order: 100.0)
        engine = ExecutionEngine(adapter)
        entry_auth = _authorization(StrategyDirection.SHORT, 100.0, decision_id="paper04-entry-short-partial", reason="entry")
        assert engine.submit(ExecutionEngine.from_authorization(entry_auth, decision_id="paper04-entry-short-partial")).filled
        position = adapter.positions()[0]
        exit_auth = _authorization(StrategyDirection.LONG, 30.0, decision_id="paper04-short-partial-exit", reason="approved partial exit")
        result = engine.submit(ExecutionEngine.from_exit_authorization(exit_auth, decision_id="paper04-short-partial-exit", position=position, quantity=30.0))
        assert result.filled, result.snapshot
        assert adapter.positions() == (PositionSnapshot("ITC", -70.0, 100.0),), adapter.positions()

    def exit_cannot_exceed_position():
        adapter = PaperBrokerAdapter()
        engine = ExecutionEngine(adapter)
        entry_auth = _authorization(StrategyDirection.LONG, 50.0, decision_id="paper04-entry-bound", reason="entry")
        assert engine.submit(ExecutionEngine.from_authorization(entry_auth, decision_id="paper04-entry-bound")).filled
        position = adapter.positions()[0]
        exit_auth = _authorization(StrategyDirection.SHORT, 51.0, decision_id="paper04-oversize-exit", reason="invalid oversize exit")
        try:
            ExecutionEngine.from_exit_authorization(exit_auth, decision_id="paper04-oversize-exit", position=position, quantity=51.0)
        except ValueError as exc:
            assert "exceed" in str(exc)
        else:
            raise AssertionError("oversized exit was accepted")

    def exit_direction_must_oppose_position():
        position = PositionSnapshot("ITC", 50.0, 100.0)
        auth = _authorization(StrategyDirection.LONG, 50.0, decision_id="paper04-wrong-direction", reason="invalid exit direction")
        try:
            ExecutionEngine.from_exit_authorization(auth, decision_id="paper04-wrong-direction", position=position)
        except ValueError as exc:
            assert "oppose" in str(exc)
        else:
            raise AssertionError("same-direction exit was accepted")

    def duplicate_exit_is_idempotent():
        adapter = PaperBrokerAdapter(config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0), price_provider=lambda _order: 100.0)
        engine = ExecutionEngine(adapter)
        entry_auth = _authorization(StrategyDirection.LONG, 50.0, decision_id="paper04-entry-idempotent", reason="entry")
        assert engine.submit(ExecutionEngine.from_authorization(entry_auth, decision_id="paper04-entry-idempotent")).filled
        position = adapter.positions()[0]
        exit_auth = _authorization(StrategyDirection.SHORT, 50.0, decision_id="paper04-exit-idempotent", reason="approved target exit")
        request = ExecutionEngine.from_exit_authorization(exit_auth, decision_id="paper04-exit-idempotent", position=position)
        first = engine.submit(request)
        second = engine.submit(request)
        assert first.filled
        assert second.snapshot.broker_order_id == first.snapshot.broker_order_id
        assert adapter.positions() == ()

    def exit_from_flat_position_is_rejected():
        position = PositionSnapshot("ITC", 0.0, 0.0)
        auth = _authorization(StrategyDirection.SHORT, 1.0, decision_id="paper04-flat-exit", reason="invalid flat exit")
        try:
            ExecutionEngine.from_exit_authorization(auth, decision_id="paper04-flat-exit", position=position)
        except ValueError as exc:
            assert "flat position" in str(exc)
        else:
            raise AssertionError("flat-position exit was accepted")

    cases = (
        _case("full_long_stop_exit", full_long_stop_exit),
        _case("full_short_target_exit", full_short_target_exit),
        _case("partial_long_time_exit", partial_long_time_exit),
        _case("partial_short_exit", partial_short_exit),
        _case("exit_cannot_exceed_position", exit_cannot_exceed_position),
        _case("exit_direction_must_oppose_position", exit_direction_must_oppose_position),
        _case("duplicate_exit_is_idempotent", duplicate_exit_is_idempotent),
        _case("exit_from_flat_position_is_rejected", exit_from_flat_position_is_rejected),
    )
    return ExitExecutionReport(cases)

__all__ = ["ExitExecutionCase", "ExitExecutionReport", "run_exit_execution_certification"]

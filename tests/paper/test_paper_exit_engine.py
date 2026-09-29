"""Tests for PaperExitEngine and same-candle ambiguity resolution."""

from __future__ import annotations

import pandas as pd
import pytest

from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
)
from paper.runtime import PaperOrder, PaperOrderStatus, PaperTradingConfig, PaperTradingRuntime
from trading.paper.exit_engine import ExitReason, PaperExitEngine
from trading.strategy.models import StrategyDirection


def _filled_order(
    direction: StrategyDirection = StrategyDirection.LONG,
    fill_price: float = 100.0,
    quantity: float = 10.0,
    timestamp: str = "2026-09-29 10:00:00+05:30",
) -> PaperOrder:
    runtime = PaperTradingRuntime(config=PaperTradingConfig(fee_bps=0.0, slippage_bps=0.0))
    auth = ExecutionAuthorization(
        timestamp=pd.Timestamp(timestamp),
        symbol="RELIANCE",
        direction=direction,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test",
        risk_version="test",
        approved_quantity=quantity,
        approved_notional=fill_price * quantity,
    )
    return runtime.submit(auth, price=fill_price, quantity=quantity)


def test_exit_engine_opens_position():
    engine = PaperExitEngine()
    order = _filled_order()

    pos = engine.open_position(
        order,
        stop_price=98.0,
        target_price=104.0,
    )
    assert engine.has_open_position("RELIANCE")
    assert pos.symbol == "RELIANCE"
    assert pos.stop_price == 98.0
    assert pos.target_price == 104.0


def test_exit_engine_long_target_hit():
    engine = PaperExitEngine(fee_bps=0.0, slippage_bps=0.0)
    order = _filled_order(direction=StrategyDirection.LONG, fill_price=100.0)
    pos = engine.open_position(order, stop_price=98.0, target_price=104.0)

    # Candle reaches 105.0 high, low is 99.0 (stop not touched)
    candle = {
        "symbol": "RELIANCE",
        "timestamp": pd.Timestamp("2026-09-29 10:05:00+05:30"),
        "open": 100.5,
        "high": 105.0,
        "low": 99.0,
        "close": 103.5,
    }
    outcomes = engine.process_candle(candle)

    assert len(outcomes) == 1
    assert not engine.has_open_position("RELIANCE")
    outcome = outcomes[0]
    assert outcome.exit_price == 104.0
    assert outcome.net_pnl == 40.0  # (104 - 100) * 10
    assert engine.exit_reasons[pos.trade_id] == ExitReason.TARGET


def test_exit_engine_long_stop_loss_hit():
    engine = PaperExitEngine(fee_bps=0.0, slippage_bps=0.0)
    order = _filled_order(direction=StrategyDirection.LONG, fill_price=100.0)
    pos = engine.open_position(order, stop_price=98.0, target_price=104.0)

    # Candle drops to 97.0 low, high is 101.0 (target not touched)
    candle = {
        "symbol": "RELIANCE",
        "timestamp": pd.Timestamp("2026-09-29 10:05:00+05:30"),
        "open": 99.5,
        "high": 101.0,
        "low": 97.0,
        "close": 97.5,
    }
    outcomes = engine.process_candle(candle)

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.exit_price == 98.0
    assert outcome.net_pnl == -20.0  # (98 - 100) * 10
    assert engine.exit_reasons[pos.trade_id] == ExitReason.STOP_LOSS


def test_exit_engine_conservative_same_candle_ambiguity():
    """When both Target and Stop are hit in the same candle, must resolve to STOP_LOSS."""
    engine = PaperExitEngine(fee_bps=0.0, slippage_bps=0.0)
    order = _filled_order(direction=StrategyDirection.LONG, fill_price=100.0)
    pos = engine.open_position(order, stop_price=98.0, target_price=104.0)

    # Wide candle: low hits 97.0 (below stop) AND high hits 105.0 (above target)
    candle = {
        "symbol": "RELIANCE",
        "timestamp": pd.Timestamp("2026-09-29 10:05:00+05:30"),
        "open": 100.0,
        "high": 105.0,
        "low": 97.0,
        "close": 102.0,
    }
    outcomes = engine.process_candle(candle)

    assert len(outcomes) == 1
    outcome = outcomes[0]
    # Under conservative rule, STOP_LOSS must win
    assert outcome.exit_price == 98.0
    assert outcome.net_pnl < 0
    assert engine.exit_reasons[pos.trade_id] == ExitReason.STOP_LOSS


def test_exit_engine_session_cutoff():
    """At or after 15:15 IST, open positions must be closed at market close."""
    engine = PaperExitEngine(session_cutoff_time="15:15", fee_bps=0.0, slippage_bps=0.0)
    order = _filled_order(direction=StrategyDirection.LONG, fill_price=100.0)
    pos = engine.open_position(order, stop_price=95.0, target_price=110.0)

    # 15:15 IST candle (neither stop nor target touched)
    candle = {
        "symbol": "RELIANCE",
        "timestamp": pd.Timestamp("2026-09-29 15:15:00+05:30"),
        "open": 101.0,
        "high": 102.0,
        "low": 100.5,
        "close": 101.5,
    }
    outcomes = engine.process_candle(candle)

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.exit_price == 101.5
    assert engine.exit_reasons[pos.trade_id] == ExitReason.SESSION_CLOSE


def test_exit_engine_tracks_mae_and_mfe():
    engine = PaperExitEngine(fee_bps=0.0, slippage_bps=0.0)
    order = _filled_order(direction=StrategyDirection.LONG, fill_price=100.0, quantity=10.0)
    pos = engine.open_position(order, stop_price=90.0, target_price=115.0)

    # Candle 1: High 103, Low 99 (no exit)
    engine.process_candle({
        "symbol": "RELIANCE",
        "timestamp": pd.Timestamp("2026-09-29 10:05:00+05:30"),
        "open": 100.0,
        "high": 103.0,
        "low": 99.0,
        "close": 102.0,
    })
    assert pos.mfe == 30.0   # (103 - 100) * 10
    assert pos.mae == -10.0  # (99 - 100) * 10

"""Phase 21 live-signal engine tests."""

from datetime import time

import pandas as pd

from trading.live.signal_engine import (
    LiveSignalBlockReason,
    LiveSignalEngine,
    LiveSignalStatus,
)
from trading.strategy.models import StrategyInput


def _input(
    timestamp: str,
    *,
    symbol: str = "ITC",
    rvol: float = 2.0,
    regime: str = "TREND_UP",
) -> StrategyInput:
    return StrategyInput(
        timestamp=pd.Timestamp(timestamp),
        symbol=symbol,
        decision_features={
            "vwap_distance_pct": 0.5,
            "rvol_20": rvol,
            "higher_high": True,
            "higher_low": True,
            "lower_low": False,
            "lower_high": False,
        },
        regime=regime,
        regime_probability=0.9,
    )


def _observed(timestamp: str) -> pd.Timestamp:
    return pd.Timestamp(timestamp)


def test_live_signal_emits_signal_for_valid_causal_input() -> None:
    engine = LiveSignalEngine()
    event = engine.evaluate(
        _input("2026-09-25T09:20:00+05:30"),
        observed_at=_observed("2026-09-25T09:20:05+05:30"),
    )

    assert event.status is LiveSignalStatus.SIGNAL
    assert event.block_reason is None
    assert event.decision.direction.value == "LONG"
    assert event.event_id.startswith("SIG-")


def test_live_signal_preserves_no_trade_as_first_class_result() -> None:
    engine = LiveSignalEngine()
    event = engine.evaluate(
        _input("2026-09-25T09:20:00+05:30", rvol=0.5),
        observed_at=_observed("2026-09-25T09:20:05+05:30"),
    )

    assert event.status is LiveSignalStatus.NO_TRADE
    assert event.decision.primary_reason is not None


def test_live_signal_blocks_stale_input() -> None:
    engine = LiveSignalEngine(max_staleness_seconds=300)
    event = engine.evaluate(
        _input("2026-09-25T09:20:00+05:30"),
        observed_at=_observed("2026-09-25T09:25:01+05:30"),
    )

    assert event.status is LiveSignalStatus.BLOCKED
    assert event.block_reason is LiveSignalBlockReason.STALE_INPUT


def test_live_signal_blocks_future_input() -> None:
    engine = LiveSignalEngine()
    event = engine.evaluate(
        _input("2026-09-25T09:20:00+05:30"),
        observed_at=_observed("2026-09-25T09:19:59+05:30"),
    )

    assert event.status is LiveSignalStatus.BLOCKED
    assert event.block_reason is LiveSignalBlockReason.FUTURE_INPUT


def test_live_signal_blocks_outside_session() -> None:
    engine = LiveSignalEngine()
    event = engine.evaluate(
        _input("2026-09-25T09:10:00+05:30"),
        observed_at=_observed("2026-09-25T09:10:05+05:30"),
    )

    assert event.status is LiveSignalStatus.BLOCKED
    assert event.block_reason is LiveSignalBlockReason.OUTSIDE_SESSION


def test_live_signal_rejects_out_of_order_and_duplicate_without_advancing_state() -> None:
    engine = LiveSignalEngine()
    first = engine.evaluate(
        _input("2026-09-25T09:20:00+05:30"),
        observed_at=_observed("2026-09-25T09:20:05+05:30"),
    )
    duplicate = engine.evaluate(
        _input("2026-09-25T09:20:00+05:30"),
        observed_at=_observed("2026-09-25T09:20:06+05:30"),
    )
    older = engine.evaluate(
        _input("2026-09-25T09:15:00+05:30"),
        observed_at=_observed("2026-09-25T09:20:06+05:30"),
    )

    assert first.status is LiveSignalStatus.SIGNAL
    assert duplicate.block_reason is LiveSignalBlockReason.DUPLICATE
    assert older.block_reason is LiveSignalBlockReason.OUT_OF_ORDER
    assert engine.last_timestamp("ITC") == pd.Timestamp(
        "2026-09-25T09:20:00+05:30"
    )


def test_live_signal_allows_independent_symbol_chronology() -> None:
    engine = LiveSignalEngine()
    itc = engine.evaluate(
        _input("2026-09-25T09:20:00+05:30", symbol="ITC"),
        observed_at=_observed("2026-09-25T09:20:05+05:30"),
    )
    tcs = engine.evaluate(
        _input("2026-09-25T09:15:00+05:30", symbol="TCS"),
        observed_at=_observed("2026-09-25T09:15:05+05:30"),
    )

    assert itc.status is LiveSignalStatus.SIGNAL
    assert tcs.status is LiveSignalStatus.SIGNAL


def test_live_signal_does_not_call_risk_or_execution() -> None:
    engine = LiveSignalEngine()
    event = engine.evaluate(
        _input("2026-09-25T09:20:00+05:30"),
        observed_at=_observed("2026-09-25T09:20:05+05:30"),
    )

    assert not hasattr(event, "authorization")
    assert not hasattr(event, "order")


def test_live_signal_uses_ist_session_for_utc_input() -> None:
    engine = LiveSignalEngine()
    event = engine.evaluate(
        _input("2026-09-25T03:50:00+00:00"),
        observed_at=_observed("2026-09-25T03:50:05+00:00"),
    )

    assert event.status is LiveSignalStatus.SIGNAL


def test_live_signal_custom_session_bounds() -> None:
    engine = LiveSignalEngine(
        session_start=time(10, 0),
        session_end=time(11, 0),
    )
    event = engine.evaluate(
        _input("2026-09-25T09:30:00+05:30"),
        observed_at=_observed("2026-09-25T09:30:05+05:30"),
    )

    assert event.status is LiveSignalStatus.BLOCKED
    assert event.block_reason is LiveSignalBlockReason.OUTSIDE_SESSION

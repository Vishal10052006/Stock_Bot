"""Phase 21 Live Signal Engine tests.

References:
- docs/PHASE_21_LIVE_SIGNAL_ENGINE.md
- trading/strategy/engine.py
- trading/risk/pipeline.py
"""

from __future__ import annotations

import pandas as pd
import pytest

from live_signal import (
    LiveRiskState,
    LiveSignalEngine,
    LiveSignalInput,
    LiveSignalStatus,
    SignalFreshnessPolicy,
)


TIMESTAMP = pd.Timestamp("2026-09-27T09:30:00Z")


def make_input(**overrides) -> LiveSignalInput:
    features = {
        "close": 100.0,
        "atr_14": 2.0,
        "swing_low": 95.0,
        "support_20": 95.0,
        "vwap_distance_pct": 0.02,
        "rvol_20": 1.5,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }
    values = {
        "timestamp": TIMESTAMP,
        "symbol": "ITC",
        "decision_features": features,
        "risk_state": LiveRiskState(
            available_equity=100_000.0,
            day_start_equity=100_000.0,
        ),
        "regime": "TREND_UP",
        "regime_probability": 0.90,
        "versions": {
            "feature": "feature-v1",
            "analysis": "analysis-v1",
            "market": "market-v1",
            "research": "research-v1",
        },
    }
    values.update(overrides)
    return LiveSignalInput(**values)


def engine() -> LiveSignalEngine:
    return LiveSignalEngine(
        freshness=SignalFreshnessPolicy(max_age_seconds=30),
        now_provider=lambda: pd.Timestamp("2026-09-27T09:30:05Z"),
    )


def test_actionable_signal_reuses_strategy_and_risk_authorities():
    signal = engine().build(make_input())

    assert signal.status is LiveSignalStatus.ACTIONABLE
    assert signal.direction.value == "LONG"
    assert signal.risk.status.value == "APPROVED"
    assert signal.position_size is not None
    assert signal.position_size > 0
    assert signal.entry_price == 100.0
    assert signal.stop_price is not None
    assert signal.target_price is not None
    assert signal.signal_id


def test_same_decision_state_has_deterministic_signal_id():
    first = engine().build(make_input())
    second = engine().build(make_input())

    assert first.signal_id == second.signal_id
    assert first.as_dict() == second.as_dict()


def test_stale_input_fails_closed_without_strategy_execution():
    stale = make_input(
        timestamp=pd.Timestamp("2026-09-27T09:28:00Z"),
    )

    signal = engine().build(stale)

    assert signal.status is LiveSignalStatus.NO_TRADE
    assert signal.no_trade_reason.value == "STALE_DATA"
    assert signal.risk.status.value == "REJECTED"


def test_future_input_fails_closed():
    future = make_input(
        timestamp=pd.Timestamp("2026-09-27T09:31:00Z"),
    )

    signal = engine().build(future)

    assert signal.status is LiveSignalStatus.NO_TRADE
    assert signal.no_trade_reason.value == "STALE_DATA"


def test_invalid_market_data_fails_closed():
    state = LiveRiskState(
        available_equity=100_000.0,
        day_start_equity=100_000.0,
        market_data_valid=False,
    )

    signal = engine().build(make_input(risk_state=state))

    assert signal.status is LiveSignalStatus.NO_TRADE
    assert signal.no_trade_reason.value == "INVALID_INPUT"
    assert "market data" in signal.rationale


def test_kill_switch_fails_closed():
    state = LiveRiskState(
        available_equity=100_000.0,
        day_start_equity=100_000.0,
        kill_switch_active=True,
    )

    signal = engine().build(make_input(risk_state=state))

    assert signal.status is LiveSignalStatus.NO_TRADE
    assert signal.no_trade_reason.value == "INVALID_INPUT"
    assert "kill switch" in signal.rationale


def test_strategy_no_trade_is_preserved():
    weak_regime = make_input(regime="SIDEWAYS", regime_probability=0.90)

    signal = engine().build(weak_regime)

    assert signal.status is LiveSignalStatus.NO_TRADE
    assert signal.direction.value == "NO_TRADE"
    assert signal.risk.status.value == "REJECTED"
    assert signal.no_trade_reason.value == "STRATEGY_REJECTED"


def test_risk_rejection_is_preserved():
    state = LiveRiskState(
        available_equity=100_000.0,
        day_start_equity=100_000.0,
        open_positions=3,
    )

    signal = engine().build(make_input(risk_state=state))

    assert signal.status is LiveSignalStatus.NO_TRADE
    assert signal.direction.value == "LONG"
    assert signal.risk.status.value == "REJECTED"
    assert signal.no_trade_reason.value == "RISK_REJECTED"
    assert signal.position_size is None


def test_missing_candidate_fields_fail_closed():
    features = {
        "close": 100.0,
        "vwap_distance_pct": 0.02,
        "rvol_20": 1.5,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }

    signal = engine().build(make_input(decision_features=features))

    assert signal.status is LiveSignalStatus.NO_TRADE
    assert signal.no_trade_reason.value == "RISK_REJECTED"
    assert "Candidate construction failed" in signal.risk.reason


def test_timezone_is_required():
    with pytest.raises(ValueError, match="timezone-aware"):
        make_input(timestamp=pd.Timestamp("2026-09-27 09:30:00"))

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from market.data.events import MarketEvent, MarketEventType
from scripts.validate_live_review_runtime import validate_observations
from trading.live.risk_context import LiveManualRiskContext
from trading.risk.kill_switch import KillSwitchState


def _event(*, symbol="RELIANCE", price=2500.0):
    timestamp = pd.Timestamp("2026-10-03T10:00:00Z")
    return MarketEvent(
        event_id="evt-1",
        symbol=symbol,
        exchange="NSE",
        event_type=MarketEventType.TRADE,
        price=price,
        volume=10.0,
        exchange_timestamp=timestamp.to_pydatetime(),
        received_timestamp=datetime(2026, 10, 3, 10, 0, 1, tzinfo=timezone.utc),
        sequence_number=1,
    )


def _risk(*, market_data_valid=True, system_ready=True, kill_switch_active=False):
    return LiveManualRiskContext(
        as_of=pd.Timestamp("2026-10-03T10:00:02Z"),
        source="test",
        available_equity=100000.0,
        day_start_equity=100000.0,
        available_cash=90000.0,
        peak_equity=100000.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        open_positions=0,
        trades_today=0,
        gross_exposure=0.0,
        symbol_already_open=False,
        position_context=None,
        liquidity_available=True,
        kill_switch_active=kill_switch_active,
        sector=None,
        symbol_exposure={},
        sector_exposure={},
        pairwise_correlation={},
        atr=None,
        high_volatility=False,
        market_data_valid=market_data_valid,
        system_ready=system_ready,
        kill_switch_state=KillSwitchState(manual=kill_switch_active),
        max_age_seconds=30.0,
    )


def test_live_observation_validation_ready_for_human_review():
    report = validate_observations(
        symbol="RELIANCE",
        event=_event(),
        risk_context=_risk(),
        observed_at=pd.Timestamp("2026-10-03T10:00:03Z"),
    )
    assert report.status == "READY_FOR_HUMAN_REVIEW"
    assert report.broker_orders == 0
    assert report.execution_authority == "HUMAN_MANUAL_BUY_SELL"
    assert report.blocked_reasons == ()


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"event": None, "risk_context": _risk()}, "no valid live market event"),
        ({"event": _event(symbol="TCS"), "risk_context": _risk()}, "symbol does not match"),
        ({"event": _event(), "risk_context": _risk(market_data_valid=False)}, "market data state"),
        ({"event": _event(), "risk_context": _risk(system_ready=False)}, "account/segment"),
        ({"event": _event(), "risk_context": _risk(kill_switch_active=True)}, "kill switch"),
        ({"event": _event(), "risk_context": None}, "account/risk context"),
    ],
)
def test_live_observation_validation_blocks_invalid_state(kwargs, reason):
    report = validate_observations(
        symbol="RELIANCE",
        observed_at=pd.Timestamp("2026-10-03T10:00:03Z"),
        **kwargs,
    )
    assert report.status == "BLOCKED"
    assert any(reason in item for item in report.blocked_reasons)


def test_live_observation_validation_blocks_stale_risk_context():
    report = validate_observations(
        symbol="RELIANCE",
        event=_event(),
        risk_context=_risk(),
        observed_at=pd.Timestamp("2026-10-03T10:01:00Z"),
    )
    assert report.status == "BLOCKED"
    assert any("stale by 57.0s" in item for item in report.blocked_reasons)


def test_live_observation_validation_blocks_decision_after_observation():
    risk = _risk()
    report = validate_observations(
        symbol="RELIANCE",
        event=_event(),
        risk_context=risk,
        observed_at=pd.Timestamp("2026-10-03T09:59:00Z"),
    )
    assert report.status == "BLOCKED"
    assert any("future relative to risk observation" in item for item in report.blocked_reasons)

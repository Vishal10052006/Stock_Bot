import pandas as pd
import pytest

from runtime.live_signal import LiveSignalEngine
from trading.strategy.models import StrategyInput


def _input(ts):
    return StrategyInput(
        timestamp=pd.Timestamp(ts),
        symbol="TCS",
        decision_features={
            "vwap_distance_pct": 0.5,
            "rvol_20": 1.5,
            "higher_high": True,
            "higher_low": True,
            "lower_low": False,
            "lower_high": False,
        },
        regime="TREND_UP",
        regime_probability=0.8,
    )


def test_live_signal_is_strategy_only():
    engine = LiveSignalEngine(max_input_age_seconds=60)
    result = engine.evaluate(
        _input("2026-09-26T09:15:00Z"),
        observed_at="2026-09-26T09:15:30Z",
    )
    assert result.signal.direction.value in {"LONG", "NO_TRADE"}
    assert result.evidence()["live_broker_order_submission"] is False


def test_stale_input_fails_closed():
    engine = LiveSignalEngine(max_input_age_seconds=10)
    with pytest.raises(ValueError, match="stale"):
        engine.evaluate(
            _input("2026-09-26T09:15:00Z"),
            observed_at="2026-09-26T09:15:11Z",
        )


def test_future_input_fails_closed():
    engine = LiveSignalEngine(max_input_age_seconds=60)
    with pytest.raises(ValueError, match="future"):
        engine.evaluate(
            _input("2026-09-26T09:16:00Z"),
            observed_at="2026-09-26T09:15:30Z",
        )


def test_duplicate_timestamp_fails_closed():
    engine = LiveSignalEngine(max_input_age_seconds=60)
    engine.evaluate(_input("2026-09-26T09:15:00Z"), observed_at="2026-09-26T09:15:01Z")
    with pytest.raises(ValueError, match="strictly increasing"):
        engine.evaluate(_input("2026-09-26T09:15:00Z"), observed_at="2026-09-26T09:15:02Z")

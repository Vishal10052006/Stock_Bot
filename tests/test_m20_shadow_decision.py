"""Tests for the M20.3 shadow decision trace boundary."""

from __future__ import annotations

import pandas as pd

from runtime.shadow_decision import ShadowDecisionRecorder


def test_shadow_decision_recorder_records_every_decision() -> None:
    rows = pd.DataFrame(
        [
            {
                "timestamp": "2026-09-28T09:15:00Z",
                "symbol": "ITC",
                "close": 100.0,
                "regime": "TREND_UP",
                "regime_probability": 0.90,
                "vwap_distance_pct": 0.01,
                "rvol_20": 1.5,
                "higher_high": True,
                "higher_low": True,
                "lower_low": False,
                "lower_high": False,
            },
            {
                "timestamp": "2026-09-28T09:20:00Z",
                "symbol": "ITC",
                "close": 101.0,
                "regime": "TREND_DOWN",
                "regime_probability": 0.90,
                "vwap_distance_pct": -0.01,
                "rvol_20": 1.5,
                "higher_high": False,
                "higher_low": False,
                "lower_low": True,
                "lower_high": True,
            },
        ]
    )

    recorder = ShadowDecisionRecorder()
    run = recorder.run(rows)

    assert len(run.steps) == 2
    assert len(recorder.traces()) == 2
    evidence = recorder.evidence()
    assert evidence["decision_count"] == 2
    assert evidence["live_broker_order_submission"] is False


def test_shadow_decision_trace_is_json_safe() -> None:
    rows = pd.DataFrame(
        [
            {
                "timestamp": "2026-09-28T09:15:00Z",
                "symbol": "ITC",
                "close": 100.0,
                "regime": "RANGE",
                "regime_probability": 0.90,
                "vwap_distance_pct": 0.0,
                "rvol_20": 1.0,
                "higher_high": False,
                "higher_low": False,
                "lower_low": False,
                "lower_high": False,
            }
        ]
    )

    recorder = ShadowDecisionRecorder()
    recorder.run(rows)

    mapping = recorder.traces()[0].to_mapping()
    assert mapping["symbol"] == "ITC"
    assert isinstance(mapping["timestamp"], str)

from __future__ import annotations

import pandas as pd

from scripts.trading.analyze_risk_capacity import Scenario, run_scenario


def _rows() -> pd.DataFrame:
    # Causal strategy-ready fixture with one actionable LONG and one later row.
    return pd.DataFrame(
        [
            {
                "timestamp": "2026-09-21T10:00:00+05:30",
                "symbol": "TEST",
                "close": 100.0,
                "regime": "TREND",
                "regime_probability": 0.9,
                "vwap_distance_pct": 0.02,
                "rvol_20": 2.0,
                "higher_high": 1,
                "higher_low": 1,
                "lower_low": 0,
                "lower_high": 0,
            },
            {
                "timestamp": "2026-09-21T10:05:00+05:30",
                "symbol": "TEST",
                "close": 101.0,
                "regime": "TREND",
                "regime_probability": 0.9,
                "vwap_distance_pct": 0.02,
                "rvol_20": 2.0,
                "higher_high": 1,
                "higher_low": 1,
                "lower_low": 0,
                "lower_high": 0,
            },
        ]
    )


def test_counterfactual_scenario_is_explicit():
    result = run_scenario(
        _rows(),
        Scenario("frozen_75_hard_reject", 0.75, False),
    )

    assert result["scenario"]["max_gross_exposure"] == 0.75
    assert result["scenario"]["allow_resize"] is False
    assert "risk_rejection_reasons" in result
    assert "claim_boundary" not in result

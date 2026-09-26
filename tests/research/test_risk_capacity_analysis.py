from __future__ import annotations

import pandas as pd

from scripts.trading.analyze_risk_capacity import Scenario, run_scenario


def _rows() -> pd.DataFrame:
    # Causal strategy-ready fixture with a LONG signal whose risk-first
    # quantity intentionally exceeds the frozen 75% gross-exposure ceiling.
    return pd.DataFrame(
        [
            {
                "timestamp": "2026-09-21T10:00:00+05:30",
                "symbol": "TEST",
                "close": 100.0,
                "regime": "TREND_UP",
                "regime_probability": 0.9,
                "vwap_distance_pct": 0.02,
                "rvol_20": 2.0,
                "higher_high": True,
                "higher_low": True,
                "lower_low": False,
                "lower_high": False,
                "atr_14": 0.01,
                "support_20": 99.99,
            },
            {
                "timestamp": "2026-09-21T10:05:00+05:30",
                "symbol": "TEST",
                "close": 101.0,
                "regime": "TREND_UP",
                "regime_probability": 0.9,
                "vwap_distance_pct": 0.02,
                "rvol_20": 2.0,
                "higher_high": True,
                "higher_low": True,
                "lower_low": False,
                "lower_high": False,
                "atr_14": 0.01,
                "support_20": 100.99,
            },
        ]
    )


def test_counterfactual_scenario_is_explicit_and_tracks_gross_rejection():
    result = run_scenario(
        _rows(),
        Scenario("frozen_75_hard_reject", 0.75, False),
    )

    assert result["scenario"]["max_gross_exposure"] == 0.75
    assert result["scenario"]["allow_resize"] is False
    assert result["strategy_signals"] >= 1
    assert result["gross_exposure_rejections"] >= 1
    assert result["risk_rejection_reasons"]["MAX_GROSS_EXPOSURE"] >= 1
    assert "claim_boundary" not in result


def test_resize_counterfactual_can_convert_capacity_rejection_to_fill():
    result = run_scenario(
        _rows(),
        Scenario("frozen_75_resize_enabled", 0.75, True),
    )

    assert result["strategy_signals"] >= 1
    assert result["paper_fills"] >= 1
    assert result["risk_rejection_reasons"].get("MAX_GROSS_EXPOSURE", 0) == 0

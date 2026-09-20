"""Tests for the Analysis Bot's first integrated contract/engine slice."""
from __future__ import annotations

import pandas as pd

from intelligence.analysis.contracts import AnalysisInput
from intelligence.analysis.engine import AnalysisEngine
from intelligence.analysis.validation import validate_analysis_context, validate_feature_mapping


def _features() -> dict[str, object]:
    return {
        "rsi_14": 62.0,
        "macd_histogram": 1.2,
        "roc_14": 0.4,
        "vwap_distance_pct": 0.8,
        "ema_9_20_distance_pct": 0.2,
        "ema_20_50_distance_pct": 0.5,
        "rvol_20": 1.4,
        "volume_change_1": 0.2,
        "atr_normalized": 0.01,
        "bb_width_normalized": 0.02,
        "realized_volatility_20": 0.015,
        "higher_high": True,
        "higher_low": True,
        "lower_high": False,
        "lower_low": False,
        "retest_up": True,
        "retest_down": False,
        "opening_range_high_distance_pct": 0.1,
        "opening_range_low_distance_pct": 1.0,
        "stock_vs_market_return_1": 0.2,
        "stock_vs_sector_return_1": 0.3,
    }


def test_analysis_engine_is_structured_and_non_trading() -> None:
    timestamp = pd.Timestamp("2026-09-20 10:25:00+05:30")
    context = AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=timestamp,
            symbol="RELIANCE",
            features=_features(),
            market_context={"market_return_1": 0.1, "market_volatility_20": 0.01},
            sector_context={"sector_return_1": 0.2, "sector_volatility_20": 0.02},
            data_version="market-v1",
            feature_version="v1.0",
        )
    )
    assert context.symbol == "RELIANCE"
    assert context.analytical_direction == "BULLISH"
    assert "volume_confirmation" in context.candidates
    assert all("BUY" not in candidate and "SELL" not in candidate for candidate in context.candidates)
    validate_analysis_context(context)


def test_feature_validation_rejects_infinity() -> None:
    try:
        validate_feature_mapping({"x": float("inf")})
    except ValueError as exc:
        assert "invalid feature value" in str(exc)
    else:
        raise AssertionError("infinity should be rejected")

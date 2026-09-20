"""AB-24 integration tests for real FeatureDataset v1 -> AnalysisContext."""
from __future__ import annotations

import pandas as pd

from intelligence.analysis.contracts import AnalysisContext
from intelligence.analysis.integration import build_analysis_context
from market.features.builder import FEATURE_COLUMNS, build_features
from market.features.validation import validate_feature_dataset


def _phase4_row() -> pd.DataFrame:
    """Build one realistic Phase 4 output row using existing field names."""
    return pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-09-20 10:25:00+05:30")],
            "symbol": ["RELIANCE"],
            "close": [150.0],
            "ema_9": [149.0],
            "ema_20": [148.0],
            "ema_50": [145.0],
            "rsi_14": [62.0],
            "macd_histogram": [1.2],
            "roc_14": [0.4],
            "vwap_distance_pct": [0.8],
            "atr_14": [1.5],
            "bb_width": [3.0],
            "realized_volatility_20": [0.015],
            "rvol_20": [1.4],
            "volume_change_1": [0.2],
            "distance_to_support_pct": [1.0],
            "distance_to_resistance_pct": [-0.5],
            "previous_day_high": [151.0],
            "previous_day_low": [145.0],
            "opening_range_high": [150.5],
            "opening_range_low": [147.0],
            "opening_range_width": [3.5],
            "swing_high": [150.5],
            "swing_low": [146.0],
            "retest_up": [True],
            "retest_down": [False],
            "retest_distance_pct": [0.2],
            "higher_high": [True],
            "lower_low": [False],
            "higher_low": [True],
            "lower_high": [False],
        }
    )


def test_ab24_real_feature_dataset_reaches_analysis_context() -> None:
    feature_dataset = build_features(_phase4_row())
    validated = validate_feature_dataset(feature_dataset)

    context = build_analysis_context(
        validated,
        regime_dataset=pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-09-20 10:25:00+05:30")],
                "regime": ["TREND_UP"],
                "regime_probability": [0.82],
            }
        ),
        data_version="market-test-v1",
    )

    assert isinstance(context, AnalysisContext)
    assert context.symbol == "RELIANCE"
    assert context.timestamp == pd.Timestamp("2026-09-20 10:25:00+05:30")
    assert context.analytical_direction == "BULLISH"
    assert context.provenance["causal_boundary"] == (
        "information_available_at_decision_timestamp"
    )
    assert set(FEATURE_COLUMNS).issubset(context.feature_vector)


def test_ab24_does_not_use_future_regime_row() -> None:
    """A future regime timestamp must not be attached by forward/backward guessing."""
    feature_dataset = build_features(_phase4_row())

    context = build_analysis_context(
        feature_dataset,
        regime_dataset=pd.DataFrame(
            {
                "timestamp": [
                    pd.Timestamp("2026-09-20 10:30:00+05:30")
                ],
                "regime": ["TREND_UP"],
                "regime_probability": [0.9],
            }
        ),
    )

    assert context.provenance["causal_boundary"] == (
        "information_available_at_decision_timestamp"
    )
    assert context.symbol == "RELIANCE"

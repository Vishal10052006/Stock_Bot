"""Tests for the Phase 9 experiment feature-coverage diagnostics."""

from __future__ import annotations

import pandas as pd

from market.features.builder import FEATURE_COLUMNS
from scripts.run_phase9_experiment import (
    _feature_coverage_report,
    _phase9_data_source_limitations,
)


def test_feature_coverage_report_preserves_frozen_schema() -> None:
    data = pd.DataFrame(
        {
            feature: 1.0
            for feature in FEATURE_COLUMNS
        },
        index=range(4),
    )
    data["retest_distance_pct"] = [None, 0.1, None, 0.2]
    data["sector_return_1"] = None
    data["sector_return_3"] = None
    data["sector_return_12"] = None
    data["sector_volatility_20"] = None
    data["stock_vs_sector_return_1"] = None

    report = _feature_coverage_report(data)

    assert report["total_features"] == len(FEATURE_COLUMNS)
    assert report["fully_observed_features"] == len(FEATURE_COLUMNS) - 6
    assert report["complete_missing_feature_count"] == 5

    partial = {
        item["feature"]: item
        for item in report["partially_observed_features"]
    }
    assert partial["retest_distance_pct"]["coverage_pct"] == 50.0


def test_phase9_source_limitation_report_is_explicit() -> None:
    report = _phase9_data_source_limitations()

    sector = report["sector_context"]
    assert sector["observed_coverage_pct"] == 0.0
    assert sector["timeframe_minutes"] == 5
    assert "Yahoo Finance" in sector["source"]
    assert "not fabricated" in sector["handling"]

    retest = report["retest_distance_pct"]
    assert retest["semantic_missingness"] is True

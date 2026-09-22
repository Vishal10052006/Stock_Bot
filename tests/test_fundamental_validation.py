"""Validation tests for historical fundamental observations."""
from __future__ import annotations

import pandas as pd

from intelligence.analysis.fundamentals.contracts import FundamentalSnapshot
from intelligence.analysis.fundamentals.validation import validate_fundamental_snapshots


def _snapshot() -> FundamentalSnapshot:
    return FundamentalSnapshot(
        symbol="TCS",
        period_start=pd.Timestamp("2026-04-01 00:00:00+05:30"),
        period_end=pd.Timestamp("2026-06-30 00:00:00+05:30"),
        published_at=pd.Timestamp("2026-07-20 18:00:00+05:30"),
        available_at=pd.Timestamp("2026-07-20 18:01:00+05:30"),
        metrics={"revenue": 100.0, "net_income": 10.0},
        source="test",
        source_version="v1",
    )


def test_historical_validation_accepts_valid_snapshot() -> None:
    report = validate_fundamental_snapshots([_snapshot()])
    assert report.valid is True
    assert report.observations == 1
    assert report.symbols == 1
    assert report.duplicate_keys == 0


def test_historical_validation_detects_duplicate_observations() -> None:
    snapshot = _snapshot()
    report = validate_fundamental_snapshots([snapshot, snapshot])
    assert report.valid is False
    assert report.duplicate_keys == 1

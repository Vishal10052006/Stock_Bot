"""Tests for Phase 12 report generation."""

from __future__ import annotations

import pandas as pd

from backtesting.engine import HistoricalBacktestEngine
from backtesting.reports import build_report


def _row(timestamp: str, close: float) -> dict:
    return {
        "timestamp": timestamp,
        "symbol": "ITC",
        "close": close,
        "regime": "TREND_UP",
        "regime_probability": 0.90,
        "vwap_distance_pct": 1.0,
        "rvol_20": 1.5,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }


def test_report_is_json_safe() -> None:
    result = HistoricalBacktestEngine().run(
        pd.DataFrame(
            [
                _row("2026-01-01 09:15:00+05:30", 100.0),
                _row("2026-01-01 09:20:00+05:30", 101.0),
            ]
        )
    )

    report = build_report(result)
    payload = report.to_dict()

    assert payload["step_count"] == 2
    assert payload["order_count"] == 1
    assert payload["completed_trade_count"] == 1
    assert payload["trade_count"] == 1

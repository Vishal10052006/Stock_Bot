from pathlib import Path

import pandas as pd

from scripts.trading.analyze_empirical_paper import analyze


def _row(timestamp: str, *, regime: str = "TREND_UP") -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "symbol": "RELIANCE",
        "close": 100.0,
        "regime": regime,
        "regime_probability": 0.9,
        "vwap_distance_pct": 0.5,
        "rvol_20": 1.4,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }


def test_analyze_reports_decision_and_equity_coverage() -> None:
    rows = pd.DataFrame(
        [
            _row("2026-09-21 10:00:00"),
            _row("2026-09-21 10:05:00"),
        ]
    )

    report = analyze(rows)

    assert report["run"]["steps"] == 2
    assert report["run"]["signals"] == 2
    assert report["run"]["filled_orders"] == 1
    assert report["risk"]["status_counts"]["APPROVED"] == 1
    assert report["risk"]["status_counts"]["REJECTED"] == 1
    assert report["equity"]["observations"] == 2
    assert report["equity"]["max_drawdown"] >= 0


def test_analyze_reports_rejection_reason() -> None:
    rows = pd.DataFrame(
        [
            _row("2026-09-21 10:00:00"),
            _row("2026-09-21 10:05:00"),
        ]
    )

    report = analyze(rows)

    reasons = {
        item["reason"]: item["count"]
        for item in report["risk"]["signal_rejection_reasons"]
    }
    assert any("already has an open position" in reason for reason in reasons)


def test_analyzer_input_is_chronological() -> None:
    rows = pd.DataFrame(
        [
            _row("2026-09-21 10:05:00"),
            _row("2026-09-21 10:00:00"),
        ]
    )

    from scripts.trading.run_empirical_paper import _load_rows

    path = Path("tests") / "_tmp_empirical_analysis.parquet"
    try:
        rows.to_parquet(path)
        try:
            _load_rows(path)
        except ValueError as exc:
            assert "chronological order" in str(exc)
    finally:
        path.unlink(missing_ok=True)

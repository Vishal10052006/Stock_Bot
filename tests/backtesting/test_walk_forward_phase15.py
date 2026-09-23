import pandas as pd
import pytest

from backtesting.metrics import BacktestMetrics
from backtesting.walk_forward import (
    WalkForwardTradingReport,
    evaluate_walk_forward,
    generate_windows,
    validate_walk_forward_report,
)


def _data(rows: int = 120) -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-01 09:15:00", periods=rows, freq="5min", tz="Asia/Kolkata")
    return pd.DataFrame({"timestamp": timestamps, "symbol": ["ITC"] * rows, "value": range(rows)})


def _metrics(pnl: float) -> BacktestMetrics:
    return BacktestMetrics(
        trade_count=4, winning_trades=2, losing_trades=2,
        gross_pnl=pnl + 2.0, net_pnl=pnl, total_fees=1.0, total_slippage=1.0,
        win_rate=0.5, average_win=5.0, average_loss=-3.0, profit_factor=1.5,
        expectancy=pnl / 4, maximum_drawdown=2.0, sharpe_ratio=1.0, sortino_ratio=1.0,
        exposure_minutes=60.0, turnover=1000.0,
    )


def test_walk_forward_windows_are_chronological_and_non_overlapping() -> None:
    windows = generate_windows(_data(), folds=4, train_ratio=0.50, purge_minutes=10)
    assert len(windows) == 4
    for i, window in enumerate(windows):
        assert window.train_end < window.test_start
        if i:
            assert windows[i - 1].test_end < window.test_start


def test_walk_forward_evaluator_receives_causal_future_test_only() -> None:
    seen = []
    def evaluator(train, test):
        assert train["timestamp"].max() < test["timestamp"].min()
        seen.append((len(train), len(test)))
        return _metrics(10.0)
    report = evaluate_walk_forward(_data(), folds=3, train_ratio=0.50, purge_minutes=15, evaluator=evaluator)
    assert len(seen) == 3
    assert report.summary["fold_count"] == 3.0
    assert report.summary["total_trades"] == 12.0
    assert report.summary["positive_fold_fraction"] == 1.0
    assert len(report.fingerprint) == 64


def test_walk_forward_records_purged_rows() -> None:
    windows = generate_windows(_data(), folds=3, train_ratio=0.50, purge_minutes=10)
    assert all(window.purged_rows >= 1 for window in windows)


def test_walk_forward_rejects_duplicate_symbol_timestamp_rows() -> None:
    data = _data().copy()
    data.loc[1, "timestamp"] = data.loc[0, "timestamp"]
    with pytest.raises(ValueError, match="duplicate symbol/timestamp"):
        generate_windows(data, folds=3)


def test_walk_forward_requires_symbol_column() -> None:
    with pytest.raises(ValueError, match="symbol"):
        generate_windows(_data().drop(columns=["symbol"]), folds=3)


def test_walk_forward_rejects_test_mutation() -> None:
    def evaluator(train, test):
        test.loc[:, "value"] = -1
        return None
    with pytest.raises(RuntimeError, match="mutated test partition"):
        evaluate_walk_forward(_data(), folds=3, purge_minutes=5, evaluator=evaluator)


def test_walk_forward_report_rejects_overlapping_windows() -> None:
    windows = generate_windows(_data(), folds=3, purge_minutes=5)
    broken = list(windows)
    broken[1] = type(broken[1])(
        fold_id=2, train_start=broken[1].train_start, train_end=broken[0].train_end,
        test_start=broken[0].test_start, test_end=broken[1].test_end,
        train_rows=broken[1].train_rows, test_rows=broken[1].test_rows,
        purged_rows=broken[1].purged_rows,
    )
    with pytest.raises(ValueError, match="test windows overlap"):
        WalkForwardTradingReport(tuple(broken), (_metrics(1.0),) * 3)


def test_validate_walk_forward_report_rejects_wrong_result_count() -> None:
    windows = generate_windows(_data(), folds=3, purge_minutes=5)
    report = object.__new__(WalkForwardTradingReport)
    object.__setattr__(report, "windows", windows)
    object.__setattr__(report, "results", (_metrics(1.0),))
    with pytest.raises(ValueError, match="one result per window"):
        validate_walk_forward_report(report)

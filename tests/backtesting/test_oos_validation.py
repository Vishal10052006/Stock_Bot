import pandas as pd
import pytest

from backtesting.metrics import BacktestMetrics
from backtesting.oos import OOSReport
from backtesting.oos_validation import (
    CostSensitivityPoint,
    OOSFoldEvidence,
    validate_oos_evidence,
)


def _metrics(trades: int = 4, pnl: float = 12.0) -> BacktestMetrics:
    return BacktestMetrics(
        trade_count=trades, winning_trades=trades, losing_trades=0,
        gross_pnl=pnl, net_pnl=pnl, total_fees=1.0, total_slippage=0.5,
        win_rate=1.0, average_win=pnl / trades if trades else 0.0,
        average_loss=0.0, profit_factor=float("inf"),
        expectancy=pnl / trades if trades else 0.0, maximum_drawdown=0.0,
        sharpe_ratio=1.0, sortino_ratio=1.0, exposure_minutes=60.0,
        turnover=1000.0,
    )


def _oos() -> OOSReport:
    timestamps = pd.date_range("2026-01-01", periods=4, freq="5min", tz="UTC")
    return OOSReport(
        train_rows=10, validation_rows=5, test_rows=4,
        train_end=timestamps[0], validation_end=timestamps[1], test_start=timestamps[2],
        predictions=pd.Series([0, 1, 0, 1]),
        test_data=pd.DataFrame({"timestamp": timestamps[2:]}),
    )


def test_final_oos_report_preserves_evidence() -> None:
    report = validate_oos_evidence(
        _oos(), test_metrics=_metrics(),
        fold_evidence=(OOSFoldEvidence(1, 4.0, 1.0, 0.0, 2), OOSFoldEvidence(2, -2.0, -0.5, 2.0, 2)),
        regime_metrics={"TREND": _metrics(2, 8.0)},
        cost_sensitivity=(CostSensitivityPoint("base", 12.0, 3.0), CostSensitivityPoint("high_cost", 5.0, 1.25)),
    )
    assert report.decision == "UNDECIDED"
    assert report.train_end < report.test_start
    assert report.test_rows == 4
    assert report.stability["fold_count"] == 2.0
    assert report.stability["positive_fold_fraction"] == 0.5
    assert report.regime_summary["TREND"]["trade_count"] == 2
    assert report.cost_sensitivity[1].net_pnl == 5.0
    assert len(report.fingerprint) == 64


def test_oos_rejects_prediction_count_mismatch() -> None:
    oos = _oos()
    broken = OOSReport(oos.train_rows, oos.validation_rows, oos.test_rows, oos.train_end, oos.validation_end, oos.test_start, pd.Series([0]), oos.test_data)
    with pytest.raises(ValueError, match="prediction count"):
        validate_oos_evidence(broken, test_metrics=_metrics())


def test_oos_rejects_test_data_count_mismatch() -> None:
    oos = _oos()
    broken = OOSReport(oos.train_rows, oos.validation_rows, oos.test_rows, oos.train_end, oos.validation_end, oos.test_start, oos.predictions, oos.test_data.iloc[:1].copy())
    with pytest.raises(ValueError, match="test-data count"):
        validate_oos_evidence(broken, test_metrics=_metrics())


def test_oos_rejects_invalid_decision() -> None:
    with pytest.raises(ValueError, match="decision"):
        validate_oos_evidence(_oos(), test_metrics=_metrics(), decision="PROMOTE")


def test_cost_and_regime_contracts_are_validated() -> None:
    with pytest.raises(ValueError, match="label must be non-empty"):
        CostSensitivityPoint("", 1.0, 0.5)
    with pytest.raises(ValueError, match="fold_id"):
        OOSFoldEvidence(0, 1.0, 0.5, 0.0, 1)

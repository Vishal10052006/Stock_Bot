"""Phase 14 final out-of-sample validation contract.

This module reports descriptive OOS trading evidence after Phase 13 leakage
controls have passed. It does not tune a model, touch the final test set, or
turn empirical results into an automatic promotion decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

import pandas as pd

from backtesting.metrics import BacktestMetrics
from backtesting.oos import OOSReport
from utils.fingerprint import artifact_fingerprint


@dataclass(frozen=True, slots=True)
class CostSensitivityPoint:
    """One frozen cost/slippage sensitivity observation."""
    label: str
    net_pnl: float
    expectancy: float

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("label must be non-empty")
        if not isfinite(self.net_pnl) or not isfinite(self.expectancy):
            raise ValueError("cost sensitivity values must be finite")


@dataclass(frozen=True, slots=True)
class OOSFoldEvidence:
    """Descriptive evidence for one frozen OOS evaluation fold."""
    fold_id: int
    net_pnl: float
    expectancy: float
    maximum_drawdown: float
    trade_count: int

    def __post_init__(self) -> None:
        if self.fold_id < 1:
            raise ValueError("fold_id must be positive")
        if self.trade_count < 0:
            raise ValueError("trade_count must not be negative")
        values = (self.net_pnl, self.expectancy, self.maximum_drawdown)
        if not all(isfinite(value) for value in values):
            raise ValueError("fold metrics must be finite")


@dataclass(frozen=True, slots=True)
class OOSValidationReport:
    """Immutable final OOS evidence package."""
    train_rows: int
    validation_rows: int
    test_rows: int
    train_end: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp
    test_metrics: BacktestMetrics
    fold_evidence: tuple[OOSFoldEvidence, ...]
    regime_metrics: tuple[tuple[str, BacktestMetrics], ...]
    cost_sensitivity: tuple[CostSensitivityPoint, ...]
    decision: str = "UNDECIDED"

    def __post_init__(self) -> None:
        if min(self.train_rows, self.validation_rows, self.test_rows) <= 0:
            raise ValueError("OOS partitions must all contain at least one row")
        if self.train_end >= self.test_start:
            raise ValueError("training context must end before OOS test starts")
        if self.test_metrics.trade_count < 0:
            raise ValueError("test trade_count must not be negative")
        if self.decision not in {"UNDECIDED", "PASS", "FAIL"}:
            raise ValueError("decision must be UNDECIDED, PASS, or FAIL")

    @property
    def stability(self) -> dict[str, float]:
        """Return descriptive fold-stability statistics."""
        if not self.fold_evidence:
            return {"fold_count": 0.0, "positive_fold_fraction": 0.0, "worst_fold_net_pnl": 0.0, "worst_fold_expectancy": 0.0}
        returns = [fold.net_pnl for fold in self.fold_evidence]
        expectancies = [fold.expectancy for fold in self.fold_evidence]
        return {
            "fold_count": float(len(self.fold_evidence)),
            "positive_fold_fraction": sum(value > 0 for value in returns) / len(returns),
            "worst_fold_net_pnl": min(returns),
            "worst_fold_expectancy": min(expectancies),
        }

    @property
    def fingerprint(self) -> str:
        return artifact_fingerprint(self)

    @property
    def regime_summary(self) -> dict[str, dict[str, float | int]]:
        return {
            name: {
                "trade_count": metrics.trade_count,
                "net_pnl": metrics.net_pnl,
                "expectancy": metrics.expectancy,
                "maximum_drawdown": metrics.maximum_drawdown,
                "profit_factor": metrics.profit_factor,
            }
            for name, metrics in self.regime_metrics
        }


def validate_oos_evidence(
    oos_report: OOSReport,
    *,
    test_metrics: BacktestMetrics,
    fold_evidence: tuple[OOSFoldEvidence, ...] = (),
    regime_metrics: Mapping[str, BacktestMetrics] | None = None,
    cost_sensitivity: tuple[CostSensitivityPoint, ...] = (),
    decision: str = "UNDECIDED",
) -> OOSValidationReport:
    """Build the final OOS evidence package from already-executed boundaries."""
    if not isinstance(oos_report, OOSReport):
        raise TypeError("oos_report must be an OOSReport")
    if not isinstance(test_metrics, BacktestMetrics):
        raise TypeError("test_metrics must be BacktestMetrics")
    if not isinstance(fold_evidence, tuple):
        raise TypeError("fold_evidence must be a tuple")
    if not all(isinstance(item, OOSFoldEvidence) for item in fold_evidence):
        raise TypeError("fold_evidence entries must be OOSFoldEvidence")
    if not isinstance(cost_sensitivity, tuple):
        raise TypeError("cost_sensitivity must be a tuple")
    if not all(isinstance(item, CostSensitivityPoint) for item in cost_sensitivity):
        raise TypeError("cost_sensitivity entries must be CostSensitivityPoint")
    if len(oos_report.predictions) != oos_report.test_rows:
        raise ValueError("OOS prediction count must equal test row count")
    if len(oos_report.test_data) != oos_report.test_rows:
        raise ValueError("OOS test-data count must equal test row count")
    if oos_report.train_end >= oos_report.test_start:
        raise ValueError("OOS training context reaches the test period")

    regimes = tuple(sorted((regime_metrics or {}).items(), key=lambda item: item[0]))
    for name, metrics in regimes:
        if not name.strip():
            raise ValueError("regime names must be non-empty")
        if not isinstance(metrics, BacktestMetrics):
            raise TypeError("regime metrics must be BacktestMetrics")

    return OOSValidationReport(
        train_rows=oos_report.train_rows,
        validation_rows=oos_report.validation_rows,
        test_rows=oos_report.test_rows,
        train_end=oos_report.train_end,
        validation_end=oos_report.validation_end,
        test_start=oos_report.test_start,
        test_metrics=test_metrics,
        fold_evidence=fold_evidence,
        regime_metrics=regimes,
        cost_sensitivity=cost_sensitivity,
        decision=decision,
    )

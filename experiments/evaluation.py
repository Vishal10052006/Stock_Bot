"""S22 experiment evaluation boundary.

This module validates measured experiment outputs without turning metrics into
an automatic trading decision. It separates measurement integrity from
research policy.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .record import ExperimentRecord


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Immutable validation report for one completed experiment record."""

    definition_fingerprint: str
    observations: int
    metric_count: int
    sections: tuple[str, ...]
    issues: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Return whether the measured record passed integrity checks."""
        return not self.issues


def _collect_numeric_metrics(
    value: Any,
    *,
    path: str,
    output: list[tuple[str, float]],
) -> None:
    """Collect scalar numeric metrics while ignoring structural containers."""
    if isinstance(value, bool):
        return

    if isinstance(value, (int, float)):
        output.append((path, float(value)))
        return

    if isinstance(value, dict):
        for key, child in value.items():
            _collect_numeric_metrics(
                child,
                path=f"{path}.{key}",
                output=output,
            )
        return

    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _collect_numeric_metrics(
                child,
                path=f"{path}[{index}]",
                output=output,
            )


def _validate_metric_ranges(
    metrics: list[tuple[str, float]],
) -> list[str]:
    """Validate generic numeric invariants without judging performance."""
    issues: list[str] = []

    bounded_zero_one = (
        "accuracy",
        "balanced_accuracy",
        "macro_precision",
        "macro_recall",
        "macro_f1",
        "win_rate",
    )
    non_negative = (
        "brier_score",
        "expected_calibration_error",
        "log_loss",
        "trade_count",
        "winning_trades",
        "losing_trades",
        "total_fees",
        "total_slippage",
        "maximum_drawdown",
        "exposure_minutes",
        "turnover",
    )

    for path, value in metrics:
        name = path.rsplit(".", 1)[-1]

        if math.isnan(value):
            issues.append(f"{path} must not be NaN")
            continue

        # Infinite profit factor is a legitimate representation when there
        # are wins and no losses; other infinite measurements are invalid.
        if math.isinf(value) and name != "profit_factor":
            issues.append(f"{path} must be finite")
            continue

        if name in bounded_zero_one and not 0.0 <= value <= 1.0:
            issues.append(f"{path} must be in [0, 1]")

        if name in non_negative and value < 0.0:
            issues.append(f"{path} must be non-negative")

    return issues


def _validate_backtest_consistency(record: ExperimentRecord) -> list[str]:
    """Validate consistency between backtest summary and its trade metrics."""
    backtest = record.baseline_results.get("backtest")
    if not isinstance(backtest, dict):
        return []

    completed = backtest.get("completed_trades")
    metrics = backtest.get("metrics")

    if not isinstance(metrics, dict):
        return ["baseline_results.backtest.metrics must be a mapping"]

    trade_count = metrics.get("trade_count")
    if isinstance(completed, (int, float)) and isinstance(
        trade_count,
        (int, float),
    ):
        if completed != trade_count:
            return [
                "backtest completed_trades must equal metrics.trade_count"
            ]

    winning = metrics.get("winning_trades")
    losing = metrics.get("losing_trades")
    if all(isinstance(value, (int, float)) for value in (trade_count, winning, losing)):
        if winning + losing > trade_count:
            return [
                "backtest winning_trades + losing_trades "
                "must not exceed trade_count"
            ]

    return []


def evaluate_experiment_record(
    record: ExperimentRecord,
) -> EvaluationReport:
    """Validate measured experiment outputs and return a neutral report.

    The function does not rank experiments, select a strategy, or infer
    profitability. It only checks that recorded measurements are structurally
    and numerically coherent.
    """
    if not isinstance(record, ExperimentRecord):
        raise TypeError("record must be an ExperimentRecord")

    sections: list[str] = []
    metrics: list[tuple[str, float]] = []

    result_groups = (
        ("baseline_results", record.baseline_results),
        ("model_results", record.model_results),
        ("stratified_results", record.stratified_results),
    )

    for section, values in result_groups:
        if values:
            sections.append(section)
            _collect_numeric_metrics(
                values,
                path=section,
                output=metrics,
            )

    issues = _validate_metric_ranges(metrics)
    issues.extend(_validate_backtest_consistency(record))

    return EvaluationReport(
        definition_fingerprint=record.definition_fingerprint,
        observations=record.observations,
        metric_count=len(metrics),
        sections=tuple(sections),
        issues=tuple(dict.fromkeys(issues)),
    )

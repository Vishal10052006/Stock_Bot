"""Explicit adapter for executing the existing validation boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from backtesting.oos import OOSReport, evaluate_oos
from backtesting.walk_forward import (
    WalkForwardTradingReport,
    evaluate_walk_forward,
)
from .definition import ExperimentDefinition
from .record import ExperimentRecord


@dataclass(frozen=True, slots=True)
class ExperimentExecutionInputs:
    """Explicit inputs required to execute a research experiment.

    No dataset, model, or validation configuration is created implicitly.
    Callers provide the exact data and evaluators that belong to the frozen
    experiment definition.
    """

    oos_dataset: Any
    oos_predictor: Callable[[pd.DataFrame, pd.DataFrame], pd.Series]
    walk_forward_data: pd.DataFrame
    walk_forward_evaluator: Callable[[pd.DataFrame, pd.DataFrame], object]
    folds: int = 3
    purge_minutes: int = 60


def _oos_summary(report: OOSReport) -> dict[str, Any]:
    """Serialize only structural OOS evidence, not invented performance."""
    return {
        "train_rows": report.train_rows,
        "validation_rows": report.validation_rows,
        "test_rows": report.test_rows,
        "train_end": str(report.train_end),
        "validation_end": str(report.validation_end),
        "test_start": str(report.test_start),
    }


def _walk_forward_summary(
    report: WalkForwardTradingReport,
) -> dict[str, Any]:
    """Serialize structural walk-forward evidence."""
    return {
        "folds": len(report.windows),
        "windows": [
            {
                "fold_id": window.fold_id,
                "train_start": str(window.train_start),
                "train_end": str(window.train_end),
                "test_start": str(window.test_start),
                "test_end": str(window.test_end),
                "train_rows": window.train_rows,
                "test_rows": window.test_rows,
            }
            for window in report.windows
        ],
    }


def execute_validation_experiment(
    definition: ExperimentDefinition,
    inputs: ExperimentExecutionInputs,
) -> ExperimentRecord:
    """Execute the explicit OOS and walk-forward validation boundaries.

    The function does not select models, thresholds, or decision outcomes.
    It records only the structural outputs available from the supplied
    validation contracts. A research-specific caller can add measured
    metrics to an ExperimentRecord in a later, explicit evaluation stage.
    """

    if not isinstance(definition, ExperimentDefinition):
        raise TypeError(
            "definition must be an ExperimentDefinition"
        )

    if not isinstance(inputs.walk_forward_data, pd.DataFrame):
        raise TypeError(
            "walk_forward_data must be a pandas DataFrame"
        )

    oos_report = evaluate_oos(
        inputs.oos_dataset,
        predictor=inputs.oos_predictor,
    )

    walk_forward_report = evaluate_walk_forward(
        inputs.walk_forward_data,
        folds=inputs.folds,
        purge_minutes=inputs.purge_minutes,
        evaluator=inputs.walk_forward_evaluator,
    )

    observations = (
        oos_report.test_rows
        + sum(window.test_rows for window in walk_forward_report.windows)
    )

    return ExperimentRecord.from_definition(
        definition,
        observations=observations,
        baseline_results={
            "oos": _oos_summary(oos_report),
        },
        model_results={
            "walk_forward": _walk_forward_summary(walk_forward_report),
        },
        interpretation=(
            "Validation boundaries executed successfully. "
            "No performance conclusion is inferred by this adapter."
        ),
        decision="INCONCLUSIVE",
        limitations=(
            "This adapter records validation structure, not model quality.",
            "Backtest profitability metrics require an explicit trading evaluator.",
        ),
    )

"""Explicit adapter for executing the existing validation boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from backtesting.engine import BacktestConfig, BacktestResult, HistoricalBacktestEngine
from backtesting.metrics import BacktestMetrics, calculate_metrics
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
    oos_config: TemporalSplitConfig | None = None
    folds: int = 3
    purge_minutes: int = 60
    backtest_rows: pd.DataFrame | None = None
    backtest_config: BacktestConfig | None = None


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


def _backtest_summary(
    result: BacktestResult,
    metrics: BacktestMetrics,
) -> dict[str, Any]:
    """Serialize explicit trading backtest evidence and metrics."""
    return {
        "completed_trades": result.completed_trades,
        "net_pnl": result.net_pnl,
        "metrics": {
            "trade_count": metrics.trade_count,
            "winning_trades": metrics.winning_trades,
            "losing_trades": metrics.losing_trades,
            "gross_pnl": metrics.gross_pnl,
            "net_pnl": metrics.net_pnl,
            "total_fees": metrics.total_fees,
            "total_slippage": metrics.total_slippage,
            "win_rate": metrics.win_rate,
            "average_win": metrics.average_win,
            "average_loss": metrics.average_loss,
            "profit_factor": metrics.profit_factor,
            "expectancy": metrics.expectancy,
            "maximum_drawdown": metrics.maximum_drawdown,
            "sharpe_ratio": metrics.sharpe_ratio,
            "exposure_minutes": metrics.exposure_minutes,
            "turnover": metrics.turnover,
        },
    }


def execute_backtest(
    rows: pd.DataFrame,
    *,
    config: BacktestConfig | None = None,
) -> tuple[BacktestResult, BacktestMetrics]:
    """Execute the authoritative historical backtest and calculate metrics."""
    if not isinstance(rows, pd.DataFrame):
        raise TypeError("rows must be a pandas DataFrame")
    engine = HistoricalBacktestEngine(
        config=config or BacktestConfig()
    )
    result = engine.run(rows)
    return result, calculate_metrics(result.outcomes)


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

    if not isinstance(inputs, ExperimentExecutionInputs):
        raise TypeError(
            "inputs must be an ExperimentExecutionInputs"
        )

    if not isinstance(inputs.walk_forward_data, pd.DataFrame):
        raise TypeError(
            "walk_forward_data must be a pandas DataFrame"
        )

    backtest_result: BacktestResult | None = None
    backtest_metrics: BacktestMetrics | None = None
    if inputs.backtest_rows is not None:
        backtest_result, backtest_metrics = execute_backtest(
            inputs.backtest_rows,
            config=inputs.backtest_config,
        )

    oos_report = evaluate_oos(
        inputs.oos_dataset,
        config=inputs.oos_config,
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
            **(
                {
                    "backtest": _backtest_summary(
                        backtest_result,
                        backtest_metrics,
                    )
                }
                if backtest_result is not None and backtest_metrics is not None
                else {}
            ),
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
            "Backtest execution is optional and must be supplied explicitly.",
        ),
    )

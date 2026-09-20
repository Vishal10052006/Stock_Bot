"""Experiment harness with majority, class-prior and frozen-strategy baselines."""
from __future__ import annotations
from dataclasses import dataclass
from research.experiments.metrics import ClassificationMetrics, evaluate, majority_baseline


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    experiment_id: str
    hypothesis: str
    dataset_version: str
    code_version: str
    change: str
    expected: str
    actual: str
    metrics: ClassificationMetrics
    majority_metrics: ClassificationMetrics
    baseline_strategy_metrics: ClassificationMetrics | None
    decision: str


def run_experiment(
    *,
    experiment_id,
    hypothesis,
    dataset_version,
    code_version,
    change,
    expected,
    y_true,
    y_pred,
    probabilities,
    classes,
    baseline_strategy_pred=None,
    baseline_strategy_probabilities=None,
    clusters_by_date=None,
    clusters_by_symbol=None,
    actual="UNSET",
) -> ExperimentResult:
    """Evaluate one predeclared change without selecting thresholds on test data."""
    metrics = evaluate(
        y_true, y_pred, probabilities, classes=classes,
        clusters_by_date=clusters_by_date, clusters_by_symbol=clusters_by_symbol,
    )

    majority_pred, majority_prob = majority_baseline(y_true, classes)
    majority_metrics = evaluate(
        y_true, majority_pred, majority_prob, classes=classes,
        clusters_by_date=clusters_by_date, clusters_by_symbol=clusters_by_symbol,
    )

    baseline_metrics = None
    if baseline_strategy_pred is not None and baseline_strategy_probabilities is not None:
        baseline_metrics = evaluate(
            y_true, baseline_strategy_pred, baseline_strategy_probabilities,
            classes=classes,
            clusters_by_date=clusters_by_date,
            clusters_by_symbol=clusters_by_symbol,
        )

    # KEEP/REJECT must be decided from the experiment's frozen failure criterion.
    # This function deliberately never tunes or chooses a winner.
    return ExperimentResult(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        dataset_version=dataset_version,
        code_version=code_version,
        change=change,
        expected=expected,
        actual=actual,
        metrics=metrics,
        majority_metrics=majority_metrics,
        baseline_strategy_metrics=baseline_metrics,
        decision="UNDECIDED",
    )

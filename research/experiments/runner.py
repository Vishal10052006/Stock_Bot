"""Experiment harness that records baselines without tuning on test data."""
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
    decision: str


def run_experiment(*, experiment_id, hypothesis, dataset_version, code_version,
                    change, expected, y_true, y_pred, probabilities, classes,
                    clusters_by_date=None, clusters_by_symbol=None,
                    actual="UNSET") -> ExperimentResult:
    metrics = evaluate(
        y_true, y_pred, probabilities, classes=classes,
        clusters_by_date=clusters_by_date, clusters_by_symbol=clusters_by_symbol,
    )
    majority_pred, majority_prob = majority_baseline(y_true, classes)
    majority_metrics = evaluate(
        y_true, majority_pred, majority_prob, classes=classes,
        clusters_by_date=clusters_by_date, clusters_by_symbol=clusters_by_symbol,
    )
    # The experiment owner must apply the predeclared failure criterion.
    return ExperimentResult(
        experiment_id=experiment_id, hypothesis=hypothesis,
        dataset_version=dataset_version, code_version=code_version,
        change=change, expected=expected, actual=actual,
        metrics=metrics, majority_metrics=majority_metrics,
        decision="UNDECIDED",
    )

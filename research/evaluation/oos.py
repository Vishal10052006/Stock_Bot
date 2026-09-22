"""Out-of-sample evaluation for causal Research Intelligence observations.

The evaluator does not fit a model and never tunes a threshold. It partitions
already-frozen observations chronologically and reports descriptive metrics on
unseen test folds only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from research.evaluation.intelligence import (
    ResearchEvaluationObservation,
    ResearchOutcomeEvaluation,
    evaluate_research_outcomes,
)
from research.validation.walk_forward import build_walk_forward_folds


@dataclass(frozen=True, slots=True)
class ResearchOOSFoldResult:
    fold_id: int
    train_count: int
    validation_count: int
    test_count: int
    evaluation: ResearchOutcomeEvaluation


@dataclass(frozen=True, slots=True)
class ResearchOOSResult:
    observations: int
    folds: tuple[ResearchOOSFoldResult, ...]
    pooled_test_evaluation: ResearchOutcomeEvaluation | None
    decision: str = "UNDECIDED"


def evaluate_research_oos(
    observations: tuple[ResearchEvaluationObservation, ...]
    | list[ResearchEvaluationObservation],
    *,
    train_size: int,
    validation_size: int,
    test_size: int,
    purge: timedelta,
    step: int | None = None,
) -> ResearchOOSResult:
    """Evaluate frozen research scores on chronological unseen test folds."""
    rows = tuple(sorted(
        observations,
        key=lambda row: (row.decision_time, row.symbol),
    ))
    if not rows:
        raise ValueError("observations must be non-empty")
    if min(train_size, validation_size, test_size) <= 0:
        raise ValueError("fold sizes must be positive")
    for row in rows:
        row.validate()

    folds = build_walk_forward_folds(
        [row.decision_time for row in rows],
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        purge=purge,
        step=step,
    )

    results: list[ResearchOOSFoldResult] = []
    pooled: list[ResearchEvaluationObservation] = []

    for fold in folds:
        test_rows = tuple(rows[index] for index in fold.test_indices)
        if not test_rows:
            continue
        evaluation = evaluate_research_outcomes(test_rows)
        results.append(ResearchOOSFoldResult(
            fold_id=fold.fold_id,
            train_count=len(fold.train_indices),
            validation_count=len(fold.validation_indices),
            test_count=len(fold.test_indices),
            evaluation=evaluation,
        ))
        pooled.extend(test_rows)

    pooled_evaluation = evaluate_research_outcomes(pooled) if pooled else None
    return ResearchOOSResult(
        observations=len(rows),
        folds=tuple(results),
        pooled_test_evaluation=pooled_evaluation,
    )

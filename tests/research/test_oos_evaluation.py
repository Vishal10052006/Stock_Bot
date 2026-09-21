from datetime import datetime, timedelta, timezone

from research.evaluation.intelligence import ResearchEvaluationObservation
from research.evaluation.oos import evaluate_research_oos

UTC = timezone.utc
T0 = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def _row(index: int) -> ResearchEvaluationObservation:
    decision = T0 + timedelta(hours=index)
    return ResearchEvaluationObservation(
        symbol="ABC",
        decision_time=decision,
        feature_available_at=decision - timedelta(minutes=1),
        research_score=0.5 if index % 2 == 0 else -0.5,
        outcome_timestamp=decision + timedelta(minutes=30),
        forward_return=0.01 if index % 2 == 0 else -0.01,
    )


def test_oos_evaluation_uses_test_folds_only():
    result = evaluate_research_oos(
        [_row(i) for i in range(18)],
        train_size=8,
        validation_size=3,
        test_size=3,
        purge=timedelta(hours=1),
    )

    assert result.observations == 18
    assert result.folds
    assert all(f.test_count == 3 for f in result.folds)
    assert result.pooled_test_evaluation is not None
    assert result.pooled_test_evaluation.observations == sum(
        f.test_count for f in result.folds
    )

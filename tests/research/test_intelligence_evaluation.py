from datetime import datetime, timedelta, timezone

import pytest

from research.evaluation.intelligence import (
    ResearchEvaluationObservation,
    evaluate_research_outcomes,
)

UTC = timezone.utc
T0 = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def observation(score, ret, *, symbol="ABC", outcome_minutes=5):
    return ResearchEvaluationObservation(
        symbol=symbol,
        decision_time=T0,
        feature_available_at=T0 - timedelta(minutes=1),
        research_score=score,
        outcome_timestamp=T0 + timedelta(minutes=outcome_minutes),
        forward_return=ret,
    )


def test_research_outcome_evaluation_is_descriptive_and_deterministic():
    result = evaluate_research_outcomes(
        [
            observation(0.8, 0.10),
            observation(-0.7, -0.05),
            observation(0.0, 0.02),
        ]
    )

    assert result.observations == 3
    assert result.score_return_correlation > 0.0
    assert result.directional_agreement == 1.0
    assert result.mean_forward_return == pytest.approx(0.07 / 3)
    assert result.positive_score_mean_return == pytest.approx(0.10)
    assert result.negative_score_mean_return == pytest.approx(-0.05)
    assert result.neutral_score_mean_return == pytest.approx(0.02)


def test_research_outcome_rejects_future_feature_availability():
    row = ResearchEvaluationObservation(
        symbol="ABC",
        decision_time=T0,
        feature_available_at=T0 + timedelta(minutes=1),
        research_score=0.5,
        outcome_timestamp=T0 + timedelta(minutes=5),
        forward_return=0.01,
    )

    with pytest.raises(ValueError, match="available"):
        row.validate()


def test_research_outcome_rejects_non_future_outcome():
    row = observation(0.5, 0.01, outcome_minutes=0)

    with pytest.raises(ValueError, match="strictly after"):
        row.validate()


def test_research_outcome_rejects_score_outside_model_contract():
    row = observation(1.5, 0.01)

    with pytest.raises(ValueError, match=r"\[-1, 1\]"):
        row.validate()

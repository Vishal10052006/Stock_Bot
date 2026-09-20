"""Point-in-time evaluation contract for Research Intelligence.

This module measures the relationship between an already-computed research
score and a future market outcome. It does not produce a trading decision,
choose thresholds, or claim predictive edge.

The key causal rule is explicit: the outcome timestamp must be strictly after
the research decision time.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class ResearchEvaluationObservation:
    """One frozen research score paired with a future market outcome."""

    symbol: str
    decision_time: object
    feature_available_at: object
    research_score: float
    outcome_timestamp: object
    forward_return: float

    def validate(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if self.feature_available_at > self.decision_time:
            raise ValueError("research features must be available by decision_time")
        if self.outcome_timestamp <= self.decision_time:
            raise ValueError("outcome_timestamp must be strictly after decision_time")
        if not isfinite(float(self.research_score)):
            raise ValueError("research_score must be finite")
        if not -1.0 <= float(self.research_score) <= 1.0:
            raise ValueError("research_score must be within [-1, 1]")
        if not isfinite(float(self.forward_return)):
            raise ValueError("forward_return must be finite")


@dataclass(frozen=True, slots=True)
class ResearchOutcomeEvaluation:
    """Descriptive OOS evaluation summary for research scores."""

    observations: int
    score_return_correlation: float
    directional_agreement: float
    mean_forward_return: float
    positive_score_mean_return: float
    negative_score_mean_return: float
    neutral_score_mean_return: float


def evaluate_research_outcomes(
    observations: tuple[ResearchEvaluationObservation, ...] | list[ResearchEvaluationObservation],
) -> ResearchOutcomeEvaluation:
    """Evaluate frozen research scores against future outcomes.

    Directional agreement counts a positive research score as agreeing with a
    positive future return, and a negative score with a negative return.
    Neutral scores and zero-return outcomes are excluded from that numerator.
    No threshold is learned from the supplied outcomes.
    """
    if not observations:
        raise ValueError("observations must be non-empty")

    rows = tuple(observations)
    for row in rows:
        row.validate()

    scores = [float(row.research_score) for row in rows]
    returns = [float(row.forward_return) for row in rows]

    score_mean = sum(scores) / len(scores)
    return_mean = sum(returns) / len(returns)
    numerator = sum(
        (score - score_mean) * (ret - return_mean)
        for score, ret in zip(scores, returns)
    )
    score_ss = sum((score - score_mean) ** 2 for score in scores)
    return_ss = sum((ret - return_mean) ** 2 for ret in returns)
    denominator = (score_ss * return_ss) ** 0.5
    correlation = numerator / denominator if denominator else 0.0

    directional_pairs = [
        (score, ret)
        for score, ret in zip(scores, returns)
        if score != 0.0 and ret != 0.0
    ]
    directional_agreement = (
        sum((score > 0) == (ret > 0) for score, ret in directional_pairs)
        / len(directional_pairs)
        if directional_pairs
        else 0.0
    )

    def mean_for(predicate) -> float:
        selected = [ret for score, ret in zip(scores, returns) if predicate(score)]
        return sum(selected) / len(selected) if selected else 0.0

    return ResearchOutcomeEvaluation(
        observations=len(rows),
        score_return_correlation=correlation,
        directional_agreement=directional_agreement,
        mean_forward_return=return_mean,
        positive_score_mean_return=mean_for(lambda score: score > 0),
        negative_score_mean_return=mean_for(lambda score: score < 0),
        neutral_score_mean_return=mean_for(lambda score: score == 0),
    )

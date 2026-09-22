"""Evidence-weighted Research Bot intelligence model.

The model converts a point-in-time ResearchContext into a structured research
stance. It is intentionally not a price/return predictor and does not emit a
trade decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import exp, isfinite, log
from typing import Iterable, Mapping

from research.contracts import ResearchContext


@dataclass(frozen=True, slots=True)
class ResearchIntelligenceResult:
    """Structured research stance at one point in time."""

    model_version: str
    symbol: str
    as_of: datetime
    score: float
    stance: str
    confidence: float
    evidence_count: int
    source_count: int
    event_count: int
    positive_evidence_fraction: float
    negative_evidence_fraction: float
    conflict_score: float
    provenance: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if not isfinite(float(self.score)) or not -1.0 <= self.score <= 1.0:
            raise ValueError("score must be finite and within [-1, 1]")
        if not isfinite(float(self.confidence)) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be finite and within [0, 1]")
        for name, value in (
            ("positive_evidence_fraction", self.positive_evidence_fraction),
            ("negative_evidence_fraction", self.negative_evidence_fraction),
            ("conflict_score", self.conflict_score),
        ):
            if not isfinite(float(value)) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and within [0, 1]")
        if min(self.evidence_count, self.source_count, self.event_count) < 0:
            raise ValueError("evidence/source/event counts cannot be negative")


class ResearchIntelligenceModel:
    """Aggregate causal research evidence into a bounded information stance.

    The score is constrained to [-1, 1]. It is a research-context score, not
    an expected return, price probability, or trading recommendation.
    """

    model_version = "research-intelligence-1.1"

    def __init__(
        self,
        *,
        source_reliability: Mapping[str, float] | None = None,
        half_life_days: float = 7.0,
    ) -> None:
        if half_life_days <= 0:
            raise ValueError("half_life_days must be positive")

        self.source_reliability = {
            source: self._bounded(value)
            for source, value in (source_reliability or {}).items()
        }
        self.half_life_days = float(half_life_days)

    def score_context(self, context: ResearchContext) -> ResearchIntelligenceResult:
        if len(context.documents) != len(context.sentiment):
            raise ValueError(
                "ResearchContext documents and sentiment must have equal length"
            )
        if context.as_of.tzinfo is None or context.as_of.utcoffset() is None:
            raise ValueError("ResearchContext.as_of must be timezone-aware")

        if not context.documents:
            return ResearchIntelligenceResult(
                model_version=self.model_version,
                symbol=context.symbol,
                as_of=context.as_of,
                score=0.0,
                stance="neutral",
                confidence=0.0,
                evidence_count=0,
                source_count=0,
                event_count=len(context.events),
                positive_evidence_fraction=0.0,
                negative_evidence_fraction=0.0,
                conflict_score=0.0,
                provenance=(),
            )

        event_weight_by_document: dict[str, float] = {}
        for event in context.events:
            weight = self._bounded(event.importance) * self._bounded(event.confidence)
            event_weight_by_document[event.document_id] = min(
                1.0,
                event_weight_by_document.get(event.document_id, 0.0) + weight,
            )

        weighted_scores: list[float] = []
        weights: list[float] = []
        positive_weight = 0.0
        negative_weight = 0.0
        provenance: list[str] = []

        for document, sentiment in zip(context.documents, context.sentiment):
            if document.available_at > context.as_of:
                raise ValueError(
                    f"future research document entered context: {document.document_id}"
                )

            age_days = max(
                0.0,
                (context.as_of - document.available_at).total_seconds() / 86400.0,
            )
            recency = exp(-log(2.0) * age_days / self.half_life_days)
            reliability = self.source_reliability.get(document.source_id, 0.5)
            sentiment_confidence = self._bounded(sentiment.confidence)

            event_weight = event_weight_by_document.get(document.document_id, 0.0)
            evidence_weight = recency * reliability * sentiment_confidence
            evidence_weight *= 1.0 + 0.5 * event_weight

            signed_score = max(-1.0, min(1.0, float(sentiment.score)))
            # Non-informative evidence can legitimately have zero weight.
            # It must not make a final aggregate non-finite.
            if not isfinite(evidence_weight) or evidence_weight < 0.0:
                raise ValueError(
                    f"invalid evidence weight for document {document.document_id}"
                )
            weighted_scores.append(signed_score * evidence_weight)
            weights.append(evidence_weight)

            if signed_score > 0:
                positive_weight += evidence_weight
            elif signed_score < 0:
                negative_weight += evidence_weight

            provenance.append(
                f"{document.document_id}:{document.source_id}:"
                f"{document.available_at.isoformat()}"
            )

        total_weight = sum(weights)
        score = 0.0 if total_weight == 0 else sum(weighted_scores) / total_weight
        score = max(-1.0, min(1.0, score))

        # Fraction denominators must include only directional evidence. If all
        # available evidence is neutral/non-directional, fractions are zero.
        directional_weight = positive_weight + negative_weight
        positive_fraction = (
            positive_weight / directional_weight
            if directional_weight > 0.0
            else 0.0
        )
        negative_fraction = (
            negative_weight / directional_weight
            if directional_weight > 0.0
            else 0.0
        )
        conflict_score = min(
            1.0,
            2.0 * min(positive_fraction, negative_fraction),
        )

        source_count = len({d.source_id for d in context.documents})
        evidence_factor = min(1.0, len(context.documents) / 5.0)
        source_factor = min(1.0, source_count / 3.0)
        directional_factor = abs(positive_fraction - negative_fraction)
        confidence = min(
            1.0,
            0.35 * evidence_factor
            + 0.25 * source_factor
            + 0.25 * directional_factor
            + 0.15 * (1.0 - conflict_score),
        )

        if score > 0.15:
            stance = "positive"
        elif score < -0.15:
            stance = "negative"
        else:
            stance = "neutral"

        return ResearchIntelligenceResult(
            model_version=self.model_version,
            symbol=context.symbol,
            as_of=context.as_of,
            score=score,
            stance=stance,
            confidence=confidence,
            evidence_count=len(context.documents),
            source_count=source_count,
            event_count=len(context.events),
            positive_evidence_fraction=positive_fraction,
            negative_evidence_fraction=negative_fraction,
            conflict_score=conflict_score,
            provenance=tuple(provenance),
        )

    def score_contexts(
        self,
        contexts: Iterable[ResearchContext],
    ) -> tuple[ResearchIntelligenceResult, ...]:
        """Score a deterministic sequence without changing model state."""
        return tuple(self.score_context(context) for context in contexts)

    @staticmethod
    def _bounded(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

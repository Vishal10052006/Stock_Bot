"""Point-in-time Research Intelligence observations paired with market outcomes.

The builder uses completed OHLCV candles and research documents available by the
decision timestamp. Future returns are measured from the decision candle's
close to the close of an exact future candle, so the current candle's OHLCV is
not used before it is complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite

from market.candles.models import Candle
from research.contracts import ResearchContext, ResearchDocument
from research.evaluation.intelligence import (
    ResearchEvaluationObservation,
)
from research.evaluation.intelligence import ResearchOutcomeEvaluation
from research.integration.context import ResearchContextBuilder
from research.intelligence.model import ResearchIntelligenceModel


@dataclass(frozen=True, slots=True)
class ResearchMarketObservation:
    """One causal Research Intelligence observation at a fixed horizon."""

    symbol: str
    decision_time: datetime
    feature_available_at: datetime
    decision_close: float
    outcome_timestamp: datetime
    outcome_close: float
    forward_return: float
    horizon_minutes: int
    research_score: float
    research_confidence: float
    evidence_count: int
    source_document_ids: tuple[str, ...]

    def validate(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if self.feature_available_at > self.decision_time:
            raise ValueError("research features must be available by decision_time")
        if self.outcome_timestamp <= self.decision_time:
            raise ValueError("outcome_timestamp must be strictly after decision_time")
        if self.horizon_minutes <= 0:
            raise ValueError("horizon_minutes must be positive")
        if not isfinite(self.decision_close) or self.decision_close <= 0:
            raise ValueError("decision_close must be finite and positive")
        if not isfinite(self.outcome_close) or self.outcome_close <= 0:
            raise ValueError("outcome_close must be finite and positive")
        if not isfinite(self.forward_return):
            raise ValueError("forward_return must be finite")
        if not -1.0 <= self.research_score <= 1.0:
            raise ValueError("research_score must be within [-1, 1]")


def _completed_time(candle: Candle) -> datetime:
    """Return when the candle's close becomes observable."""
    return candle.timestamp + timedelta(minutes=candle.timeframe_minutes)


def build_research_market_observations(
    *,
    symbol: str,
    candles: tuple[Candle, ...] | list[Candle],
    documents: tuple[ResearchDocument, ...] | list[ResearchDocument],
    horizons_minutes: tuple[int, ...] = (30, 60),
    intelligence_model: ResearchIntelligenceModel | None = None,
    context_builder: ResearchContextBuilder | None = None,
    require_evidence: bool = False,
) -> tuple[ResearchMarketObservation, ...]:
    """Build causal research/outcome observations from historical inputs.

    Candle timestamps are treated as bucket start times, matching the
    repository's OHLCV convention. Therefore the decision timestamp is the
    candle close timestamp. Future outcome candles must end exactly at the
    requested horizon; missing target candles are skipped rather than
    interpolated.
    """
    rows = tuple(candles)
    if not rows:
        raise ValueError("candles must be non-empty")
    if not symbol.strip():
        raise ValueError("symbol must be non-empty")

    horizons = tuple(horizons_minutes)
    if not horizons or any(h <= 0 for h in horizons):
        raise ValueError("horizons_minutes must contain positive values")
    if len(set(horizons)) != len(horizons):
        raise ValueError("horizons_minutes must be unique")

    for candle in rows:
        if candle.symbol != symbol:
            raise ValueError("all candles must match symbol")
    ordered = tuple(sorted(rows, key=lambda candle: candle.timestamp))
    if len({c.timestamp for c in ordered}) != len(ordered):
        raise ValueError("candles must have unique timestamps")

    model = intelligence_model or ResearchIntelligenceModel()
    contexts = context_builder or ResearchContextBuilder()

    by_end_time = {_completed_time(candle): candle for candle in ordered}
    observations: list[ResearchMarketObservation] = []

    for candle in ordered:
        decision_time = _completed_time(candle)
        context: ResearchContext = contexts.build(
            symbol=symbol,
            as_of=decision_time,
            documents=tuple(documents),
        )
        intelligence = model.score_context(context)

        if require_evidence and intelligence.evidence_count == 0:
            continue

        feature_available_at = (
            max((document.available_at for document in context.documents), default=decision_time)
        )
        if feature_available_at > decision_time:
            raise ValueError("context builder returned future research evidence")

        for horizon in horizons:
            target_time = decision_time + timedelta(minutes=horizon)
            target = by_end_time.get(target_time)
            if target is None:
                continue

            forward_return = target.close / candle.close - 1.0
            observation = ResearchMarketObservation(
                symbol=symbol,
                decision_time=decision_time,
                feature_available_at=feature_available_at,
                decision_close=candle.close,
                outcome_timestamp=target_time,
                outcome_close=target.close,
                forward_return=forward_return,
                horizon_minutes=horizon,
                research_score=intelligence.score,
                research_confidence=intelligence.confidence,
                evidence_count=intelligence.evidence_count,
                source_document_ids=tuple(d.document_id for d in context.documents),
            )
            observation.validate()
            observations.append(observation)

    return tuple(observations)


def to_evaluation_observations(
    observations: tuple[ResearchMarketObservation, ...] | list[ResearchMarketObservation],
) -> tuple[ResearchEvaluationObservation, ...]:
    """Convert built market observations to the generic outcome evaluator."""
    return tuple(
        ResearchEvaluationObservation(
            symbol=row.symbol,
            decision_time=row.decision_time,
            feature_available_at=row.feature_available_at,
            research_score=row.research_score,
            outcome_timestamp=row.outcome_timestamp,
            forward_return=row.forward_return,
        )
        for row in observations
    )

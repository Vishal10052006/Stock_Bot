"""Stable Research Bot to Analysis Bot context contract.

Research supplies evidence and a structured information stance. It does not
supply orders, position sizing, risk approvals, or a trading recommendation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from research.contracts import ResearchContext
from research.intelligence.model import ResearchIntelligenceResult


@dataclass(frozen=True, slots=True)
class ResearchAnalysisContext:
    contract_version: str
    symbol: str
    as_of: datetime
    research_version: str
    intelligence_model_version: str
    research_score: float
    research_stance: str
    research_confidence: float
    evidence_count: int
    source_count: int
    event_count: int
    conflict_score: float
    document_ids: tuple[str, ...]
    provenance: tuple[str, ...]
    events: tuple[dict[str, Any], ...]
    sentiment: tuple[dict[str, Any], ...]

    @classmethod
    def from_context(
        cls,
        context: ResearchContext,
        intelligence: ResearchIntelligenceResult,
    ) -> "ResearchAnalysisContext":
        if context.symbol != intelligence.symbol:
            raise ValueError("context and intelligence symbols must match")
        if context.as_of != intelligence.as_of:
            raise ValueError("context and intelligence timestamps must match")

        return cls(
            contract_version="RB-12.1",
            symbol=context.symbol,
            as_of=context.as_of,
            research_version=context.research_version,
            intelligence_model_version=intelligence.model_version,
            research_score=intelligence.score,
            research_stance=intelligence.stance,
            research_confidence=intelligence.confidence,
            evidence_count=intelligence.evidence_count,
            source_count=intelligence.source_count,
            event_count=intelligence.event_count,
            conflict_score=intelligence.conflict_score,
            document_ids=tuple(d.document_id for d in context.documents),
            provenance=context.provenance,
            events=tuple({
                "event_id": event.event_id,
                "document_id": event.document_id,
                "event_type": event.event_type.value,
                "symbol": event.symbol,
                "event_time": event.event_time.isoformat(),
                "available_at": event.available_at.isoformat(),
                "importance": event.importance,
                "confidence": event.confidence,
                "evidence": event.evidence,
            } for event in context.events),
            sentiment=tuple({
                "label": item.label,
                "score": item.score,
                "confidence": item.confidence,
                "model_version": item.model_version,
            } for item in context.sentiment),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["as_of"] = self.as_of.isoformat()
        return payload

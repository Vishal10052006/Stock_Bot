"""RB-12 Research -> Analysis contract."""
from __future__ import annotations
from datetime import datetime
from research.contracts import ResearchContext, ResearchDocument, ResearchEvent, SentimentResult, ImpactResult
from research.causal.availability import filter_point_in_time
from research.events.detector import EventDetector
from research.sentiment.analyzer import LexiconSentiment
from research.impact.analyzer import RuleImpactAnalyzer


class ResearchContextBuilder:
    def __init__(self, event_detector=None, sentiment=None, impact=None) -> None:
        self.event_detector = event_detector or EventDetector()
        self.sentiment = sentiment or LexiconSentiment()
        self.impact = impact or RuleImpactAnalyzer()

    def build(self, *, symbol: str, as_of: datetime, documents: tuple[ResearchDocument, ...]) -> ResearchContext:
        eligible = filter_point_in_time(documents, as_of)
        eligible = tuple(d for d in eligible if symbol in d.symbols)
        events: list[ResearchEvent] = []
        sentiments: list[SentimentResult] = []
        impacts: list[ImpactResult] = []
        provenance: list[str] = []
        for document in eligible:
            events.extend(self.event_detector.detect(document))
            sentiments.append(self.sentiment.analyze(document))
            provenance.append(f"{document.source_id}:{document.external_id}:{document.available_at.isoformat()}")
        for event in events:
            impacts.append(self.impact.analyze(event))
        return ResearchContext(symbol, as_of, eligible, tuple(events), tuple(sentiments), tuple(impacts), tuple(provenance))

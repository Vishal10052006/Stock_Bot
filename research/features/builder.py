"""Causal research feature construction."""
from __future__ import annotations
from datetime import datetime
from collections import Counter
from research.contracts import ResearchDocument
from research.events.detector import EventDetector
from research.sentiment.analyzer import LexiconSentiment


class ResearchFeatureBuilder:
    def __init__(self, event_detector: EventDetector | None = None,
                 sentiment: LexiconSentiment | None = None) -> None:
        self.event_detector = event_detector or EventDetector()
        self.sentiment = sentiment or LexiconSentiment()

    def build(self, documents: tuple[ResearchDocument, ...], *,
              symbol: str, decision_time: datetime) -> dict[str, float]:
        eligible = tuple(
            d for d in documents
            if d.available_at <= decision_time and symbol in d.symbols
        )
        sentiments = [self.sentiment.analyze(d).score for d in eligible]
        event_types = Counter(
            event.event_type.value
            for document in eligible
            for event in self.event_detector.detect(document)
        )
        source_count = len({d.source_id for d in eligible})
        return {
            "research_doc_count": float(len(eligible)),
            "research_source_count": float(source_count),
            "research_sentiment_mean": float(sum(sentiments) / len(sentiments)) if sentiments else 0.0,
            "research_sentiment_positive_fraction": float(sum(s > 0.1 for s in sentiments) / len(sentiments)) if sentiments else 0.0,
            "research_sentiment_negative_fraction": float(sum(s < -0.1 for s in sentiments) / len(sentiments)) if sentiments else 0.0,
            "research_event_count": float(sum(event_types.values())),
            "research_earnings_events": float(event_types["EARNINGS"]),
            "research_guidance_events": float(event_types["GUIDANCE"]),
            "research_regulatory_events": float(event_types["REGULATORY"]),
            "research_corporate_action_events": float(event_types["CORPORATE_ACTION"]),
        }

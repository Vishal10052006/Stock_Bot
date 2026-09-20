"""Research Bot contract, causality and deterministic-baseline tests."""
from datetime import datetime, timedelta, timezone

import pytest

from research.causal.availability import filter_point_in_time
from research.contracts import ResearchDocument
from research.events.detector import EventDetector
from research.integration.context import ResearchContextBuilder
from research.sentiment.analyzer import LexiconSentiment
from research.features.validator import validate_feature_row

UTC = timezone.utc


def make_doc(*, available_offset: int = 0, content: str = "Strong earnings beat and growth") -> ResearchDocument:
    published = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
    observed = published + timedelta(minutes=available_offset)
    return ResearchDocument(
        document_id=f"doc-{available_offset}", source_id="test", external_id=f"x-{available_offset}",
        title="RELIANCE earnings", content=content,
        published_at=published, observed_at=observed,
        processed_at=observed, available_at=observed, symbols=("RELIANCE",),
    )


def test_point_in_time_excludes_late_information():
    decision = datetime(2026, 9, 20, 9, 5, tzinfo=UTC)
    docs = (make_doc(available_offset=0), make_doc(available_offset=10))
    assert len(filter_point_in_time(docs, decision)) == 1


def test_future_research_cannot_enter_context():
    decision = datetime(2026, 9, 20, 9, 5, tzinfo=UTC)
    context = ResearchContextBuilder().build(symbol="RELIANCE", as_of=decision, documents=(make_doc(available_offset=0), make_doc(available_offset=10)))
    assert len(context.documents) == 1
    assert all(d.available_at <= decision for d in context.documents)


def test_sentiment_is_deterministic_and_not_a_trade_signal():
    result = LexiconSentiment().analyze(make_doc())
    assert result.label == "positive"
    assert result.model_version == "lexicon-1.0"


def test_event_detector_has_provenance():
    event = EventDetector().detect(make_doc())[0]
    assert event.document_id == "doc-0"
    assert event.evidence


def test_research_feature_validator_rejects_future_information():
    with pytest.raises(ValueError):
        validate_feature_row(
            decision_time=datetime(2026, 9, 20, 9, 5, tzinfo=UTC),
            available_at=datetime(2026, 9, 20, 9, 6, tzinfo=UTC),
            features={"sentiment_score": 0.4},
        )


def test_research_feature_validator_rejects_targets():
    with pytest.raises(ValueError):
        validate_feature_row(
            decision_time=datetime(2026, 9, 20, 9, 5, tzinfo=UTC),
            available_at=datetime(2026, 9, 20, 9, 4, tzinfo=UTC),
            features={"future_return": 0.1},
        )

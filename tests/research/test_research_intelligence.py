"""Tests for the Research Bot intelligence model."""

from datetime import datetime, timedelta, timezone

from research.contracts import ResearchDocument
from research.events.detector import EventDetector
from research.integration.context import ResearchContextBuilder
from research.intelligence import ResearchIntelligenceModel
from research.sentiment.analyzer import LexiconSentiment

UTC = timezone.utc


def make_doc(
    *,
    document_id: str,
    source_id: str,
    minutes: int,
    content: str,
) -> ResearchDocument:
    published = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
    available = published + timedelta(minutes=minutes)
    return ResearchDocument(
        document_id=document_id,
        source_id=source_id,
        external_id=document_id,
        title="RELIANCE research",
        content=content,
        published_at=published,
        observed_at=available,
        processed_at=available,
        available_at=available,
        symbols=("RELIANCE",),
    )


def build_context(*documents: ResearchDocument):
    decision = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
    return ResearchContextBuilder().build(
        symbol="RELIANCE",
        as_of=decision,
        documents=documents,
    )


def test_positive_context_produces_positive_stance():
    context = build_context(
        make_doc(
            document_id="positive-1",
            source_id="source-a",
            minutes=0,
            content="earnings growth strong profit record",
        )
    )
    result = ResearchIntelligenceModel(
        source_reliability={"source-a": 1.0}
    ).score_context(context)

    assert result.stance == "positive"
    assert result.score > 0.15
    assert result.evidence_count == 1
    assert result.provenance == (
        "positive-1:source-a:2026-09-20T09:00:00+00:00",
    )


def test_negative_context_produces_negative_stance():
    context = build_context(
        make_doc(
            document_id="negative-1",
            source_id="source-a",
            minutes=0,
            content="loss weak decline downgrade penalty risk",
        )
    )
    result = ResearchIntelligenceModel(
        source_reliability={"source-a": 1.0}
    ).score_context(context)

    assert result.stance == "negative"
    assert result.score < -0.15


def test_conflicting_evidence_is_exposed():
    context = build_context(
        make_doc(
            document_id="positive-1",
            source_id="source-a",
            minutes=0,
            content="strong growth profit",
        ),
        make_doc(
            document_id="negative-1",
            source_id="source-b",
            minutes=5,
            content="weak loss decline risk",
        ),
    )
    result = ResearchIntelligenceModel(
        source_reliability={"source-a": 1.0, "source-b": 1.0}
    ).score_context(context)

    assert result.conflict_score > 0
    assert result.positive_evidence_fraction > 0
    assert result.negative_evidence_fraction > 0


def test_future_documents_are_not_used():
    decision = datetime(2026, 9, 20, 9, 5, tzinfo=UTC)
    early = make_doc(
        document_id="early",
        source_id="source-a",
        minutes=0,
        content="strong growth profit",
    )
    late = make_doc(
        document_id="late",
        source_id="source-a",
        minutes=10,
        content="loss weak decline",
    )

    context = ResearchContextBuilder().build(
        symbol="RELIANCE",
        as_of=decision,
        documents=(early, late),
    )
    result = ResearchIntelligenceModel(
        source_reliability={"source-a": 1.0}
    ).score_context(context)

    assert result.evidence_count == 1
    assert result.provenance == (
        "early:source-a:2026-09-20T09:00:00+00:00",
    )


def test_event_evidence_increases_weight_without_creating_direction():
    document = make_doc(
        document_id="event-1",
        source_id="source-a",
        minutes=0,
        content="earnings growth strong",
    )
    context = build_context(document)
    result = ResearchIntelligenceModel(
        source_reliability={"source-a": 1.0}
    ).score_context(context)

    assert result.event_count == 1
    assert result.score > 0
    assert 0 <= result.confidence <= 1


def test_empty_context_is_neutral_with_zero_confidence():
    decision = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
    from research.contracts import ResearchContext

    context = ResearchContext(
        symbol="RELIANCE",
        as_of=decision,
        documents=(),
        events=(),
        sentiment=(),
        impacts=(),
        provenance=(),
    )
    result = ResearchIntelligenceModel().score_context(context)

    assert result.score == 0.0
    assert result.stance == "neutral"
    assert result.confidence == 0.0
    assert result.evidence_count == 0

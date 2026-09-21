from datetime import datetime, timezone

import pytest

from research.contracts import ResearchContext, ResearchDocument, SentimentResult
from research.intelligence import ResearchIntelligenceModel, ResearchIntelligencePipeline

UTC = timezone.utc


def make_doc(
    document_id: str,
    *,
    available_minute: int = 0,
    content: str = "earnings growth strong profit",
) -> ResearchDocument:
    available = datetime(2026, 9, 21, 9, available_minute, tzinfo=UTC)
    return ResearchDocument(
        document_id=document_id,
        source_id="nse-corporate-filings",
        external_id=document_id,
        title="  RELIANCE   earnings  ",
        content=f"  {content}\\n",
        published_at=available,
        observed_at=available,
        processed_at=available,
        available_at=available,
        symbols=("RELIANCE",),
    )


def test_pipeline_normalizes_builds_and_serializes_analysis_context():
    result = ResearchIntelligencePipeline().run(
        symbol="RELIANCE",
        as_of=datetime(2026, 9, 21, 9, 5, tzinfo=UTC),
        documents=(make_doc("doc-1"),),
    )

    assert result.context.documents[0].title == "RELIANCE earnings"
    assert result.intelligence.model_version == "research-intelligence-1.1"
    assert result.intelligence.event_count == 1

    payload = result.analysis_context.to_dict()
    assert payload["symbol"] == "RELIANCE"
    assert payload["research_score"] > 0
    assert "buy" not in payload
    assert "position_size" not in payload


def test_pipeline_excludes_future_documents():
    result = ResearchIntelligencePipeline().run(
        symbol="RELIANCE",
        as_of=datetime(2026, 9, 21, 9, 5, tzinfo=UTC),
        documents=(
            make_doc("early", available_minute=0),
            make_doc("future", available_minute=6, content="loss decline risk"),
        ),
    )

    assert tuple(d.document_id for d in result.context.documents) == ("early",)


def test_model_rejects_misaligned_context():
    now = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    document = make_doc("doc-1")
    context = ResearchContext(
        symbol="RELIANCE",
        as_of=now,
        documents=(document,),
        events=(),
        sentiment=(),
        impacts=(),
        provenance=(),
    )

    with pytest.raises(ValueError, match="equal length"):
        ResearchIntelligenceModel().score_context(context)


def test_model_rejects_future_document_inside_context():
    as_of = datetime(2026, 9, 21, 9, 5, tzinfo=UTC)
    document = make_doc("future", available_minute=6)
    sentiment = SentimentResult(
        label="positive",
        score=0.5,
        confidence=1.0,
        model_version="test",
    )
    context = ResearchContext(
        symbol="RELIANCE",
        as_of=as_of,
        documents=(document,),
        events=(),
        sentiment=(sentiment,),
        impacts=(),
        provenance=(),
    )

    with pytest.raises(ValueError, match="future research document"):
        ResearchIntelligenceModel().score_context(context)


def test_model_emits_finite_zero_fractions_for_neutral_only_evidence():
    now = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    document = make_doc("neutral", content="quarterly filing update")
    sentiment = SentimentResult(
        label="neutral",
        score=0.0,
        confidence=1.0,
        model_version="test",
    )
    context = ResearchContext(
        symbol="RELIANCE",
        as_of=now,
        documents=(document,),
        events=(),
        sentiment=(sentiment,),
        impacts=(),
        provenance=(),
    )

    result = ResearchIntelligenceModel().score_context(context)

    assert result.score == 0.0
    assert result.positive_evidence_fraction == 0.0
    assert result.negative_evidence_fraction == 0.0
    assert result.conflict_score == 0.0


def test_result_contract_rejects_out_of_range_values():
    now = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    with pytest.raises(ValueError):
        from research.intelligence.model import ResearchIntelligenceResult

        ResearchIntelligenceResult(
            model_version="test",
            symbol="RELIANCE",
            as_of=now,
            score=1.5,
            stance="positive",
            confidence=0.5,
            evidence_count=1,
            source_count=1,
            event_count=0,
            positive_evidence_fraction=1.0,
            negative_evidence_fraction=0.0,
            conflict_score=0.0,
            provenance=("doc-1",),
        )

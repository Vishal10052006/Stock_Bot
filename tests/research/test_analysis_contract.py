from datetime import datetime, timezone

from research.contracts import ResearchContext
from research.integration.analysis_contract import ResearchAnalysisContext
from research.intelligence.model import ResearchIntelligenceResult

UTC = timezone.utc


def test_analysis_contract_contains_research_only():
    now = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
    context = ResearchContext(
        symbol="ABC",
        as_of=now,
        documents=(),
        events=(),
        sentiment=(),
        impacts=(),
        provenance=(),
    )
    intelligence = ResearchIntelligenceResult(
        model_version="test",
        symbol="ABC",
        as_of=now,
        score=0.2,
        stance="positive",
        confidence=0.5,
        evidence_count=0,
        source_count=0,
        event_count=0,
        positive_evidence_fraction=0.0,
        negative_evidence_fraction=0.0,
        conflict_score=0.0,
        provenance=(),
    )

    payload = ResearchAnalysisContext.from_context(context, intelligence).to_dict()

    assert payload["symbol"] == "ABC"
    assert payload["research_score"] == 0.2
    assert "buy" not in payload
    assert "sell" not in payload
    assert "position_size" not in payload

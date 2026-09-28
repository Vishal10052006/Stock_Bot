"""Tests for the M20.4 approved research runtime."""

from __future__ import annotations

from datetime import datetime, timezone

from research.contracts import ResearchDocument
from runtime.research_runtime import ApprovedResearchRuntime


UTC = timezone.utc


class FakeProvider:
    source_id = "fake-approved"

    def __init__(self, documents):
        self.documents = tuple(documents)

    def fetch(self, *, symbols, start, end):
        return self.documents


def document(document_id: str, available_at: datetime) -> ResearchDocument:
    published = available_at.replace(hour=8)
    return ResearchDocument(
        document_id=document_id,
        source_id="fake-approved",
        external_id=document_id,
        title="ITC market update",
        content="ITC reported a market update.",
        published_at=published,
        observed_at=available_at,
        processed_at=available_at,
        available_at=available_at,
        symbols=("ITC",),
    )


def test_approved_research_runtime_deduplicates_and_builds_context() -> None:
    available = datetime(2026, 9, 28, 9, 0, tzinfo=UTC)
    docs = (
        document("doc-1", available),
        document("doc-1", available),
    )

    runtime = ApprovedResearchRuntime(
        providers=(FakeProvider(docs),),
    )

    run = runtime.collect(
        symbols=("itc",),
        start=datetime(2026, 9, 28, 8, 0, tzinfo=UTC),
        end=datetime(2026, 9, 28, 10, 0, tzinfo=UTC),
        as_of=datetime(2026, 9, 28, 9, 30, tzinfo=UTC),
    )

    assert len(run.documents) == 1
    assert len(run.contexts) == 1
    assert run.contexts[0].symbol == "ITC"
    assert run.contexts[0].source_count == 1
    assert run.evidence()["point_in_time_context"] is True
    assert run.evidence()["production_mutation"] is False
    assert run.evidence()["live_broker_order_submission"] is False


def test_research_runtime_excludes_evidence_not_yet_available() -> None:
    late = datetime(2026, 9, 28, 10, 0, tzinfo=UTC)

    runtime = ApprovedResearchRuntime(
        providers=(FakeProvider((document("late", late),)),),
    )

    run = runtime.collect(
        symbols=("ITC",),
        start=datetime(2026, 9, 28, 8, 0, tzinfo=UTC),
        end=datetime(2026, 9, 28, 11, 0, tzinfo=UTC),
        as_of=datetime(2026, 9, 28, 9, 30, tzinfo=UTC),
    )

    assert len(run.documents) == 1
    assert run.contexts[0].documents == ()


def test_research_runtime_validates_window_and_symbols() -> None:
    runtime = ApprovedResearchRuntime(providers=())

    try:
        runtime.collect(
            symbols=(),
            start=datetime(2026, 9, 28, 8, 0, tzinfo=UTC),
            end=datetime(2026, 9, 28, 9, 0, tzinfo=UTC),
        )
    except ValueError as exc:
        assert "symbol" in str(exc)
    else:
        raise AssertionError("expected empty-symbol validation")

    try:
        runtime.collect(
            symbols=("ITC",),
            start=datetime(2026, 9, 28, 9, 0, tzinfo=UTC),
            end=datetime(2026, 9, 28, 8, 0, tzinfo=UTC),
        )
    except ValueError as exc:
        assert "start" in str(exc)
    else:
        raise AssertionError("expected window validation")

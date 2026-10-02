"""Tests for the causal live research runtime."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from research.contracts import ResearchDocument
from research.live.runtime import LiveResearchCache, LiveResearchRuntime


UTC = timezone.utc


class FakeProvider:
    source_id = "test-source"

    def __init__(self, documents):
        self.documents = tuple(documents)
        self.calls = 0

    def fetch(self, *, symbols, start, end):
        self.calls += 1
        return tuple(
            document
            for document in self.documents
            if document.available_at <= end
        )


def _document(*, external_id: str, available_at: datetime, symbol: str = "RELIANCE"):
    return ResearchDocument(
        document_id=f"doc-{external_id}",
        source_id="test-source",
        external_id=external_id,
        title=f"{external_id} announcement",
        content=f"{symbol} company announcement",
        published_at=available_at - timedelta(minutes=1),
        observed_at=available_at,
        processed_at=available_at,
        available_at=available_at,
        symbols=(symbol,),
    )


def test_live_cache_excludes_evidence_unavailable_at_decision_time():
    decision = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)
    before = _document(
        external_id="before",
        available_at=decision - timedelta(minutes=5),
    )
    after = _document(
        external_id="after",
        available_at=decision + timedelta(minutes=1),
    )
    provider = FakeProvider((before, after))

    cache = LiveResearchCache(
        providers=(provider,),
        clock=lambda: decision + timedelta(minutes=2),
    )
    cache.refresh(
        symbols=("RELIANCE",),
        start=decision - timedelta(hours=1),
        end=decision + timedelta(minutes=2),
    )

    snapshot = cache.snapshot(symbol="RELIANCE", as_of=decision)

    assert [document.external_id for document in snapshot] == ["before"]


def test_live_cache_preserves_source_availability_in_rb12_context():
    decision = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)
    document = _document(
        external_id="causal",
        available_at=decision - timedelta(minutes=2),
    )
    provider = FakeProvider((document,))
    cache = LiveResearchCache(
        providers=(provider,),
        clock=lambda: decision,
    )

    cache.refresh(
        symbols=("RELIANCE",),
        start=decision - timedelta(hours=1),
        end=decision,
    )
    context = cache.build_analysis_context(
        symbol="RELIANCE",
        as_of=decision,
    )

    assert context.contract_version == "RB-12.1"
    assert context.symbol == "RELIANCE"
    assert context.as_of == decision
    assert context.evidence_count == 1
    assert context.document_ids == ("doc-causal",)
    assert context.provenance


def test_live_cache_retains_future_evidence_but_excludes_it_from_snapshot():
    decision = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)
    future = _document(
        external_id="future",
        available_at=decision + timedelta(seconds=1),
    )
    provider = FakeProvider((future,))
    cache = LiveResearchCache(
        providers=(provider,),
        clock=lambda: decision,
    )

    # A refresh at T must not drop a source document merely because it belongs
    # to T+epsilon. The document becomes usable only when the requested
    # decision snapshot reaches its source-provided availability timestamp.
    cache.refresh(
        symbols=("RELIANCE",),
        start=decision - timedelta(hours=1),
        end=decision + timedelta(seconds=1),
    )

    assert cache.snapshot(symbol="RELIANCE", as_of=decision) == ()
    later = cache.snapshot(
        symbol="RELIANCE",
        as_of=decision + timedelta(seconds=1),
    )
    assert [document.external_id for document in later] == ["future"]


def test_live_cache_rejects_conflicting_duplicate_identity():
    decision = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)
    first = _document(
        external_id="duplicate",
        available_at=decision - timedelta(minutes=1),
    )
    conflicting = ResearchDocument(
        document_id="doc-conflict",
        source_id=first.source_id,
        external_id=first.external_id,
        title=first.title,
        content="different payload",
        published_at=first.published_at,
        observed_at=first.observed_at,
        processed_at=first.processed_at,
        available_at=first.available_at,
        symbols=first.symbols,
    )
    cache = LiveResearchCache(
        providers=(FakeProvider((first, conflicting)),),
        clock=lambda: decision,
    )

    with pytest.raises(ValueError, match="conflicting research documents"):
        cache.refresh(
            symbols=("RELIANCE",),
            start=decision - timedelta(hours=1),
            end=decision,
        )


def test_live_runtime_refreshes_and_records_provider_failure():
    decision = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)
    document = _document(
        external_id="runtime",
        available_at=decision - timedelta(minutes=1),
    )
    provider = FakeProvider((document,))
    cache = LiveResearchCache(
        providers=(provider,),
        clock=lambda: decision,
    )
    runtime = LiveResearchRuntime(
        cache=cache,
        symbols=("RELIANCE",),
        poll_interval=timedelta(hours=1),
        lookback=timedelta(hours=2),
        clock=lambda: decision,
    )

    count = runtime.refresh_once()

    assert count == 1
    assert runtime.refresh_count == 1
    assert runtime.last_refresh_at == decision
    assert runtime.last_error is None
    assert provider.calls == 1


def test_live_runtime_rejects_naive_decision_time():
    decision = datetime(2026, 10, 2, 10, 0)
    document = _document(
        external_id="naive",
        available_at=datetime(2026, 10, 2, 9, 59, tzinfo=UTC),
    )
    provider = FakeProvider((document,))
    cache = LiveResearchCache(providers=(provider,))

    with pytest.raises(ValueError, match="as_of must be timezone-aware"):
        cache.snapshot(symbol="RELIANCE", as_of=decision)

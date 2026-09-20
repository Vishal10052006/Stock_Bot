"""End-to-end tests for archived research records entering the PIT corpus."""
from datetime import datetime, timedelta, timezone

from research.corpus import HistoricalArchiveRecord, HistoricalResearchCorpusBuilder
from research.corpus.schema import ResearchCorpusManifest

UTC = timezone.utc
T0 = datetime(2026, 9, 20, 9, 15, tzinfo=UTC)


def _manifest():
    return ResearchCorpusManifest(
        dataset_id="historical-archive",
        version="1.0.0",
        source="test-archive",
        accessed_at=datetime(2026, 9, 21, tzinfo=UTC),
    )


def _record():
    return HistoricalArchiveRecord(
        archive_id="archive-abc",
        source_id="source-a",
        external_id="external-abc",
        title="Earnings update",
        content="Revenue increased.",
        published_at=T0,
        observed_at=T0 + timedelta(minutes=2),
        available_at=T0 + timedelta(minutes=3),
        symbols=("ABC",),
        archived_at=datetime(2026, 9, 22, tzinfo=UTC),
    )


def test_archive_to_corpus_preserves_causal_timestamps_and_provenance():
    corpus, audit = HistoricalResearchCorpusBuilder().build_from_archive_records(
        (_record(),),
        manifest=_manifest(),
    )

    document = corpus.documents[0].document
    record = _record()

    assert audit.accepted_documents == 1
    assert document.document_id == record.archive_id
    assert document.external_id == record.external_id
    assert document.published_at == record.published_at
    assert document.observed_at == record.observed_at
    assert document.available_at == record.available_at
    assert document.content_hash == record.content_hash
    assert document.metadata["archive_id"] == record.archive_id
    assert document.metadata["source_reference"] == "archive://source-a/external-abc"


def test_archive_to_corpus_allows_explicit_non_causal_processing_time():
    processing_time = datetime(2026, 9, 23, tzinfo=UTC)

    corpus, _ = HistoricalResearchCorpusBuilder().build_from_archive_records(
        (_record(),),
        manifest=_manifest(),
        processed_at=processing_time,
    )

    assert corpus.documents[0].document.processed_at == processing_time
    assert corpus.documents[0].document.available_at == T0 + timedelta(minutes=3)

def test_archive_to_corpus_to_observation_preserves_pit_availability():
    from market.candles.models import Candle
    from research.evaluation.observation_builder import build_research_market_observations

    corpus, _ = HistoricalResearchCorpusBuilder().build_from_archive_records(
        (_record(),),
        manifest=_manifest(),
    )
    candles = tuple(
        Candle(
            symbol="ABC",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=T0 + timedelta(minutes=5 * i),
            open=100.0 + i,
            high=100.0 + i,
            low=100.0 + i,
            close=100.0 + i,
            volume=1000.0,
        )
        for i in range(4)
    )

    rows = build_research_market_observations(
        symbol="ABC",
        candles=candles,
        documents=tuple(item.document for item in corpus.documents),
        horizons_minutes=(10,),
        require_evidence=True,
    )

    assert rows
    assert rows[0].source_document_ids == ("archive-abc",)
    assert rows[0].feature_available_at == T0 + timedelta(minutes=3)
    # The first 5-minute candle closes at T0+5; decision_time is candle completion.
    assert rows[0].decision_time == T0 + timedelta(minutes=5)
    assert rows[0].feature_available_at < rows[0].decision_time
    assert rows[0].outcome_timestamp == T0 + timedelta(minutes=20)
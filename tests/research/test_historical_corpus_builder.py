"""Tests for the historical Research Bot corpus builder."""
from datetime import datetime, timedelta, timezone

from research.contracts import ResearchDocument
from research.corpus.builder import HistoricalResearchCorpusBuilder
from research.corpus.schema import ResearchCorpusManifest


UTC = timezone.utc
T0 = datetime(2026, 6, 29, 10, 0, tzinfo=UTC)


def manifest():
    return ResearchCorpusManifest(
        dataset_id="nse-historical-research",
        version="1.0.0",
        source="archived-test-fixture",
        accessed_at=T0,
    )


def doc(
    doc_id,
    *,
    symbol="RELIANCE",
    available_offset=0,
    published_offset=0,
):
    published = T0 + timedelta(minutes=published_offset)
    available = T0 + timedelta(minutes=available_offset)
    return ResearchDocument(
        document_id=doc_id,
        source_id="test-source",
        external_id=doc_id,
        title="Test filing",
        content="Company reported results.",
        published_at=published,
        observed_at=available,
        processed_at=available,
        available_at=available,
        symbols=(symbol,),
        metadata={"source_reference": f"archive://{doc_id}"},
    )


def test_builder_filters_symbol_and_window_without_rewriting_timestamps():
    corpus, audit = HistoricalResearchCorpusBuilder().build(
        (
            doc("keep", available_offset=5),
            doc("other", symbol="TCS"),
            doc("outside", published_offset=-120),
        ),
        manifest=manifest(),
        symbols=("RELIANCE",),
        time_start=T0,
        time_end=T0 + timedelta(minutes=60),
    )

    assert corpus.document_count == 1
    assert corpus.documents[0].document.document_id == "keep"
    assert corpus.documents[0].document.available_at == T0 + timedelta(minutes=5)
    assert audit.accepted_documents == 1
    assert audit.rejected_documents == 0


def test_builder_deduplicates_document_ids_deterministically():
    corpus, audit = HistoricalResearchCorpusBuilder().build(
        (doc("same"), doc("same")),
        manifest=manifest(),
    )

    assert corpus.document_count == 1
    assert audit.duplicate_documents == 1


def test_builder_rejects_timezone_naive_historical_documents():
    bad = doc("naive")
    naive = ResearchDocument(
        document_id=bad.document_id,
        source_id=bad.source_id,
        external_id=bad.external_id,
        title=bad.title,
        content=bad.content,
        published_at=bad.published_at.replace(tzinfo=None),
        observed_at=bad.observed_at,
        processed_at=bad.processed_at,
        available_at=bad.available_at,
        symbols=bad.symbols,
    )

    corpus, audit = HistoricalResearchCorpusBuilder().build(
        (naive,),
        manifest=manifest(),
    )

    assert corpus.document_count == 0
    assert audit.rejected_document_ids == ("naive",)


def test_builder_preserves_source_reference_and_fingerprint():
    corpus, _ = HistoricalResearchCorpusBuilder().build(
        (doc("source-ref"),),
        manifest=manifest(),
    )

    assert corpus.documents[0].source_reference == "archive://source-ref"
    assert len(corpus.fingerprint) == 64
